from __future__ import annotations

import json
import mimetypes
import urllib.parse
import urllib.request
from pathlib import Path
import re
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from gramps.gen.db import DBMODE_R, DBMODE_W, DbTxn
from gramps.gen.lib import (
    ChildRef, Date, Event, EventRef, EventRoleType, EventType,
    Family, Media, MediaRef, Name, NameType, Person, Place, PlaceName,
    PlaceType, Surname, Url, UrlType,
)
from gramps.plugins.db.dbapi.sqlite import SQLite

from .build import rebuild_pages
from .gramps_data import get_event, get_year
from .settings import get_config


app = typer.Typer(help="Greatgramps — manage your Gramps family tree database.", no_args_is_help=True)
console = Console()

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "greatgramps/0.1 (family tree tool)"

NOMINATIM_TYPE_MAP = {
    'city': PlaceType.CITY,
    'town': PlaceType.TOWN,
    'village': PlaceType.VILLAGE,
    'hamlet': PlaceType.HAMLET,
    'county': PlaceType.COUNTY,
    'state': PlaceType.STATE,
    'country': PlaceType.COUNTRY,
    'parish': PlaceType.PARISH,
    'municipality': PlaceType.MUNICIPALITY,
    'borough': PlaceType.BOROUGH,
    'district': PlaceType.DISTRICT,
    'region': PlaceType.REGION,
    'province': PlaceType.PROVINCE,
    'locality': PlaceType.LOCALITY,
    'neighbourhood': PlaceType.NEIGHBORHOOD,
    'suburb': PlaceType.NEIGHBORHOOD,
    'farm': PlaceType.FARM,
}


def _open_db(write=False):
    config = get_config()
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W if write else DBMODE_R)
    return db


def _geocode(query: str):
    params = urllib.parse.urlencode({'q': query, 'format': 'json', 'limit': 5})
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}", headers={'User-Agent': USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _person_name(person) -> str:
    n = person.get_primary_name()
    primary = f"{n.get_first_name()} {n.get_surname()}".strip()
    primary_surname = n.get_surname()
    alt_surnames = [
        a.get_surname() for a in person.get_alternate_names()
        if a.get_surname() and a.get_surname() != primary_surname
    ]
    if alt_surnames:
        return f"{primary} ({', '.join(alt_surnames)})"
    return primary


def _event_label(event) -> str:
    desc = event.get_description() or str(event.get_type())
    year = event.get_date_object().get_year()
    return f"{desc} ({year})" if year else desc


def _stem_to_description(stem: str) -> str:
    parts = stem.split('_')
    year = parts[0]
    record_type = 'register' if year == '1939' else 'census'
    if len(parts) >= 4 and parts[-2] == 'page':
        name = ' '.join(p.capitalize() for p in parts[1:-2])
        return f"{year} {record_type} - {name} household (page {parts[-1]})"
    name = ' '.join(p.capitalize() for p in parts[1:])
    return f"{year} {record_type} - {name} household"


def _confirm(yes: bool = False):
    if yes:
        return
    try:
        input("Press Enter to confirm (Ctrl+C to cancel) ")
    except KeyboardInterrupt:
        console.print("\nCancelled.")
        raise typer.Exit(0)


def _place_table(places) -> Table:
    table = Table()
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Lat")
    table.add_column("Lon")
    for place in places:
        table.add_row(
            place.get_gramps_id(),
            place.get_name().get_value(),
            str(place.get_type()),
            place.get_latitude() or "—",
            place.get_longitude() or "—",
        )
    return table


def _people_table(people: list[tuple]) -> Table:
    table = Table()
    table.add_column("ID")
    table.add_column("Name")
    for person, name in people:
        table.add_row(person.get_gramps_id(), name)
    return table


@app.command("rebuild-page", no_args_is_help=True)
def rebuild_page(
    ids: List[str] = typer.Argument(..., help="Person or event IDs to rebuild (e.g. I0061 E0315)"),
):
    """Copy static files and rebuild specific person or event pages."""
    rebuild_pages(ids)


@app.command("add-place", no_args_is_help=True)
def add_place(
    query: str = typer.Argument(..., help="Location to geocode and add"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Geocode a location and add it as a Place in the database."""
    console.print(f"Geocoding: [bold]{query}[/bold]")
    results = _geocode(query)
    if not results:
        console.print(f"[red]No results found for {query!r}[/red]")
        raise typer.Exit(1)

    result = results[0]
    lat, lon = result['lat'], result['lon']
    display_name = result['display_name']
    addresstype = result.get('addresstype', result.get('type', ''))
    place_type_int = NOMINATIM_TYPE_MAP.get(addresstype, PlaceType.UNKNOWN)
    name = display_name.split(',')[0].strip()

    summary = Table(show_header=False)
    summary.add_column("Field", style="bold")
    summary.add_column("Value")
    summary.add_row("Name", name)
    summary.add_row("Full", display_name)
    summary.add_row("Type", addresstype)
    summary.add_row("Lat", str(lat))
    summary.add_row("Lon", str(lon))
    console.print(summary)

    _confirm(yes)

    db = _open_db(write=True)
    try:
        place = Place()
        pn = PlaceName()
        pn.set_value(name)
        place.set_name(pn)
        place.set_latitude(str(lat))
        place.set_longitude(str(lon))
        place.set_type(PlaceType(place_type_int))
        with DbTxn('Add place', db) as trans:
            db.add_place(place, trans)
        console.print("\n[green]Place added:[/green]")
        console.print(_place_table([place]))
    finally:
        db.close()


@app.command("search-place", no_args_is_help=True)
def search_place(query: str = typer.Argument(..., help="Name to search for")):
    """Search for places in the database by name."""
    db = _open_db()
    try:
        q = query.lower()
        all_places = [db.get_place_from_handle(h) for h in db.get_place_handles()]
        matches = sorted(
            [p for p in all_places if q in p.get_name().get_value().lower()],
            key=lambda p: p.get_name().get_value().lower(),
        )
        if not matches:
            console.print(f"No places found matching [bold]{query!r}[/bold]")
            return
        console.print(f"{len(matches)} place(s) matching [bold]{query!r}[/bold]:")
        console.print(_place_table(matches))
    finally:
        db.close()


@app.command("add-census", no_args_is_help=True)
def add_census(
    filepath: Path = typer.Argument(..., help="Path to census image file"),
    person_ids: List[str] = typer.Argument(..., help="Person IDs to link to this event"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Add a census event from an image file and link people to it."""
    filepath = filepath.resolve()
    if not filepath.exists():
        console.print(f"[red]File not found: {filepath}[/red]")
        raise typer.Exit(1)

    parts = filepath.stem.split('_')
    if not parts[0].isdigit():
        console.print("[red]Filename must start with a year (e.g. 1921_jarvis_nuttall.jpg)[/red]")
        raise typer.Exit(1)

    year = int(parts[0])
    description = _stem_to_description(filepath.stem)

    db = _open_db(write=True)
    try:
        people = []
        for pid in person_ids:
            person = db.get_person_from_gramps_id(pid)
            if not person:
                console.print(f"[red]Person {pid!r} not found[/red]")
                raise typer.Exit(1)
            people.append((person, _person_name(person)))

        summary = Table(show_header=False)
        summary.add_column("Field", style="bold")
        summary.add_column("Value")
        summary.add_row("File", str(filepath))
        summary.add_row("Year", str(year))
        summary.add_row("Description", description)
        console.print(summary)
        console.print("\n[bold]People:[/bold]")
        console.print(_people_table(people))

        _confirm(yes)

        existing_media_paths = {
            db.get_media_from_handle(h).get_path(): h
            for h in db.get_media_handles()
        }

        with DbTxn('Add census event', db) as trans:
            event = Event()
            event.set_type(EventType(EventType.CENSUS))
            date = Date()
            date.set_yr_mon_day(year, 0, 0)
            event.set_date_object(date)
            event.set_description(description)

            path_str = str(filepath)
            if path_str in existing_media_paths:
                media_handle = existing_media_paths[path_str]
            else:
                mime = mimetypes.guess_type(path_str)[0] or 'image/jpeg'
                media = Media()
                media.set_path(path_str)
                media.set_mime_type(mime)
                media.set_description(filepath.stem)
                media_handle = db.add_media(media, trans)

            mref = MediaRef()
            mref.set_reference_handle(media_handle)
            event.add_media_reference(mref)

            db.add_event(event, trans)

            for person, _ in people:
                eref = EventRef()
                eref.set_reference_handle(event.get_handle())
                eref.set_role(EventRoleType(EventRoleType.PRIMARY))
                person.add_event_ref(eref)
                db.commit_person(person, trans)

        result = Table(show_header=False)
        result.add_column("Field", style="bold")
        result.add_column("Value")
        result.add_row("Event ID", event.get_gramps_id())
        result.add_row("Description", event.get_description())
        result.add_row("Year", str(year))
        result.add_row("Image", filepath.name)
        console.print(f"\n[green]Event created:[/green]")
        console.print(result)
    finally:
        db.close()


@app.command("add-event-people", no_args_is_help=True)
def add_event_people(
    event_id: str = typer.Argument(..., help="Event ID"),
    person_ids: List[str] = typer.Argument(..., help="Person IDs to link"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Link people to an existing event."""
    db = _open_db(write=True)
    try:
        event = db.get_event_from_gramps_id(event_id)
        if not event:
            console.print(f"[red]Event {event_id!r} not found[/red]")
            raise typer.Exit(1)

        event_year = event.get_date_object().get_year() or None

        def _person_row(person):
            birth = get_event(db, person, EventType.BIRTH)
            birth_year = get_year(birth)
            age = str(event_year - birth_year) if event_year and birth_year else ""
            return (person, _person_name(person), str(birth_year) if birth_year else "", age)

        def _people_age_table(rows):
            table = Table()
            table.add_column("ID")
            table.add_column("Name")
            table.add_column("Born")
            table.add_column("Age")
            for person, name, born, age in rows:
                table.add_row(person.get_gramps_id(), name, born, age)
            return table

        to_add, skipped = [], []
        for pid in person_ids:
            person = db.get_person_from_gramps_id(pid)
            if not person:
                console.print(f"[red]Person {pid!r} not found[/red]")
                raise typer.Exit(1)
            if any(e.get_reference_handle() == event.get_handle() for e in person.get_event_ref_list()):
                skipped.append(_person_row(person))
            else:
                to_add.append(_person_row(person))

        console.print(f"[bold]Event:[/bold] {event.get_gramps_id()} — {_event_label(event)}")

        if skipped:
            console.print("\n[yellow]Already linked (skipping):[/yellow]")
            console.print(_people_age_table(skipped))

        if not to_add:
            console.print("No new people to add.")
            return

        console.print("\n[bold]To add:[/bold]")
        console.print(_people_age_table(to_add))

        _confirm(yes)

        with DbTxn('Add people to event', db) as trans:
            for person, _, _, _ in to_add:
                eref = EventRef()
                eref.set_reference_handle(event.get_handle())
                eref.set_role(EventRoleType(EventRoleType.PRIMARY))
                person.add_event_ref(eref)
                db.commit_person(person, trans)

        console.print(f"[green]Added {len(to_add)} person(s) to {event_id}[/green]\n")

        all_people = []
        for handle in db.get_person_handles():
            p = db.get_person_from_handle(handle)
            for eref in p.get_event_ref_list():
                if eref.get_reference_handle() == event.get_handle():
                    birth = get_event(db, p, EventType.BIRTH)
                    all_people.append((p, _person_name(p), get_year(birth)))
                    break
        event_year = event.get_date_object().get_year() or None
        all_people.sort(key=lambda x: x[2] or 9999)
        table = Table()
        table.add_column("ID")
        table.add_column("Name")
        table.add_column("Born")
        table.add_column("Age")
        for p, name, birth_year in all_people:
            age = str(event_year - birth_year) if event_year and birth_year else ""
            table.add_row(p.get_gramps_id(), name, str(birth_year) if birth_year else "", age)
        console.print(table)
    finally:
        db.close()


EVENT_TYPE_MAP = {
    'birth': EventType(EventType.BIRTH),
    'death': EventType(EventType.DEATH),
    'burial': EventType(EventType.BURIAL),
    'baptism': EventType(EventType.BAPTISM),
    'confirmation': EventType(EventType.CONFIRMATION),
    'marriage': EventType(EventType.MARRIAGE),
    'divorce': EventType(EventType.DIVORCE),
    'occupation': EventType(EventType.OCCUPATION),
    'residence': EventType(EventType.RESIDENCE),
    'census': EventType(EventType.CENSUS),
    'military': EventType(EventType.MILITARY_SERV),
    'education': EventType(EventType.EDUCATION),
    'graduation': EventType(EventType.GRADUATION),
    'retirement': EventType(EventType.RETIREMENT),
    'immigration': EventType(EventType.IMMIGRATION),
    'emigration': EventType(EventType.EMIGRATION),
    'award': EventType((EventType.CUSTOM, 'Award')),
    'probate': EventType((EventType.CUSTOM, 'Probate')),
    'conviction': EventType((EventType.CUSTOM, 'Conviction')),
    'sentencing': EventType((EventType.CUSTOM, 'Sentencing')),
}

_MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10,
    'november': 11, 'december': 12,
}


def _parse_date(date_str: str) -> tuple[int, int, int] | None:
    """Parse 'YYYY', 'YYYY-MM-DD', 'Mon YYYY', or 'DD Mon YYYY' into (year, month, day)."""
    s = date_str.strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        y, m, d = s.split('-')
        return int(y), int(m), int(d)
    s = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', s)
    parts = s.split()
    if len(parts) == 3:
        try:
            return int(parts[2]), _MONTH_MAP.get(parts[1].lower(), 0), int(parts[0])
        except (ValueError, KeyError):
            pass
    if len(parts) == 2:
        try:
            return int(parts[1]), _MONTH_MAP.get(parts[0].lower(), 0), 0
        except (ValueError, KeyError):
            pass
    if len(parts) == 1:
        try:
            return int(parts[0]), 0, 0
        except ValueError:
            pass
    return None


def _resolve_place(db, query: str):
    """Return a place by ID or name search. Prints options and exits if ambiguous."""
    place = db.get_place_from_gramps_id(query)
    if place:
        return place
    all_places = [db.get_place_from_handle(h) for h in db.get_place_handles()]
    matches = sorted(
        [p for p in all_places if query.lower() in p.get_name().get_value().lower()],
        key=lambda p: p.get_name().get_value().lower(),
    )
    if not matches:
        console.print(f"[red]No place found matching {query!r}[/red]")
        raise typer.Exit(1)
    if len(matches) == 1:
        return matches[0]
    console.print(f"[yellow]{len(matches)} places match {query!r} — be more specific:[/yellow]")
    console.print(_place_table(matches))
    raise typer.Exit(1)


@app.command("add-event", no_args_is_help=True)
def add_event(
    event_type_str: str = typer.Argument(..., help=f"Event type: {', '.join(EVENT_TYPE_MAP)}"),
    person_ids: List[str] = typer.Argument(..., help="One or more person IDs"),
    date: Optional[str] = typer.Option(None, "--date", help="Date: year or 'DD Mon YYYY'"),
    place_query: Optional[str] = typer.Option(None, "--place", help="Place name or ID"),
    gallery: Optional[Path] = typer.Option(None, "--gallery", help="Media file to attach"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Add an event and link it to one or more people."""
    event_type = EVENT_TYPE_MAP.get(event_type_str.lower())
    if event_type is None:
        console.print(f"[red]Unknown event type {event_type_str!r}. Choose from: {', '.join(EVENT_TYPE_MAP)}[/red]")
        raise typer.Exit(1)

    parsed_date = None
    if date:
        parsed_date = _parse_date(date)
        if parsed_date is None:
            console.print(f"[red]Could not parse date {date!r}[/red]")
            raise typer.Exit(1)

    if gallery and not gallery.exists():
        console.print(f"[red]File not found: {gallery}[/red]")
        raise typer.Exit(1)

    db = _open_db(write=True)
    try:
        people = []
        for pid in person_ids:
            person = db.get_person_from_gramps_id(pid)
            if not person:
                console.print(f"[red]Person {pid!r} not found[/red]")
                raise typer.Exit(1)
            people.append((person, _person_name(person)))

        place = _resolve_place(db, place_query) if place_query else None

        summary = Table(show_header=False)
        summary.add_column("Field", style="bold")
        summary.add_column("Value")
        summary.add_row("Type", event_type_str)
        if parsed_date:
            summary.add_row("Date", date)
        if place:
            summary.add_row("Place", f"{place.get_name().get_value()} ({place.get_gramps_id()})")
        if gallery:
            summary.add_row("Gallery", str(gallery))
        console.print(summary)
        console.print("\n[bold]People:[/bold]")
        console.print(_people_table(people))

        _confirm(yes)

        with DbTxn(f'Add {event_type_str} event', db) as trans:
            event = Event()
            event.set_type(event_type)

            if parsed_date:
                y, m, d = parsed_date
                dt = Date()
                dt.set_yr_mon_day(y, m, d)
                event.set_date_object(dt)

            if place:
                event.set_place_handle(place.get_handle())

            if gallery:
                path_str = str(gallery.resolve())
                existing = {db.get_media_from_handle(h).get_path(): h for h in db.get_media_handles()}
                if path_str in existing:
                    media_handle = existing[path_str]
                else:
                    mime = mimetypes.guess_type(path_str)[0] or 'image/jpeg'
                    media = Media()
                    media.set_path(path_str)
                    media.set_mime_type(mime)
                    media.set_description(gallery.stem)
                    media_handle = db.add_media(media, trans)
                mref = MediaRef()
                mref.set_reference_handle(media_handle)
                event.add_media_reference(mref)

            db.add_event(event, trans)

            for person, _ in people:
                eref = EventRef()
                eref.set_reference_handle(event.get_handle())
                eref.set_role(EventRoleType(EventRoleType.PRIMARY))
                person.add_event_ref(eref)
                db.commit_person(person, trans)

        ids = ', '.join(person_ids)
        console.print(f"[green]Event {event.get_gramps_id()} created and linked to {ids}[/green]")
    finally:
        db.close()


@app.command("add-event-place", no_args_is_help=True)
def add_event_place(
    event_id: str = typer.Argument(..., help="Event ID"),
    place_query: str = typer.Argument(..., help="Place ID or name to search for"),
):
    """Set the place on an existing event."""
    db = _open_db(write=True)
    try:
        event = db.get_event_from_gramps_id(event_id)
        if not event:
            console.print(f"[red]Event {event_id!r} not found[/red]")
            raise typer.Exit(1)

        place = db.get_place_from_gramps_id(place_query)
        if not place:
            all_places = [db.get_place_from_handle(h) for h in db.get_place_handles()]
            matches = [p for p in all_places if place_query.lower() in p.get_name().get_value().lower()]
            if not matches:
                console.print(f"[red]No place found matching {place_query!r}[/red]")
                raise typer.Exit(1)
            if len(matches) > 1:
                console.print(f"[yellow]Ambiguous — {len(matches)} places match {place_query!r}:[/yellow]")
                console.print(_place_table(sorted(matches, key=lambda p: p.get_name().get_value().lower())))
                raise typer.Exit(1)
            place = matches[0]

        current_handle = event.get_place_handle()
        if current_handle:
            current = db.get_place_from_handle(current_handle)
            console.print(f"[yellow]Replacing existing place: {current.get_gramps_id()} — {current.get_name().get_value()}[/yellow]")

        with DbTxn('Set event place', db) as trans:
            event.set_place_handle(place.get_handle())
            db.commit_event(event, trans)

        console.print(f"[green]Place set:[/green] {event_id} → {place.get_name().get_value()} ({place.get_gramps_id()})")
    finally:
        db.close()


@app.command("person-events", no_args_is_help=True)
def person_events(
    person_id: str = typer.Argument(..., help="Person ID"),
):
    """List all events for a person."""
    db = _open_db()
    try:
        person = db.get_person_from_gramps_id(person_id)
        if not person:
            console.print(f"[red]Person {person_id!r} not found[/red]")
            raise typer.Exit(1)

        console.print(f"[bold]{person_id}: {_person_name(person)}[/bold]\n")

        erefs = person.get_event_ref_list()
        if not erefs:
            console.print("No events.")
            return

        table = Table()
        table.add_column("ID")
        table.add_column("Type")
        table.add_column("Date")
        table.add_column("Description")
        table.add_column("Place")

        for eref in erefs:
            event = db.get_event_from_handle(eref.get_reference_handle())
            year = str(event.get_date_object().get_year()) if event.get_date_object().get_year() else ""
            place_handle = event.get_place_handle()
            place_name = db.get_place_from_handle(place_handle).get_name().get_value() if place_handle else ""
            table.add_row(
                event.get_gramps_id(),
                str(event.get_type()),
                year,
                event.get_description() or "",
                place_name,
            )

        console.print(table)
    finally:
        db.close()


@app.command("list-parents", no_args_is_help=True)
def list_parents(
    person_id: str = typer.Argument(..., help="Person ID"),
):
    """List a person's parents."""
    db = _open_db()
    try:
        person = db.get_person_from_gramps_id(person_id)
        if not person:
            console.print(f"[red]Person {person_id!r} not found[/red]")
            raise typer.Exit(1)

        console.print(f"[bold]{person_id}: {_person_name(person)}[/bold]")

        handles = person.get_parent_family_handle_list()
        if not handles:
            console.print("No parents.")
            return

        family = db.get_family_from_handle(handles[0])
        parents = []
        for handle in (family.get_father_handle(), family.get_mother_handle()):
            if handle:
                p = db.get_person_from_handle(handle)
                parents.append((p, _person_name(p)))

        console.print(_people_table(parents))
    finally:
        db.close()


@app.command("list-children", no_args_is_help=True)
def list_children(
    person_id: str = typer.Argument(..., help="Person ID"),
):
    """List a person's children."""
    db = _open_db()
    try:
        person = db.get_person_from_gramps_id(person_id)
        if not person:
            console.print(f"[red]Person {person_id!r} not found[/red]")
            raise typer.Exit(1)

        children = []
        for fam_handle in person.get_family_handle_list():
            family = db.get_family_from_handle(fam_handle)
            for cref in family.get_child_ref_list():
                child = db.get_person_from_handle(cref.get_reference_handle())
                birth = get_event(db, child, EventType.BIRTH)
                birth_year = get_year(birth)
                children.append((child, _person_name(child), birth_year))

        children.sort(key=lambda c: c[2] or 9999)

        console.print(f"[bold]{person_id}: {_person_name(person)}[/bold]")
        if not children:
            console.print("No children.")
            return

        table = Table()
        table.add_column("ID")
        table.add_column("Name")
        table.add_column("Born")
        for child, name, birth_year in children:
            table.add_row(child.get_gramps_id(), name, str(birth_year) if birth_year else "")
        console.print(table)
    finally:
        db.close()


@app.command("list-event-people", no_args_is_help=True)
def list_event_people(
    event_id: str = typer.Argument(..., help="Event ID"),
):
    """List people attached to an event."""
    db = _open_db()
    try:
        event = db.get_event_from_gramps_id(event_id)
        if not event:
            console.print(f"[red]Event {event_id!r} not found[/red]")
            raise typer.Exit(1)

        console.print(f"[bold]{event_id}: {_event_label(event)}[/bold]\n")

        event_year = event.get_date_object().get_year() or None
        people = []
        for handle in db.get_person_handles():
            person = db.get_person_from_handle(handle)
            for eref in person.get_event_ref_list():
                if eref.get_reference_handle() == event.get_handle():
                    birth = get_event(db, person, EventType.BIRTH)
                    birth_year = get_year(birth)
                    people.append((person, _person_name(person), birth_year))
                    break

        if not people:
            console.print("No people linked to this event.")
            return

        people.sort(key=lambda p: p[2] or 9999)
        table = Table()
        table.add_column("ID")
        table.add_column("Name")
        table.add_column("Born")
        table.add_column("Age")
        for person, name, birth_year in people:
            age = str(event_year - birth_year) if event_year and birth_year else ""
            table.add_row(person.get_gramps_id(), name, str(birth_year) if birth_year else "", age)
        console.print(table)
    finally:
        db.close()


@app.command("rm-event-person", no_args_is_help=True)
def rm_event_person(
    event_id: str = typer.Argument(..., help="Event ID"),
    person_id: str = typer.Argument(..., help="Person ID to remove"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Remove a person from an event."""
    db = _open_db(write=True)
    try:
        event = db.get_event_from_gramps_id(event_id)
        if not event:
            console.print(f"[red]Event {event_id!r} not found[/red]")
            raise typer.Exit(1)

        person = db.get_person_from_gramps_id(person_id)
        if not person:
            console.print(f"[red]Person {person_id!r} not found[/red]")
            raise typer.Exit(1)

        erefs = person.get_event_ref_list()
        new_erefs = [e for e in erefs if e.get_reference_handle() != event.get_handle()]
        if len(new_erefs) == len(erefs):
            console.print(f"[yellow]{person_id} is not linked to {event_id}[/yellow]")
            raise typer.Exit(1)

        console.print(f"[bold]Event:[/bold] {event_id} — {_event_label(event)}")
        console.print(f"[bold]Remove:[/bold] {person_id} — {_person_name(person)}")
        _confirm(yes)

        with DbTxn('Remove person from event', db) as trans:
            person.set_event_ref_list(new_erefs)
            db.commit_person(person, trans)

        console.print(f"[green]Removed {person_id} from {event_id}[/green]")
    finally:
        db.close()


@app.command("add-ancestry-link", no_args_is_help=True)
def add_ancestry_link(
    person_id: str = typer.Argument(..., help="Person ID"),
    url: str = typer.Argument(..., help="Full Ancestry URL"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Add an Ancestry URL to a person."""
    db = _open_db(write=True)
    try:
        person = db.get_person_from_gramps_id(person_id)
        if not person:
            console.print(f"[red]Person {person_id!r} not found[/red]")
            raise typer.Exit(1)

        existing = [u for u in person.get_url_list() if str(u.get_type()) == 'Ancestry']
        if existing:
            console.print(f"[yellow]Already has Ancestry link: {existing[0].get_path()}[/yellow]")

        console.print(f"[bold]{person_id}:[/bold] {_person_name(person)}")
        console.print(f"[bold]URL:[/bold]       {url}")

        _confirm(yes)

        url_obj = Url()
        url_type = UrlType()
        url_type.set((UrlType.CUSTOM, 'Ancestry'))
        url_obj.set_type(url_type)
        url_obj.set_path(url)

        with DbTxn('Add Ancestry link', db) as trans:
            person.add_url(url_obj)
            db.commit_person(person, trans)

        console.print(f"[green]Ancestry link added to {person_id}[/green]")
    finally:
        db.close()


@app.command("add-grave-link", no_args_is_help=True)
def add_grave_link(
    person_id: str = typer.Argument(..., help="Person ID"),
    url: str = typer.Argument(..., help="Full Find A Grave URL"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Add a Find A Grave URL to a person."""
    db = _open_db(write=True)
    try:
        person = db.get_person_from_gramps_id(person_id)
        if not person:
            console.print(f"[red]Person {person_id!r} not found[/red]")
            raise typer.Exit(1)

        existing = [u for u in person.get_url_list() if str(u.get_type()) == 'Find A Grave']
        if existing:
            console.print(f"[yellow]Already has Find A Grave link: {existing[0].get_path()}[/yellow]")

        console.print(f"[bold]{person_id}:[/bold] {_person_name(person)}")
        console.print(f"[bold]URL:[/bold]       {url}")

        _confirm(yes)

        url_obj = Url()
        url_type = UrlType()
        url_type.set((UrlType.CUSTOM, 'Find A Grave'))
        url_obj.set_type(url_type)
        url_obj.set_path(url)

        with DbTxn('Add Find A Grave link', db) as trans:
            person.add_url(url_obj)
            db.commit_person(person, trans)

        console.print(f"[green]Find A Grave link added to {person_id}[/green]")
    finally:
        db.close()


@app.command("add-child", no_args_is_help=True)
def add_child(
    father_id: str = typer.Argument(..., help="Father's person ID"),
    mother_id: str = typer.Argument(..., help="Mother's person ID"),
    child_name: str = typer.Argument(..., help="Child's given name (surname taken from father)"),
    dob: Optional[str] = typer.Option(None, "--dob", help="Date of birth (e.g. '1 Jan 1950' or 1950)"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Add a child to a family (surname from father), creating the family if it doesn't exist."""
    parsed_dob = None
    if dob:
        parsed_dob = _parse_date(dob)
        if parsed_dob is None:
            console.print(f"[red]Could not parse date {dob!r}[/red]")
            raise typer.Exit(1)

    db = _open_db(write=True)
    try:
        father = db.get_person_from_gramps_id(father_id)
        if not father:
            console.print(f"[red]Father {father_id!r} not found[/red]")
            raise typer.Exit(1)
        mother = db.get_person_from_gramps_id(mother_id)
        if not mother:
            console.print(f"[red]Mother {mother_id!r} not found[/red]")
            raise typer.Exit(1)

        given = child_name
        surname = father.get_primary_name().get_surname()

        existing_family = None
        for fam_handle in father.get_family_handle_list():
            fam = db.get_family_from_handle(fam_handle)
            if fam.get_mother_handle() == mother.get_handle():
                existing_family = fam
                break

        summary = Table(show_header=False)
        summary.add_column("Field", style="bold")
        summary.add_column("Value")
        summary.add_row("Father", f"{father_id} — {_person_name(father)}")
        summary.add_row("Mother", f"{mother_id} — {_person_name(mother)}")
        summary.add_row("Child", f"{given} {surname}")
        if parsed_dob:
            summary.add_row("Date of birth", dob)
        summary.add_row("Family", f"{existing_family.get_gramps_id()} (existing)" if existing_family else "new family will be created")
        console.print(summary)

        _confirm(yes)

        with DbTxn('Add child', db) as trans:
            child = Person()
            pname = Name()
            pname.set_first_name(given)
            surn = Surname()
            surn.set_surname(surname)
            pname.set_surname_list([surn])
            pname.set_type(NameType(NameType.BIRTH))
            child.set_primary_name(pname)
            db.add_person(child, trans)

            if parsed_dob:
                birth = Event()
                birth.set_type(EventType(EventType.BIRTH))
                y, m, d = parsed_dob
                dt = Date()
                dt.set_yr_mon_day(y, m, d)
                birth.set_date_object(dt)
                db.add_event(birth, trans)
                eref = EventRef()
                eref.set_reference_handle(birth.get_handle())
                eref.set_role(EventRoleType(EventRoleType.PRIMARY))
                child.add_event_ref(eref)

            if existing_family:
                family = existing_family
            else:
                family = Family()
                family.set_father_handle(father.get_handle())
                family.set_mother_handle(mother.get_handle())
                db.add_family(family, trans)
                father.add_family_handle(family.get_handle())
                db.commit_person(father, trans)
                mother.add_family_handle(family.get_handle())
                db.commit_person(mother, trans)

            cref = ChildRef()
            cref.set_reference_handle(child.get_handle())
            family.add_child_ref(cref)
            db.commit_family(family, trans)

            child.add_parent_family_handle(family.get_handle())
            db.commit_person(child, trans)

        console.print(f"\n[green]Child {child.get_gramps_id()} ({given} {surname}) added to family {family.get_gramps_id()}[/green]")
        if parsed_dob:
            console.print(f"[green]Birth event {birth.get_gramps_id()} created[/green]")
    finally:
        db.close()
