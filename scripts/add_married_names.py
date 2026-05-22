#!/usr/bin/env python3
"""Add married-name alternate names to female people in Gramps.

Only adds a married name when:
- Person is female
- Family relationship is Married (0) or Civil Union (2)
- Spouse has a surname different from the person's primary surname
- No alternate name with that surname already exists
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from greatgramps.gramps_data import open_db
from gramps.gen.db import DBMODE_W, DbTxn
from gramps.gen.lib import Name, NameType, Surname
from gramps.plugins.db.dbapi.sqlite import SQLite
from greatgramps.settings import get_config

FEMALE = 0


def main():
    config = get_config()
    db_rw = SQLite()
    db_rw.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        to_add = []  # (gramps_id, display_name, spouse_surname)

        for handle in db_rw.get_person_handles():
            person = db_rw.get_person_from_handle(handle)
            if person.get_gender() != FEMALE:
                continue

            primary = person.get_primary_name()
            primary_surname = primary.get_surname()
            existing_surnames = {primary_surname} | {
                n.get_surname() for n in person.get_alternate_names()
            }

            for fam_handle in person.get_family_handle_list():
                family = db_rw.get_family_from_handle(fam_handle)
                if int(family.get_relationship()) not in (0, 2):
                    continue

                spouse_handle = family.get_father_handle()
                if not spouse_handle or spouse_handle == person.get_handle():
                    continue

                spouse = db_rw.get_person_from_handle(spouse_handle)
                if not spouse:
                    continue

                spouse_surname = spouse.get_primary_name().get_surname()
                if not spouse_surname or spouse_surname in existing_surnames:
                    continue

                existing_surnames.add(spouse_surname)
                display = f"{primary.get_first_name()} {primary_surname}".strip()
                to_add.append((person.get_gramps_id(), handle, display, spouse_surname))

        if not to_add:
            print('Nothing to add.')
            return

        print(f'{len(to_add)} married names to add:\n')
        for gid, _handle, display, surname in to_add:
            print(f'  {gid}  {display}  →  {surname}')

        print()
        try:
            answer = input(f'Add {len(to_add)} married names? [Y/n] ').strip().lower()
            if answer == 'n':
                print('Cancelled.')
                return
        except (KeyboardInterrupt, EOFError):
            print('\nCancelled.')
            return

        with DbTxn('Add married names', db_rw) as trans:
            for gid, _handle, display, spouse_surname in to_add:
                person = db_rw.get_person_from_gramps_id(gid)
                name = Name()
                name.set_type(NameType(NameType.MARRIED))
                name.set_first_name(primary.get_first_name())
                surname_obj = Surname()
                surname_obj.set_surname(spouse_surname)
                name.set_surname_list([surname_obj])
                person.add_alternate_name(name)
                db_rw.commit_person(person, trans)

        print(f'Done — {len(to_add)} married names added.')

    finally:
        db_rw.close()


if __name__ == '__main__':
    main()
