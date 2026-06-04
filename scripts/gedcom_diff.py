#!/usr/bin/env python3
"""Compare a Gramps person against a matching GEDCOM record and interactively apply changes."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
import os
load_dotenv(REPO_ROOT / '.env')
_cfg = os.environ.get('GREATGRAMPS_CONFIG', 'config.yml')
if not Path(_cfg).is_absolute():
    os.environ['GREATGRAMPS_CONFIG'] = str(REPO_ROOT / _cfg)

from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement

from greatgramps.settings import get_config
from gramps.gen.db import DBMODE_W, DbTxn
from gramps.gen.lib import (
    Attribute, AttributeType, Date, Event, EventRef, EventRoleType, EventType,
)
from gramps.plugins.db.dbapi.sqlite import SQLite


GEDCOM_FILE = REPO_ROOT / 'ged' / 'Nuttall Family Tree.ged'

MONTH_NAMES = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10,
    'november': 11, 'december': 12,
}


def parse_gedcom_date(date_str: str) -> tuple[int | None, int, int]:
    if not date_str:
        return None, 0, 0
    s = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str.strip())
    parts = s.split()
    if len(parts) == 3:
        try:
            return int(parts[2]), MONTH_MAP.get(parts[1].lower(), 0), int(parts[0])
        except (ValueError, KeyError):
            pass
    if len(parts) == 2:
        try:
            return int(parts[1]), MONTH_MAP.get(parts[0].lower(), 0), 0
        except (ValueError, KeyError):
            pass
    if len(parts) == 1:
        try:
            return int(parts[0]), 0, 0
        except ValueError:
            pass
    return None, 0, 0


def fmt_date(d) -> str:
    day, month, year = d.get_day(), d.get_month(), d.get_year()
    parts = []
    if day:
        parts.append(str(day))
    if month:
        parts.append(MONTH_NAMES[month])
    if year:
        parts.append(str(year))
    return ' '.join(parts) if parts else '—'


def find_place(db, place_str: str):
    if not place_str:
        return None
    first = place_str.split(',')[0].strip().lower()
    for h in db.get_place_handles():
        p = db.get_place_from_handle(h)
        if p.get_name().get_value().lower() == first:
            return p
    return None


def get_event(person, db, event_type_int):
    for eref in person.get_event_ref_list():
        ev = db.get_event_from_handle(eref.get_reference_handle())
        if ev.get_type() == EventType(event_type_int):
            return ev
    return None


def get_census_event(person, db, year: int):
    for eref in person.get_event_ref_list():
        ev = db.get_event_from_handle(eref.get_reference_handle())
        if ev.get_type() == EventType(EventType.CENSUS) and ev.get_date_object().get_year() == year:
            return ev
    return None


def has_occupation(person, year: int) -> bool:
    for attr in person.get_attribute_list():
        if (attr.get_type() == AttributeType(AttributeType.OCCUPATION)
                and f'({year})' in attr.get_value()):
            return True
    return False


def extract_occupation(note: str) -> str | None:
    m = re.search(r'Occupation:\s*([^;]+)', note, re.IGNORECASE)
    return m.group(1).strip() if m else None


def place_name(db, handle) -> str:
    return db.get_place_from_handle(handle).get_name().get_value() if handle else '—'


def prompt(label: str, current: str, proposed: str) -> str | None:
    """Return None to skip, or the value to use (original proposed or modified)."""
    print(f'\n  {label}')
    if current and current != '—':
        print(f'    Current:  {current}')
    print(f'    Proposed: {proposed}')
    try:
        answer = input('  [Y]es / [m]odify / [n]o: ').strip().lower()
        if answer == 'n':
            return None
        if answer == 'm':
            try:
                modified = input(f'  Value: ').strip()
                return modified if modified else proposed
            except (KeyboardInterrupt, EOFError):
                print('\nAborted.')
                sys.exit(0)
        return proposed
    except (KeyboardInterrupt, EOFError):
        print('\nAborted.')
        sys.exit(0)


def _date_specificity(year, month, day) -> int:
    if day: return 3
    if month: return 2
    if year: return 1
    return 0


def diff_event_date(event, ged_date_str: str, label: str, accepted: list):
    if not ged_date_str:
        return
    gy, gm, gd = parse_gedcom_date(ged_date_str)
    if not gy:
        return
    d = event.get_date_object()
    if gd == d.get_day() and gm == d.get_month() and gy == d.get_year():
        return
    if _date_specificity(gy, gm, gd) < _date_specificity(d.get_year(), d.get_month(), d.get_day()):
        return
    result = prompt(f'{label} date', fmt_date(d), ged_date_str)
    if result is None:
        return
    ry, rm, rd = parse_gedcom_date(result)
    if not ry:
        print(f'  Could not parse {result!r}, skipping.')
        return
    h = event.get_handle()
    def apply(db, trans, h=h, y=ry, m=rm, d=rd):
        ev = db.get_event_from_handle(h)
        dt = ev.get_date_object()
        dt.set_yr_mon_day(y, m, d)
        ev.set_date_object(dt)
        db.commit_event(ev, trans)
    accepted.append(apply)


def diff_event_place(db, event, ged_place_str: str, label: str, accepted: list):
    if not ged_place_str:
        return
    ged_place = find_place(db, ged_place_str)
    if not ged_place:
        return
    current = place_name(db, event.get_place_handle())
    proposed_name = ged_place.get_name().get_value()
    if proposed_name == current:
        return
    result = prompt(f'{label} place (GEDCOM: {ged_place_str})', current, proposed_name)
    if result is None:
        return
    if result != proposed_name:
        resolved = find_place(db, result)
        if not resolved:
            print(f'  Place {result!r} not found in database, skipping.')
            return
        ph = resolved.get_handle()
    else:
        ph = ged_place.get_handle()
    h = event.get_handle()
    def apply(db, trans, h=h, ph=ph):
        ev = db.get_event_from_handle(h)
        ev.set_place_handle(ph)
        db.commit_event(ev, trans)
    accepted.append(apply)


def main():
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} <GRAMPS_PERSON_ID>')
        sys.exit(1)

    gramps_id = sys.argv[1]

    print('Loading GEDCOM...')
    parser = Parser()
    parser.parse_file(str(GEDCOM_FILE))
    gedcom_individuals = [
        el for el in parser.get_element_list()
        if isinstance(el, IndividualElement)
    ]

    config = get_config()
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        person = db.get_person_from_gramps_id(gramps_id)
        if not person:
            print(f'Person {gramps_id!r} not found in Gramps.')
            return

        pn = person.get_primary_name()
        gramps_full = f'{pn.get_first_name()} {pn.get_surname()}'.strip()
        birth_event = get_event(person, db, EventType.BIRTH)
        gramps_birth_year = birth_event.get_date_object().get_year() if birth_event else None

        print(f'\nGramps: {gramps_id} — {gramps_full} (b. {gramps_birth_year})')

        # Find GEDCOM match by name + birth year
        candidates = []
        for el in gedcom_individuals:
            n = el.get_name()
            if f'{n[0]} {n[1]}'.strip().lower() != gramps_full.lower():
                continue
            birth_str, _, _ = el.get_birth_data()
            gy, _, _ = parse_gedcom_date(birth_str)
            if gramps_birth_year and gy and abs(gy - gramps_birth_year) > 2:
                continue
            candidates.append((el, gy))

        if not candidates:
            print(f'No GEDCOM match found for {gramps_full!r} (b. {gramps_birth_year})')
            return

        if len(candidates) > 1:
            print('Multiple GEDCOM matches:')
            for i, (el, yr) in enumerate(candidates):
                print(f'  {i + 1}. {el.get_pointer()} (b. {yr})')
            try:
                choice = int(input('Choose: ')) - 1
                ged = candidates[choice][0]
            except (ValueError, IndexError, KeyboardInterrupt):
                print('Aborted.')
                return
        else:
            ged = candidates[0][0]

        ged_n = ged.get_name()
        print(f'GEDCOM: {ged.get_pointer()} — {ged_n[0]} {ged_n[1]}'.strip())

        accepted = []

        # ── Birth ─────────────────────────────────────────────────────────
        if birth_event:
            ged_birth_str, ged_birth_place_str, _ = ged.get_birth_data()
            diff_event_date(birth_event, ged_birth_str, 'Birth', accepted)
            diff_event_place(db, birth_event, ged_birth_place_str, 'Birth', accepted)

        # ── Death ─────────────────────────────────────────────────────────
        death_event = get_event(person, db, EventType.DEATH)
        if death_event:
            ged_death_str, ged_death_place_str, _ = ged.get_death_data()
            diff_event_date(death_event, ged_death_str, 'Death', accepted)
            diff_event_place(db, death_event, ged_death_place_str, 'Death', accepted)

        # ── Baptism, Burial, Probate ───────────────────────────────────────
        for child in ged.get_child_elements():
            tag = child.get_tag()

            if tag in ('BAPM', 'BAPT', 'CHR'):
                bapm_event = get_event(person, db, EventType.BAPTISM)
                if bapm_event:
                    ged_date = ged_place = ''
                    for gc in child.get_child_elements():
                        if gc.get_tag() == 'DATE': ged_date = gc.get_value()
                        if gc.get_tag() == 'PLAC': ged_place = gc.get_value()
                    diff_event_date(bapm_event, ged_date, 'Baptism', accepted)
                    diff_event_place(db, bapm_event, ged_place, 'Baptism', accepted)

            elif tag == 'BURI':
                buri_event = get_event(person, db, EventType.BURIAL)
                if buri_event:
                    ged_date = ged_place = ''
                    for gc in child.get_child_elements():
                        if gc.get_tag() == 'DATE': ged_date = gc.get_value()
                        if gc.get_tag() == 'PLAC': ged_place = gc.get_value()
                    diff_event_date(buri_event, ged_date, 'Burial', accepted)
                    diff_event_place(db, buri_event, ged_place, 'Burial', accepted)

            elif tag == 'PROB':
                if not get_event(person, db, EventType.PROBATE):
                    ged_date = ged_place_str = ''
                    for gc in child.get_child_elements():
                        if gc.get_tag() == 'DATE': ged_date = gc.get_value()
                        if gc.get_tag() == 'PLAC': ged_place_str = gc.get_value()
                    ged_place = find_place(db, ged_place_str)
                    ph = ged_place.get_handle() if ged_place else None
                    result = prompt('Add Probate event', '', f'{ged_date}, {ged_place_str}')
                    if result is not None:
                        date_part = result.split(',')[0].strip() if ',' in result else result
                        gy, gm, gd = parse_gedcom_date(date_part) if date_part else parse_gedcom_date(ged_date)
                        if result != f'{ged_date}, {ged_place_str}' and ',' in result:
                            place_part = result.split(',', 1)[1].strip()
                            new_place = find_place(db, place_part)
                            ph = new_place.get_handle() if new_place else ph
                        def apply_probate(db, trans, y=gy, m=gm, d=gd, ph=ph, pid=gramps_id):
                            ev = Event()
                            ev.set_type(EventType(EventType.PROBATE))
                            dt = Date()
                            dt.set_yr_mon_day(y or 0, m, d)
                            ev.set_date_object(dt)
                            if ph:
                                ev.set_place_handle(ph)
                            db.add_event(ev, trans)
                            p = db.get_person_from_gramps_id(pid)
                            eref = EventRef()
                            eref.set_reference_handle(ev.get_handle())
                            eref.set_role(EventRoleType(EventRoleType.PRIMARY))
                            p.add_event_ref(eref)
                            db.commit_person(p, trans)
                        accepted.append(apply_probate)

        # ── Census places & occupations from RESI ─────────────────────────
        for child in ged.get_child_elements():
            if child.get_tag() != 'RESI':
                continue
            ged_date = ged_place_str = ged_note = ''
            for gc in child.get_child_elements():
                if gc.get_tag() == 'DATE': ged_date = gc.get_value()
                if gc.get_tag() == 'PLAC': ged_place_str = gc.get_value()
                if gc.get_tag() == 'NOTE': ged_note = gc.get_value()

            gy, _, _ = parse_gedcom_date(ged_date)
            if not gy:
                continue

            census_event = get_census_event(person, db, gy)
            if census_event:
                diff_event_place(db, census_event, ged_place_str, f'{gy} census', accepted)

            occupation = extract_occupation(ged_note)
            if occupation and not has_occupation(person, gy):
                occ_str = f'{occupation} ({gy})'
                result = prompt(f'Add occupation attribute', '', occ_str)
                if result is not None:
                    def apply_occupation(db, trans, val=result, pid=gramps_id):
                        p = db.get_person_from_gramps_id(pid)
                        attr = Attribute()
                        attr.set_type(AttributeType(AttributeType.OCCUPATION))
                        attr.set_value(val)
                        p.add_attribute(attr)
                        db.commit_person(p, trans)
                    accepted.append(apply_occupation)

        # ── Apply ─────────────────────────────────────────────────────────
        if not accepted:
            print('\nNo changes accepted.')
            return

        print(f'\nApplying {len(accepted)} change(s)...')
        with DbTxn(f'GEDCOM diff {gramps_id}', db) as trans:
            for fn in accepted:
                fn(db, trans)
        print('Done.')

    finally:
        db.close()


if __name__ == '__main__':
    main()
