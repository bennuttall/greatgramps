#!/home/ben/.virtualenvs/gramps/bin/python
"""Batch-apply missing census places and occupations from GEDCOM to Gramps."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
import os
load_dotenv(REPO_ROOT / '.env')
_cfg = os.environ.get('GREATGRAMPS_CONFIG', 'config.yml')
if not Path(_cfg).is_absolute():
    os.environ['GREATGRAMPS_CONFIG'] = str(REPO_ROOT / _cfg)

from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement

from greatgramps.settings import get_config
from gramps.gen.db import DBMODE_W, DbTxn
from gramps.gen.lib import Attribute, AttributeType, EventType
from gramps.plugins.db.dbapi.sqlite import SQLite


GEDCOM_FILE = REPO_ROOT / 'ged' / 'Nuttall Family Tree.ged'
CENSUS_YEARS = {1841, 1851, 1861, 1871, 1881, 1891, 1901, 1911, 1921, 1939}

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def parse_year(date_str: str) -> int | None:
    s = date_str.strip()
    try:
        return int(s)
    except ValueError:
        pass
    parts = s.split()
    for p in reversed(parts):
        try:
            return int(p)
        except ValueError:
            pass
    return None


def person_name(person) -> str:
    n = person.get_primary_name()
    return f'{n.get_first_name()} {n.get_surname()}'.strip()


def get_census_event(person, db, year: int):
    for eref in person.get_event_ref_list():
        ev = db.get_event_from_handle(eref.get_reference_handle())
        if ev.get_type() == EventType(EventType.CENSUS) and ev.get_date_object().get_year() == year:
            return ev
    return None


def get_birth_year(person, db) -> int | None:
    for eref in person.get_event_ref_list():
        ev = db.get_event_from_handle(eref.get_reference_handle())
        if ev.get_type() == EventType(EventType.BIRTH):
            yr = ev.get_date_object().get_year()
            return yr if yr else None
    return None


def has_occupation(person, year: int) -> bool:
    for attr in person.get_attribute_list():
        if (attr.get_type() == AttributeType(AttributeType.OCCUPATION)
                and f'({year})' in attr.get_value()):
            return True
    return False


def extract_occupation(note: str) -> str | None:
    m = re.search(r'Occupation:\s*([^;]+)', note, re.IGNORECASE)
    return m.group(1).strip() if m else None


def find_place(db, place_str: str):
    if not place_str:
        return None
    first = place_str.split(',')[0].strip().lower()
    for h in db.get_place_handles():
        p = db.get_place_from_handle(h)
        if p.get_name().get_value().lower() == first:
            return p
    return None


def build_gedcom_index(gedcom_individuals) -> dict[str, list]:
    """Index GEDCOM individuals by lowercased full name."""
    index = {}
    for el in gedcom_individuals:
        n = el.get_name()
        full = f'{n[0]} {n[1]}'.strip().lower()
        index.setdefault(full, []).append(el)
    return index


def find_gedcom_match(gramps_person, db, ged_index):
    full = person_name(gramps_person).lower()
    candidates = ged_index.get(full, [])
    if not candidates:
        return None
    birth_year = get_birth_year(gramps_person, db)
    if not birth_year or len(candidates) == 1:
        return candidates[0]
    for el in candidates:
        birth_str, _, _ = el.get_birth_data()
        gy = parse_year(birth_str)
        if gy and abs(gy - birth_year) <= 2:
            return el
    return candidates[0]


def main():
    print('Loading GEDCOM...')
    parser = Parser()
    parser.parse_file(str(GEDCOM_FILE))
    gedcom_individuals = [
        el for el in parser.get_element_list()
        if isinstance(el, IndividualElement)
    ]
    ged_index = build_gedcom_index(gedcom_individuals)
    print(f'  {len(gedcom_individuals)} GEDCOM individuals indexed.')

    config = get_config()
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        # Collect all people who have at least one census event in Gramps
        gramps_people = []
        for handle in db.get_person_handles():
            p = db.get_person_from_handle(handle)
            for eref in p.get_event_ref_list():
                ev = db.get_event_from_handle(eref.get_reference_handle())
                if ev.get_type() == EventType(EventType.CENSUS):
                    gramps_people.append(p)
                    break

        print(f'  {len(gramps_people)} Gramps people with census events.\n')

        changes = []  # (description, apply_fn)

        for gramps_person in gramps_people:
            gid = gramps_person.get_gramps_id()
            name = person_name(gramps_person)

            ged = find_gedcom_match(gramps_person, db, ged_index)
            if not ged:
                continue

            for child in ged.get_child_elements():
                if child.get_tag() != 'RESI':
                    continue

                ged_date = ged_place_str = ged_note = ''
                for gc in child.get_child_elements():
                    if gc.get_tag() == 'DATE':
                        ged_date = gc.get_value()
                    elif gc.get_tag() == 'PLAC':
                        ged_place_str = gc.get_value()
                    elif gc.get_tag() == 'NOTE':
                        ged_note = gc.get_value()

                year = parse_year(ged_date)
                if year not in CENSUS_YEARS:
                    continue

                census_ev = get_census_event(gramps_person, db, year)
                if not census_ev:
                    continue

                # Missing place
                if ged_place_str and not census_ev.get_place_handle():
                    place = find_place(db, ged_place_str)
                    if place:
                        ev_handle = census_ev.get_handle()
                        ph = place.get_handle()
                        desc = f'{gid} {name}: {year} census place → {place.get_name().get_value()} (GEDCOM: {ged_place_str})'

                        def apply_place(db, trans, h=ev_handle, p=ph):
                            ev = db.get_event_from_handle(h)
                            ev.set_place_handle(p)
                            db.commit_event(ev, trans)

                        changes.append((desc, apply_place))

                # Missing occupation
                occupation = extract_occupation(ged_note)
                if occupation and not has_occupation(gramps_person, year):
                    occ_str = f'{occupation} ({year})'
                    desc = f'{gid} {name}: occupation {year} → {occ_str}'

                    def apply_occ(db, trans, pid=gid, val=occ_str):
                        p = db.get_person_from_gramps_id(pid)
                        attr = Attribute()
                        attr.set_type(AttributeType(AttributeType.OCCUPATION))
                        attr.set_value(val)
                        p.add_attribute(attr)
                        db.commit_person(p, trans)

                    changes.append((desc, apply_occ))

        if not changes:
            print('No missing data found.')
            return

        print(f'Found {len(changes)} change(s):\n')
        for desc, _ in changes:
            print(f'  + {desc}')

        print()
        try:
            answer = input(f'Apply all {len(changes)} change(s)? [Y/n]: ').strip().lower()
        except (KeyboardInterrupt, EOFError):
            print('\nAborted.')
            return

        if answer == 'n':
            print('Aborted.')
            return

        with DbTxn('Census GEDCOM sync', db) as trans:
            for _, fn in changes:
                fn(db, trans)

        print(f'Applied {len(changes)} change(s).')

    finally:
        db.close()


if __name__ == '__main__':
    main()
