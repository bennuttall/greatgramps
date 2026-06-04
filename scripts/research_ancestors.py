#!/usr/bin/env python3
"""Iterate over a generation of direct ancestors, show census coverage, and open for research."""

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
from rich.table import Table

from gramps.gen.db import DBMODE_R
from gramps.gen.lib.eventtype import EventType
from gramps.plugins.db.dbapi.sqlite import SQLite

from greatgramps.gramps_data import (
    CENSUS_DATES, ancestors_with_distances, get_event, get_year, relationship_label,
)
from greatgramps.settings import get_config

console = Console()


def _person_name(person) -> str:
    pn = person.get_primary_name()
    return f"{pn.get_first_name()} {pn.get_surname()}".strip()


def _print_census_table(db, person, event_person_count):
    birth_year = get_year(get_event(db, person, EventType.BIRTH))
    death_year = get_year(get_event(db, person, EventType.DEATH))

    person_census_by_year: dict[int, list] = {}
    for eref in person.get_event_ref_list():
        event = db.get_event_from_handle(eref.get_reference_handle())
        if int(event.get_type()) == EventType.CENSUS:
            year = event.get_date_object().get_year()
            if year:
                person_census_by_year.setdefault(year, []).append(event)

    eligible = [
        y for y in sorted(CENSUS_DATES)
        if (birth_year is None or birth_year <= y)
        and (death_year is None or death_year >= y)
    ]

    if not eligible:
        console.print("  No census years fall within this person's lifespan.")
        return

    table = Table()
    table.add_column("Year")
    table.add_column("Age", justify="right")
    table.add_column("Record")
    table.add_column("People", justify="right")

    for year in eligible:
        age = str(year - birth_year) if birth_year else ""
        events = person_census_by_year.get(year, [])
        if events:
            for event in events:
                count = event_person_count.get(event.get_handle(), 0)
                table.add_row(str(year), age, "[green]Yes[/green]", str(count))
        else:
            table.add_row(str(year), age, "[red]No[/red]", "")

    console.print(table)


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        console.print("Usage: research_ancestors.py <generation>")
        sys.exit(1)

    generation = int(sys.argv[1])

    config = get_config()
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_R)

    try:
        me = db.get_person_from_gramps_id(config.me)
        if not me:
            console.print(f"[red]Home person {config.me!r} not found[/red]")
            sys.exit(1)

        ancestor_distances = ancestors_with_distances(db, me)

        # pre-build event -> person count index
        event_person_count: dict = {}
        for handle in db.get_person_handles():
            p = db.get_person_from_handle(handle)
            for eref in p.get_event_ref_list():
                h = eref.get_reference_handle()
                event_person_count[h] = event_person_count.get(h, 0) + 1

        people = []
        for gid, dist in ancestor_distances.items():
            if dist != generation:
                continue
            person = db.get_person_from_gramps_id(gid)
            if not person:
                continue
            birth_year = get_year(get_event(db, person, EventType.BIRTH))
            people.append((birth_year or 9999, person))

        if not people:
            console.print(f"No ancestors found at generation {generation}.")
            return

        people.sort(key=lambda x: x[0])
        console.print(f"\n[bold]{len(people)} ancestor(s) at generation {generation}[/bold]")

        for _, person in people:
            gid = person.get_gramps_id()
            name = _person_name(person)
            relation = relationship_label(generation, 0, person.get_gender())

            console.print(f"\n[bold]{name}[/bold]  {relation}  {gid}")
            _print_census_table(db, person, event_person_count)

            try:
                answer = input("\n[r to research / enter to skip]: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                console.print("\nStopped.")
                break

            if answer != 'r':
                continue

            ancestry_url = next(
                (u.get_path() for u in person.get_url_list() if str(u.get_type()) == 'Ancestry'),
                None,
            )
            webbrowser.open(f"http://localhost:8000/people/{gid}/")
            if ancestry_url:
                webbrowser.open(ancestry_url)
            else:
                console.print("[yellow]No Ancestry link.[/yellow]")

            while True:
                try:
                    again = input("[enter to check again / c to continue]: ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    console.print("\nStopped.")
                    return
                if again == 'c':
                    break
                fresh_db = SQLite()
                fresh_db.load(str(config.validated_db_path), mode=DBMODE_R)
                try:
                    fresh_person = fresh_db.get_person_from_gramps_id(gid)
                    fresh_epc: dict = {}
                    for h in fresh_db.get_person_handles():
                        p = fresh_db.get_person_from_handle(h)
                        for eref in p.get_event_ref_list():
                            eh = eref.get_reference_handle()
                            fresh_epc[eh] = fresh_epc.get(eh, 0) + 1
                    _print_census_table(fresh_db, fresh_person, fresh_epc)
                finally:
                    fresh_db.close()

    finally:
        db.close()


if __name__ == '__main__':
    main()
