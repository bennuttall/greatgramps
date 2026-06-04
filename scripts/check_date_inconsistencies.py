#!/usr/bin/env python3
"""Check for date inconsistencies and duplicate singular events."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / '.env')
_cfg = os.environ.get('GREATGRAMPS_CONFIG', 'config.yml')
if not Path(_cfg).is_absolute():
    os.environ['GREATGRAMPS_CONFIG'] = str(REPO_ROOT / _cfg)

from greatgramps.gramps_data import open_db
from gramps.gen.lib.eventtype import EventType


MONTH_NAMES = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# Events that naturally occur after death — excluded from the after-death check.
# Checked by string name to handle custom event types (e.g. Probate stored as type 0).
SKIP_AFTER_DEATH_NAMES = frozenset({'Burial', 'Cremation', 'Probate'})

# Event types that should appear at most once per person.
UNIQUE_EVENT_NAMES = frozenset({
    'Birth', 'Baptism', 'Adult Christening', 'Death', 'Burial', 'Cremation', 'Will', 'Probate',
})

# Event types that should only ever have one participant.
SINGLETON_EVENT_NAMES = frozenset({
    'Birth', 'Baptism', 'Adult Christening', 'Death', 'Burial', 'Cremation',
})


def date_is_before(d1, d2) -> bool:
    """Return True only when d1 is definitively earlier than d2."""
    y1, y2 = d1.get_year(), d2.get_year()
    if not y1 or not y2:
        return False
    if y1 != y2:
        return y1 < y2
    m1, m2 = d1.get_month(), d2.get_month()
    if not m1 or not m2:
        return False
    if m1 != m2:
        return m1 < m2
    d1v, d2v = d1.get_day(), d2.get_day()
    if not d1v or not d2v:
        return False
    return d1v < d2v


def fmt_date(d) -> str:
    parts = []
    if d.get_day():
        parts.append(str(d.get_day()))
    if d.get_month():
        parts.append(MONTH_NAMES[d.get_month()])
    if d.get_year():
        parts.append(str(d.get_year()))
    return ' '.join(parts) if parts else '—'


def person_name(person) -> str:
    n = person.get_primary_name()
    return f'{n.get_first_name()} {n.get_surname()}'.strip()


def main():
    db = open_db()
    issues = []
    shared_event_issues = []

    try:
        # Pre-build event → people map for the shared-event check
        event_to_people: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for person in db.iter_people():
            entry = (person.get_gramps_id(), person_name(person))
            for eref in person.get_event_ref_list():
                event_to_people[eref.get_reference_handle()].append(entry)

        for person in db.iter_people():
            pid = person.get_gramps_id()
            name = person_name(person)
            birth_date = death_date = None

            for eref in person.get_event_ref_list():
                ev = db.get_event_from_handle(eref.get_reference_handle())
                et = int(ev.get_type())
                d = ev.get_date_object()
                if et == EventType.BIRTH and d.get_year():
                    birth_date = d
                elif et == EventType.DEATH and d.get_year():
                    death_date = d

            # Duplicate singular events
            events_by_type: dict[str, list] = defaultdict(list)
            for eref in person.get_event_ref_list():
                ev = db.get_event_from_handle(eref.get_reference_handle())
                etype = str(ev.get_type())
                if etype in UNIQUE_EVENT_NAMES:
                    events_by_type[etype].append(ev)
            for etype, evs in sorted(events_by_type.items()):
                if len(evs) > 1:
                    detail = ', '.join(f'{ev.get_gramps_id()} {fmt_date(ev.get_date_object())}' for ev in evs)
                    issues.append((pid, name, f'Multiple {etype} events: {detail}'))

            if not birth_date and not death_date:
                continue

            for eref in person.get_event_ref_list():
                ev = db.get_event_from_handle(eref.get_reference_handle())
                et = int(ev.get_type())
                d = ev.get_date_object()
                if not d.get_year():
                    continue

                eid = ev.get_gramps_id()
                etype = str(ev.get_type())

                if et == EventType.BIRTH:
                    continue

                if birth_date and date_is_before(d, birth_date):
                    issues.append((pid, name, f'{eid} ({etype}) {fmt_date(d)} — before birth {fmt_date(birth_date)}'))
                    continue

                if et == EventType.DEATH or etype in SKIP_AFTER_DEATH_NAMES:
                    continue

                if death_date and date_is_before(death_date, d):
                    issues.append((pid, name, f'{eid} ({etype}) {fmt_date(d)} — after death {fmt_date(death_date)}'))

        # Events that should only have one participant
        for event in db.iter_events():
            etype = str(event.get_type())
            if etype not in SINGLETON_EVENT_NAMES:
                continue
            people = event_to_people.get(event.get_handle(), [])
            if len(people) > 1:
                eid = event.get_gramps_id()
                d = fmt_date(event.get_date_object())
                names = ', '.join(f'{pid} {name}' for pid, name in people)
                shared_event_issues.append(f'{eid} ({etype}) {d}: {names}')

    finally:
        db.close()

    if not issues and not shared_event_issues:
        print('No inconsistencies found.')
        return

    if issues:
        print(f'{len(issues)} date / duplicate inconsistencies:\n')
        current_pid = None
        for pid, name, desc in sorted(issues):
            if pid != current_pid:
                print(f'{pid}  {name}')
                current_pid = pid
            print(f'  {desc}')
        print()

    if shared_event_issues:
        print(f'{len(shared_event_issues)} events shared between multiple people:\n')
        for line in sorted(shared_event_issues):
            print(f'  {line}')
        print()


if __name__ == '__main__':
    main()
