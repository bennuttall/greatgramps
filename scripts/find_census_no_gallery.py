"""Find Census events in the GRAMPS database that have no gallery item,
then check which have a matching file in /home/ben/GRAMPS/Gallery/Census/."""

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
os.environ.setdefault('GREATGRAMPS_CONFIG', str(REPO_ROOT / 'config.yml'))

from greatgramps.gramps_data import open_db
from gramps.gen.lib.eventtype import EventType

CENSUS_DIR = Path('/home/ben/GRAMPS/Gallery/Census')


def get_census_files():
    """Return list of (year_str, filename_stem, full_path)."""
    entries = []
    for f in CENSUS_DIR.rglob('*'):
        if f.is_file():
            year_dir = f.parent.name  # e.g. '1841' or '1939 Register'
            year_match = re.match(r'(\d{4})', year_dir)
            year = int(year_match.group(1)) if year_match else None
            entries.append((year, f.stem, f))
    return entries


def event_has_media(db, event):
    return bool(event.get_media_list())


def find_matching_files(census_files, year, participants):
    """Find gallery files that match year and any participant name."""
    matches = []
    for file_year, stem, path in census_files:
        if file_year != year:
            continue
        stem_lower = stem.lower()
        for name in participants:
            parts = name.lower().split()
            if all(p in stem_lower for p in parts if p):
                matches.append(path)
                break
            # Try just surname
            if parts and parts[-1] in stem_lower:
                matches.append(path)
                break
    return matches


def main():
    db = open_db()
    census_files = get_census_files()

    print(f"Total census gallery files: {len(census_files)}\n")

    # Build event -> participants map efficiently
    event_handle_to_people = {}
    for person in db.iter_people():
        name = person.get_primary_name()
        full_name = f"{name.get_first_name()} {name.get_surname()}".strip()
        for eref in person.get_event_ref_list():
            h = eref.get_reference_handle()
            event_handle_to_people.setdefault(h, []).append(full_name)

    # Collect all census events without media
    no_media = []
    for event in db.iter_events():
        if int(event.get_type()) != EventType.CENSUS:
            continue
        if event_has_media(db, event):
            continue
        year = event.get_date_object().get_year() or None
        gid = event.get_gramps_id()
        participants = event_handle_to_people.get(event.get_handle(), [])
        no_media.append((year or 0, gid, year, participants))

    no_media.sort()

    print(f"Census events with no gallery item: {len(no_media)}\n")

    has_match = []
    no_match = []

    for _, gid, year, participants in no_media:
        matches = find_matching_files(census_files, year, participants) if year else []
        row = (gid, year, participants, matches)
        if matches:
            has_match.append(row)
        else:
            no_match.append(row)

    if has_match:
        print("=== Events with no gallery item but matching file exists ===\n")
        for gid, year, participants, matches in has_match:
            print(f"  {gid}  {year}  {', '.join(participants)}")
            for m in matches:
                print(f"    -> {m.relative_to(CENSUS_DIR.parent)}")

    print()
    if no_match:
        print("=== Events with no gallery item and no matching file found ===\n")
        for gid, year, participants, _ in no_match:
            print(f"  {gid}  {str(year) if year else '?'}  {', '.join(participants) or '(no participants)'}")

    print()
    print(f"Summary: {len(no_media)} census events missing gallery items")
    print(f"  {len(has_match)} have a potential matching file in the gallery dir")
    print(f"  {len(no_match)} have no matching file")

    db.close()


if __name__ == '__main__':
    main()
