import re
from pathlib import Path

from gramps.plugins.db.dbapi.sqlite import SQLite
from gramps.gen.db import DBMODE_R
from gramps.gen.lib import AttributeType
from gramps.gen.lib.eventtype import EventType
from gramps.gen.utils.alive import probably_alive

from .settings import get_config


def event_url_slug(gramps_id):
    """Convert event gramps_id to a URL/filesystem-safe slug."""
    return re.sub(r'[^\w-]', '_', gramps_id).strip('_') or gramps_id


def _resolve_media_path(path):
    p = Path(path)
    if not p.is_absolute():
        p = Path.home() / p
    return p


def open_db():
    db_path = get_config().validated_db_path
    print(f"Opening Gramps database: {db_path}")
    db = SQLite()
    db.load(str(db_path), mode=DBMODE_R)
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
    urls = {str(u.get_type()): u.get_path() for u in person.get_url_list()}
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
        'grave_url': urls.get('Find a Grave'),
        'ancestry_url': urls.get('Ancestry'),
        'is_living': probably_alive(person, db),
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

MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']


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


def _event_dict(db, event, birth_year, desc=None, desc_url=None, desc_gender=None, label=None, show_age=True):
    etype = int(event.get_type())
    place_h = event.get_place_handle()
    place_obj = db.get_place_from_handle(place_h) if place_h else None
    date_obj = event.get_date_object()
    event_year = date_obj.get_year() or None
    event_month = date_obj.get_month() or 0
    event_day = date_obj.get_day() or 0
    age = max(0, event_year - birth_year - 1) if (show_age and event_year and birth_year) else None
    gid = event.get_gramps_id()
    return {
        'gramps_id': gid,
        'url_slug': event_url_slug(gid),
        'type': label or EVENT_TYPE_LABELS.get(etype, str(event.get_type())),
        'sort': EVENT_SORT_ORDER.index(etype) if etype in EVENT_SORT_ORDER else 99,
        'date': format_date(date_obj),
        'year': event_year,
        'month': event_month,
        'day': event_day,
        'place': place_obj.get_name().get_value() if place_obj else None,
        'place_id': place_obj.get_gramps_id() if place_obj else None,
        'description': desc if desc is not None else (event.get_description() or None),
        'description_url': desc_url,
        'description_gender': desc_gender,
        'age': age,
    }


def get_all_events(db, person):
    birth_year = get_year(get_event(db, person, EventType.BIRTH))
    grave_url = next(
        (url.get_path() for url in person.get_url_list() if str(url.get_type()) == 'Find a Grave'),
        None
    )
    events = []

    for eref in person.get_event_ref_list():
        event = db.get_event_from_handle(eref.get_reference_handle())
        etype = int(event.get_type())
        is_burial = etype == EventType.BURIAL
        is_birth = etype == EventType.BIRTH
        desc_url = grave_url if is_burial else None
        desc = 'Find a Grave' if (is_burial and grave_url and not event.get_description()) else None
        events.append(_event_dict(db, event, birth_year, desc=desc, desc_url=desc_url, show_age=not is_burial and not is_birth))

    for fam_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(fam_handle)
        is_father = family.get_father_handle() == person.get_handle()
        spouse_h = family.get_mother_handle() if is_father else family.get_father_handle()
        spouse = db.get_person_from_handle(spouse_h) if spouse_h else None
        spouse_name = person_data(db, spouse)['full_name'] if spouse else None
        spouse_url = f'../{spouse.get_gramps_id()}/' if spouse else None
        for eref in family.get_event_ref_list():
            event = db.get_event_from_handle(eref.get_reference_handle())
            spouse_gender = spouse.get_gender() if spouse else None
            events.append(_event_dict(db, event, birth_year, desc=spouse_name, desc_url=spouse_url, desc_gender=spouse_gender))

        for child_ref in family.get_child_ref_list():
            child = db.get_person_from_handle(child_ref.get_reference_handle())
            birth = get_event(db, child, EventType.BIRTH)
            if birth:
                child_data = person_data(db, child)
                events.append(_event_dict(
                    db, birth, birth_year,
                    label='Child born',
                    desc=child_data['full_name'],
                    desc_url=f'../{child.get_gramps_id()}/',
                    desc_gender=child.get_gender(),
                ))

    events.sort(key=lambda e: (e['year'] or 9999, e['month'], e['day'], e['sort']))
    return events


FAMILY_REL_LABELS = {
    0: 'Married',
    1: 'Unmarried',
    2: 'Civil union',
    3: 'Unknown',
    4: 'Unknown',
}


def get_spouses(db, person):
    spouses = []
    for fam_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(fam_handle)
        is_father = family.get_father_handle() == person.get_handle()
        spouse_handle = family.get_mother_handle() if is_father else family.get_father_handle()
        spouse = db.get_person_from_handle(spouse_handle) if spouse_handle else None
        rel_type = FAMILY_REL_LABELS.get(int(family.get_relationship()), 'Unknown')
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
            'rel_type': rel_type,
            'marriage': marriage,
        })
    return spouses


def get_siblings(db, person):
    gid = person.get_gramps_id()
    my_family_handles = set(person.get_parent_family_handle_list())
    seen = {gid}
    result = []

    for pfh in my_family_handles:
        family = db.get_family_from_handle(pfh)
        for cref in family.get_child_ref_list():
            child = db.get_person_from_handle(cref.get_reference_handle())
            if child and child.get_gramps_id() not in seen:
                seen.add(child.get_gramps_id())
                result.append({**person_data(db, child), 'half_sibling': False})

    my_parent_handles = set()
    for pfh in my_family_handles:
        family = db.get_family_from_handle(pfh)
        if family.get_father_handle():
            my_parent_handles.add(family.get_father_handle())
        if family.get_mother_handle():
            my_parent_handles.add(family.get_mother_handle())

    for parent_handle in my_parent_handles:
        parent = db.get_person_from_handle(parent_handle)
        for fam_handle in parent.get_family_handle_list():
            if fam_handle in my_family_handles:
                continue
            family = db.get_family_from_handle(fam_handle)
            for cref in family.get_child_ref_list():
                child = db.get_person_from_handle(cref.get_reference_handle())
                if child and child.get_gramps_id() not in seen:
                    seen.add(child.get_gramps_id())
                    result.append({**person_data(db, child), 'half_sibling': True})

    result.sort(key=lambda p: p['birth_year'] or 9999)
    return result


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


def collect_ancestors(db, person, generation=0, ancestors=None, couple_slot=None, _slot_counter=None):
    if ancestors is None:
        ancestors = {}
        _slot_counter = [0]
    gid = person.get_gramps_id()
    if gid in ancestors:
        return ancestors
    data = person_data(db, person)
    data['generation'] = generation
    data['couple_slot'] = couple_slot
    ancestors[gid] = data
    father, mother = get_parents(db, person)
    if father or mother:
        slot = _slot_counter[0]
        _slot_counter[0] += 1
        if father:
            collect_ancestors(db, father, generation + 1, ancestors, slot, _slot_counter)
        if mother:
            collect_ancestors(db, mother, generation + 1, ancestors, slot, _slot_counter)
    return ancestors


def collect_ancestor_tree(db, person, max_gen=4):
    """Return (nodes, grid_rows, grid_cols) for a pedigree chart.

    Each node is person_data plus 'gen' and 'grid_style' (CSS grid placement).
    Ahnentafel numbering: subject=1, father=2, mother=3, paternal GF=4, etc.
    """
    leaves = 1 << max_gen
    nodes = []
    queue = [(person, 1)]
    while queue:
        p, ahn = queue.pop(0)
        gen = ahn.bit_length() - 1
        if gen > max_gen:
            continue
        pos = ahn - (1 << gen)
        span = leaves >> gen
        row_start = pos * span + 1
        row_end = row_start + span
        data = person_data(db, p)
        data['gen'] = gen
        data['grid_style'] = f'grid-column:{gen + 1};grid-row:{row_start}/{row_end}'
        father, mother = get_parents(db, p)
        data['has_parents'] = bool(father or mother)
        data['has_further'] = gen == max_gen and data['has_parents']
        nodes.append(data)
        if father:
            queue.append((father, ahn * 2))
        if mother:
            queue.append((mother, ahn * 2 + 1))
    return nodes, leaves, max_gen + 1


def collect_all_descendants(db, person):
    """Returns {gramps_id: person_data} for all descendants, each with a 'generation' key."""
    result = {}
    seen = {person.get_gramps_id()}
    queue = [(child, 1) for child in get_children(db, person)]
    while queue:
        p, gen = queue.pop(0)
        gid = p.get_gramps_id()
        if gid in seen:
            continue
        seen.add(gid)
        data = person_data(db, p)
        data['generation'] = gen
        result[gid] = data
        queue.extend((child, gen + 1) for child in get_children(db, p))
    return result


def group_descendants_by_generation(descendants):
    by_gen = {}
    for data in descendants.values():
        by_gen.setdefault(data['generation'], []).append(data)
    return [
        {'gen': g, 'people': sorted(people, key=lambda p: p['birth_year'] or 9999)}
        for g, people in sorted(by_gen.items())
    ]


def count_descendants(db, person):
    count = 0
    seen = set()
    queue = [person]
    while queue:
        p = queue.pop(0)
        gid = p.get_gramps_id()
        if gid in seen:
            continue
        seen.add(gid)
        children = get_children(db, p)
        count += len(children)
        queue.extend(children)
    return count


def collect_descendant_tree(db, person, max_gen=4):
    """Return (nodes, grid_rows, grid_cols) for a descendants chart.

    Grid: row = generation (1-indexed), column = leaf position (1-indexed).
    """
    def count_leaves(p, gen):
        if gen >= max_gen:
            return 1
        children = get_children(db, p)
        if not children:
            return 1
        return sum(count_leaves(c, gen + 1) for c in children)

    nodes = []

    def place_nodes(p, gen, col_start):
        data = person_data(db, p)
        all_children = get_children(db, p)
        visible_children = all_children if gen < max_gen else []
        leaf_count = count_leaves(p, gen)
        data['gen'] = gen
        data['grid_style'] = f'grid-row:{gen + 1};grid-column:{col_start + 1}/{col_start + leaf_count + 1}'
        data['num_children'] = len(all_children)
        data['has_children'] = bool(all_children)
        data['has_further'] = gen == max_gen and bool(all_children)
        nodes.append(data)
        cursor = col_start
        for child in visible_children:
            place_nodes(child, gen + 1, cursor)
            cursor += count_leaves(child, gen + 1)

    place_nodes(person, 0, 0)
    total_leaves = count_leaves(person, 0)
    return nodes, max_gen + 1, total_leaves


def place_data(place):
    return {
        'gramps_id': place.get_gramps_id(),
        'name': place.get_name().get_value(),
        'type': str(place.get_type()),
        'lat': place.get_latitude() or None,
        'lon': place.get_longitude() or None,
        'parent_handles': [ref.get_reference_handle() for ref in place.get_placeref_list()],
    }


def build_place_event_index(db):
    """Returns (place_handle -> [event_dict], event_handle -> [person_data]) indexes."""
    from greatgramps.gramps_data import format_date, EVENT_TYPE_LABELS

    # event_handle -> list of involved parties as dicts with 'people' and 'couple'
    event_parties = {}

    for person in db.iter_people():
        pdata = person_data(db, person)
        for eref in person.get_event_ref_list():
            h = eref.get_reference_handle()
            event_parties.setdefault(h, {'people': [], 'couple': None})
            event_parties[h]['people'].append(pdata)

    for family in db.iter_families():
        fh = family.get_father_handle()
        mh = family.get_mother_handle()
        father = person_data(db, db.get_person_from_handle(fh)) if fh else None
        mother = person_data(db, db.get_person_from_handle(mh)) if mh else None
        for eref in family.get_event_ref_list():
            h = eref.get_reference_handle()
            event_parties.setdefault(h, {'people': [], 'couple': None})
            event_parties[h]['couple'] = (father, mother)

    place_index = {}
    for event in db.iter_events():
        ph = event.get_place_handle()
        if not ph:
            continue
        etype = int(event.get_type())
        parties = event_parties.get(event.get_handle(), {'people': [], 'couple': None})
        entry = {
            'type': EVENT_TYPE_LABELS.get(etype, str(event.get_type())),
            'date': format_date(event.get_date_object()),
            'year': event.get_date_object().get_year() or None,
            'people': parties['people'],
            'couple': parties['couple'],
        }
        place_index.setdefault(ph, []).append(entry)

    for events in place_index.values():
        events.sort(key=lambda e: e['year'] or 9999)

    return place_index


def build_event_list(db, ancestor_ids):
    """Returns all events with an is_ancestor_event flag, sorted by year."""
    event_parties = {}

    for person in db.iter_people():
        pdata = person_data(db, person)
        for eref in person.get_event_ref_list():
            h = eref.get_reference_handle()
            event_parties.setdefault(h, {'people': [], 'couple': None})
            event_parties[h]['people'].append(pdata)

    for family in db.iter_families():
        fh = family.get_father_handle()
        mh = family.get_mother_handle()
        father = person_data(db, db.get_person_from_handle(fh)) if fh else None
        mother = person_data(db, db.get_person_from_handle(mh)) if mh else None
        for eref in family.get_event_ref_list():
            h = eref.get_reference_handle()
            event_parties.setdefault(h, {'people': [], 'couple': None})
            event_parties[h]['couple'] = (father, mother)

    events = []
    for event in db.iter_events():
        parties = event_parties.get(event.get_handle(), {'people': [], 'couple': None})
        people = parties['people']
        couple = parties['couple']
        all_people = list(people) + [p for p in couple if p] if couple else list(people)
        year = event.get_date_object().get_year() or None
        if not year:
            continue
        is_ancestor_event = any(p['gramps_id'] in ancestor_ids for p in all_people)
        etype = int(event.get_type())
        place_h = event.get_place_handle()
        place_obj = db.get_place_from_handle(place_h) if place_h else None
        gid = event.get_gramps_id()
        events.append({
            'gramps_id': gid,
            'url_slug': event_url_slug(gid),
            'type': EVENT_TYPE_LABELS.get(etype, str(event.get_type())),
            'date': format_date(event.get_date_object()),
            'year': year,
            'people': people,
            'couple': couple,
            'place': place_obj.get_name().get_value() if place_obj else None,
            'place_id': place_obj.get_gramps_id() if place_obj else None,
            'is_ancestor_event': is_ancestor_event,
        })

    events.sort(key=lambda e: e['year'] or 9999)
    return events


def build_event_pages_data(db):
    """Returns {gramps_id: event_detail} for all events, with deduplicated participants."""
    event_parties = {}
    for person in db.iter_people():
        pdata = person_data(db, person)
        for eref in person.get_event_ref_list():
            h = eref.get_reference_handle()
            event_parties.setdefault(h, {'people': [], 'couple': None})
            event_parties[h]['people'].append(pdata)
    for family in db.iter_families():
        fh = family.get_father_handle()
        mh = family.get_mother_handle()
        father = person_data(db, db.get_person_from_handle(fh)) if fh else None
        mother = person_data(db, db.get_person_from_handle(mh)) if mh else None
        children = sorted(
            [person_data(db, db.get_person_from_handle(cr.get_reference_handle()))
             for cr in family.get_child_ref_list()],
            key=lambda p: p['birth_year'] or 9999,
        )
        for eref in family.get_event_ref_list():
            h = eref.get_reference_handle()
            event_parties.setdefault(h, {'people': [], 'couple': None, 'children': []})
            event_parties[h]['couple'] = (father, mother)
            event_parties[h]['children'] = children

    result = {}
    for event in db.iter_events():
        handle = event.get_handle()
        parties = event_parties.get(handle, {'people': [], 'couple': None, 'children': []})
        etype = int(event.get_type())
        place_h = event.get_place_handle()
        place_obj = db.get_place_from_handle(place_h) if place_h else None
        notes = []
        for note_handle in event.get_note_list():
            note = db.get_note_from_handle(note_handle)
            text = str(note.get()).strip()
            if text:
                notes.append(text)
        seen = set()
        participants = []
        couple = parties['couple']
        if couple:
            for p in couple:
                if p and p['gramps_id'] not in seen:
                    seen.add(p['gramps_id'])
                    participants.append(p)
        for p in parties['people']:
            if p['gramps_id'] not in seen:
                seen.add(p['gramps_id'])
                participants.append(p)
        gid = event.get_gramps_id()
        result[event_url_slug(gid)] = {
            'gramps_id': gid,
            'url_slug': event_url_slug(gid),
            'type': EVENT_TYPE_LABELS.get(etype, str(event.get_type())),
            'date': format_date(event.get_date_object()),
            'year': event.get_date_object().get_year() or None,
            'place': place_obj.get_name().get_value() if place_obj else None,
            'place_id': place_obj.get_gramps_id() if place_obj else None,
            'description': event.get_description() or None,
            'notes': notes,
            'people': participants,
            'couple': couple,
            'children': parties.get('children', []),
            'photos': get_event_photos(db, event),
        }
    return result


def build_birthday_list(db):
    """Returns birthdays grouped by month, each month having a list of days with people."""
    by_date = {}
    for person in db.iter_people():
        birth = get_event(db, person, EventType.BIRTH)
        if not birth:
            continue
        date_obj = birth.get_date_object()
        month = date_obj.get_month()
        day = date_obj.get_day()
        if not month or not day:
            continue
        pdata = person_data(db, person)
        by_date.setdefault((month, day), []).append(pdata)

    for people in by_date.values():
        people.sort(key=lambda p: p['birth_year'] or 9999)

    by_month = {}
    for (month, day), people in sorted(by_date.items()):
        by_month.setdefault(month, []).append({'day': day, 'people': people})

    return [
        {'month': month, 'month_name': MONTH_NAMES[month], 'days': days}
        for month, days in sorted(by_month.items())
    ]


def _collect_photos(db, obj):
    photos = []
    for ref in obj.get_media_list():
        media = db.get_media_from_handle(ref.get_reference_handle())
        if not media.get_mime_type().startswith('image/'):
            continue
        src = _resolve_media_path(media.get_path())
        if not src.exists():
            continue
        photos.append({
            'media_id': media.get_gramps_id(),
            'src': src,
            'rect': ref.get_rectangle(),
            'description': media.get_description(),
        })
    return photos


def get_occupations(person) -> list[dict]:
    occupations = []
    for attr in person.get_attribute_list():
        if attr.get_type() == AttributeType(AttributeType.OCCUPATION):
            value = attr.get_value()
            m = re.search(r'\((\d{4})\)\s*$', value)
            year = int(m.group(1)) if m else None
            label = value[:m.start()].strip() if m else value
            occupations.append({'label': label, 'year': year})
    return sorted(occupations, key=lambda o: o['year'] or 0)


def get_photos(db, person):
    return _collect_photos(db, person)


def get_event_photos(db, event):
    return _collect_photos(db, event)
