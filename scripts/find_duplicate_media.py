#!/usr/bin/env python3
"""Find media objects in the Gramps database that point to the same file."""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / '.env')
_cfg = os.environ.get('GREATGRAMPS_CONFIG', 'config.yml')
if not Path(_cfg).is_absolute():
    os.environ['GREATGRAMPS_CONFIG'] = str(REPO_ROOT / _cfg)

from greatgramps.gramps_data import open_db
from greatgramps.settings import get_config


def main():
    config = get_config()
    db = open_db()

    by_path: dict[Path, list] = defaultdict(list)
    for h in db.get_media_handles():
        media = db.get_media_from_handle(h)
        p = Path(media.get_path())
        resolved = (p if p.is_absolute() else config.validated_db_path / p).resolve()
        by_path[resolved].append(media)

    db.close()

    duplicates = {path: items for path, items in by_path.items() if len(items) > 1}

    if not duplicates:
        print("No duplicate media objects found.")
        return

    for path, items in sorted(duplicates.items()):
        print(path)
        for media in items:
            print(f"  {media.get_gramps_id()}")

    print(f"\n{len(duplicates)} duplicate file(s) across {sum(len(v) for v in duplicates.values())} media objects")


if __name__ == '__main__':
    main()
