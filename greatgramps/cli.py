from __future__ import annotations

import json
import mimetypes
import urllib.parse
import urllib.request
from pathlib import Path
import re
from typing import List, Optional

import yaml

import typer
from rich.console import Console
from rich.table import Table
from typer.main import TyperGroup

from gramps.gen.const import HOME_DIR as GRAMPS_HOME_DIR
from gramps.gen.db import DBMODE_R, DBMODE_W, DbTxn
from gramps.gen.lib import (
    ChildRef, Date, Event, EventRef, EventRoleType, EventType,
    Family, Media, MediaRef, Name, NameType, Person, Place, PlaceName,
    PlaceRef, PlaceType, Surname, Url, UrlType,
)
from gramps.plugins.db.dbapi.sqlite import SQLite

from .gramps_data import CENSUS_DATES, GRAVE_URL_TYPE, format_date, get_event, get_year, ancestors_with_distances, get_children, collect_all_descendants
from .paper_sizes import PAPER_SIZE_NAMES
from .settings import get_config


class _SortedGroup(TyperGroup):
    def list_commands(self, ctx):
        return sorted(self.commands)


app = typer.Typer(help="Greatgramps — manage your Gramps family tree database.", no_args_is_help=True, cls=_SortedGroup)
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


def _require_extra(extra: str):
    console.print(f"[red]This command requires the '{extra}' extra. Install with: pip install greatgramps\\[{extra}][/red]")
    raise typer.Exit(1)


def _to_media_path(gallery: Path) -> str:
    """Return gallery path relative to the DB dir (matching how paths are stored)."""
    db_path = get_config().validated_db_path
    try:
        return str(gallery.resolve().relative_to(db_path))
    except ValueError:
        return str(gallery.resolve())


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
    exact = [p for p in matches if p.get_name().get_value().lower() == query.lower()]
    if len(exact) == 1:
        return exact[0]
    console.print(f"[yellow]{len(matches)} places match {query!r} — be more specific:[/yellow]")
    console.print(_place_table(matches))
    raise typer.Exit(1)


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.rsplit(' ', 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0], '')


def _build_person(db, trans, full_name: str) -> Person:
    given, surname = _split_name(full_name)
    person = Person()
    pname = Name()
    pname.set_first_name(given)
    if surname:
        surn = Surname()
        surn.set_surname(surname)
        pname.set_surname_list([surn])
    pname.set_type(NameType(NameType.BIRTH))
    person.set_primary_name(pname)
    db.add_person(person, trans)
    return person


def _attach_event(db, trans, person: Person, event_type: EventType, parsed_date=None, place=None) -> Event:
    event = Event()
    event.set_type(event_type)
    if parsed_date:
        y, m, d = parsed_date
        dt = Date()
        dt.set_yr_mon_day(y, m, d)
        event.set_date_object(dt)
    if place:
        event.set_place_handle(place.get_handle())
    db.add_event(event, trans)
    eref = EventRef()
    eref.set_reference_handle(event.get_handle())
    eref.set_role(EventRoleType(EventRoleType.PRIMARY))
    person.add_event_ref(eref)
    return event


def _family_handles(parent1, parent2=None) -> tuple:
    """Return (father_handle, mother_handle) by gender, falling back to positional."""
    h1, g1 = parent1.get_handle(), parent1.get_gender()
    h2 = parent2.get_handle() if parent2 else None
    g2 = parent2.get_gender() if parent2 else None
    if parent2 is None:
        return (None, h1) if g1 == Person.FEMALE else (h1, None)
    if g1 == Person.MALE and g2 != Person.MALE:
        return h1, h2
    if g2 == Person.MALE and g1 != Person.MALE:
        return h2, h1
    if g1 == Person.FEMALE and g2 != Person.FEMALE:
        return h2, h1
    if g2 == Person.FEMALE and g1 != Person.FEMALE:
        return h1, h2
    return h1, h2  # same gender or both unknown — positional


def _get_or_create_family(db, trans, parent1, parent2=None) -> tuple[Family, bool]:
    """Return (family, created). Searches parent1's families for a matching pair first."""
    father_h, mother_h = _family_handles(parent1, parent2)
    for fam_handle in parent1.get_family_handle_list():
        fam = db.get_family_from_handle(fam_handle)
        if (fam.get_father_handle() or None) == father_h and (fam.get_mother_handle() or None) == mother_h:
            return fam, False
    family = Family()
    family.set_father_handle(father_h)
    family.set_mother_handle(mother_h)
    db.add_family(family, trans)
    parent1.add_family_handle(family.get_handle())
    db.commit_person(parent1, trans)
    if parent2:
        parent2.add_family_handle(family.get_handle())
        db.commit_person(parent2, trans)
    return family, True


@app.command("add-ancestry-link", no_args_is_help=True)
def add_ancestry_link(
    person_id: str = typer.Argument(..., help="Person ID"),
    url: str = typer.Argument(..., help="Ancestry person ID or full URL"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Add an Ancestry URL to a person."""
    if url.isdigit():
        config = get_config()
        if not config.ancestry_tree_id:
            console.print("[red]ancestry_tree_id not set in config[/red]")
            raise typer.Exit(1)
        url = f"https://www.ancestry.co.uk/family-tree/person/tree/{config.ancestry_tree_id}/person/{url}/"
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


@app.command("add-census", no_args_is_help=True)
def add_census(
    person_ids: List[str] = typer.Argument(..., help="Person IDs to link to this event"),
    gallery: Optional[Path] = typer.Option(None, "--gallery", help="Path to census image file"),
    year_opt: Optional[int] = typer.Option(None, "--year", help="Census year (e.g. 1911); uses the full census date"),
    name: Optional[str] = typer.Option(None, "--name", help="Head of household for description (e.g. 'John Smith')"),
    place_query: Optional[str] = typer.Option(None, "--place", help="Place name or ID"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Add a census event and link people to it."""
    year_from_stem = None
    description_from_stem = None

    if gallery:
        gallery = gallery.resolve()
        if not gallery.exists():
            console.print(f"[red]File not found: {gallery}[/red]")
            raise typer.Exit(1)
        parts = gallery.stem.split('_')
        if not parts[0].isdigit():
            console.print("[red]Filename must start with a year (e.g. 1921_jarvis_nuttall.jpg)[/red]")
            raise typer.Exit(1)
        year_from_stem = int(parts[0])
        description_from_stem = _stem_to_description(gallery.stem)

    year = year_opt or year_from_stem

    if year is None:
        console.print("[red]Provide a census image (--gallery) or a year (--year)[/red]")
        raise typer.Exit(1)

    if year_opt and year_opt not in CENSUS_DATES:
        console.print(f"[red]{year_opt} is not a known census year. Known: {', '.join(str(y) for y in sorted(CENSUS_DATES))}[/red]")
        raise typer.Exit(1)

    if not gallery and not name:
        console.print("[red]Provide --gallery or --name (for the event description)[/red]")
        raise typer.Exit(1)

    record_type = 'register' if year == 1939 else 'census'
    description = f"{year} {record_type} - {name} household" if name else description_from_stem

    if year_opt:
        day, month, _ = CENSUS_DATES[year_opt]
    else:
        day, month = 0, 0

    db = _open_db(write=True)
    try:
        people = []
        for pid in person_ids:
            person = db.get_person_from_gramps_id(pid)
            if not person:
                console.print(f"[red]Person {pid!r} not found[/red]")
                raise typer.Exit(1)
            birth_year = get_year(get_event(db, person, EventType.BIRTH))
            age = str(year - birth_year) if birth_year else ""
            people.append((person, _person_name(person), birth_year, age))

        place = _resolve_place(db, place_query) if place_query else None

        summary = Table(show_header=False)
        summary.add_column("Field", style="bold")
        summary.add_column("Value")
        if gallery:
            summary.add_row("File", str(gallery))
        summary.add_row("Year", str(year))
        summary.add_row("Description", description)
        if place:
            summary.add_row("Place", f"{place.get_name().get_value()} ({place.get_gramps_id()})")
        console.print(summary)

        people_table = Table()
        people_table.add_column("ID")
        people_table.add_column("Name")
        people_table.add_column("Born", justify="right")
        people_table.add_column("Age", justify="right")
        for person, name, birth_year, age in people:
            people_table.add_row(person.get_gramps_id(), name, str(birth_year) if birth_year else "", age)
        console.print("\n[bold]People:[/bold]")
        console.print(people_table)

        _confirm(yes)

        with DbTxn('Add census event', db) as trans:
            event = Event()
            event.set_type(EventType(EventType.CENSUS))
            date = Date()
            date.set_yr_mon_day(year, month, day)
            event.set_date_object(date)
            event.set_description(description)

            if place:
                event.set_place_handle(place.get_handle())

            if gallery:
                path_str = _to_media_path(gallery)
                existing_media_paths = {
                    db.get_media_from_handle(h).get_path(): h
                    for h in db.get_media_handles()
                }
                if path_str in existing_media_paths:
                    media_handle = existing_media_paths[path_str]
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

            for person, *_ in people:
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
        if gallery:
            result.add_row("Image", gallery.name)
        console.print(f"\n[green]Event created:[/green]")
        console.print(result)
    finally:
        db.close()


@app.command("add-child", no_args_is_help=True)
def add_child(
    child_id: str = typer.Argument(..., help="Child's person ID"),
    parent1_id: str = typer.Argument(..., help="First parent's person ID"),
    parent2_id: Optional[str] = typer.Argument(None, help="Second parent's person ID"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Link an existing person as a child to one or two parents."""
    db = _open_db(write=True)
    try:
        child = db.get_person_from_gramps_id(child_id)
        if not child:
            console.print(f"[red]Child {child_id!r} not found[/red]")
            raise typer.Exit(1)
        parent1 = db.get_person_from_gramps_id(parent1_id)
        if not parent1:
            console.print(f"[red]Parent {parent1_id!r} not found[/red]")
            raise typer.Exit(1)
        parent2 = None
        if parent2_id:
            parent2 = db.get_person_from_gramps_id(parent2_id)
            if not parent2:
                console.print(f"[red]Parent {parent2_id!r} not found[/red]")
                raise typer.Exit(1)

        father_h, mother_h = _family_handles(parent1, parent2)
        existing_fam_id = None
        for fam_handle in parent1.get_family_handle_list():
            fam = db.get_family_from_handle(fam_handle)
            if (fam.get_father_handle() or None) == father_h and (fam.get_mother_handle() or None) == mother_h:
                existing_fam_id = fam.get_gramps_id()
                break

        summary = Table(show_header=False)
        summary.add_column("Field", style="bold")
        summary.add_column("Value")
        summary.add_row("Child", f"{child_id} — {_person_name(child)}")
        summary.add_row("Parent 1", f"{parent1_id} — {_person_name(parent1)}")
        if parent2:
            summary.add_row("Parent 2", f"{parent2_id} — {_person_name(parent2)}")
        summary.add_row("Family", f"{existing_fam_id} (existing)" if existing_fam_id else "new family will be created")
        console.print(summary)

        _confirm(yes)

        with DbTxn('Add child', db) as trans:
            family, _ = _get_or_create_family(db, trans, parent1, parent2)
            cref = ChildRef()
            cref.set_reference_handle(child.get_handle())
            family.add_child_ref(cref)
            db.commit_family(family, trans)
            child.add_parent_family_handle(family.get_handle())
            db.commit_person(child, trans)

        console.print(f"[green]{child_id} ({_person_name(child)}) added to family {family.get_gramps_id()}[/green]")
    finally:
        db.close()


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
                path_str = _to_media_path(gallery)
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
            age = str(max(0, event_year - birth_year - 1)) if event_year and birth_year else ""
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

        _age_sort = lambda rows: sorted(rows, key=lambda r: int(r[2]) if r[2] else 9999)

        if skipped:
            console.print("\n[yellow]Already linked (skipping):[/yellow]")
            console.print(_people_age_table(_age_sort(skipped)))

        if not to_add:
            console.print("No new people to add.")
            return

        console.print("\n[bold]To add:[/bold]")
        console.print(_people_age_table(_age_sort(to_add)))

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
            age = str(max(0, event_year - birth_year - 1)) if event_year and birth_year else ""
            table.add_row(p.get_gramps_id(), name, str(birth_year) if birth_year else "", age)
        console.print(table)
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


@app.command("add-family", no_args_is_help=True)
def add_family(
    parent1_id: str = typer.Argument(..., help="First parent's person ID"),
    parent2_id: Optional[str] = typer.Argument(None, help="Second parent's person ID"),
    child_ids: Optional[List[str]] = typer.Option(None, "--child", help="Child's person ID (can be repeated)"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Create a family for one or two parents, optionally adding children."""
    db = _open_db(write=True)
    try:
        parent1 = db.get_person_from_gramps_id(parent1_id)
        if not parent1:
            console.print(f"[red]Person {parent1_id!r} not found[/red]")
            raise typer.Exit(1)
        parent2 = None
        if parent2_id:
            parent2 = db.get_person_from_gramps_id(parent2_id)
            if not parent2:
                console.print(f"[red]Person {parent2_id!r} not found[/red]")
                raise typer.Exit(1)

        children = []
        for cid in (child_ids or []):
            child = db.get_person_from_gramps_id(cid)
            if not child:
                console.print(f"[red]Person {cid!r} not found[/red]")
                raise typer.Exit(1)
            children.append(child)

        father_h, mother_h = _family_handles(parent1, parent2)
        existing_fam = None
        for fam_handle in parent1.get_family_handle_list():
            fam = db.get_family_from_handle(fam_handle)
            if (fam.get_father_handle() or None) == father_h and (fam.get_mother_handle() or None) == mother_h:
                existing_fam = fam
                break

        if existing_fam and not children:
            console.print(f"[yellow]Family {existing_fam.get_gramps_id()} already exists for these parents.[/yellow]")
            raise typer.Exit(0)

        if existing_fam and children:
            existing_child_handles = {cr.get_reference_handle() for cr in existing_fam.get_child_ref_list()}
            skipped = [c for c in children if c.get_handle() in existing_child_handles]
            children = [c for c in children if c.get_handle() not in existing_child_handles]
            for c in skipped:
                console.print(f"[yellow]{c.get_gramps_id()} ({_person_name(c)}) already in {existing_fam.get_gramps_id()} — skipped[/yellow]")
            if not children:
                raise typer.Exit(0)

        summary = Table(show_header=False)
        summary.add_column("Field", style="bold")
        summary.add_column("Value")
        summary.add_row("Parent 1", f"{parent1_id} — {_person_name(parent1)}")
        if parent2:
            summary.add_row("Parent 2", f"{parent2_id} — {_person_name(parent2)}")
        for child in children:
            summary.add_row("Child", f"{child.get_gramps_id()} — {_person_name(child)}")
        summary.add_row("Family", f"{existing_fam.get_gramps_id()} (existing)" if existing_fam else "new family will be created")
        console.print(summary)

        _confirm(yes)

        with DbTxn('Add family', db) as trans:
            family, created = _get_or_create_family(db, trans, parent1, parent2)
            for child in children:
                cref = ChildRef()
                cref.set_reference_handle(child.get_handle())
                family.add_child_ref(cref)
                child.add_parent_family_handle(family.get_handle())
                db.commit_person(child, trans)
            if children:
                db.commit_family(family, trans)

        action = "created" if created else "updated"
        console.print(f"[green]Family {family.get_gramps_id()} {action}[/green]")
    finally:
        db.close()


@app.command("add-grave-link", no_args_is_help=True)
def add_grave_link(
    person_id: str = typer.Argument(..., help="Person ID"),
    memorial: str = typer.Argument(..., help="Find A Grave memorial ID or full URL"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Add a Find A Grave URL to a person."""
    if memorial.isdigit():
        url = f"https://www.findagrave.com/memorial/{memorial}"
    else:
        url = memorial

    db = _open_db(write=True)
    try:
        person = db.get_person_from_gramps_id(person_id)
        if not person:
            console.print(f"[red]Person {person_id!r} not found[/red]")
            raise typer.Exit(1)

        existing = [u for u in person.get_url_list() if str(u.get_type()).lower() == GRAVE_URL_TYPE.lower()]
        if existing:
            console.print(f"[yellow]Already has Find A Grave link: {existing[0].get_path()}[/yellow]")

        console.print(f"[bold]{person_id}:[/bold] {_person_name(person)}")
        console.print(f"[bold]URL:[/bold]       {url}")

        _confirm(yes)

        url_obj = Url()
        url_type = UrlType()
        url_type.set((UrlType.CUSTOM, GRAVE_URL_TYPE))
        url_obj.set_type(url_type)
        url_obj.set_path(url)

        with DbTxn('Add Find A Grave link', db) as trans:
            person.add_url(url_obj)
            db.commit_person(person, trans)

        console.print(f"[green]Find A Grave link added to {person_id}[/green]")
    finally:
        db.close()


@app.command("add-parents", no_args_is_help=True)
def add_parents(
    child_id: str = typer.Argument(..., help="Child's person ID"),
    parent1_id: str = typer.Argument(..., help="First parent's person ID"),
    parent2_id: Optional[str] = typer.Argument(None, help="Second parent's person ID"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Link a child to one or two parents, filling a missing parent slot in an existing family if possible."""
    db = _open_db(write=True)
    try:
        child = db.get_person_from_gramps_id(child_id)
        if not child:
            console.print(f"[red]Child {child_id!r} not found[/red]")
            raise typer.Exit(1)
        parent1 = db.get_person_from_gramps_id(parent1_id)
        if not parent1:
            console.print(f"[red]Parent {parent1_id!r} not found[/red]")
            raise typer.Exit(1)
        parent2 = None
        if parent2_id:
            parent2 = db.get_person_from_gramps_id(parent2_id)
            if not parent2:
                console.print(f"[red]Parent {parent2_id!r} not found[/red]")
                raise typer.Exit(1)

        father_h, mother_h = _family_handles(parent1, parent2)
        parents_by_handle = {parent1.get_handle(): parent1}
        if parent2:
            parents_by_handle[parent2.get_handle()] = parent2

        # Scan child's existing parent families for a match or a partial slot to fill
        update_fam = None   # existing family to update
        fill_father = None  # handle to write into the father slot
        fill_mother = None  # handle to write into the mother slot

        for fam_handle in child.get_parent_family_handle_list():
            fam = db.get_family_from_handle(fam_handle)
            fam_father = fam.get_father_handle() or None
            fam_mother = fam.get_mother_handle() or None

            if fam_father == father_h and fam_mother == mother_h:
                console.print(f"[yellow]{child_id} is already a child of these parents in {fam.get_gramps_id()}[/yellow]")
                raise typer.Exit(0)

            if parent2 is None:
                # Single parent: fill an empty slot in a family that already has the other parent
                if father_h and fam_father is None and fam_mother is not None:
                    update_fam, fill_father = fam, father_h
                    break
                if mother_h and fam_mother is None and fam_father is not None:
                    update_fam, fill_mother = fam, mother_h
                    break
            else:
                # Two parents: one slot already matches, fill the empty one
                if fam_father == father_h and fam_mother is None:
                    update_fam, fill_mother = fam, mother_h
                    break
                if fam_mother == mother_h and fam_father is None:
                    update_fam, fill_father = fam, father_h
                    break

        summary = Table(show_header=False)
        summary.add_column("Field", style="bold")
        summary.add_column("Value")
        summary.add_row("Child", f"{child_id} — {_person_name(child)}")
        summary.add_row("Parent 1", f"{parent1_id} — {_person_name(parent1)}")
        if parent2:
            summary.add_row("Parent 2", f"{parent2_id} — {_person_name(parent2)}")
        if update_fam:
            summary.add_row("Family", f"{update_fam.get_gramps_id()} (filling empty slot in existing family)")
        else:
            summary.add_row("Family", "new family will be created")
        console.print(summary)

        _confirm(yes)

        if update_fam:
            with DbTxn('Add parent to family', db) as trans:
                if fill_father:
                    update_fam.set_father_handle(fill_father)
                    parents_by_handle[fill_father].add_family_handle(update_fam.get_handle())
                    db.commit_person(parents_by_handle[fill_father], trans)
                if fill_mother:
                    update_fam.set_mother_handle(fill_mother)
                    parents_by_handle[fill_mother].add_family_handle(update_fam.get_handle())
                    db.commit_person(parents_by_handle[fill_mother], trans)
                db.commit_family(update_fam, trans)
            console.print(f"[green]Family {update_fam.get_gramps_id()} updated[/green]")
        else:
            with DbTxn('Add parents', db) as trans:
                family, created = _get_or_create_family(db, trans, parent1, parent2)
                cref = ChildRef()
                cref.set_reference_handle(child.get_handle())
                family.add_child_ref(cref)
                db.commit_family(family, trans)
                child.add_parent_family_handle(family.get_handle())
                db.commit_person(child, trans)
            action = "created" if created else "existing"
            console.print(f"[green]{child_id} ({_person_name(child)}) added to family {family.get_gramps_id()} ({action})[/green]")
    finally:
        db.close()


@app.command("add-person", no_args_is_help=True)
def add_person(
    name: str = typer.Argument(..., help="Full name, e.g. 'John Smith'"),
    birth: Optional[str] = typer.Option(None, "--birth", help="Birth date, e.g. '1 Jan 1950' or 1950"),
    death: Optional[str] = typer.Option(None, "--death", help="Death date"),
    burial: Optional[str] = typer.Option(None, "--burial", help="Burial date"),
    birth_place: Optional[str] = typer.Option(None, "--birth-place", help="Birth place ID or name"),
    death_place: Optional[str] = typer.Option(None, "--death-place", help="Death place ID or name"),
    burial_place: Optional[str] = typer.Option(None, "--burial-place", help="Burial place ID or name"),
    gender: Optional[str] = typer.Option(None, "--gender", help="Gender: m/male or f/female"),
    father_id: Optional[str] = typer.Option(None, "--father", help="Father's person ID"),
    mother_id: Optional[str] = typer.Option(None, "--mother", help="Mother's person ID"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Add a new person to the database."""
    parsed_birth = _parse_date(birth) if birth else None
    if birth and parsed_birth is None:
        console.print(f"[red]Could not parse birth date {birth!r}[/red]")
        raise typer.Exit(1)
    parsed_death = _parse_date(death) if death else None
    if death and parsed_death is None:
        console.print(f"[red]Could not parse death date {death!r}[/red]")
        raise typer.Exit(1)
    parsed_burial = _parse_date(burial) if burial else None
    if burial and parsed_burial is None:
        console.print(f"[red]Could not parse burial date {burial!r}[/red]")
        raise typer.Exit(1)

    explicit_gender = None
    if gender:
        g = gender.strip().lower()
        if g in ('m', 'male'):
            explicit_gender = Person.MALE
        elif g in ('f', 'female'):
            explicit_gender = Person.FEMALE
        elif g in ('u', 'unknown'):
            explicit_gender = Person.UNKNOWN
        else:
            console.print(f"[red]Unknown gender {gender!r}. Use m/male, f/female, or u/unknown[/red]")
            raise typer.Exit(1)

    db = _open_db(write=True)
    try:
        father = None
        if father_id:
            father = db.get_person_from_gramps_id(father_id)
            if not father:
                console.print(f"[red]Father {father_id!r} not found[/red]")
                raise typer.Exit(1)
        mother = None
        if mother_id:
            mother = db.get_person_from_gramps_id(mother_id)
            if not mother:
                console.print(f"[red]Mother {mother_id!r} not found[/red]")
                raise typer.Exit(1)

        place_birth = _resolve_place(db, birth_place) if birth_place else None
        place_death = _resolve_place(db, death_place) if death_place else None
        place_burial = _resolve_place(db, burial_place) if burial_place else None

        # Determine gender: explicit → inferred → prompt
        gender_source = None
        if explicit_gender is not None:
            resolved_gender = explicit_gender
            gender_source = 'specified'
        else:
            given, _ = _split_name(name)
            resolved_gender = db.genderStats.guess_gender(given)
            if resolved_gender != Person.UNKNOWN:
                gender_source = 'inferred'

        if resolved_gender == Person.UNKNOWN and gender_source is None:
            while True:
                try:
                    g = input("Gender not inferred from name. Specify [m/f/u]: ").strip().lower()
                except KeyboardInterrupt:
                    console.print("\nCancelled.")
                    raise typer.Exit(0)
                if g in ('m', 'male'):
                    resolved_gender = Person.MALE
                    break
                elif g in ('f', 'female'):
                    resolved_gender = Person.FEMALE
                    break
                elif g in ('u', 'unknown', ''):
                    resolved_gender = Person.UNKNOWN
                    break
                console.print("[red]Enter m (male), f (female), or u (unknown)[/red]")

        summary = Table(show_header=False)
        summary.add_column("Field", style="bold")
        summary.add_column("Value")
        summary.add_row("Name", name)
        if resolved_gender == Person.MALE:
            suffix = " (inferred from name)" if gender_source == 'inferred' else ""
            summary.add_row("Gender", f"Male{suffix}")
        elif resolved_gender == Person.FEMALE:
            suffix = " (inferred from name)" if gender_source == 'inferred' else ""
            summary.add_row("Gender", f"Female{suffix}")
        if birth or place_birth:
            val = " — ".join(filter(None, [birth, place_birth and place_birth.get_name().get_value()]))
            summary.add_row("Birth", val)
        if death or place_death:
            val = " — ".join(filter(None, [death, place_death and place_death.get_name().get_value()]))
            summary.add_row("Death", val)
        if burial or place_burial:
            val = " — ".join(filter(None, [burial, place_burial and place_burial.get_name().get_value()]))
            summary.add_row("Burial", val)
        if father:
            summary.add_row("Father", f"{father_id} — {_person_name(father)}")
        if mother:
            summary.add_row("Mother", f"{mother_id} — {_person_name(mother)}")
        console.print(summary)

        _confirm(yes)

        with DbTxn('Add person', db) as trans:
            person = _build_person(db, trans, name)
            if resolved_gender != Person.UNKNOWN:
                person.set_gender(resolved_gender)
            birth_event = _attach_event(db, trans, person, EventType(EventType.BIRTH), parsed_birth, place_birth) if (parsed_birth or place_birth) else None
            death_event = _attach_event(db, trans, person, EventType(EventType.DEATH), parsed_death, place_death) if (parsed_death or place_death) else None
            burial_event = _attach_event(db, trans, person, EventType(EventType.BURIAL), parsed_burial, place_burial) if (parsed_burial or place_burial) else None
            db.commit_person(person, trans)
            if father or mother:
                parent1 = father or mother
                parent2 = mother if father else None
                family, _ = _get_or_create_family(db, trans, parent1, parent2)
                cref = ChildRef()
                cref.set_reference_handle(person.get_handle())
                family.add_child_ref(cref)
                db.commit_family(family, trans)
                person.add_parent_family_handle(family.get_handle())
                db.commit_person(person, trans)

        console.print(f"[green]Person {person.get_gramps_id()} ({name}) added[/green]")
        if birth_event:
            console.print(f"[green]Birth event {birth_event.get_gramps_id()} created[/green]")
        if death_event:
            console.print(f"[green]Death event {death_event.get_gramps_id()} created[/green]")
        if burial_event:
            console.print(f"[green]Burial event {burial_event.get_gramps_id()} created[/green]")
        if father or mother:
            console.print(f"[green]Added to family {family.get_gramps_id()}[/green]")
    finally:
        db.close()


@app.command("add-place", no_args_is_help=True)
def add_place(
    query: str = typer.Argument(..., help="Location to geocode and add"),
    enclose: Optional[str] = typer.Option(None, "--enclose", help="Enclose new place within this place ID or name"),
    latlong: Optional[str] = typer.Option(None, "--latlong", help="Skip geocoding and use these coordinates, as 'lat,lon'"),
    type_: Optional[str] = typer.Option(None, "--type", help="Override the place type, e.g. 'Town' or a custom type like 'Cemetery'"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Geocode a location and add it as a Place in the database."""
    if latlong:
        try:
            lat_str, lon_str = (part.strip() for part in latlong.split(','))
            lat, lon = float(lat_str), float(lon_str)
        except ValueError:
            console.print(f"[red]Invalid --latlong {latlong!r}, expected 'lat,lon'[/red]")
            raise typer.Exit(1)
        name = query
        display_name = query
        addresstype = 'manual'
        place_type_int = PlaceType.UNKNOWN
    else:
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

    place_type = PlaceType(place_type_int)
    if type_:
        builtin_types = {v.lower(): k for k, v in PlaceType().get_map().items() if k != PlaceType.CUSTOM}
        builtin_int = builtin_types.get(type_.lower())
        place_type = PlaceType(builtin_int if builtin_int is not None else (PlaceType.CUSTOM, type_))
        addresstype = type_

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
        parent = _resolve_place(db, enclose) if enclose else None

        place = Place()
        pn = PlaceName()
        pn.set_value(name)
        place.set_name(pn)
        place.set_latitude(str(lat))
        place.set_longitude(str(lon))
        place.set_type(place_type)
        if parent:
            pref = PlaceRef()
            pref.set_reference_handle(parent.get_handle())
            place.add_placeref(pref)
        with DbTxn('Add place', db) as trans:
            db.add_place(place, trans)
        console.print("\n[green]Place added:[/green]")
        console.print(_place_table([place]))
        if parent:
            console.print(f"[green]Enclosed by {parent.get_gramps_id()} ({parent.get_name().get_value()})[/green]")
    finally:
        db.close()


@app.command("build")
def build_site():
    """Build the full site."""
    try:
        from .build import build
    except ImportError:
        _require_extra("html")
    build()


@app.command("census-check", no_args_is_help=True)
def census_check(
    person_id: str = typer.Argument(..., help="Person ID"),
):
    """Show census years this person should have a record for, and whether they do."""
    db = _open_db()
    try:
        person = db.get_person_from_gramps_id(person_id)
        if not person:
            console.print(f"[red]Person {person_id!r} not found[/red]")
            raise typer.Exit(1)

        birth = get_event(db, person, EventType.BIRTH)
        death = get_event(db, person, EventType.DEATH)
        birth_year = get_year(birth)
        death_year = get_year(death)

        born_str = str(birth_year) if birth_year else "unknown"
        died_str = str(death_year) if death_year else "unknown"
        console.print(f"[bold]{person_id}: {_person_name(person)}[/bold]  born {born_str}  died {died_str}\n")

        # person's census events indexed by year
        person_census_by_year: dict[int, list] = {}
        for eref in person.get_event_ref_list():
            event = db.get_event_from_handle(eref.get_reference_handle())
            if int(event.get_type()) == EventType.CENSUS:
                year = event.get_date_object().get_year()
                if year:
                    person_census_by_year.setdefault(year, []).append(event)

        # event handle -> count of linked people
        event_person_count: dict = {}
        for handle in db.get_person_handles():
            p = db.get_person_from_handle(handle)
            for eref in p.get_event_ref_list():
                h = eref.get_reference_handle()
                event_person_count[h] = event_person_count.get(h, 0) + 1

        eligible = [
            y for y in sorted(CENSUS_DATES)
            if (birth_year is None or birth_year <= y)
            and (death_year is None or death_year >= y)
        ]

        if not eligible:
            console.print("No census years fall within this person's lifespan.")
            return

        table = Table()
        table.add_column("Year")
        table.add_column("Record")
        table.add_column("People on record", justify="right")

        for year in eligible:
            events = person_census_by_year.get(year, [])
            if events:
                for event in events:
                    count = event_person_count.get(event.get_handle(), 0)
                    table.add_row(str(year), "[green]Yes[/green]", str(count))
            else:
                table.add_row(str(year), "[red]No[/red]", "")

        console.print(table)
    finally:
        db.close()


@app.command("config")
def init_config(
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Path to write the config file (skips the prompt)"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Overwrite existing config without prompting"),
):
    """Interactively generate a config file (config.yml by default) for this project."""
    if output is None:
        try:
            output = Path(input("Config file name [config.yml]: ").strip() or "config.yml")
        except KeyboardInterrupt:
            console.print("\nCancelled.")
            raise typer.Exit(0)

    if output.exists() and not yes:
        console.print(f"[yellow]{output} already exists.[/yellow]")
        try:
            answer = input("Overwrite? [y/N] ").strip().lower()
        except KeyboardInterrupt:
            console.print("\nCancelled.")
            raise typer.Exit(0)
        if answer not in ('y', 'yes'):
            raise typer.Exit(0)

    grampsdb_dir = Path(GRAMPS_HOME_DIR) / "grampsdb"
    discovered = []
    if grampsdb_dir.is_dir():
        for entry in sorted(grampsdb_dir.iterdir()):
            name_file = entry / "name.txt"
            if entry.is_dir() and name_file.exists():
                discovered.append((entry, name_file.read_text().strip()))

    db_path: Path
    if discovered:
        console.print("\nGramps databases found:")
        table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
        table.add_column(justify="right", style="bold")
        table.add_column()
        table.add_column(style="dim")
        for i, (path, name) in enumerate(discovered, 1):
            table.add_row(str(i), name, str(path))
        table.add_row("0", "Enter a custom path", "")
        console.print(table)

        while True:
            try:
                raw = input(f"Choose [1–{len(discovered)}, or 0 for custom]: ").strip()
            except KeyboardInterrupt:
                console.print("\nCancelled.")
                raise typer.Exit(0)
            if raw.isdigit():
                choice = int(raw)
                if 1 <= choice <= len(discovered):
                    db_path = discovered[choice - 1][0]
                    break
                elif choice == 0:
                    discovered = []  # fall through to custom path prompt
                    break
            console.print(f"[red]Enter a number between 0 and {len(discovered)}.[/red]")

    if not discovered:
        while True:
            try:
                raw = input("Path to Gramps database: ").strip()
            except KeyboardInterrupt:
                console.print("\nCancelled.")
                raise typer.Exit(0)
            db_path = Path(raw).expanduser()
            if db_path.exists():
                break
            console.print(f"[red]Not found: {db_path}[/red]")

    db = SQLite()
    db.load(str(db_path), mode=DBMODE_R)
    roots = []
    try:
        all_people = sorted(
            [db.get_person_from_handle(h) for h in db.get_person_handles()],
            key=lambda p: p.get_gramps_id(),
        )

        def _match_people(query: str) -> list:
            q = query.lower()
            return [p for p in all_people if q in p.get_gramps_id().lower() or q in _person_name(p).lower()]

        displayed = all_people[:5]
        search_label = "first 5 in database"
        console.print("\nChoose root people — the starting points for the site.")

        while True:
            if displayed:
                console.print(f"\n[bold]People ({search_label}):[/bold]")
                table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
                table.add_column(justify="right", style="bold")
                table.add_column()
                table.add_column(style="dim")
                for i, person in enumerate(displayed, 1):
                    pid = person.get_gramps_id()
                    name = _person_name(person)
                    if pid in roots:
                        name = f"[green]{name} (added)[/green]"
                    table.add_row(str(i), name, pid)
                console.print(table)
            else:
                console.print("[yellow]No matches.[/yellow]")

            suffix = " (at least one required)" if not roots else " (or Enter to finish)"
            try:
                raw = input(f"Pick number, or search by name/ID{suffix}: ").strip()
            except KeyboardInterrupt:
                console.print("\nCancelled.")
                raise typer.Exit(0)

            if not raw:
                if not roots:
                    console.print("[red]At least one root person is required.[/red]")
                else:
                    break
                continue

            if raw.isdigit() and 1 <= int(raw) <= len(displayed):
                person = displayed[int(raw) - 1]
                pid = person.get_gramps_id()
                if pid in roots:
                    console.print(f"[yellow]{pid} already added.[/yellow]")
                else:
                    roots.append(pid)
                    console.print(f"[green]Added {pid} — {_person_name(person)}[/green]")
                continue

            results = _match_people(raw)
            displayed = results[:5]
            count = len(results)
            if count > 5:
                search_label = f"top 5 of {count} matching {raw!r}"
            elif count:
                search_label = f"{count} matching {raw!r}"
            else:
                search_label = ""
    finally:
        db.close()

    try:
        site_title = input("\nSite title [Family tree]: ").strip() or "Family tree"
    except KeyboardInterrupt:
        console.print("\nCancelled.")
        raise typer.Exit(0)

    try:
        raw = input("Ancestry tree ID (press Enter to skip): ").strip()
    except KeyboardInterrupt:
        console.print("\nCancelled.")
        raise typer.Exit(0)
    ancestry_tree_id = raw or None

    try:
        output_dir = input("Output directory [www]: ").strip() or "www"
    except KeyboardInterrupt:
        console.print("\nCancelled.")
        raise typer.Exit(0)

    try:
        site_root = input("Site root [/]: ").strip() or "/"
    except KeyboardInterrupt:
        console.print("\nCancelled.")
        raise typer.Exit(0)

    config_data: dict = {
        'db_path': str(db_path),
        'roots': roots,
        'site_title': site_title,
    }
    if ancestry_tree_id:
        config_data['ancestry_tree_id'] = ancestry_tree_id
    if output_dir != 'www':
        config_data['output_dir'] = output_dir
    if site_root != '/':
        config_data['site_root'] = site_root

    with open(output, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    console.print(f"\n[green]Config written to:[/green] {output.resolve()}")

    env_line = f"GREATGRAMPS_CONFIG={output.resolve()}"
    env_file = Path(".env")
    write_env = True
    if env_file.exists():
        console.print(f"\n[yellow].env already exists.[/yellow]")
        console.print(f"  Will add: {env_line}")
        try:
            answer = input("Overwrite .env? [y/N] ").strip().lower()
        except KeyboardInterrupt:
            console.print("\nSkipping .env.")
            write_env = False
        else:
            write_env = answer in ('y', 'yes')

    if write_env:
        env_file.write_text(env_line + "\n")
        console.print(f"[green].env written.[/green]")

    console.print("\nBuild the site with [bold]grgr build[/bold]")


@app.command("enclose-place", no_args_is_help=True)
def enclose_place(
    child_query: str = typer.Argument(..., help="Place ID or name to be enclosed"),
    parent_query: str = typer.Argument(..., help="Place ID or name that encloses it"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Set one place as enclosed by another (Gramps 'Enclosed by' relationship)."""
    db = _open_db(write=True)
    try:
        child = _resolve_place(db, child_query)
        parent = _resolve_place(db, parent_query)

        if child.get_handle() == parent.get_handle():
            console.print("[red]A place cannot enclose itself[/red]")
            raise typer.Exit(1)

        existing = [
            db.get_place_from_handle(r.get_reference_handle())
            for r in child.get_placeref_list()
        ]
        if any(p.get_handle() == parent.get_handle() for p in existing):
            console.print(
                f"[yellow]{child.get_gramps_id()} is already enclosed by "
                f"{parent.get_gramps_id()} ({parent.get_name().get_value()})[/yellow]"
            )
            raise typer.Exit(0)

        summary = Table(show_header=False)
        summary.add_column("Field", style="bold")
        summary.add_column("Value")
        summary.add_row("Place", f"{child.get_gramps_id()} — {child.get_name().get_value()}")
        summary.add_row("Enclosed by", f"{parent.get_gramps_id()} — {parent.get_name().get_value()}")
        if existing:
            summary.add_row("Also enclosed by", ", ".join(p.get_name().get_value() for p in existing))
        console.print(summary)

        _confirm(yes)

        with DbTxn('Set place enclosed by', db) as trans:
            pref = PlaceRef()
            pref.set_reference_handle(parent.get_handle())
            child.add_placeref(pref)
            db.commit_place(child, trans)

        console.print(
            f"[green]{child.get_gramps_id()} ({child.get_name().get_value()}) "
            f"is now enclosed by {parent.get_gramps_id()} ({parent.get_name().get_value()})[/green]"
        )
    finally:
        db.close()


@app.command("list-ancestors", no_args_is_help=True)
def list_ancestors(
    person_id: str = typer.Argument(..., help="Person ID"),
    generations: Optional[int] = typer.Option(None, "-n", "--generations", help="Limit to this many generations"),
):
    """List ancestors of a person grouped by generation."""
    db = _open_db()
    try:
        person = db.get_person_from_gramps_id(person_id)
        if not person:
            console.print(f"[red]Person {person_id!r} not found[/red]")
            raise typer.Exit(1)
        distances = ancestors_with_distances(db, person)
        console.print(f"[bold]{person_id}: {_person_name(person)}[/bold]\n")

        table = Table()
        table.add_column("ID")
        table.add_column("Name")
        table.add_column("Generation", justify="right")

        for gid, dist in sorted(distances.items(), key=lambda x: (x[1], x[0])):
            if dist == 0:
                continue
            if generations is not None and dist > generations:
                continue
            person = db.get_person_from_gramps_id(gid)
            table.add_row(gid, _person_name(person), str(dist))

        console.print(table)
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


@app.command("list-descendants", no_args_is_help=True)
def list_descendants(
    person_id: str = typer.Argument(..., help="Person ID"),
    generations: Optional[int] = typer.Option(None, "-n", "--generations", help="Limit to this many generations"),
):
    """List descendants of a person grouped by generation."""
    db = _open_db()
    try:
        person = db.get_person_from_gramps_id(person_id)
        if not person:
            console.print(f"[red]Person {person_id!r} not found[/red]")
            raise typer.Exit(1)
        descendants = collect_all_descendants(db, person)
        console.print(f"[bold]{person_id}: {_person_name(person)}[/bold]\n")

        table = Table()
        table.add_column("ID")
        table.add_column("Name")
        table.add_column("Generation", justify="right")

        for gid, data in sorted(descendants.items(), key=lambda x: (x[1]['generation'], x[0])):
            if generations is not None and data['generation'] > generations:
                continue
            table.add_row(gid, data['full_name'], str(data['generation']))

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
            age = str(max(0, event_year - birth_year - 1)) if event_year and birth_year else ""
            table.add_row(person.get_gramps_id(), name, str(birth_year) if birth_year else "", age)
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


@app.command("list-person-events", no_args_is_help=True)
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


@app.command("list-unconnected")
def list_unconnected():
    """List people with no family connections (not a parent, spouse, or child in any family)."""
    db = _open_db()
    try:
        people = []
        for handle in db.get_person_handles():
            person = db.get_person_from_handle(handle)
            if not person.get_family_handle_list() and not person.get_parent_family_handle_list():
                people.append((person, _person_name(person)))

        people.sort(key=lambda p: p[1])

        if not people:
            console.print("No unconnected people found.")
            return

        console.print(f"[bold]{len(people)} unconnected person(s):[/bold]")
        console.print(_people_table(people))
    finally:
        db.close()


@app.command("orphans")
def orphans(
    delete: bool = typer.Option(False, "--delete", help="Delete orphaned people (and any families left empty), unattached events and unused places"),
    delete_groups: bool = typer.Option(False, "--delete-groups", help="Offer to delete each disconnected group, confirming one group at a time"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompts"),
):
    """Find orphaned people, unattached events and unused places.

    Orphaned people are linked to nobody else, including those alone in an empty family.
    Unattached events belong to no person or family. Unused places have no events, directly
    or via any place they enclose. Also reports groups of people that are linked to each
    other but not to any configured root.
    """
    db = _open_db(write=delete or delete_groups)
    try:
        # Build adjacency between people who share a family
        adjacent: dict[str, set[str]] = {}
        for handle in db.get_family_handles():
            family = db.get_family_from_handle(handle)
            members = [family.get_father_handle(), family.get_mother_handle()]
            members += [ref.get_reference_handle() for ref in family.get_child_ref_list()]
            members = [h for h in members if h]
            for h in members:
                adjacent.setdefault(h, set()).update(m for m in members if m != h)

        # Connected components
        seen: set[str] = set()
        components: list[set[str]] = []
        for handle in db.get_person_handles():
            if handle in seen:
                continue
            component: set[str] = set()
            stack = [handle]
            while stack:
                h = stack.pop()
                if h in component:
                    continue
                component.add(h)
                stack.extend(adjacent.get(h, set()) - component)
            seen |= component
            components.append(component)

        root_handles = set()
        for root_id in get_config().roots:
            root = db.get_person_from_gramps_id(root_id)
            if root:
                root_handles.add(root.get_handle())

        orphan_people = []
        disconnected = []
        for component in components:
            if len(component) == 1:
                orphan_people.append(db.get_person_from_handle(next(iter(component))))
            elif not component & root_handles:
                disconnected.append(sorted(
                    (db.get_person_from_handle(h) for h in component),
                    key=lambda p: p.get_gramps_id(),
                ))
        orphan_people.sort(key=lambda p: p.get_gramps_id())

        # Events referenced by no person or family
        referenced: set[str] = set()
        for handle in db.get_person_handles():
            referenced.update(r.get_reference_handle() for r in db.get_person_from_handle(handle).get_event_ref_list())
        for handle in db.get_family_handles():
            referenced.update(r.get_reference_handle() for r in db.get_family_from_handle(handle).get_event_ref_list())
        unattached_events = sorted(
            (e for e in db.iter_events() if e.get_handle() not in referenced),
            key=lambda e: e.get_gramps_id(),
        )

        # Places with no events, directly or through any place they enclose
        backlinks = {h: list(db.find_backlink_handles(h)) for h in db.get_place_handles()}
        unused_cache: dict[str, bool] = {}

        def place_unused(handle):
            if handle in unused_cache:
                return unused_cache[handle]
            unused_cache[handle] = False  # treat enclosure cycles as used
            for cls, h in backlinks.get(handle, []):
                if cls != 'Place' or not place_unused(h):
                    return False
            unused_cache[handle] = True
            return True

        unused_places = sorted(
            (db.get_place_from_handle(h) for h in db.get_place_handles() if place_unused(h)),
            key=lambda p: p.get_gramps_id(),
        )

        if not orphan_people and not disconnected and not unattached_events and not unused_places:
            console.print("No orphaned people, unattached events or unused places found.")
            return

        if orphan_people:
            console.print(f"[bold]{len(orphan_people)} orphaned person(s):[/bold]")
            table = Table()
            table.add_column("ID")
            table.add_column("Name")
            table.add_column("Empty families")
            for person in orphan_people:
                families = person.get_family_handle_list() + person.get_parent_family_handle_list()
                family_ids = ', '.join(db.get_family_from_handle(h).get_gramps_id() for h in families)
                table.add_row(person.get_gramps_id(), _person_name(person), family_ids)
            console.print(table)

        for group in disconnected:
            console.print(f"\n[bold]Group of {len(group)} not connected to any root:[/bold]")
            console.print(_people_table([(p, _person_name(p)) for p in group]))

        if unattached_events:
            console.print(f"\n[bold]{len(unattached_events)} event(s) attached to no person or family:[/bold]")
            table = Table()
            table.add_column("ID")
            table.add_column("Type")
            table.add_column("Date")
            table.add_column("Place")
            table.add_column("Description")
            for event in unattached_events:
                place_h = event.get_place_handle()
                place = db.get_place_from_handle(place_h).get_name().get_value() if place_h else ''
                table.add_row(event.get_gramps_id(), str(event.get_type()), format_date(event.get_date_object()) or '',
                              place, event.get_description() or '')
            console.print(table)

        if unused_places:
            console.print(f"\n[bold]{len(unused_places)} place(s) with no events, directly or via enclosed places:[/bold]")
            table = Table()
            table.add_column("ID")
            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Enclosed by")
            for place in unused_places:
                chain = []
                current = place
                while current.get_placeref_list():
                    current = db.get_place_from_handle(current.get_placeref_list()[0].ref)
                    chain.append(current.get_name().get_value())
                table.add_row(place.get_gramps_id(), place.get_name().get_value(), str(place.get_type()), ', '.join(chain))
            console.print(table)

        if delete and (orphan_people or unattached_events or unused_places):
            parts = []
            if orphan_people:
                parts.append(f"{len(orphan_people)} orphaned person(s) and their empty families")
            if unattached_events:
                parts.append(f"{len(unattached_events)} unattached event(s)")
            if unused_places:
                parts.append(f"{len(unused_places)} unused place(s)")
            console.print(f"\n[bold]Delete {', '.join(parts)}[/bold]")
            _confirm(yes)
            if orphan_people:
                _delete_people(db, orphan_people, 'Delete orphaned people')
            if unattached_events:
                with DbTxn('Delete unattached events', db) as trans:
                    for event in unattached_events:
                        db.remove_event(event.get_handle(), trans)
                ids = ', '.join(e.get_gramps_id() for e in unattached_events)
                console.print(f"[green]Deleted {len(unattached_events)} events: {ids}[/green]")
            if unused_places:
                with DbTxn('Delete unused places', db) as trans:
                    for place in unused_places:
                        db.remove_place(place.get_handle(), trans)
                ids = ', '.join(p.get_gramps_id() for p in unused_places)
                console.print(f"[green]Deleted {len(unused_places)} places: {ids}[/green]")
        elif delete:
            console.print("\nNothing to delete.")

        if delete_groups and disconnected:
            for group in disconnected:
                console.print(f"\n[bold]Group of {len(group)}:[/bold] " + ', '.join(f"{p.get_gramps_id()} {_person_name(p)}" for p in group))
                if not yes:
                    try:
                        answer = input("Delete this group? [y/N] ").strip().lower()
                    except KeyboardInterrupt:
                        console.print("\nCancelled.")
                        raise typer.Exit(0)
                    if answer not in ('y', 'yes'):
                        console.print("Skipped.")
                        continue
                _delete_people(db, group, 'Delete disconnected group')
        elif delete_groups:
            console.print("\nNo disconnected groups to delete.")
    finally:
        db.close()


def _delete_people(db, people, description):
    """Delete people from the database in one transaction and report what was removed."""
    with DbTxn(description, db) as trans:
        for person in people:
            db.delete_person_from_database(person, trans)
    ids = ', '.join(p.get_gramps_id() for p in people)
    console.print(f"[green]Deleted {len(people)} people: {ids}[/green]")


pdf_app = typer.Typer(help="Generate PDF pedigree, descendant, and hourglass charts.", no_args_is_help=True)
app.add_typer(pdf_app, name="pdf")


@app.command("rebuild-page", no_args_is_help=True)
def rebuild_page(
    ids: List[str] = typer.Argument(..., help="IDs or page names to rebuild (e.g. I0061 E0315 P0012 places)"),
):
    """Copy static files and rebuild specific pages by ID or name.

    Accepts person IDs (I…), event IDs (E…), place IDs (P…), and named
    pages: places, people, events, census, index, birthdays, surnames, ancestor-records, census-records, global-index.
    """
    try:
        from .build import rebuild_pages
    except ImportError:
        _require_extra("html")
    rebuild_pages(ids)


@app.command("rm-event", no_args_is_help=True)
def rm_event(
    event_ids: List[str] = typer.Argument(..., help="Event ID(s) to delete"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Delete one or more events, removing all references from people and families."""
    db = _open_db(write=True)
    try:
        events = []
        for eid in event_ids:
            event = db.get_event_from_gramps_id(eid)
            if not event:
                console.print(f"[red]Event {eid!r} not found[/red]")
                raise typer.Exit(1)
            events.append(event)

        linked_people = {}
        linked_families = {}
        for event in events:
            h = event.get_handle()
            linked_people[h] = []
            for person_handle in db.get_person_handles():
                person = db.get_person_from_handle(person_handle)
                if any(e.get_reference_handle() == h for e in person.get_event_ref_list()):
                    linked_people[h].append(person)
            linked_families[h] = []
            for fam_handle in db.get_family_handles():
                family = db.get_family_from_handle(fam_handle)
                if any(e.get_reference_handle() == h for e in family.get_event_ref_list()):
                    linked_families[h].append(family)

        for event in events:
            h = event.get_handle()
            console.print(f"[bold]Delete:[/bold] {event.get_gramps_id()} — {_event_label(event)}")
            for person in linked_people[h]:
                console.print(f"  Remove ref from {person.get_gramps_id()} — {_person_name(person)}")
            for family in linked_families[h]:
                console.print(f"  Remove ref from family {family.get_gramps_id()}")

        _confirm(yes)

        with DbTxn('Delete events', db) as trans:
            for event in events:
                h = event.get_handle()
                for person in linked_people[h]:
                    new_erefs = [e for e in person.get_event_ref_list() if e.get_reference_handle() != h]
                    person.set_event_ref_list(new_erefs)
                    db.commit_person(person, trans)
                for family in linked_families[h]:
                    new_erefs = [e for e in family.get_event_ref_list() if e.get_reference_handle() != h]
                    family.set_event_ref_list(new_erefs)
                    db.commit_family(family, trans)
                db.remove_event(h, trans)

        ids = ', '.join(e.get_gramps_id() for e in events)
        console.print(f"[green]Deleted {ids}[/green]")
    finally:
        db.close()


@app.command("rm-event-people", no_args_is_help=True)
def rm_event_person(
    event_id: str = typer.Argument(..., help="Event ID"),
    person_ids: List[str] = typer.Argument(..., help="Person ID(s) to remove"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Remove one or more people from an event."""
    db = _open_db(write=True)
    try:
        event = db.get_event_from_gramps_id(event_id)
        if not event:
            console.print(f"[red]Event {event_id!r} not found[/red]")
            raise typer.Exit(1)

        to_remove = []
        for pid in person_ids:
            person = db.get_person_from_gramps_id(pid)
            if not person:
                console.print(f"[red]Person {pid!r} not found[/red]")
                raise typer.Exit(1)
            erefs = person.get_event_ref_list()
            new_erefs = [e for e in erefs if e.get_reference_handle() != event.get_handle()]
            if len(new_erefs) == len(erefs):
                console.print(f"[yellow]{pid} is not linked to {event_id}[/yellow]")
                raise typer.Exit(1)
            to_remove.append((person, new_erefs))

        console.print(f"[bold]Event:[/bold] {event_id} — {_event_label(event)}")
        for person, _ in to_remove:
            console.print(f"[bold]Remove:[/bold] {person.get_gramps_id()} — {_person_name(person)}")
        _confirm(yes)

        with DbTxn('Remove people from event', db) as trans:
            for person, new_erefs in to_remove:
                person.set_event_ref_list(new_erefs)
                db.commit_person(person, trans)

        ids = ', '.join(p.get_gramps_id() for p, _ in to_remove)
        console.print(f"[green]Removed {ids} from {event_id}[/green]")
    finally:
        db.close()


@app.command("rm-people", no_args_is_help=True)
def rm_people(
    person_ids: List[str] = typer.Argument(..., help="Person ID(s) to delete"),
    descendants: bool = typer.Option(False, "-d", "--descendants", help="Also delete all descendants"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Delete one or more people from the database, cleaning up family relationships."""
    db = _open_db(write=True)
    try:
        roots = []
        for person_id in person_ids:
            person = db.get_person_from_gramps_id(person_id)
            if not person:
                console.print(f"[red]Person {person_id!r} not found[/red]")
                raise typer.Exit(1)
            roots.append(person)

        all_people = list(roots)

        if descendants:
            seen_ids = {p.get_gramps_id() for p in roots}
            queue = []
            for root in roots:
                queue.extend(get_children(db, root))
            while queue:
                child = queue.pop(0)
                gid = child.get_gramps_id()
                if gid in seen_ids:
                    continue
                seen_ids.add(gid)
                all_people.append(child)
                queue.extend(get_children(db, child))

        root_ids = {p.get_gramps_id() for p in roots}
        desc_people = [p for p in all_people if p.get_gramps_id() not in root_ids]

        for person in roots:
            console.print(f"[bold]Delete:[/bold] {person.get_gramps_id()} — {_person_name(person)}")
            for h in person.get_family_handle_list():
                family = db.get_family_from_handle(h)
                console.print(f"  Remove as spouse from family {family.get_gramps_id()}")
            for h in person.get_parent_family_handle_list():
                family = db.get_family_from_handle(h)
                console.print(f"  Remove as child from family {family.get_gramps_id()}")

        if desc_people:
            console.print(f"\n[bold]Descendants ({len(desc_people)}):[/bold]")
            for person in desc_people:
                console.print(f"  {person.get_gramps_id()} — {_person_name(person)}")

        if len(all_people) > 1:
            console.print(f"\n[bold]Total:[/bold] {len(all_people)} people")
        _confirm(yes)

        with DbTxn('Delete people', db) as trans:
            for person in all_people:
                db.delete_person_from_database(person, trans)

        ids = ', '.join(p.get_gramps_id() for p in all_people)
        console.print(f"[green]Deleted {len(all_people)} people: {ids}[/green]")
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


def _import_pdf_extra():
    try:
        import greatgramps.tree_pdf as tree_pdf
    except ImportError:
        _require_extra("pdf")
    return tree_pdf


def _resolve_paper(paper: str, PAPER_SIZES):
    if paper not in PAPER_SIZES:
        console.print(f"[red]Unknown paper size {paper!r} — choose from: {', '.join(PAPER_SIZES)}[/red]")
        raise typer.Exit(1)
    return PAPER_SIZES[paper]


def _get_person_or_exit(db, person_id):
    person = db.get_person_from_gramps_id(person_id)
    if not person:
        console.print(f"[red]Person {person_id!r} not found[/red]")
        raise typer.Exit(1)
    return person


@pdf_app.command("ancestors", no_args_is_help=True)
def pdf_ancestors(
    person_id: str = typer.Argument(..., help="Person ID (root of the pedigree chart)"),
    generations: int = typer.Argument(..., help="Number of generations to show (minimum 2)"),
    output: Optional[Path] = typer.Argument(None, help="Output PDF filename (default: ancestor_tree_PERSONID_Ngen.pdf)"),
    color: bool = typer.Option(True, "--color/--no-color", help="Use colour boxes (default: color)"),
    paper: str = typer.Option("A4", "--paper", help=f"Paper size ({'|'.join(PAPER_SIZE_NAMES)})"),
):
    """Generate a printable PDF ancestor pedigree chart."""
    tree_pdf = _import_pdf_extra()
    if generations < 2:
        console.print("[red]Minimum 2 generations.[/red]")
        raise typer.Exit(1)
    page_size = _resolve_paper(paper, tree_pdf.PAPER_SIZES)
    output = output or Path(f"ancestor_tree_{person_id}_{generations}gen.pdf")

    db = _open_db()
    try:
        _get_person_or_exit(db, person_id)
        warning = tree_pdf.generate_ancestor_pdf(db, person_id, generations, output, color=color, page_size=page_size)
        if warning:
            console.print(f"[yellow]{warning}[/yellow]")
        console.print(f"Saved: {output}")
    finally:
        db.close()


@pdf_app.command("descendants", no_args_is_help=True)
def pdf_descendants(
    person_id: str = typer.Argument(..., help="Person ID (root of the descendant chart)"),
    generations: int = typer.Argument(..., help="Number of generations to show (minimum 2)"),
    output: Optional[Path] = typer.Argument(None, help="Output PDF filename (default: descendant_tree_PERSONID_Ngen.pdf)"),
    color: bool = typer.Option(True, "--color/--no-color", help="Use colour boxes (default: color)"),
    paper: str = typer.Option("A4", "--paper", help=f"Paper size ({'|'.join(PAPER_SIZE_NAMES)})"),
):
    """Generate a printable PDF descendant tree chart."""
    tree_pdf = _import_pdf_extra()
    if generations < 2:
        console.print("[red]Minimum 2 generations.[/red]")
        raise typer.Exit(1)
    page_size = _resolve_paper(paper, tree_pdf.PAPER_SIZES)
    output = output or Path(f"descendant_tree_{person_id}_{generations}gen.pdf")

    db = _open_db()
    try:
        _get_person_or_exit(db, person_id)
        warning = tree_pdf.generate_descendant_pdf(db, person_id, generations, output, color=color, page_size=page_size)
        if warning:
            console.print(f"[yellow]{warning}[/yellow]")
        console.print(f"Saved: {output}")
    finally:
        db.close()


@pdf_app.command("hourglass", no_args_is_help=True)
def pdf_hourglass(
    person_id: str = typer.Argument(..., help="Person ID (root of the hourglass chart)"),
    ancestor_generations: int = typer.Argument(..., help="Number of ancestor generations to show (minimum 2)"),
    descendant_generations: int = typer.Argument(..., help="Number of descendant generations to show (minimum 2)"),
    output: Optional[Path] = typer.Argument(None, help="Output PDF filename (default: hourglass_PERSONID_AxDgen.pdf)"),
    color: bool = typer.Option(True, "--color/--no-color", help="Use colour boxes (default: color)"),
    paper: str = typer.Option("A4", "--paper", help=f"Paper size ({'|'.join(PAPER_SIZE_NAMES)})"),
):
    """Generate a printable PDF hourglass chart (ancestors above, descendants below)."""
    tree_pdf = _import_pdf_extra()
    if ancestor_generations < 2 or descendant_generations < 2:
        console.print("[red]Minimum 2 generations in each direction.[/red]")
        raise typer.Exit(1)
    page_size = _resolve_paper(paper, tree_pdf.PAPER_SIZES)
    output = output or Path(f"hourglass_{person_id}_{ancestor_generations}x{descendant_generations}gen.pdf")

    db = _open_db()
    try:
        _get_person_or_exit(db, person_id)
        warning = tree_pdf.generate_hourglass_pdf(
            db, person_id, ancestor_generations, descendant_generations, output, color=color, page_size=page_size,
        )
        if warning:
            console.print(f"[yellow]{warning}[/yellow]")
        console.print(f"Saved: {output}")
    finally:
        db.close()


@app.command("update-person", no_args_is_help=True)
def update_person(
    person_id: str = typer.Argument(..., help="Person ID"),
    birth: Optional[str] = typer.Option(None, "--birth", help="Birth date, e.g. '1 Jan 1950' or 1950"),
    death: Optional[str] = typer.Option(None, "--death", help="Death date"),
    baptism: Optional[str] = typer.Option(None, "--baptism", help="Baptism date"),
    burial: Optional[str] = typer.Option(None, "--burial", help="Burial date"),
    birth_place: Optional[str] = typer.Option(None, "--birth-place", help="Birth place ID or name"),
    death_place: Optional[str] = typer.Option(None, "--death-place", help="Death place ID or name"),
    burial_place: Optional[str] = typer.Option(None, "--burial-place", help="Burial place ID or name"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
):
    """Set or update event dates and places on a person."""
    date_inputs = [
        ("Birth",   EventType.BIRTH,   birth),
        ("Death",   EventType.DEATH,   death),
        ("Baptism", EventType.BAPTISM, baptism),
        ("Burial",  EventType.BURIAL,  burial),
    ]
    parsed_dates = {}
    for label, event_type, date_str in date_inputs:
        if date_str:
            result = _parse_date(date_str)
            if result is None:
                console.print(f"[red]Could not parse {label.lower()} date {date_str!r}[/red]")
                raise typer.Exit(1)
            parsed_dates[event_type] = (label, date_str, result)

    place_inputs = [
        ("Birth",  EventType.BIRTH,  birth_place),
        ("Death",  EventType.DEATH,  death_place),
        ("Burial", EventType.BURIAL, burial_place),
    ]

    if not parsed_dates and not any(p for _, _, p in place_inputs):
        console.print("[red]Specify at least one of --birth, --death, --baptism, --burial, --birth-place, --death-place, --burial-place[/red]")
        raise typer.Exit(1)

    db = _open_db(write=True)
    try:
        person = db.get_person_from_gramps_id(person_id)
        if not person:
            console.print(f"[red]Person {person_id!r} not found[/red]")
            raise typer.Exit(1)

        resolved_places = {}
        for label, event_type, place_query in place_inputs:
            if place_query:
                resolved_places[event_type] = (label, _resolve_place(db, place_query))

        all_event_types = sorted(
            set(parsed_dates.keys()) | set(resolved_places.keys()),
            key=lambda t: [EventType.BIRTH, EventType.DEATH, EventType.BAPTISM, EventType.BURIAL].index(t) if t in [EventType.BIRTH, EventType.DEATH, EventType.BAPTISM, EventType.BURIAL] else 99,
        )

        fields = []
        for event_type in all_event_types:
            label = (parsed_dates.get(event_type) or resolved_places.get(event_type))[0]
            date_str, parsed_date = (parsed_dates[event_type][1], parsed_dates[event_type][2]) if event_type in parsed_dates else (None, None)
            place = resolved_places[event_type][1] if event_type in resolved_places else None
            existing = get_event(db, person, event_type)
            fields.append((label, event_type, date_str, parsed_date, place, existing))

        summary = Table(show_header=False)
        summary.add_column("Field", style="bold")
        summary.add_column("Value")
        summary.add_row("Person", f"{person_id} — {_person_name(person)}")
        for label, event_type, date_str, parsed_date, place, existing in fields:
            parts = []
            if date_str:
                parts.append(date_str)
            if place:
                parts.append(place.get_name().get_value())
            if existing:
                current_date = format_date(existing.get_date_object()) or "(no date)"
                current_place_handle = existing.get_place_handle()
                current_place = db.get_place_from_handle(current_place_handle).get_name().get_value() if current_place_handle else "(no place)"
                action = f"updating {existing.get_gramps_id()}, was: {current_date} — {current_place}"
            else:
                action = "new event"
            summary.add_row(label, f"{' — '.join(parts)}  ({action})")
        console.print(summary)

        _confirm(yes)

        with DbTxn('Update person events', db) as trans:
            person_modified = False
            for label, event_type, date_str, parsed_date, place, existing in fields:
                if existing:
                    if parsed_date:
                        y, m, d = parsed_date
                        dt = Date()
                        dt.set_yr_mon_day(y, m, d)
                        existing.set_date_object(dt)
                    if place:
                        existing.set_place_handle(place.get_handle())
                    db.commit_event(existing, trans)
                else:
                    _attach_event(db, trans, person, EventType(event_type), parsed_date, place)
                    person_modified = True
            if person_modified:
                db.commit_person(person, trans)

        for label, event_type, date_str, parsed_date, place, existing in fields:
            parts = []
            if date_str:
                parts.append(date_str)
            if place:
                parts.append(place.get_name().get_value())
            if existing:
                console.print(f"[green]Updated {label} ({existing.get_gramps_id()}) → {' — '.join(parts)}[/green]")
            else:
                console.print(f"[green]{label} event created[/green]")
    finally:
        db.close()
