import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')

from gramps.plugins.db.dbapi.sqlite import SQLite
from gramps.gen.db import DBMODE_R
from gramps.gen.lib.eventtype import EventType

DB_PATH = '/home/ben/.gramps/grampsdb/678295e2'
ME = 'I0018'


def open_db():
    db = SQLite()
    db.load(DB_PATH, mode=DBMODE_R)
    return db


def get_event(db, person, event_type):
    for eref in person.get_event_ref_list():
        event = db.get_event_from_handle(eref.get_reference_handle())
        if event.get_type() == event_type:
            return event
    return None


def get_year(event):
    if event is None:
        return None
    year = event.get_date_object().get_year()
    return year if year else None


def get_place_name(db, event):
    if event is None:
        return None
    place_handle = event.get_place_handle()
    if not place_handle:
        return None
    place = db.get_place_from_handle(place_handle)
    return place.get_name().get_value() if place else None


def person_data(db, person):
    birth = get_event(db, person, EventType.BIRTH)
    death = get_event(db, person, EventType.DEATH)
    name = person.get_primary_name()
    return {
        'gramps_id': person.get_gramps_id(),
        'given': name.get_first_name(),
        'surname': name.get_surname(),
        'full_name': f'{name.get_first_name()} {name.get_surname()}'.strip(),
        'birth_year': get_year(birth),
        'birth_place': get_place_name(db, birth),
        'death_year': get_year(death),
        'death_place': get_place_name(db, death),
        'gender': person.get_gender(),
    }


def get_parents(db, person):
    handles = person.get_parent_family_handle_list()
    if not handles:
        return None, None
    family = db.get_family_from_handle(handles[0])
    father_handle = family.get_father_handle()
    mother_handle = family.get_mother_handle()
    father = db.get_person_from_handle(father_handle) if father_handle else None
    mother = db.get_person_from_handle(mother_handle) if mother_handle else None
    return father, mother


def get_children(db, person):
    children = []
    for fam_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(fam_handle)
        for child_ref in family.get_child_ref_list():
            child = db.get_person_from_handle(child_ref.get_reference_handle())
            if child:
                children.append(child)
    return children


def collect_all_people(db):
    return {
        p.get_gramps_id(): person_data(db, p)
        for p in db.iter_people()
    }


def collect_ancestors(db, person, generation=0, ancestors=None):
    if ancestors is None:
        ancestors = {}
    gid = person.get_gramps_id()
    if gid in ancestors:
        return ancestors
    data = person_data(db, person)
    data['generation'] = generation
    ancestors[gid] = data
    father, mother = get_parents(db, person)
    if father:
        collect_ancestors(db, father, generation + 1, ancestors)
    if mother:
        collect_ancestors(db, mother, generation + 1, ancestors)
    return ancestors
