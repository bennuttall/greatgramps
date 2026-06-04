#!/home/ben/.virtualenvs/gramps/bin/python
"""Set exact census dates on all Census events based on the official UK census dates."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / '.env')
_cfg = os.environ.get('GREATGRAMPS_CONFIG', 'config.yml')
if not Path(_cfg).is_absolute():
    os.environ['GREATGRAMPS_CONFIG'] = str(REPO_ROOT / _cfg)

from greatgramps.settings import get_config
from gramps.gen.db import DBMODE_W, DbTxn
from gramps.gen.lib import Date
from gramps.gen.lib.eventtype import EventType
from gramps.plugins.db.dbapi.sqlite import SQLite


CENSUS_DATES = {
    1841: (6,  6, 1841),
    1851: (30, 3, 1851),
    1861: (7,  4, 1861),
    1871: (2,  4, 1871),
    1881: (3,  4, 1881),
    1891: (5,  4, 1891),
    1901: (31, 3, 1901),
    1911: (2,  4, 1911),
    1921: (19, 6, 1921),
    1939: (29, 9, 1939),
}


def main():
    config = get_config()
    db = SQLite()
    db.load(str(config.validated_db_path), mode=DBMODE_W)

    try:
        to_update = []
        for event in db.iter_events():
            if int(event.get_type()) != EventType.CENSUS:
                continue
            year = event.get_date_object().get_year()
            if year not in CENSUS_DATES:
                continue
            day, month, _ = CENSUS_DATES[year]
            existing = event.get_date_object()
            if existing.get_day() == day and existing.get_month() == month:
                continue
            to_update.append((event, day, month, year))

        if not to_update:
            print('All census events already have correct dates.')
            return

        by_year = {}
        for event, day, month, year in to_update:
            by_year.setdefault(year, []).append(event.get_gramps_id())

        print(f'{len(to_update)} events to update:\n')
        for year in sorted(by_year):
            day, month, _ = CENSUS_DATES[year]
            print(f'  {year} ({day:02d}/{month:02d}/{year}): {len(by_year[year])} events')

        print()
        try:
            answer = input(f'Apply all {len(to_update)} update(s)? [Y/n]: ').strip().lower()
        except (KeyboardInterrupt, EOFError):
            print('\nAborted.')
            return

        if answer == 'n':
            print('Aborted.')
            return

        with DbTxn('Set census dates', db) as trans:
            for event, day, month, year in to_update:
                d = Date()
                d.set_yr_mon_day(year, month, day)
                event.set_date_object(d)
                db.commit_event(event, trans)

        print(f'Updated {len(to_update)} census events.')

    finally:
        db.close()


if __name__ == '__main__':
    main()
