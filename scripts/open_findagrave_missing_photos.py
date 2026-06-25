#!/usr/bin/env python3
"""Walk through people with a Find A Grave link whose burial event has no gallery picture."""

from __future__ import annotations

import mimetypes
import os
import select
import subprocess
import sys
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / '.env')
_cfg = os.environ.get('GREATGRAMPS_CONFIG', 'config.yml')
if not Path(_cfg).is_absolute():
    os.environ['GREATGRAMPS_CONFIG'] = str(REPO_ROOT / _cfg)

from rich.console import Console

from gramps.gen.db import DBMODE_W, DbTxn
from gramps.gen.lib import Media, MediaRef
from gramps.gen.lib.eventtype import EventType
from gramps.plugins.db.dbapi.sqlite import SQLite

from greatgramps.gramps_data import format_date, get_event, get_place_name
from greatgramps.settings import get_config

console = Console()

SITE_ROOT = 'I0018'
BASE_URL = f'http://localhost:8000/{SITE_ROOT}/people'
GRGR_BIN = Path(sys.executable).parent / 'grgr'


def _prompt(text: str) -> str:
    line = input(text)
    while not line.strip() and select.select([sys.stdin], [], [], 0)[0]:
        line = input()
    return line.strip()


def _burial_has_image(db, burial_event) -> bool:
    return any(
        db.get_media_from_handle(ref.get_reference_handle()).get_mime_type().startswith('image/')
        for ref in burial_event.get_media_list()
    )


def _snapshot(graves_dir: Path) -> set[str]:
    if not graves_dir.exists():
        return set()
    return {f.name for f in graves_dir.iterdir() if f.is_file()}


def main():
    config = get_config()
    graves_dir = config.validated_db_path / 'Gallery' / 'Graves'

    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        people = []
        for handle in db.get_person_handles(sort_handles=True):
            person = db.get_person_from_handle(handle)
            find_a_grave_url = next(
                (u.get_path() for u in person.get_url_list() if str(u.get_type()).lower() == 'find a grave'),
                None,
            )
            if not find_a_grave_url:
                continue
            burial = get_event(db, person, EventType(EventType.BURIAL))
            if not burial:
                continue
            if _burial_has_image(db, burial):
                continue
            people.append((person, find_a_grave_url, burial))

        if not people:
            console.print("[yellow]No people found with a Find A Grave link and a burial event missing a photo.[/yellow]")
            return

        console.print(f"{len(people)} people with a Find A Grave link and no burial photo\n")

        for person, find_a_grave_url, burial in people:
            gramps_id = person.get_gramps_id()
            pn = person.get_primary_name()
            name = f"{pn.get_first_name()} {pn.get_surname()}".strip()
            url = f"{BASE_URL}/{gramps_id}/"

            console.print()
            console.print(f"[bold]{name}[/bold] ({gramps_id})")
            burial_date = format_date(burial.get_date_object())
            burial_place = get_place_name(db, burial)
            console.print(f"Burial: {burial_date or '?'} at {burial_place or '?'}")
            console.print(find_a_grave_url)

            try:
                open_choice = _prompt("Open? Y/n: ").lower()
            except (KeyboardInterrupt, EOFError):
                console.print("\nStopped.")
                break
            if open_choice == 'n':
                continue
            webbrowser.open(find_a_grave_url)

            before = _snapshot(graves_dir)

            try:
                added = _prompt("Added the photo? Y/n/e (existing): ").lower()
            except (KeyboardInterrupt, EOFError):
                console.print("\nStopped.")
                break
            if added == 'n':
                continue

            if added == 'e':
                try:
                    substring = _prompt("Search existing files (substring): ")
                except (KeyboardInterrupt, EOFError):
                    console.print("\nStopped.")
                    break
                all_files = sorted(_snapshot(graves_dir))
                matches = [f for f in all_files if substring.lower() in f.lower()]
                if not matches:
                    console.print(f"[yellow]No files matching {substring!r} — skipping.[/yellow]")
                    continue
                if len(matches) == 1:
                    new_file = graves_dir / matches[0]
                else:
                    console.print(f"{len(matches)} matches:")
                    for i, f in enumerate(matches, 1):
                        console.print(f"  {i}. {f}")
                    try:
                        pick = _prompt("Choose number: ")
                    except (KeyboardInterrupt, EOFError):
                        console.print("\nStopped.")
                        break
                    if not pick.isdigit() or not (1 <= int(pick) <= len(matches)):
                        console.print("[yellow]Invalid choice — skipping.[/yellow]")
                        continue
                    new_file = graves_dir / matches[int(pick) - 1]
            else:
                after = _snapshot(graves_dir)
                new_files = after - before

                if not new_files:
                    console.print("[yellow]No new files found in Graves directory — skipping.[/yellow]")
                    continue
                if len(new_files) > 1:
                    console.print(f"[yellow]Expected one new file but found {len(new_files)} — skipping:[/yellow]")
                    for f in sorted(new_files):
                        console.print(f"  {f}")
                    continue

                new_file = graves_dir / next(iter(new_files))
            mime_type, _ = mimetypes.guess_type(str(new_file))
            if not mime_type:
                mime_type = 'image/jpeg'

            media = Media()
            media.set_path(str(new_file))
            media.set_mime_type(mime_type)
            media.set_description(f"Burial — {name}")

            with DbTxn('Add burial photo', db) as trans:
                db.add_media(media, trans)
                ref = MediaRef()
                ref.set_reference_handle(media.get_handle())
                burial.add_media_reference(ref)
                db.commit_event(burial, trans)

            console.print(f"[green]Photo attached:[/green] {new_file.name} → {burial.get_gramps_id()}")
            subprocess.run([str(GRGR_BIN), 'rebuild-page', gramps_id], cwd=REPO_ROOT, check=True)
            console.print(f"[green]Page rebuilt:[/green] {url}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
