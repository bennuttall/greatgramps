#!/usr/bin/env python3
"""Remove all 'Merged Gramps ID' attributes from people in the database."""

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

from greatgramps.gramps_data import open_db
from gramps.gen.db import DBMODE_W, DbTxn
from gramps.plugins.db.dbapi.sqlite import SQLite
from greatgramps.settings import get_config


def main():
    config = get_config()
    db_rw = SQLite()
    db_rw.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        to_update = []

        for handle in db_rw.get_person_handles():
            person = db_rw.get_person_from_handle(handle)
            attrs = person.get_attribute_list()
            filtered = [a for a in attrs if str(a.get_type()) != 'Merged Gramps ID']
            if len(filtered) < len(attrs):
                to_update.append((handle, person, filtered, len(attrs) - len(filtered)))

        if not to_update:
            print('No Merged Gramps ID attributes found.')
            return

        for handle, person, filtered, count in to_update:
            print(f"  {person.get_gramps_id()} {person.get_primary_name().get_name()} — removing {count}")

        print(f'\n{sum(c for *_, c in to_update)} attribute(s) across {len(to_update)} people will be removed.')
        answer = input('Proceed? [y/N] ').strip().lower()
        if answer != 'y':
            print('Aborted.')
            return

        with DbTxn('Remove Merged Gramps ID attributes', db_rw) as trans:
            for handle, person, filtered, _ in to_update:
                person.set_attribute_list(filtered)
                db_rw.commit_person(person, trans)

        print('Done.')
    finally:
        db_rw.close()


if __name__ == '__main__':
    main()
