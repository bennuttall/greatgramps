import re
from pathlib import Path

from gramps.plugins.db.dbapi.sqlite import SQLite
from gramps.gen.db import DBMODE_R
from gramps.gen.lib import AttributeType
from gramps.gen.lib.eventtype import EventType
from gramps.gen.utils.alive import probably_alive


def event_url_slug(gramps_id):
    """Convert event gramps_id to a URL/filesystem-safe slug."""
    return re.sub(r'[^\w-]', '_', gramps_id).strip('_') or gramps_id


def _resolve_media_path(db, path, db_path):
    p = Path(path)
    if not p.is_absolute():
        base = db.get_mediapath() or db_path
        p = Path(base) / p
    return p


def open_db(db_path):
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


def _alt_names(db, person, primary_name):
    result = []
    seen_surnames = {primary_name.get_surname()}
    for n in person.get_alternate_names():
        entry = {
            'given': n.get_first_name(),
            'surname': n.get_surname(),
            'full_name': f'{n.get_first_name()} {n.get_surname()}'.strip(),
            'type': str(n.get_type()),
        }
        result.append(entry)
        seen_surnames.add(n.get_surname())
    if person.get_gender() != FEMALE:
        return result
    for fam_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(fam_handle)
        if int(family.get_relationship()) not in (0, 2):  # married or civil union only
            continue
        spouse_handle = family.get_father_handle()
        if not spouse_handle or spouse_handle == person.get_handle():
            continue
        spouse = db.get_person_from_handle(spouse_handle)
        if not spouse:
            continue
        spouse_surname = spouse.get_primary_name().get_surname()
        if spouse_surname and spouse_surname not in seen_surnames:
            result.append({
                'given': '',
                'surname': spouse_surname,
                'full_name': spouse_surname,
                'type': 'Married Name',
            })
            seen_surnames.add(spouse_surname)
    return result


def person_data(db, person, *, include_private=False):
    is_private = person.get_privacy()
    redact = is_private and not include_private
    birth = None if redact else get_event(db, person, EventType.BIRTH)
    death = None if redact else get_event(db, person, EventType.DEATH)
    name = person.get_primary_name()
    urls = {} if redact else {str(u.get_type()): u.get_path() for u in person.get_url_list()}
    tag_names = sorted(db.get_tag_from_handle(h).get_name() for h in person.get_tag_list())
    return {
        'gramps_id': person.get_gramps_id(),
        'given': name.get_first_name(),
        'surname': name.get_surname(),
        'full_name': f'{name.get_first_name()} {name.get_surname()}'.strip() or '[Unknown]',
        'birth_year': get_year(birth),
        'birth_place': get_place_name(db, birth),
        'death_year': get_year(death),
        'death_place': get_place_name(db, death),
        'gender': person.get_gender(),
        'grave_url': urls.get('Find a Grave'),
        'ancestry_url': urls.get('Ancestry'),
        'external_links': [] if redact else sorted(
            [{'label': str(u.get_type()), 'url': u.get_path()} for u in person.get_url_list()],
            key=lambda x: (0 if x['label'] == 'Ancestry' else 1, x['label']),
        ),
        'is_living': probably_alive(person, db),
        'alt_names': [] if redact else _alt_names(db, person, name),
        'tags': tag_names,
        'is_private': redact,
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
    EventType.CREMATION: 'Cremation',
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
    _post_death = {EventType.BURIAL, EventType.CREMATION, EventType.PROBATE}
    age = max(0, event_year - birth_year - 1) if (show_age and etype not in _post_death and event_year and birth_year) else None
    gid = event.get_gramps_id()
    has_photo = any(
        db.get_media_from_handle(ref.get_reference_handle()).get_mime_type().startswith('image/')
        for ref in event.get_media_list()
    )
    tag_names = {db.get_tag_from_handle(h).get_name() for h in event.get_tag_list()}
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
        'has_photo': has_photo,
        'is_interesting': 'Interesting' in tag_names,
        'is_conflict': 'Conflict' in tag_names,
    }


def get_all_events(db, person, *, include_private=False):
    birth_year = get_year(get_event(db, person, EventType.BIRTH))
    grave_url = next(
        (url.get_path() for url in person.get_url_list() if str(url.get_type()) == 'Find a Grave'),
        None
    )
    events = []

    for eref in person.get_event_ref_list():
        event = db.get_event_from_handle(eref.get_reference_handle())
        if event.get_privacy() and not include_private:
            continue
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
        spouse_name = person_data(db, spouse, include_private=include_private)['full_name'] if spouse else None
        spouse_url = f'/people/{spouse.get_gramps_id()}/' if spouse else None
        for eref in family.get_event_ref_list():
            event = db.get_event_from_handle(eref.get_reference_handle())
            if event.get_privacy() and not include_private:
                continue
            spouse_gender = spouse.get_gender() if spouse else None
            events.append(_event_dict(db, event, birth_year, desc=spouse_name, desc_url=spouse_url, desc_gender=spouse_gender))

        for child_ref in family.get_child_ref_list():
            child = db.get_person_from_handle(child_ref.get_reference_handle())
            birth = get_event(db, child, EventType.BIRTH)
            if birth and not (birth.get_privacy() and not include_private):
                child_data = person_data(db, child, include_private=include_private)
                events.append(_event_dict(
                    db, birth, birth_year,
                    label='Child born',
                    desc=child_data['full_name'],
                    desc_url=f'/people/{child.get_gramps_id()}/',
                    desc_gender=child.get_gender(),
                ))

    _LAST = {'Death': 0, 'Burial': 1, 'Cremation': 1, 'Probate': 1}
    events.sort(key=lambda e: (
        0 if e['type'] == 'Birth' else (2 if e['type'] in _LAST else 1),
        _LAST.get(e['type'], 0),
        e['year'] or 9999,
        e['month'],
        e['day'],
        e['sort'],
    ))
    return events


FAMILY_REL_LABELS = {
    0: 'Married',
    1: 'Unmarried',
    2: 'Civil union',
    3: 'Unknown',
    4: 'Unknown',
}


def get_spouses(db, person, *, include_private=False):
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
            if event.get_privacy() and not include_private:
                continue
            if int(event.get_type()) == EventType.MARRIAGE:
                place_h = event.get_place_handle()
                marriage = {
                    'date': format_date(event.get_date_object()),
                    'year': event.get_date_object().get_year() or None,
                    'place': db.get_place_from_handle(place_h).get_name().get_value() if place_h else None,
                }
                break
        spouses.append({
            'person': person_data(db, spouse, include_private=include_private) if spouse else None,
            'rel_type': rel_type,
            'marriage': marriage,
        })
    return spouses


def get_siblings(db, person, *, include_private=False):
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
                result.append({**person_data(db, child, include_private=include_private), 'half_sibling': False})

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
                    result.append({**person_data(db, child, include_private=include_private), 'half_sibling': True})

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


def ancestors_with_ahnentafel(db, person):
    """Returns {gramps_id: ahnentafel_number} for all ancestors including self (1).

    Ahnentafel numbering: subject=1, father=2, mother=3, paternal GF=4,
    paternal GM=5, maternal GF=6, maternal GM=7, etc. Lower numbers are
    more paternal; couples share consecutive numbers (2n, 2n+1).
    """
    result = {}
    queue = [(person, 1)]
    while queue:
        p, num = queue.pop(0)
        gid = p.get_gramps_id()
        if gid in result:
            continue
        result[gid] = num
        father, mother = get_parents(db, p)
        if father:
            queue.append((father, 2 * num))
        if mother:
            queue.append((mother, 2 * num + 1))
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


def is_related_by_marriage(db, me_ancestors, person):
    """Returns True if person is a spouse of a blood relative of mine."""
    me_ancestor_set = set(me_ancestors)
    for fam_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(fam_handle)
        if int(family.get_relationship()) not in (0, 2):  # married or civil union only
            continue
        for handle in [family.get_father_handle(), family.get_mother_handle()]:
            if handle and handle != person.get_handle():
                spouse = db.get_person_from_handle(handle)
                if spouse:
                    spouse_ancestors = ancestors_with_distances(db, spouse)
                    if me_ancestor_set & set(spouse_ancestors):
                        return True
    return False


def get_by_marriage_relation(db, me_ancestors, person, gender=2):
    """Returns a relation label for a person related by marriage, e.g. 'uncle' or 'step-grandfather'."""
    me_ancestor_set = set(me_ancestors)
    for fam_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(fam_handle)
        if int(family.get_relationship()) not in (0, 2):  # married or civil union only
            continue
        for handle in [family.get_father_handle(), family.get_mother_handle()]:
            if handle and handle != person.get_handle():
                spouse = db.get_person_from_handle(handle)
                if spouse:
                    spouse_ancestors = ancestors_with_distances(db, spouse)
                    common = me_ancestor_set & set(spouse_ancestors)
                    if common:
                        lca = min(common, key=lambda gid: me_ancestors[gid] + spouse_ancestors[gid])
                        u = me_ancestors[lca]
                        d = spouse_ancestors[lca]
                        if u == 0 and d == 0:
                            return {FEMALE: 'wife', MALE: 'husband'}.get(gender, 'spouse')
                        if u == 1 and d == 1:
                            return None  # sibling's spouse — skip
                        label = relationship_label(u, d, gender)
                        if d == 0:
                            other_spouses = [
                                db.get_person_from_handle(sh)
                                for fh in spouse.get_family_handle_list()
                                for fam in [db.get_family_from_handle(fh)]
                                for sh in [fam.get_father_handle(), fam.get_mother_handle()]
                                if sh and sh != spouse.get_handle() and sh != person.get_handle()
                            ]
                            if any(s and probably_alive(s, db) for s in other_spouses):
                                return None
                            label = 'step-' + label
                        return label
    return None


def get_children(db, person):
    children = []
    for fam_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(fam_handle)
        for child_ref in family.get_child_ref_list():
            child = db.get_person_from_handle(child_ref.get_reference_handle())
            if child:
                children.append(child)
    return children


def collect_all_people(db, *, include_private=False):
    return {
        p.get_gramps_id(): person_data(db, p, include_private=include_private)
        for p in db.iter_people()
    }


def collect_ancestors(db, person, generation=0, ancestors=None, couple_slot=None, _slot_counter=None, *, include_private=False):
    if ancestors is None:
        ancestors = {}
        _slot_counter = [0]
    gid = person.get_gramps_id()
    if gid in ancestors:
        return ancestors
    data = person_data(db, person, include_private=include_private)
    data['generation'] = generation
    data['couple_slot'] = couple_slot
    ancestors[gid] = data
    father, mother = get_parents(db, person)
    if father or mother:
        slot = _slot_counter[0]
        _slot_counter[0] += 1
        if father:
            collect_ancestors(db, father, generation + 1, ancestors, slot, _slot_counter, include_private=include_private)
        if mother:
            collect_ancestors(db, mother, generation + 1, ancestors, slot, _slot_counter, include_private=include_private)
    return ancestors


def collect_ancestor_tree(db, person, max_gen=4, *, include_private=False):
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
        data = person_data(db, p, include_private=include_private)
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


def collect_all_descendants(db, person, *, include_private=False):
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
        data = person_data(db, p, include_private=include_private)
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


def collect_descendant_tree(db, person, max_gen=4, *, include_private=False):
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
        data = person_data(db, p, include_private=include_private)
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


def build_place_event_index(db, *, include_private=False):
    """Returns (place_handle -> [event_dict], event_handle -> [person_data]) indexes."""
    from greatgramps.gramps_data import format_date, EVENT_TYPE_LABELS

    # event_handle -> list of involved parties as dicts with 'people' and 'couple'
    event_parties = {}

    for person in db.iter_people():
        pdata = person_data(db, person, include_private=include_private)
        for eref in person.get_event_ref_list():
            h = eref.get_reference_handle()
            event_parties.setdefault(h, {'people': [], 'couple': None})
            event_parties[h]['people'].append(pdata)

    for family in db.iter_families():
        fh = family.get_father_handle()
        mh = family.get_mother_handle()
        father = person_data(db, db.get_person_from_handle(fh), include_private=include_private) if fh else None
        mother = person_data(db, db.get_person_from_handle(mh), include_private=include_private) if mh else None
        for eref in family.get_event_ref_list():
            h = eref.get_reference_handle()
            event_parties.setdefault(h, {'people': [], 'couple': None})
            event_parties[h]['couple'] = (father, mother)

    place_index = {}
    for event in db.iter_events():
        if event.get_privacy() and not include_private:
            continue
        ph = event.get_place_handle()
        if not ph:
            continue
        etype = int(event.get_type())
        parties = event_parties.get(event.get_handle(), {'people': [], 'couple': None})
        gid = event.get_gramps_id()
        all_people = list(parties['people']) + [p for p in parties['couple'] if p] if parties['couple'] else list(parties['people'])
        has_photo = any(
            db.get_media_from_handle(ref.get_reference_handle()).get_mime_type().startswith('image/')
            for ref in event.get_media_list()
        )
        grave_url = None
        if etype == int(EventType.BURIAL):
            grave_url = next((p['grave_url'] for p in all_people if p.get('grave_url')), None)
        tag_names = {db.get_tag_from_handle(h).get_name() for h in event.get_tag_list()}
        entry = {
            'type': EVENT_TYPE_LABELS.get(etype, str(event.get_type())),
            'date': format_date(event.get_date_object()),
            'year': event.get_date_object().get_year() or None,
            'people': parties['people'],
            'couple': parties['couple'],
            'gramps_id': gid,
            'url_slug': event_url_slug(gid),
            'has_photo': has_photo,
            'grave_url': grave_url,
            'is_interesting': 'Interesting' in tag_names,
            'is_conflict': 'Conflict' in tag_names,
        }
        place_index.setdefault(ph, []).append(entry)

    for events in place_index.values():
        events.sort(key=lambda e: e['year'] or 9999)

    return place_index


def build_event_list(db, ancestor_ids, *, include_private=False):
    """Returns all events with an is_ancestor_event flag, sorted by year."""
    event_parties = {}

    for person in db.iter_people():
        pdata = person_data(db, person, include_private=include_private)
        for eref in person.get_event_ref_list():
            h = eref.get_reference_handle()
            event_parties.setdefault(h, {'people': [], 'couple': None})
            event_parties[h]['people'].append(pdata)

    for family in db.iter_families():
        fh = family.get_father_handle()
        mh = family.get_mother_handle()
        father = person_data(db, db.get_person_from_handle(fh), include_private=include_private) if fh else None
        mother = person_data(db, db.get_person_from_handle(mh), include_private=include_private) if mh else None
        for eref in family.get_event_ref_list():
            h = eref.get_reference_handle()
            event_parties.setdefault(h, {'people': [], 'couple': None})
            event_parties[h]['couple'] = (father, mother)

    events = []
    for event in db.iter_events():
        if event.get_privacy() and not include_private:
            continue
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
        has_photo = any(
            db.get_media_from_handle(ref.get_reference_handle()).get_mime_type().startswith('image/')
            for ref in event.get_media_list()
        )
        lat = float(place_obj.get_latitude()) if place_obj and place_obj.get_latitude() else None
        lon = float(place_obj.get_longitude()) if place_obj and place_obj.get_longitude() else None
        grave_url = None
        if etype == int(EventType.BURIAL):
            grave_url = next((p['grave_url'] for p in all_people if p.get('grave_url')), None)
        tag_names = sorted(db.get_tag_from_handle(h).get_name() for h in event.get_tag_list())
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
            'lat': lat,
            'lon': lon,
            'is_ancestor_event': is_ancestor_event,
            'has_photo': has_photo,
            'grave_url': grave_url,
            'tags': tag_names,
            'is_interesting': 'Interesting' in tag_names,
            'is_conflict': 'Conflict' in tag_names,
        })

    events.sort(key=lambda e: e['year'] or 9999)
    return events


def build_event_pages_data(db, db_path, *, include_private=False):
    """Returns {gramps_id: event_detail} for all events, with deduplicated participants."""
    event_parties = {}
    for person in db.iter_people():
        pdata = person_data(db, person, include_private=include_private)
        for eref in person.get_event_ref_list():
            h = eref.get_reference_handle()
            event_parties.setdefault(h, {'people': [], 'couple': None})
            event_parties[h]['people'].append(pdata)
    for family in db.iter_families():
        fh = family.get_father_handle()
        mh = family.get_mother_handle()
        father = person_data(db, db.get_person_from_handle(fh), include_private=include_private) if fh else None
        mother = person_data(db, db.get_person_from_handle(mh), include_private=include_private) if mh else None
        children = sorted(
            [person_data(db, db.get_person_from_handle(cr.get_reference_handle()), include_private=include_private)
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
        if event.get_privacy() and not include_private:
            continue
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
        if not couple:
            participants.sort(key=lambda p: p['birth_year'] or 9999)
        gid = event.get_gramps_id()
        tag_names = {db.get_tag_from_handle(h).get_name() for h in event.get_tag_list()}
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
            'photos': get_event_photos(db, event, db_path, include_private=include_private),
            'is_interesting': 'Interesting' in tag_names,
            'is_conflict': 'Conflict' in tag_names,
        }
    return result


def build_birthday_list(db, *, include_private=False):
    """Returns birthdays grouped by month, each month having a list of days with people."""
    by_date = {}
    for person in db.iter_people():
        if person.get_privacy() and not include_private:
            continue
        birth = get_event(db, person, EventType.BIRTH)
        if not birth or (birth.get_privacy() and not include_private):
            continue
        date_obj = birth.get_date_object()
        month = date_obj.get_month()
        day = date_obj.get_day()
        if not month or not day:
            continue
        pdata = person_data(db, person, include_private=include_private)
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


def _collect_photos(db, obj, db_path, *, include_private=False):
    photos = []
    for ref in obj.get_media_list():
        media = db.get_media_from_handle(ref.get_reference_handle())
        if media.get_privacy() and not include_private:
            continue
        mime = media.get_mime_type()
        if not mime:
            raise ValueError(f"Media has no MIME type: {media.get_gramps_id()} ({media.get_path()})")
        if not mime.startswith('image/'):
            continue
        src = _resolve_media_path(db, media.get_path(), db_path)
        if not src.is_file():
            print(f"  WARNING: media file not found, skipping: {src} ({media.get_gramps_id()})")
            continue
        photos.append({
            'media_id': media.get_gramps_id(),
            'src': src,
            'rect': ref.get_rectangle(),
            'description': media.get_description(),
        })
    return photos


def get_person_notes(db, person) -> list[str]:
    notes = []
    for handle in person.get_note_list():
        note = db.get_note_from_handle(handle)
        text = str(note.get()).strip()
        if text:
            notes.append(text)
    return notes


def get_person_attributes(person) -> list[dict]:
    return [
        {'type': str(attr.get_type()), 'value': attr.get_value()}
        for attr in person.get_attribute_list()
    ]


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


def get_photos(db, person, db_path, *, include_private=False):
    return _collect_photos(db, person, db_path, include_private=include_private)


def get_event_photos(db, event, db_path, *, include_private=False):
    return _collect_photos(db, event, db_path, include_private=include_private)


def get_all_person_pictures(db, person, db_path, *, include_private=False):
    """Return all photos attached to a person or their events, with source metadata."""
    pictures = []
    seen_media_ids = set()

    def _add(photos, page_url, page_label, year=None):
        for p in photos:
            if p['media_id'] in seen_media_ids:
                continue
            seen_media_ids.add(p['media_id'])
            pictures.append({**p, 'page_url': page_url, 'page_label': page_label, 'year': year})

    _add(_collect_photos(db, person, db_path, include_private=include_private), f'/people/{person.get_gramps_id()}/', 'Profile', year=None)

    for eref in person.get_event_ref_list():
        event = db.get_event_from_handle(eref.get_reference_handle())
        if event.get_privacy() and not include_private:
            continue
        etype = int(event.get_type())
        label = EVENT_TYPE_LABELS.get(etype, str(event.get_type()))
        year = event.get_date_object().get_year() or None
        slug = event_url_slug(event.get_gramps_id())
        _add(_collect_photos(db, event, db_path, include_private=include_private), f'/events/{slug}/', label, year=year)

    for fam_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(fam_handle)
        for eref in family.get_event_ref_list():
            event = db.get_event_from_handle(eref.get_reference_handle())
            if event.get_privacy() and not include_private:
                continue
            etype = int(event.get_type())
            label = EVENT_TYPE_LABELS.get(etype, str(event.get_type()))
            year = event.get_date_object().get_year() or None
            slug = event_url_slug(event.get_gramps_id())
            _add(_collect_photos(db, event, db_path, include_private=include_private), f'/events/{slug}/', label, year=year)

    pictures.sort(key=lambda p: p['year'] or 9999)
    return pictures


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


def _household_name(description, year):
    if not description:
        return None
    s = description
    prefix = f'{year} census - '
    if s.lower().startswith(prefix.lower()):
        s = s[len(prefix):]
    if s.lower().endswith(' household'):
        s = s[:-len(' household')]
    return s.strip() or description


def build_census_data(db, *, include_private=False):
    """Returns {year: [event_dicts]} for all Census events, sorted by description within each year."""
    event_people = {}
    for person in db.iter_people():
        pdata = person_data(db, person, include_private=include_private)
        for eref in person.get_event_ref_list():
            h = eref.get_reference_handle()
            event_people.setdefault(h, []).append(pdata)

    by_year = {}
    for event in db.iter_events():
        if int(event.get_type()) != EventType.CENSUS:
            continue
        if event.get_privacy() and not include_private:
            continue
        year = event.get_date_object().get_year() or None
        if not year:
            continue
        place_h = event.get_place_handle()
        place_obj = db.get_place_from_handle(place_h) if place_h else None
        notes = []
        for note_handle in event.get_note_list():
            note = db.get_note_from_handle(note_handle)
            text = str(note.get()).strip()
            if text:
                notes.append(text)
        people = sorted(
            event_people.get(event.get_handle(), []),
            key=lambda p: p['birth_year'] or 9999,
        )
        gid = event.get_gramps_id()
        description = event.get_description() or None
        has_photo = any(
            db.get_media_from_handle(ref.get_reference_handle()).get_mime_type().startswith('image/')
            for ref in event.get_media_list()
        )
        by_year.setdefault(year, []).append({
            'gramps_id': gid,
            'url_slug': event_url_slug(gid),
            'description': description,
            'household_name': _household_name(description, year),
            'date': format_date(event.get_date_object()),
            'year': year,
            'place': place_obj.get_name().get_value() if place_obj else None,
            'place_id': place_obj.get_gramps_id() if place_obj else None,
            'notes': notes,
            'people': people,
            'has_photo': has_photo,
        })

    for events in by_year.values():
        events.sort(key=lambda e: e['description'] or '')

    return by_year
