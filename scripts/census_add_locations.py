#!/usr/bin/env python3
"""Find Census events with no place, look up each in the GED file, and suggest locations."""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement

from greatgramps.settings import get_config
from gramps.gen.db import DBMODE_W, DbTxn
from gramps.gen.lib import Place, PlaceName, PlaceType
from gramps.gen.lib.eventtype import EventType
from gramps.plugins.db.dbapi.sqlite import SQLite

from gedcom_diff import parse_gedcom_date, find_place

GEDCOM_FILE = Path(__file__).parent / 'Nuttall Family Tree.ged'

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'greatgramps/0.1 (family tree tool)'

NOMINATIM_TYPE_MAP = {
    'city': PlaceType.CITY, 'town': PlaceType.TOWN, 'village': PlaceType.VILLAGE,
    'hamlet': PlaceType.HAMLET, 'county': PlaceType.COUNTY, 'state': PlaceType.STATE,
    'country': PlaceType.COUNTRY, 'parish': PlaceType.PARISH,
    'municipality': PlaceType.MUNICIPALITY, 'borough': PlaceType.BOROUGH,
    'district': PlaceType.DISTRICT, 'region': PlaceType.REGION,
    'province': PlaceType.PROVINCE, 'locality': PlaceType.LOCALITY,
    'neighbourhood': PlaceType.NEIGHBORHOOD, 'suburb': PlaceType.NEIGHBORHOOD,
    'farm': PlaceType.FARM,
}


PLACE_CLASSES = {'place', 'boundary'}

def _geocode(query: str):
    params = urllib.parse.urlencode({'q': query, 'format': 'json', 'limit': 10})
    req = urllib.request.Request(
        f'{NOMINATIM_URL}?{params}', headers={'User-Agent': USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        results = json.loads(resp.read().decode())
    place_results = [r for r in results if r.get('class') in PLACE_CLASSES]
    return place_results or results


def _ask(prompt_str: str) -> str:
    try:
        return input(prompt_str).strip()
    except (KeyboardInterrupt, EOFError):
        print('\nAborted.')
        sys.exit(0)


def _ged_place_candidates(db, ged_place_str: str) -> list:
    """Return DB places matching any comma-separated component of the GED place string."""
    all_places = [db.get_place_from_handle(h) for h in db.get_place_handles()]
    seen = set()
    candidates = []
    for component in ged_place_str.split(','):
        component = component.strip().lower()
        if not component:
            continue
        for p in all_places:
            if p.get_gramps_id() in seen:
                continue
            if p.get_name().get_value().lower() == component:
                seen.add(p.get_gramps_id())
                candidates.append(p)
    return candidates


def prompt_with_place(db, label: str, ged_place_str: str, db_place, ancestry_urls=()) -> tuple[str | None, dict | None]:
    """Prompt to pick a location for a census event.

    Returns (action, data) where action is 'accept_place', 'geocode', or None (skip).
    """
    ancestry_opt = ' / [a]ncestry' if ancestry_urls else ''
    candidates = _ged_place_candidates(db, ged_place_str)

    while True:
        print(f'\n  {label}')
        print(f'  GED: {ged_place_str}')

        if candidates:
            for i, p in enumerate(candidates):
                print(f'  [{i + 1}] {p.get_name().get_value()} ({p.get_gramps_id()})')
            opts = '/'.join(str(i + 1) for i in range(len(candidates)))
            answer = _ask(f'  [{opts}] / [m]odify / [n]o{ancestry_opt}: ').lower()
        else:
            print('  (not in database)')
            answer = _ask(f'  [m]odify / [n]o{ancestry_opt}: ').lower()

        if answer == 'a' and ancestry_urls:
            webbrowser.open(ancestry_urls[0])
            continue
        break

    if answer == 'n':
        return None, None

    if answer.isdigit():
        idx = int(answer) - 1
        if 0 <= idx < len(candidates):
            return 'accept_place', candidates[idx]
        return None, None

    # Modify: search DB first, offer to create if not found
    all_places = [db.get_place_from_handle(h) for h in db.get_place_handles()]

    while True:
        query = _ask(f'  Search [{ged_place_str}]: ')
        if not query:
            query = ged_place_str

        q = query.lower()
        matches = [p for p in all_places if q in p.get_name().get_value().lower()]

        if len(matches) == 1:
            p = matches[0]
            print(f'  Found: {p.get_name().get_value()} ({p.get_gramps_id()})')
            confirm = _ask('  Use this? [Y/n]: ').lower()
            if confirm == 'n':
                continue
            return 'accept_place', p

        if len(matches) > 1:
            print(f'  {len(matches)} matches:')
            for i, p in enumerate(matches):
                print(f'    {i + 1}. {p.get_name().get_value()} ({p.get_gramps_id()})')
            choice = _ask(f'  Choose [1-{len(matches)}] or n to search again: ').lower()
            if choice == 'n' or not choice.isdigit():
                continue
            idx = int(choice) - 1
            if not 0 <= idx < len(matches):
                continue
            return 'accept_place', matches[idx]

        # Not found in DB — offer to geocode and create
        print(f'  No places found matching {query!r}.')
        create = _ask('  Create new place via geocode? [Y/n]: ').lower()
        if create == 'n':
            continue

        print(f'  Geocoding: {query!r}...')
        try:
            results = _geocode(query)
        except Exception as e:
            print(f'  Geocode failed: {e}')
            continue

        if not results:
            print(f'  No geocode results for {query!r}. Try a different search term.')
            continue

        result = results[0]
        name = result['display_name'].split(',')[0].strip()
        lat, lon = result['lat'], result['lon']
        addresstype = result.get('addresstype', result.get('type', ''))
        place_type_int = NOMINATIM_TYPE_MAP.get(addresstype, PlaceType.UNKNOWN)

        print(f'  Found: {result["display_name"]}')
        confirm = _ask(f'  Create {name!r} ({addresstype})? [Y/n]: ').lower()
        if confirm == 'n':
            continue

        return 'geocode', {
            'name': name, 'lat': lat, 'lon': lon, 'place_type_int': place_type_int,
        }


def build_ged_index(gedcom_individuals):
    index = {}
    for el in gedcom_individuals:
        first, last = el.get_name()
        key = f'{first} {last}'.strip().lower()
        index.setdefault(key, []).append(el)
    return index


def find_ged_match(ged_index, full_name, birth_year):
    candidates = ged_index.get(full_name.lower(), [])
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    if birth_year:
        close = [
            el for el in candidates
            if (lambda gy: gy and abs(gy - birth_year) <= 2)(
                parse_gedcom_date(el.get_birth_data()[0])[0]
            )
        ]
        if len(close) == 1:
            return close[0]
    return candidates[0]


def get_resi_place_for_year(ged_el, year):
    for child in ged_el.get_child_elements():
        if child.get_tag() != 'RESI':
            continue
        ged_date = ged_place = ''
        for gc in child.get_child_elements():
            if gc.get_tag() == 'DATE':
                ged_date = gc.get_value()
            if gc.get_tag() == 'PLAC':
                ged_place = gc.get_value()
        gy, _, _ = parse_gedcom_date(ged_date)
        if gy == year and ged_place:
            return ged_place
    return None


def main():
    print('Loading GEDCOM...')
    parser = Parser()
    parser.parse_file(str(GEDCOM_FILE))
    gedcom_individuals = [
        el for el in parser.get_element_list()
        if isinstance(el, IndividualElement)
    ]
    ged_index = build_ged_index(gedcom_individuals)
    print(f'  {len(gedcom_individuals)} individuals loaded.')

    config = get_config()
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        # Build event -> participants map
        event_handle_to_people = {}
        for person in db.iter_people():
            pn = person.get_primary_name()
            full_name = f'{pn.get_first_name()} {pn.get_surname()}'.strip()
            for eref in person.get_event_ref_list():
                h = eref.get_reference_handle()
                event_handle_to_people.setdefault(h, []).append(
                    (person.get_gramps_id(), full_name, person)
                )

        # Collect census events with no place, sorted by year
        no_place = []
        for event in db.iter_events():
            if int(event.get_type()) != EventType.CENSUS:
                continue
            if event.get_place_handle():
                continue
            year = event.get_date_object().get_year() or None
            participants = event_handle_to_people.get(event.get_handle(), [])
            no_place.append((year or 0, event.get_gramps_id(), year, event, participants))

        no_place.sort(key=lambda x: x[0])
        print(f'\n{len(no_place)} Census events with no location.\n')
        print('─' * 60)

        saved = skipped = no_match = 0

        for _, gid, year, event, participants in no_place:
            names = ', '.join(n for _, n, _ in participants) or '(no participants)'
            print(f'\n{gid}  {year}  {names}')

            # Find GED place suggestion from any participant
            ged_place_str = None
            for _pid, full_name, person in participants:
                birth_event = next(
                    (db.get_event_from_handle(er.get_reference_handle())
                     for er in person.get_event_ref_list()
                     if int(db.get_event_from_handle(er.get_reference_handle()).get_type()) == EventType.BIRTH),
                    None,
                )
                birth_year = birth_event.get_date_object().get_year() if birth_event else None
                ged_el = find_ged_match(ged_index, full_name, birth_year)
                if not ged_el:
                    continue
                place_str = get_resi_place_for_year(ged_el, year)
                if place_str:
                    ged_place_str = place_str
                    break

            if not ged_place_str:
                print('  No GED RESI record found for this year — skipping.')
                no_match += 1
                continue

            db_place = find_place(db, ged_place_str)
            ancestry_urls = [
                u.get_path()
                for _, _, person in participants
                for u in person.get_url_list()
                if str(u.get_type()) == 'Ancestry'
            ]
            action, geocode_data = prompt_with_place(
                db, f'{year} census location', ged_place_str, db_place,
                ancestry_urls=ancestry_urls,
            )

            if action is None:
                skipped += 1
                continue

            with DbTxn(f'Census location {gid}', db) as trans:
                if action == 'accept_place':
                    place_name = geocode_data.get_name().get_value()
                    event.set_place_handle(geocode_data.get_handle())
                    db.commit_event(event, trans)
                elif action == 'geocode':
                    place = Place()
                    pn = PlaceName()
                    pn.set_value(geocode_data['name'])
                    place.set_name(pn)
                    place.set_latitude(str(geocode_data['lat']))
                    place.set_longitude(str(geocode_data['lon']))
                    place.set_type(PlaceType(geocode_data['place_type_int']))
                    db.add_place(place, trans)
                    place_name = f'{place.get_name().get_value()} ({place.get_gramps_id()}, new)'
                    event.set_place_handle(place.get_handle())
                    db.commit_event(event, trans)

            print(f'  Saved {gid} -> {place_name}')
            saved += 1

        print('\n' + '─' * 60)
        print(f'Done. ({saved} saved, {skipped} skipped, {no_match} with no GED match)')

    finally:
        db.close()


if __name__ == '__main__':
    main()
