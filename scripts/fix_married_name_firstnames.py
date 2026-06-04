#!/home/ben/.virtualenvs/gramps/bin/python
"""Fix alternate married name entries:
- Backfill missing first names for female people
- Remove married name entries from male people
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / '.env')
_cfg = os.environ.get('GREATGRAMPS_CONFIG', 'config.yml')
if not Path(_cfg).is_absolute():
    os.environ['GREATGRAMPS_CONFIG'] = str(REPO_ROOT / _cfg)

from greatgramps.settings import get_config
from gramps.gen.db import DBMODE_W, DbTxn
from gramps.gen.lib.nametype import NameType
from gramps.plugins.db.dbapi.sqlite import SQLite

MALE = 1


def main():
    config = get_config()
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        to_fix = []    # (person, first_name, [names_to_update])
        to_remove = [] # (person, [names_to_keep], [names_being_removed])

        for person in db.iter_people():
            alt_names = person.get_alternate_names()
            if not alt_names:
                continue

            if person.get_gender() == MALE:
                married = [n for n in alt_names if n.get_type() == NameType(NameType.MARRIED)]
                if married:
                    keep = [n for n in alt_names if n not in married]
                    to_remove.append((person, keep, married))
            else:
                first_name = person.get_primary_name().get_first_name()
                if not first_name:
                    continue
                needs_fix = [n for n in alt_names if not n.get_first_name()]
                if needs_fix:
                    to_fix.append((person, first_name, needs_fix))

        if not to_fix and not to_remove:
            print('Nothing to do.')
            return

        if to_remove:
            print(f'{sum(len(m) for _, _, m in to_remove)} married name(s) to remove from male people:\n')
            for person, _, married in to_remove:
                gid = person.get_gramps_id()
                pn = person.get_primary_name()
                full = f"{pn.get_first_name()} {pn.get_surname()}".strip()
                for name in married:
                    print(f'  {gid}  {full}  — remove married name: {name.get_surname()}')
            print()

        if to_fix:
            total_fix = sum(len(names) for _, _, names in to_fix)
            print(f'{total_fix} alternate name(s) to backfill first names:\n')
            for person, first_name, names in to_fix:
                gid = person.get_gramps_id()
                for name in names:
                    print(f'  {gid}  {first_name!r} → {first_name} {name.get_surname()}')
            print()

        try:
            answer = input('Apply all changes? [Y/n] ').strip().lower()
            if answer == 'n':
                print('Cancelled.')
                return
        except (KeyboardInterrupt, EOFError):
            print('\nCancelled.')
            return

        with DbTxn('Fix married name entries', db) as trans:
            for person, keep, _ in to_remove:
                person.set_alternate_names(keep)
                db.commit_person(person, trans)
            for person, first_name, names in to_fix:
                for name in names:
                    name.set_first_name(first_name)
                db.commit_person(person, trans)

        print('Done.')

    finally:
        db.close()


if __name__ == '__main__':
    main()
