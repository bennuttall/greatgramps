#!/usr/bin/env python3
"""Merge media objects in the Gramps database that point to the same file."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
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


BEARER_TYPES = [
    ('person',   lambda db: db.iter_people(),    lambda db: db.commit_person),
    ('family',   lambda db: db.iter_families(),  lambda db: db.commit_family),
    ('event',    lambda db: db.iter_events(),    lambda db: db.commit_event),
    ('place',    lambda db: db.iter_places(),    lambda db: db.commit_place),
    ('source',   lambda db: db.iter_sources(),   lambda db: db.commit_source),
    ('citation', lambda db: db.iter_citations(), lambda db: db.commit_citation),
]


def build_ref_index(db):
    """Return {media_handle: [(obj, commit_fn), ...]} across all bearer types."""
    index = defaultdict(list)
    for _, iter_fn, commit_fn in BEARER_TYPES:
        for obj in iter_fn(db):
            for ref in obj.get_media_list():
                index[ref.get_reference_handle()].append((obj, commit_fn(db)))
    return index


def main():
    config = get_config()
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        by_path: dict[Path, list] = defaultdict(list)
        for h in db.get_media_handles():
            media = db.get_media_from_handle(h)
            p = Path(media.get_path())
            resolved = (p if p.is_absolute() else config.validated_db_path / p).resolve()
            by_path[resolved].append(media)

        groups = {path: items for path, items in by_path.items() if len(items) > 1}

        if not groups:
            print("No duplicate media objects found.")
            return

        ref_index = build_ref_index(db)

        # For each group pick the winner (most references, then lowest gramps_id)
        merges = []  # [(winner, [losers])]
        for path, items in sorted(groups.items()):
            items.sort(key=lambda m: (-len(ref_index[m.get_handle()]), m.get_gramps_id()))
            winner, *losers = items
            merges.append((winner, losers))

        print(f"Found {len(merges)} duplicate file(s):\n")
        total_losers = 0
        for winner, losers in merges:
            for loser in losers:
                n_refs = len(ref_index[loser.get_handle()])
                print(f"  {loser.get_gramps_id()} → {winner.get_gramps_id()}  ({n_refs} reference(s) to update)  {winner.get_path()}")
                total_losers += 1

        print()
        try:
            answer = input(f"Merge {total_losers} duplicate(s)? [Y/n] ").strip().lower()
            if answer == 'n':
                print("Cancelled.")
                return
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return

        with DbTxn("Merge duplicate media", db) as trans:
            for winner, losers in merges:
                winner_handle = winner.get_handle()
                for loser in losers:
                    loser_handle = loser.get_handle()
                    for obj, commit_fn in ref_index[loser_handle]:
                        obj.replace_media_references(loser_handle, winner_handle)
                        commit_fn(obj, trans)
                    db.remove_media(loser_handle, trans)

        print(f"Done — {total_losers} duplicate(s) merged.")

    finally:
        db.close()


if __name__ == '__main__':
    main()
