#!/usr/bin/env python3
"""List gallery files not referenced in the GRAMPS database."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

import os
os.environ.setdefault('GREATGRAMPS_CONFIG', str(REPO_ROOT / 'config.yml'))

from greatgramps.settings import get_config
from gramps.plugins.db.dbapi.sqlite import SQLite
from gramps.gen.db import DBMODE_R


def main():
    type_filter = sys.argv[1].lower() if len(sys.argv) > 1 else None

    config = get_config()
    gallery_dir = config.validated_db_path / 'Gallery'

    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_R)

    referenced = set()
    for h in db.get_media_handles():
        m = db.get_media_from_handle(h)
        p = Path(m.get_path())
        resolved = p if p.is_absolute() else config.validated_db_path / p
        referenced.add(resolved.resolve())

    db.close()

    unreferenced = []
    for f in sorted(gallery_dir.rglob('*')):
        if not f.is_file():
            continue
        category = f.relative_to(gallery_dir).parts[0].lower()
        if type_filter and category != type_filter:
            continue
        if f.resolve() not in referenced:
            unreferenced.append(f.relative_to(gallery_dir))

    if not unreferenced:
        print("No unreferenced files found.")
        return

    for f in unreferenced:
        print(f)

    print(f"\n{len(unreferenced)} unreferenced file(s)", file=sys.stderr)


if __name__ == '__main__':
    main()
