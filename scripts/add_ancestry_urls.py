#!/usr/bin/env python3
"""Add Ancestry URLs to all Gramps people with a confident GEDCOM match."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement

from greatgramps.settings import get_config
from gramps.gen.db import DBMODE_W, DbTxn
from gramps.gen.lib import Url, UrlType
from gramps.plugins.db.dbapi.sqlite import SQLite


GEDCOM_FILE = Path(__file__).parent / 'Nuttall Family Tree.ged'


def parse_birth_year(el) -> int | None:
    birth_str, _, _ = el.get_birth_data()
    if not birth_str:
        return None
    m = re.search(r'\b(1[5-9]\d\d|20\d\d)\b', birth_str)
    return int(m.group()) if m else None


def ancestry_url(pointer: str, tree_id: str) -> str:
    num = re.search(r'\d+', pointer).group()
    base = f'https://www.ancestry.co.uk/family-tree/person/tree/{tree_id}/person'
    return f'{base}/{num}/'


def main():
    print('Loading GEDCOM...')
    parser = Parser()
    parser.parse_file(str(GEDCOM_FILE))

    # Index GEDCOM by normalised name → list of (element, birth_year)
    gedcom_by_name: dict[str, list[tuple]] = {}
    for el in parser.get_element_list():
        if not isinstance(el, IndividualElement):
            continue
        n = el.get_name()
        name = f'{n[0]} {n[1]}'.strip().lower()
        year = parse_birth_year(el)
        gedcom_by_name.setdefault(name, []).append((el, year))

    config = get_config()
    if not config.ancestry_tree_id:
        print('Error: ancestry_tree_id not set in config')
        return
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        to_add = []   # (gramps_id, name, url)
        skipped = []  # (gramps_id, name, reason)

        for h in db.get_person_handles():
            person = db.get_person_from_handle(h)
            gramps_id = person.get_gramps_id()

            # Skip if Ancestry URL already present
            if any(str(u.get_type()) == 'Ancestry' for u in person.get_url_list()):
                continue

            pn = person.get_primary_name()
            full = f'{pn.get_first_name()} {pn.get_surname()}'.strip()
            name_key = full.lower()

            # Get Gramps birth year
            gramps_year = None
            for eref in person.get_event_ref_list():
                from gramps.gen.lib import EventType
                ev = db.get_event_from_handle(eref.get_reference_handle())
                if ev.get_type() == EventType(EventType.BIRTH):
                    y = ev.get_date_object().get_year()
                    if y:
                        gramps_year = y
                    break

            candidates = gedcom_by_name.get(name_key, [])

            if not candidates:
                skipped.append((gramps_id, full, 'no GEDCOM name match'))
                continue

            # Filter by birth year — must be within 1 year if both known
            if gramps_year:
                year_matches = [
                    (el, yr) for el, yr in candidates
                    if yr is None or abs(yr - gramps_year) <= 1
                ]
            else:
                year_matches = candidates

            if len(year_matches) == 0:
                skipped.append((gramps_id, full, f'birth year mismatch (Gramps: {gramps_year})'))
            elif len(year_matches) > 1:
                skipped.append((gramps_id, full, f'{len(year_matches)} ambiguous GEDCOM matches'))
            else:
                ged_el, ged_year = year_matches[0]
                # Require at least one side has a birth year for confidence
                if gramps_year is None and ged_year is None:
                    skipped.append((gramps_id, full, 'no birth year on either side'))
                else:
                    url = ancestry_url(ged_el.get_pointer(), config.ancestry_tree_id)
                    to_add.append((gramps_id, full, gramps_year, url))

        print(f'\n{len(to_add)} confident matches found, {len(skipped)} skipped.\n')

        if not to_add:
            print('Nothing to add.')
            return

        print('Will add Ancestry URLs for:')
        for gramps_id, name, year, url in to_add:
            print(f'  {gramps_id}  {name} (b. {year})  →  {url}')

        print()
        try:
            answer = input(f'Add {len(to_add)} Ancestry URLs? [Y/n] ').strip().lower()
            if answer == 'n':
                print('Cancelled.')
                return
        except (KeyboardInterrupt, EOFError):
            print('\nCancelled.')
            return

        with DbTxn('Add Ancestry URLs', db) as trans:
            for gramps_id, name, year, url in to_add:
                person = db.get_person_from_gramps_id(gramps_id)
                url_obj = Url()
                url_type = UrlType()
                url_type.set((UrlType.CUSTOM, 'Ancestry'))
                url_obj.set_type(url_type)
                url_obj.set_path(url)
                person.add_url(url_obj)
                db.commit_person(person, trans)

        print(f'Done — {len(to_add)} Ancestry URLs added.')

    finally:
        db.close()


if __name__ == '__main__':
    main()
