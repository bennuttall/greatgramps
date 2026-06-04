#!/usr/bin/env python3
"""Find and remove media objects in the Gramps database not referenced by any person, family, event, place, source, or citation."""

from __future__ import annotations

import os
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
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        referenced = set()
        for obj in [
            *db.iter_people(),
            *db.iter_families(),
            *db.iter_events(),
            *db.iter_places(),
            *db.iter_sources(),
            *db.iter_citations(),
        ]:
            for ref in obj.get_media_list():
                referenced.add(ref.get_reference_handle())

        unreferenced = [
            db.get_media_from_handle(h)
            for h in db.get_media_handles()
            if h not in referenced
        ]

        if not unreferenced:
            print("No unreferenced media objects found.")
            return

        for media in unreferenced:
            print(f"{media.get_gramps_id()}  {media.get_path()}")

        print(f"\n{len(unreferenced)} unreferenced media object(s)")

        try:
            answer = input(f"\nRemove {len(unreferenced)} unreferenced media object(s)? [Y/n] ").strip().lower()
            if answer == 'n':
                print("Cancelled.")
                return
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return

        with DbTxn("Remove unreferenced media", db) as trans:
            for media in unreferenced:
                db.remove_media(media.get_handle(), trans)

        print(f"Done — {len(unreferenced)} media object(s) removed.")

    finally:
        db.close()


if __name__ == '__main__':
    main()
