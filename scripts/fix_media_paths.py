#!/usr/bin/env python3
"""Strip absolute DB prefix from Media item paths, making them relative."""

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
from gramps.plugins.db.dbapi.sqlite import SQLite


def main():
    config = get_config()
    prefix = str(config.validated_db_path) + '/'

    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        to_fix = []
        for h in db.get_media_handles():
            media = db.get_media_from_handle(h)
            path = media.get_path()
            if path.startswith(prefix):
                new_path = path[len(prefix):]
                to_fix.append((h, media.get_gramps_id(), path, new_path))

        if not to_fix:
            print('No media items with absolute paths found.')
            return

        print(f'{len(to_fix)} media items to update:\n')
        for _, gid, old, new in to_fix:
            print(f'  {gid}')
            print(f'    {old}')
            print(f'    → {new}')

        print()
        try:
            answer = input(f'Update {len(to_fix)} media paths? [Y/n] ').strip().lower()
            if answer == 'n':
                print('Cancelled.')
                return
        except (KeyboardInterrupt, EOFError):
            print('\nCancelled.')
            return

        with DbTxn('Fix media paths', db) as trans:
            for h, gid, _, new_path in to_fix:
                media = db.get_media_from_handle(h)
                media.set_path(new_path)
                db.commit_media(media, trans)

        print(f'Done — {len(to_fix)} media paths updated.')

    finally:
        db.close()


if __name__ == '__main__':
    main()
