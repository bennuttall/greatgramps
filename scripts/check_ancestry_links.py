#!/usr/bin/env python3
"""Report direct ancestors missing an Ancestry link in Gramps."""

from __future__ import annotations

import os
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
from gramps.gen.lib import Url, UrlType
from gramps.gen.lib.eventtype import EventType
from gramps.plugins.db.dbapi.sqlite import SQLite

from greatgramps.gramps_data import ancestors_with_distances, get_event, get_year, relationship_label
from greatgramps.settings import get_config

console = Console()


def main():
    config = get_config()
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        me = db.get_person_from_gramps_id(config.me)
        if not me:
            console.print(f"[red]Home person {config.me!r} not found[/red]")
            sys.exit(1)

        ancestor_distances = ancestors_with_distances(db, me)

        missing = []
        for gramps_id, distance in ancestor_distances.items():
            if distance == 0:
                continue
            person = db.get_person_from_gramps_id(gramps_id)
            if not person:
                continue
            has_ancestry = any(str(u.get_type()) == 'Ancestry' for u in person.get_url_list())
            if has_ancestry:
                continue
            pn = person.get_primary_name()
            name = f"{pn.get_first_name()} {pn.get_surname()}".strip()
            gender = person.get_gender()
            relation = relationship_label(distance, 0, gender)
            birth = get_event(db, person, EventType.BIRTH)
            birth_year = get_year(birth)
            missing.append((distance, birth_year or 9999, gramps_id, name, relation, birth_year))

        missing.sort(key=lambda r: (r[0], r[1]))

        if not missing:
            console.print("[green]All direct ancestors have an Ancestry link.[/green]")
            return

        console.print(f"{len(missing)} ancestor(s) missing Ancestry link\n")

        for distance, _, gramps_id, name, relation, birth_year in missing:
            person = db.get_person_from_gramps_id(gramps_id)
            ancestor_child_url = None
            ancestor_child_name = None
            for fam_handle in person.get_family_handle_list():
                family = db.get_family_from_handle(fam_handle)
                for cref in family.get_child_ref_list():
                    child = db.get_person_from_handle(cref.get_reference_handle())
                    if child and ancestor_distances.get(child.get_gramps_id()) == distance - 1:
                        ancestor_child_url = next(
                            (u.get_path() for u in child.get_url_list() if str(u.get_type()) == 'Ancestry'),
                            None,
                        )
                        cpn = child.get_primary_name()
                        ancestor_child_name = f"{cpn.get_first_name()} {cpn.get_surname()}".strip()
                        break
                if ancestor_child_url:
                    break

            if not ancestor_child_url:
                console.print(f"[yellow]No Ancestry link found on ancestor child of {gramps_id} ({name}), skipping.[/yellow]")
                continue

            console.print(f"Opening {ancestor_child_url} ({ancestor_child_name})")
            webbrowser.open(ancestor_child_url)

            try:
                ancestry_url = input(f"Ancestry link for {name} (enter to skip): ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\nStopped.")
                break

            if ancestry_url:
                url_obj = Url()
                url_type = UrlType()
                url_type.set((UrlType.CUSTOM, 'Ancestry'))
                url_obj.set_type(url_type)
                url_obj.set_path(ancestry_url)
                with DbTxn('Add Ancestry link', db) as trans:
                    person.add_url(url_obj)
                    db.commit_person(person, trans)
                console.print(f"[green]Saved Ancestry link for {gramps_id}[/green]")

    finally:
        db.close()


if __name__ == '__main__':
    main()
