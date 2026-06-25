#!/usr/bin/env python3
"""Walk through people with a Find A Grave link and update their burial place in Gramps."""

from __future__ import annotations

import os
import select
import subprocess
import sys
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / '.env')
_cfg = os.environ.get('GREATGRAMPS_CONFIG', 'config.yml')
if not Path(_cfg).is_absolute():
    os.environ['GREATGRAMPS_CONFIG'] = str(REPO_ROOT / _cfg)

from rich.console import Console

from gramps.gen.db import DBMODE_W, DbTxn
from gramps.gen.lib import Place, PlaceName, PlaceRef, PlaceType
from gramps.gen.lib.eventtype import EventType
from gramps.plugins.db.dbapi.sqlite import SQLite

from greatgramps.cli import _attach_event, _parse_date
from greatgramps.gramps_data import format_date, get_event, get_place_name
from greatgramps.settings import get_config

console = Console()

SITE_ROOT = 'I0018'
BASE_URL = f'http://localhost:8000/{SITE_ROOT}/people'
GRGR_BIN = Path(sys.executable).parent / 'grgr'


def _prompt(text: str) -> str:
    """Read a line, skipping stray blank lines a fast paste can leave ahead of the real input."""
    line = input(text)
    while not line.strip() and select.select([sys.stdin], [], [], 0)[0]:
        line = input()
    return line.strip()


def _normalize(s: str) -> str:
    return s.lower().replace('‘', "'").replace('’', "'")


def _is_cemetery(db, event) -> bool:
    handle = event.get_place_handle()
    if not handle:
        return False
    place = db.get_place_from_handle(handle)
    if not place:
        return False
    pt = place.get_type()
    if str(pt).lower() == 'cemetery':
        return True
    return 'cemetery' in place.get_name().get_value().lower()


def _enclosing_names(db, place) -> str:
    names = []
    seen = {place.get_handle()}
    refs = place.get_placeref_list()
    while refs:
        handle = refs[0].get_reference_handle()
        if handle in seen:
            break
        seen.add(handle)
        parent = db.get_place_from_handle(handle)
        if not parent:
            break
        names.append(parent.get_name().get_value())
        refs = parent.get_placeref_list()
    return ', '.join(names)


def _find_places(db, place_query: str):
    place = db.get_place_from_gramps_id(place_query)
    if place:
        return [place]
    all_places = [db.get_place_from_handle(h) for h in db.get_place_handles()]
    query = _normalize(place_query)
    return [p for p in all_places if query in _normalize(p.get_name().get_value())]


def _create_cemetery(db, name: str, latlong: str, enclose: Place = None):
    try:
        lat_str, lon_str = (part.strip() for part in latlong.split(','))
        lat, lon = float(lat_str), float(lon_str)
    except ValueError:
        console.print(f"[red]Invalid lat,lon {latlong!r}[/red]")
        return None

    place = Place()
    pn = PlaceName()
    pn.set_value(name)
    place.set_name(pn)
    place.set_latitude(str(lat))
    place.set_longitude(str(lon))
    place.set_type(PlaceType((PlaceType.CUSTOM, 'Cemetery')))
    if enclose:
        pref = PlaceRef()
        pref.set_reference_handle(enclose.get_handle())
        place.add_placeref(pref)
    with DbTxn('Add cemetery place', db) as trans:
        db.add_place(place, trans)
    console.print(f"[green]Cemetery added:[/green] {place.get_gramps_id()} — {name}")
    if enclose:
        console.print(f"[green]Enclosed by:[/green] {enclose.get_gramps_id()} — {enclose.get_name().get_value()}")
    return place


def main():
    config = get_config()
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        people = []
        for handle in db.get_person_handles(sort_handles=True):
            person = db.get_person_from_handle(handle)
            find_a_grave_url = next(
                (u.get_path() for u in person.get_url_list() if str(u.get_type()).lower() == 'find a grave'),
                None,
            )
            if find_a_grave_url:
                people.append((person, find_a_grave_url))

        if not people:
            console.print("[yellow]No people with a Find A Grave link found.[/yellow]")
            return

        without_cemetery = sum(
            1 for person, _ in people
            if not (lambda e: e and _is_cemetery(db, e))(get_event(db, person, EventType(EventType.BURIAL)))
        )
        console.print(f"{len(people)} people with a Find A Grave link, {without_cemetery} without a cemetery burial place\n")

        for person, find_a_grave_url in people:
            gramps_id = person.get_gramps_id()
            pn = person.get_primary_name()
            name = f"{pn.get_first_name()} {pn.get_surname()}".strip()
            url = f"{BASE_URL}/{gramps_id}/"

            existing_burial = get_event(db, person, EventType(EventType.BURIAL))
            if existing_burial and _is_cemetery(db, existing_burial):
                continue

            console.print()
            console.print(f"[bold]{name}[/bold] ({gramps_id})")

            if existing_burial:
                burial_date = format_date(existing_burial.get_date_object())
                burial_place = get_place_name(db, existing_burial)
                console.print(f"Current burial: {burial_date or '?'} at {burial_place or '?'}")
            else:
                console.print("Current burial: none")

            console.print(find_a_grave_url)
            try:
                open_choice = _prompt("Open? Y/n: ").lower()
            except (KeyboardInterrupt, EOFError):
                console.print("\nStopped.")
                break
            if open_choice == 'n':
                continue
            webbrowser.open(find_a_grave_url)

            place = None
            created_place = False
            while place is None:
                try:
                    place_query = _prompt("Place ID or name for burial event (enter to skip): ")
                except (KeyboardInterrupt, EOFError):
                    console.print("\nStopped.")
                    break

                if not place_query:
                    console.print("[yellow]Skipped — no place entered.[/yellow]")
                    break

                console.print(f"Searching for place matching {place_query!r}...")
                matches = _find_places(db, place_query)
                if len(matches) > 1:
                    console.print(f"[yellow]Ambiguous — {len(matches)} places match {place_query!r}:[/yellow]")
                    for p in sorted(matches, key=lambda p: p.get_name().get_value().lower()):
                        console.print(f"  {p.get_gramps_id()} — {p.get_name().get_value()}")
                    continue

                if matches:
                    candidate = matches[0]
                    enclosing = _enclosing_names(db, candidate)
                    place_label = candidate.get_name().get_value()
                    if enclosing:
                        place_label += f', {enclosing}'
                    console.print(f"Found: {candidate.get_gramps_id()} — {place_label}")
                    try:
                        confirm = _prompt("Use this place? Y/n: ").lower()
                    except (KeyboardInterrupt, EOFError):
                        console.print("\nStopped.")
                        break
                    if confirm == 'n':
                        continue
                    place = candidate
                else:
                    console.print(f"[yellow]No place found matching {place_query!r}.[/yellow]")
                    try:
                        latlong = _prompt(
                            f"Enter lat,lon to create {place_query!r} as a Cemetery (enter to skip): "
                        )
                    except (KeyboardInterrupt, EOFError):
                        console.print("\nStopped.")
                        break
                    if not latlong:
                        continue

                    try:
                        enclose_query = _prompt("Enclosed by (place ID or name, enter to skip): ")
                    except (KeyboardInterrupt, EOFError):
                        console.print("\nStopped.")
                        break

                    enclose = None
                    if enclose_query:
                        enclose_matches = _find_places(db, enclose_query)
                        if len(enclose_matches) == 1:
                            enclose = enclose_matches[0]
                        elif len(enclose_matches) > 1:
                            sorted_matches = sorted(enclose_matches, key=lambda p: p.get_name().get_value().lower())
                            console.print(f"[yellow]Ambiguous — {len(enclose_matches)} places match {enclose_query!r}:[/yellow]")
                            for i, p in enumerate(sorted_matches, 1):
                                console.print(f"  {i}. {p.get_gramps_id()} — {p.get_name().get_value()}")
                            try:
                                pick = _prompt("Choose number or ID (enter to skip enclosing): ")
                            except (KeyboardInterrupt, EOFError):
                                console.print("\nStopped.")
                                break
                            if pick:
                                if pick.isdigit() and 1 <= int(pick) <= len(sorted_matches):
                                    enclose = sorted_matches[int(pick) - 1]
                                else:
                                    pick_matches = [p for p in sorted_matches if p.get_gramps_id() == pick]
                                    if pick_matches:
                                        enclose = pick_matches[0]
                                    else:
                                        console.print(f"[yellow]No match for {pick!r}, not enclosing.[/yellow]")
                        else:
                            console.print(f"[yellow]No place found matching {enclose_query!r}, not enclosing.[/yellow]")

                    place = _create_cemetery(db, place_query, latlong, enclose)
                    if not place:
                        continue
                    created_place = True

            if place is None:
                continue

            burial_event = get_event(db, person, EventType(EventType.BURIAL))
            if burial_event:
                with DbTxn('Set burial place', db) as trans:
                    burial_event.set_place_handle(place.get_handle())
                    db.commit_event(burial_event, trans)
                console.print(f"[green]Burial place set:[/green] {gramps_id} → {place.get_name().get_value()} ({place.get_gramps_id()})")
            else:
                death_event = get_event(db, person, EventType(EventType.DEATH))
                death_year = death_event.get_date_object().get_year() if death_event else None
                if death_year:
                    date_prompt = f"No burial event found. Burial date (enter to use death year - {death_year}): "
                else:
                    date_prompt = "No burial event found. Burial date (enter to leave blank): "
                try:
                    date_str = _prompt(date_prompt)
                except (KeyboardInterrupt, EOFError):
                    console.print("\nStopped.")
                    break
                if not date_str and death_year:
                    date_str = str(death_year)
                parsed_date = _parse_date(date_str) if date_str else None
                if date_str and not parsed_date:
                    console.print(f"[red]Could not parse date {date_str!r}, leaving blank[/red]")
                with DbTxn('Add burial event', db) as trans:
                    burial_event = _attach_event(db, trans, person, EventType(EventType.BURIAL), parsed_date, place)
                    db.commit_person(person, trans)
                console.print(f"[green]Burial event {burial_event.get_gramps_id()} created:[/green] {gramps_id} → {place.get_name().get_value()} ({place.get_gramps_id()})")

            rebuild_ids = [gramps_id, 'cemeteries']
            if created_place:
                rebuild_ids += [place.get_gramps_id(), 'places']
            subprocess.run([str(GRGR_BIN), 'rebuild-page', *rebuild_ids], cwd=REPO_ROOT, check=True)
            console.print(f"[green]Page rebuilt:[/green] {url}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
