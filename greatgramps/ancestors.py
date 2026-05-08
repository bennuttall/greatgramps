#!/home/ben/.virtualenvs/gramps/bin/python
from gramps.plugins.db.dbapi.sqlite import SQLite
from gramps.gen.db import DBMODE_R
from gramps.gen.lib.eventtype import EventType

DB_PATH = '/home/ben/.gramps/grampsdb/678295e2'
ME = 'I0018'
GENERATIONS = 3


def get_birth_year(db, person):
    for eref in person.get_event_ref_list():
        event = db.get_event_from_handle(eref.get_reference_handle())
        if event.get_type() == EventType.BIRTH:
            date = event.get_date_object()
            year = date.get_year()
            return year if year else None
    return None


def get_parents(db, person):
    parent_families = person.get_parent_family_handle_list()
    if not parent_families:
        return None, None
    family = db.get_family_from_handle(parent_families[0])
    father_handle = family.get_father_handle()
    mother_handle = family.get_mother_handle()
    father = db.get_person_from_handle(father_handle) if father_handle else None
    mother = db.get_person_from_handle(mother_handle) if mother_handle else None
    return father, mother


def print_ancestors(db, person, generation=0, max_generations=GENERATIONS, label=''):
    name = person.get_primary_name().get_name()
    year = get_birth_year(db, person)
    year_str = f' (b. {year})' if year else ''
    indent = '  ' * generation
    prefix = f'{label}: ' if label else ''
    print(f'{indent}{prefix}{name}{year_str}')

    if generation < max_generations:
        father, mother = get_parents(db, person)
        if father:
            print_ancestors(db, father, generation + 1, max_generations, 'Father')
        if mother:
            print_ancestors(db, mother, generation + 1, max_generations, 'Mother')


db = SQLite()
db.load(DB_PATH, mode=DBMODE_R)

me = db.get_person_from_gramps_id(ME)
print_ancestors(db, me)

db.close()
