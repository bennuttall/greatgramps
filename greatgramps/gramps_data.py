import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')

from gramps.plugins.db.dbapi.sqlite import SQLite
from gramps.gen.db import DBMODE_R
from gramps.gen.lib.eventtype import EventType

from greatgramps.settings import get_config


def open_db():
    db = SQLite()
    db.load(str(get_config().db_path), mode=DBMODE_R)
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
    grave_url = next(
        (url.get_path() for url in person.get_url_list() if str(url.get_type()) == 'Grave'),
        None
    )
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
        'grave_url': grave_url,
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


EVENT_TYPE_LABELS = {
    EventType.BIRTH: 'Birth',
    EventType.DEATH: 'Death',
    EventType.BURIAL: 'Burial',
    EventType.BAPTISM: 'Baptism',
    EventType.CONFIRMATION: 'Confirmation',
    EventType.MARRIAGE: 'Marriage',
    EventType.DIVORCE: 'Divorce',
    EventType.OCCUPATION: 'Occupation',
    EventType.RESIDENCE: 'Residence',
    EventType.CENSUS: 'Census',
    EventType.MILITARY_SERV: 'Military service',
    EventType.EDUCATION: 'Education',
    EventType.GRADUATION: 'Graduation',
    EventType.RETIREMENT: 'Retirement',
}

EVENT_SORT_ORDER = list(EVENT_TYPE_LABELS.keys())


MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def format_date(date_obj):
    if not date_obj or not date_obj.get_year():
        return None
    year = date_obj.get_year()
    month = date_obj.get_month()
    day = date_obj.get_day()
    if day and month:
        return f'{day} {MONTHS[month]} {year}'
    if month:
        return f'{MONTHS[month]} {year}'
    return str(year)


def get_all_events(db, person):
    birth_year = get_year(get_event(db, person, EventType.BIRTH))
    events = []
    for eref in person.get_event_ref_list():
        event = db.get_event_from_handle(eref.get_reference_handle())
        etype = int(event.get_type())
        label = EVENT_TYPE_LABELS.get(etype, str(event.get_type()))
        date_str = format_date(event.get_date_object())
        place_h = event.get_place_handle()
        place = db.get_place_from_handle(place_h).get_name().get_value() if place_h else None
        desc = event.get_description() or None
        death_year = get_year(event) if etype == EventType.DEATH else None
        age = (death_year - birth_year) if (death_year and birth_year) else None
        events.append({
            'type': label,
            'sort': EVENT_SORT_ORDER.index(etype) if etype in EVENT_SORT_ORDER else 99,
            'date': date_str,
            'place': place,
            'description': desc,
            'age': age,
        })
    events.sort(key=lambda e: e['sort'])
    return events


def get_spouses(db, person):
    spouses = []
    for fam_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(fam_handle)
        is_father = family.get_father_handle() == person.get_handle()
        spouse_handle = family.get_mother_handle() if is_father else family.get_father_handle()
        spouse = db.get_person_from_handle(spouse_handle) if spouse_handle else None
        marriage = None
        for eref in family.get_event_ref_list():
            event = db.get_event_from_handle(eref.get_reference_handle())
            if int(event.get_type()) == EventType.MARRIAGE:
                place_h = event.get_place_handle()
                marriage = {
                    'date': format_date(event.get_date_object()),
                    'place': db.get_place_from_handle(place_h).get_name().get_value() if place_h else None,
                }
                break
        spouses.append({
            'person': person_data(db, spouse) if spouse else None,
            'marriage': marriage,
        })
    return spouses


def get_siblings(db, person):
    siblings = []
    for pfh in person.get_parent_family_handle_list():
        family = db.get_family_from_handle(pfh)
        for cref in family.get_child_ref_list():
            child = db.get_person_from_handle(cref.get_reference_handle())
            if child and child.get_gramps_id() != person.get_gramps_id():
                siblings.append(person_data(db, child))
    return siblings


def ancestors_with_distances(db, person):
    """Returns {gramps_id: distance} for all ancestors including self (distance 0)."""
    result = {}
    queue = [(person, 0)]
    while queue:
        p, dist = queue.pop(0)
        gid = p.get_gramps_id()
        if gid in result:
            continue
        result[gid] = dist
        father, mother = get_parents(db, p)
        if father:
            queue.append((father, dist + 1))
        if mother:
            queue.append((mother, dist + 1))
    return result


def _ordinal(n):
    return {1: '1st', 2: '2nd', 3: '3rd'}.get(n, f'{n}th')


def _great_prefix(n):
    return 'great-' if n == 1 else f'{_ordinal(n)} great-'


FEMALE, MALE = 0, 1


def relationship_label(u, d, gender=2):
    """Compute relationship label given steps up (u) and steps down (d) from the LCA."""
    g = {FEMALE: 'f', MALE: 'm'}.get(gender, '')

    if u == 0 and d == 0:
        return 'you'

    if d == 0:  # direct ancestor
        if u == 1:
            return {'f': 'mother', 'm': 'father'}.get(g, 'parent')
        if u == 2:
            return {'f': 'grandmother', 'm': 'grandfather'}.get(g, 'grandparent')
        p = _great_prefix(u - 2)
        return {'f': f'{p}grandmother', 'm': f'{p}grandfather'}.get(g, f'{p}grandparent')

    if u == 0:  # direct descendant
        if d == 1:
            return {'f': 'daughter', 'm': 'son'}.get(g, 'child')
        if d == 2:
            return {'f': 'granddaughter', 'm': 'grandson'}.get(g, 'grandchild')
        p = _great_prefix(d - 2)
        return {'f': f'{p}granddaughter', 'm': f'{p}grandson'}.get(g, f'{p}grandchild')

    if u == 1 and d == 1:
        return {'f': 'sister', 'm': 'brother'}.get(g, 'sibling')

    if d == 1:  # aunt/uncle line
        p = '' if u == 2 else _great_prefix(u - 2)
        return {'f': f'{p}aunt', 'm': f'{p}uncle'}.get(g, f'{p}aunt/uncle')

    if u == 1:  # niece/nephew line
        p = '' if d == 2 else _great_prefix(d - 2)
        return {'f': f'{p}niece', 'm': f'{p}nephew'}.get(g, f'{p}niece/nephew')

    # Cousins
    degree = min(u, d) - 1
    removal = abs(u - d)
    label = f'{_ordinal(degree)} cousin'
    if removal == 1:
        label += ' once removed'
    elif removal == 2:
        label += ' twice removed'
    elif removal > 2:
        label += f' {removal} times removed'
    return label


def get_relation_to_me(db, me_ancestors, person, gender=2):
    """Returns relationship label between ME and person, e.g. 'grandmother'."""
    other_ancestors = ancestors_with_distances(db, person)
    common = set(me_ancestors) & set(other_ancestors)
    if not common:
        return None
    lca = min(common, key=lambda gid: me_ancestors[gid] + other_ancestors[gid])
    u = me_ancestors[lca]
    d = other_ancestors[lca]
    return relationship_label(u, d, gender)


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
