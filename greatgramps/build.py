import json
import re
import shutil
import time
from collections import Counter
from datetime import date
from pathlib import Path
from PIL import Image
from chameleon import PageTemplateLoader

_PACKAGE_DIR = Path(__file__).parent

NAV_LABELS = {
    'people': 'People',
    'places': 'Places',
    'events': 'Events',
    'census': 'Census',
    'cemeteries': 'Cemeteries',
    'birthdays': 'Birthdays',
    'surnames': 'Surnames',
}


class _FallbackTemplateLoader:
    """Loads templates from a user directory, falling back to the bundled ones."""

    def __init__(self, user_dir, builtin_dir):
        self._user = PageTemplateLoader(str(user_dir)) if user_dir else None
        self._builtin = PageTemplateLoader(str(builtin_dir))

    def __getitem__(self, name):
        if self._user:
            try:
                return self._user[name]
            except KeyError:
                pass
        return self._builtin[name]
from gramps.gen.lib.eventtype import EventType
from reportlab.lib import pagesizes
from .tree_pdf import generate_ancestor_pdf, generate_descendant_pdf, generate_hourglass_pdf
from .gramps_data import (
    open_db, collect_all_people, collect_ancestors,
    get_parents, get_children, get_siblings, get_spouses, get_all_events,
    ancestors_with_distances, ancestors_with_ahnentafel, get_relation_to_me, is_related_by_marriage, get_by_marriage_relation,
    get_photos, get_occupations, get_all_person_pictures, place_data, build_place_event_index, build_event_list,
    build_event_pages_data, build_birthday_list, person_data,
    collect_ancestor_tree, collect_descendant_tree,
    collect_all_descendants, group_descendants_by_generation,
    build_census_data, CENSUS_DATES, MONTHS, relationship_label, event_url_slug,
)
from .settings import get_config


def _clean_name_token(s):
    return re.sub(r"[^\w''-]", '', s)


def process_photo(photo, media_dir, person_id):
    """Copy or crop a photo into media_dir, return the web path."""
    src = photo['src']
    rect = photo['rect']
    filename = f"{person_id}_{photo['media_id']}.webp"
    dest = media_dir / filename

    if not dest.exists():
        img = Image.open(src)
        if rect:
            x1, y1, x2, y2 = rect
            w, h = img.size
            img = img.crop((
                int(w * x1 / 100), int(h * y1 / 100),
                int(w * x2 / 100), int(h * y2 / 100),
            ))
        img.save(dest, quality=85)

    return f'/media/{filename}'


def surname_slug(name):
    slug = re.sub(r"['']", '', name)
    slug = re.sub(r'[^\w-]', '-', slug)
    return re.sub(r'-+', '-', slug).strip('-') or 'unknown'


def group_by_generation(ancestors):
    by_gen = {}
    for gid, data in ancestors.items():
        by_gen.setdefault(data['generation'], []).append(data)
    result = []
    for g in sorted(by_gen):
        people = by_gen[g]
        by_slot = {}
        for person in people:
            by_slot.setdefault(person['couple_slot'], []).append(person)
        couples = [by_slot[s] for s in sorted(by_slot, key=lambda x: -1 if x is None else x)]
        result.append({'gen': g, 'people': people, 'couples': couples})
    return result


def _make_map_json(person_place_events, people, place_lat_lon, base):
    map_points = {}
    for pgid, pdata in people.items():
        for pe in person_place_events.get(pgid, []):
            pid = pe['place_id']
            if pid not in map_points:
                lat, lon = place_lat_lon[pid]
                map_points[pid] = {
                    'lat': lat, 'lon': lon,
                    'name': pe['place'],
                    'url': f'{base}places/{pid}/',
                    'people': {},
                }
            ppl = map_points[pid]['people']
            if pgid not in ppl:
                ppl[pgid] = {
                    'name': pdata['full_name'],
                    'url': f'{base}people/{pgid}/',
                    'types': [],
                }
            ppl[pgid]['types'].append(pe['type'])
    return json.dumps([
        {
            'lat': pt['lat'], 'lon': pt['lon'],
            'name': pt['name'], 'url': pt['url'],
            'people': [
                {'name': p['name'], 'url': p['url'], 'types': list(dict.fromkeys(p['types']))}
                for p in pt['people'].values()
            ],
        }
        for pt in map_points.values()
    ])


def _make_shared_ctx(config, db):
    """Build context shared across all root builds."""
    all_people = collect_all_people(db)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    media_dir = config.output_dir / 'media'
    media_dir.mkdir(exist_ok=True)

    place_event_index = build_place_event_index(db)
    all_places = {p.get_handle(): place_data(p) for p in db.iter_places()}

    place_children = {}
    place_children_handles = {}
    for handle, pdata in all_places.items():
        for parent_handle in pdata['parent_handles']:
            place_children.setdefault(parent_handle, []).append(pdata)
            place_children_handles.setdefault(parent_handle, []).append(handle)

    def descendant_handles(start):
        result, seen, queue = [], {start}, list(place_children_handles.get(start, []))
        while queue:
            h = queue.pop(0)
            if h in seen:
                continue
            seen.add(h)
            result.append(h)
            queue.extend(place_children_handles.get(h, []))
        return result

    for handle, pdata in all_places.items():
        enclosing = []
        cur_handles = pdata['parent_handles']
        seen = {handle}
        while cur_handles:
            ph = cur_handles[0]
            if ph in seen or ph not in all_places:
                break
            seen.add(ph)
            parent = all_places[ph]
            enclosing.append(parent)
            cur_handles = parent['parent_handles']
        pdata['enclosing'] = enclosing
        pdata['sub_places'] = sorted(place_children.get(handle, []), key=lambda p: p['name'])

    place_lat_lon = {
        d['gramps_id']: (d['lat'], d['lon'])
        for d in all_places.values()
        if d['lat'] and d['lon']
    }

    person_place_events = {}
    for _gid, _pdata in all_people.items():
        _p = db.get_person_from_gramps_id(_gid)
        person_place_events[_gid] = [
            {'place_id': e['place_id'], 'place': e['place'], 'type': e['type']}
            for e in get_all_events(db, _p)
            if e.get('place_id') and e['place_id'] in place_lat_lon
        ]

    by_surname = {}
    married_by_surname = {}
    for gid, data in all_people.items():
        s = data['surname']
        if s:
            by_surname.setdefault(s, []).append(gid)
        for alt in data['alt_names']:
            if alt['type'] != 'Married Name' or not alt['surname']:
                continue
            by_surname.setdefault(alt['surname'], []).append(gid)
            married_by_surname.setdefault(alt['surname'], set()).add(gid)

    templates = _FallbackTemplateLoader(config.templates_dir, _PACKAGE_DIR / 'templates')
    layout = templates['layout.pt'].macros['layout']
    person_header = templates['person_header.pt'].macros['person_header']

    return {
        'config': config,
        'db': db,
        'all_people': all_people,
        'all_places': all_places,
        'place_event_index': place_event_index,
        'descendant_handles': descendant_handles,
        'place_lat_lon': place_lat_lon,
        'person_place_events': person_place_events,
        'by_surname': by_surname,
        'married_by_surname': married_by_surname,
        'media_dir': media_dir,
        'templates': templates,
        'layout': layout,
        'person_header': person_header,
    }


def _make_root_ctx(shared, root_id):
    """Build root-specific context for one home person."""
    config = shared['config']
    db = shared['db']

    me = db.get_person_from_gramps_id(root_id)
    my_ancestors = collect_ancestors(db, me)
    me_ancestor_distances = ancestors_with_distances(db, me)
    my_descendants_data = collect_all_descendants(db, me)
    my_descendants = set(my_descendants_data) - {root_id}

    root_dir = config.output_dir / root_id
    root_dir.mkdir(parents=True, exist_ok=True)
    people_dir = root_dir / 'people'
    people_dir.mkdir(exist_ok=True)
    events_dir = root_dir / 'events'
    events_dir.mkdir(exist_ok=True)
    places_dir = root_dir / 'places'
    places_dir.mkdir(exist_ok=True)

    base = f'/{root_id}/'
    all_places = shared['all_places']
    by_surname = shared['by_surname']
    layout = shared['layout']
    person_header = shared['person_header']
    templates = shared['templates']

    place_url = {d['gramps_id']: f'{base}places/{d["gramps_id"]}/' for d in all_places.values()}
    surname_page_url = {s: f'{base}surnames/{surname_slug(s)}/' for s in by_surname}

    root_first_name = shared['all_people'][root_id]['given'].split()[0]
    root_full_name = f"{root_first_name} {shared['all_people'][root_id]['surname']}".strip()

    has_custom_css = shared['has_custom_css']
    nav_items = [{'slug': p, 'label': NAV_LABELS[p]} for p in config.nav_pages]
    all_people = shared['all_people']
    switch_roots = [
        {'id': rid, 'name': all_people[rid]['given'].split()[0]}
        for rid in config.roots
        if rid in all_people
    ]
    switch_roots_json = json.dumps(switch_roots)

    def render(template_name, page_title, **kwargs):
        return templates[f'{template_name}.pt'](
            layout=layout, base=base, page_title=page_title,
            me_id=root_id, root_first_name=root_first_name, root_full_name=root_full_name,
            person_header=person_header, has_custom_css=has_custom_css, nav_items=nav_items,
            switch_roots=switch_roots, switch_roots_json=switch_roots_json, **kwargs
        )

    return {
        **shared,
        'me': me,
        'my_ancestors': my_ancestors,
        'my_descendants': my_descendants,
        'my_descendants_data': my_descendants_data,
        'me_ancestor_distances': me_ancestor_distances,
        'root_id': root_id,
        'root_dir': root_dir,
        'people_dir': people_dir,
        'events_dir': events_dir,
        'places_dir': places_dir,
        'base': base,
        'place_url': place_url,
        'surname_page_url': surname_page_url,
        'root_full_name': root_full_name,
        'render': render,
    }


def _render_person_pages(ctx, gid, relation, by_marriage, marriage_relation=None):
    """Render profile, ancestors, and descendants pages for one person."""
    config = ctx['config']
    db = ctx['db']
    all_people = ctx['all_people']
    my_ancestors = ctx['my_ancestors']
    my_descendants = ctx['my_descendants']
    media_dir = ctx['media_dir']
    people_dir = ctx['people_dir']
    place_lat_lon = ctx['place_lat_lon']
    place_url = ctx['place_url']
    surname_page_url = ctx['surname_page_url']
    person_place_events = ctx['person_place_events']
    render = ctx['render']
    root_id = ctx['root_id']
    base = ctx['base']

    data = all_people[gid]
    p = db.get_person_from_gramps_id(gid)
    father_p, mother_p = get_parents(db, p)
    children_p = get_children(db, p)
    spouses = sorted(get_spouses(db, p), key=lambda s: (s['marriage'] or {}).get('year') or 9999)
    person_ancestors = collect_ancestors(db, p)
    photos = [
        {**photo, 'url': process_photo(photo, media_dir, gid)}
        for photo in get_photos(db, p)
    ]
    all_pictures = [
        {**pic, 'url': process_photo(pic, media_dir, gid),
         'page_url': base + pic['page_url'][1:] if (pic.get('page_url') or '').startswith('/') else pic.get('page_url')}
        for pic in get_all_person_pictures(db, p)
    ]
    occupations = get_occupations(p)
    events = [
        {**e, 'description_url': base + e['description_url'][1:] if (e.get('description_url') or '').startswith('/people/') else e.get('description_url')}
        for e in get_all_events(db, p)
    ]
    map_points = {}
    for event in events:
        if event.get('type') == 'Probate':
            continue
        pid = event.get('place_id')
        if pid and pid in place_lat_lon:
            if pid not in map_points:
                lat, lon = place_lat_lon[pid]
                map_points[pid] = {
                    'lat': lat, 'lon': lon,
                    'name': event['place'],
                    'url': f'{base}places/{pid}/',
                    'types': [],
                }
            map_points[pid]['types'].append(event['type'])
    event_map_json = json.dumps(list(map_points.values()))
    num_ancestors = len(person_ancestors) - 1
    all_descendants = collect_all_descendants(db, p)
    for desc_gid, desc_data in all_descendants.items():
        desc_data['is_ancestor'] = desc_gid in my_ancestors and desc_gid != root_id
        desc_data['is_descendant'] = desc_gid in my_descendants
        desc_data['is_me'] = desc_gid == root_id
    num_descendants = len(all_descendants)
    descendant_generations = group_descendants_by_generation(all_descendants)
    alt_surname_urls = {
        n['surname']: surname_page_url.get(n['surname'])
        for n in data['alt_names'] if n['surname']
    }
    html = render(
        'person',
        page_title=f"{data['full_name']} — {config.site_title}",
        person=data,
        father={**person_data(db, father_p), 'is_ancestor': father_p.get_gramps_id() in my_ancestors and father_p.get_gramps_id() != root_id, 'is_descendant': father_p.get_gramps_id() in my_descendants, 'is_me': father_p.get_gramps_id() == root_id} if father_p else None,
        mother={**person_data(db, mother_p), 'is_ancestor': mother_p.get_gramps_id() in my_ancestors and mother_p.get_gramps_id() != root_id, 'is_descendant': mother_p.get_gramps_id() in my_descendants, 'is_me': mother_p.get_gramps_id() == root_id} if mother_p else None,
        children=sorted(
            [{**person_data(db, c), 'is_ancestor': c.get_gramps_id() in my_ancestors and c.get_gramps_id() != root_id, 'is_descendant': c.get_gramps_id() in my_descendants, 'is_me': c.get_gramps_id() == root_id} for c in children_p],
            key=lambda c: c['birth_year'] or 9999,
        ),
        siblings=[{**s, 'is_ancestor': s['gramps_id'] in my_ancestors and s['gramps_id'] != root_id, 'is_descendant': s['gramps_id'] in my_descendants, 'is_me': s['gramps_id'] == root_id} for s in get_siblings(db, p)],
        spouses=[{**s, 'person': {**s['person'], 'is_ancestor': s['person']['gramps_id'] in my_ancestors and s['person']['gramps_id'] != root_id, 'is_descendant': s['person']['gramps_id'] in my_descendants, 'is_me': s['person']['gramps_id'] == root_id} if s['person'] else None} for s in spouses],
        events=events,
        is_ancestor=gid in my_ancestors and gid != root_id,
        is_descendant=gid in my_descendants,
        is_me=gid == root_id,
        relation=relation,
        by_marriage=by_marriage,
        marriage_relation=marriage_relation,
        photos=photos,
        occupations=occupations,
        place_url=place_url,
        generations=group_by_generation(person_ancestors),
        descendant_generations=descendant_generations,
        event_map_json=event_map_json,
        surname_url=surname_page_url.get(data['surname']),
        alt_surname_urls=alt_surname_urls,
        current_year=date.today().year,
        num_ancestors=num_ancestors,
        num_descendants=num_descendants,
        num_pictures=len(all_pictures),
    )
    person_out = people_dir / gid
    person_out.mkdir(exist_ok=True)
    (person_out / 'index.html').write_text(html)

    tree_nodes, tree_rows, tree_cols = collect_ancestor_tree(db, p)
    tree_grid_style = (
        f'grid-template-rows:repeat({tree_rows},minmax(2.5rem,auto));'
        f'grid-template-columns:repeat({tree_cols},minmax(140px,1fr))'
    )
    surname_url = surname_page_url.get(data['surname'])
    ancestors_map_json = _make_map_json(person_place_events, person_ancestors, place_lat_lon, base)
    ancestors_dir = person_out / 'ancestors'
    ancestors_dir.mkdir(exist_ok=True)
    (ancestors_dir / 'index.html').write_text(render(
        'tree',
        page_title=f"{data['full_name']} — Ancestor Tree",
        person=data,
        nodes=tree_nodes,
        tree_grid_style=tree_grid_style,
        num_ancestors=num_ancestors,
        num_descendants=num_descendants,
        is_ancestor=gid in my_ancestors and gid != root_id,
        is_descendant=gid in my_descendants,
        is_me=gid == root_id,
        relation=relation,
        by_marriage=by_marriage,
        marriage_relation=marriage_relation,
        photos=photos,
        surname_url=surname_url,
        alt_surname_urls=alt_surname_urls,
        current_year=date.today().year,
        ancestors_map_json=ancestors_map_json,
        num_pictures=len(all_pictures),
    ))

    desc_nodes, desc_rows, desc_cols = collect_descendant_tree(db, p)
    desc_grid_style = (
        f'grid-template-columns:repeat({desc_cols},minmax(140px,1fr));'
        f'grid-template-rows:repeat({desc_rows},minmax(2.5rem,auto))'
    )
    descendants_map_json = _make_map_json(person_place_events, all_descendants, place_lat_lon, base)
    descendants_dir = person_out / 'descendants'
    descendants_dir.mkdir(exist_ok=True)
    (descendants_dir / 'index.html').write_text(render(
        'descendants_tree',
        page_title=f"{data['full_name']} — Descendant Tree",
        person=data,
        nodes=desc_nodes,
        tree_grid_style=desc_grid_style,
        num_ancestors=num_ancestors,
        num_descendants=num_descendants,
        is_ancestor=gid in my_ancestors and gid != root_id,
        is_descendant=gid in my_descendants,
        is_me=gid == root_id,
        relation=relation,
        by_marriage=by_marriage,
        marriage_relation=marriage_relation,
        photos=photos,
        surname_url=surname_url,
        alt_surname_urls=alt_surname_urls,
        current_year=date.today().year,
        descendants_map_json=descendants_map_json,
        num_pictures=len(all_pictures),
    ))

    pictures_dir = person_out / 'pictures'
    pictures_dir.mkdir(exist_ok=True)
    (pictures_dir / 'index.html').write_text(render(
        'pictures',
        page_title=f"{data['full_name']} — Pictures",
        person=data,
        pictures=all_pictures,
        num_ancestors=num_ancestors,
        num_descendants=num_descendants,
        is_ancestor=gid in my_ancestors and gid != root_id,
        is_descendant=gid in my_descendants,
        is_me=gid == root_id,
        relation=relation,
        by_marriage=by_marriage,
        marriage_relation=marriage_relation,
        photos=photos,
        surname_url=surname_url,
        alt_surname_urls=alt_surname_urls,
        current_year=date.today().year,
        num_pictures=len(all_pictures),
    ))

    return {**data, 'num_children': len(children_p), 'num_spouses': len(spouses),
            'is_ancestor': gid in my_ancestors and gid != root_id,
            'is_descendant': gid in my_descendants,
            'alt_surnames': [n['surname'] for n in data['alt_names'] if n['surname']]}


def _compute_place_events(ctx):
    """Return (places_with_events, place_events) where place_events maps handle -> sorted event list."""
    all_places = ctx['all_places']
    place_event_index = ctx['place_event_index']
    descendant_handles = ctx['descendant_handles']
    places_with_events = []
    place_events = {}
    for handle, pdata in all_places.items():
        direct = [{**e, 'sub_place': None, 'sub_place_id': None}
                  for e in place_event_index.get(handle, [])]
        nested = [
            {**e, 'sub_place': all_places[h]['name'], 'sub_place_id': all_places[h]['gramps_id']}
            for h in descendant_handles(handle)
            for e in place_event_index.get(h, [])
        ]
        events = sorted(direct + nested, key=lambda e: e['year'] or 9999)
        place_events[handle] = events
        if events:
            places_with_events.append({**pdata, 'event_count': len(events)})
    return places_with_events, place_events


def _render_place_page(ctx, handle, events):
    """Render a single place's page."""
    config = ctx['config']
    all_places = ctx['all_places']
    places_dir = ctx['places_dir']
    my_ancestors = ctx['my_ancestors']
    root_id = ctx['root_id']
    render = ctx['render']
    pdata = all_places[handle]
    sub_place_markers = [
        {'lat': sub['lat'], 'lon': sub['lon'], 'name': sub['name'], 'gramps_id': sub['gramps_id']}
        for sub in pdata['sub_places']
        if sub['lat'] and sub['lon']
    ]
    subject_marker = (
        {'lat': pdata['lat'], 'lon': pdata['lon'], 'name': pdata['name']}
        if pdata['lat'] and pdata['lon'] else None
    )
    html = render(
        'place',
        page_title=f"{pdata['name']} — {config.site_title}",
        place=pdata,
        events=events,
        ancestor_ids=set(my_ancestors) - {root_id},
        descendant_ids=ctx['my_descendants'],
        has_map=bool(subject_marker or sub_place_markers),
        subject_marker_json=json.dumps(subject_marker),
        sub_place_markers_json=json.dumps(sub_place_markers),
    )
    place_out = places_dir / pdata['gramps_id']
    place_out.mkdir(exist_ok=True)
    (place_out / 'index.html').write_text(html)


def _render_places_index(ctx, places_with_events):
    """Render the places index page."""
    config = ctx['config']
    places_dir = ctx['places_dir']
    render = ctx['render']
    places_with_events = sorted(places_with_events, key=lambda p: -p['event_count'])
    mappable = [p for p in places_with_events if p['lat'] and p['lon']]
    mappable_json = json.dumps([
        {'lat': p['lat'], 'lon': p['lon'], 'name': p['name'],
         'url': f'{p["gramps_id"]}/', 'count': p['event_count']}
        for p in mappable
    ])
    (places_dir / 'index.html').write_text(
        render('places', page_title=f'Places — {config.site_title}',
               places=places_with_events, mappable_json=mappable_json)
    )


def _render_event_page(ctx, slug, event_data, relation_map):
    """Render a single event page."""
    config = ctx['config']
    db = ctx['db']
    root_id = ctx['root_id']
    my_ancestors = ctx['my_ancestors']
    media_dir = ctx['media_dir']
    events_dir = ctx['events_dir']
    place_lat_lon = ctx['place_lat_lon']
    base = ctx['base']
    render = ctx['render']

    my_descendants = ctx['my_descendants']
    ancestor_ids = set(my_ancestors) - {root_id}
    is_ancestor_event = any(p['gramps_id'] in ancestor_ids for p in event_data['people'])
    is_descendant_event = any(p['gramps_id'] in my_descendants for p in event_data['people'])
    pid = event_data['place_id']
    if pid and pid in place_lat_lon:
        lat, lon = place_lat_lon[pid]
        event_map_json = json.dumps([{
            'lat': lat, 'lon': lon,
            'name': event_data['place'],
            'url': f'{base}places/{pid}/',
        }])
    else:
        event_map_json = '[]'
    photos = [
        {**photo, 'url': process_photo(photo, media_dir, event_data['gramps_id'])}
        for photo in event_data['photos']
    ]
    event_out = events_dir / slug
    event_out.mkdir(exist_ok=True)
    couple = event_data.get('couple')
    people = event_data.get('people', [])
    if event_data['type'] == 'Census' and event_data.get('description'):
        page_title = f"{event_data['description']} — {config.site_title}"
    elif couple:
        names = ' and '.join(p['full_name'] for p in couple if p)
        person_str = f' of {names}' if names else ''
        page_title = f"{event_data['type']}{person_str} — {config.site_title}"
    elif len(people) == 1:
        page_title = f"{event_data['type']} of {people[0]['full_name']} — {config.site_title}"
    else:
        page_title = f"{event_data['type']} — {config.site_title}"
    if event_data['type'] == 'Census':
        template = 'census'
    elif event_data['type'] == 'Marriage':
        template = 'marriage'
    else:
        template = 'event'
    couple_details = []
    if template == 'marriage':
        for pd in filter(None, event_data.get('couple') or []):
            p_obj = db.get_person_from_gramps_id(pd['gramps_id'])
            father_obj, mother_obj = get_parents(db, p_obj) if p_obj else (None, None)
            person_photos = [
                {**photo, 'url': process_photo(photo, media_dir, pd['gramps_id'])}
                for photo in (get_photos(db, p_obj) if p_obj else [])
            ]
            couple_details.append({
                **pd,
                'father': person_data(db, father_obj) if father_obj else None,
                'mother': person_data(db, mother_obj) if mother_obj else None,
                'photos': person_photos,
            })
    (event_out / 'index.html').write_text(render(
        template,
        page_title=page_title,
        event=event_data,
        photos=photos,
        couple_photos=[],
        couple_details=couple_details,
        children=event_data.get('children', []),
        is_ancestor_event=is_ancestor_event,
        is_descendant_event=is_descendant_event,
        ancestor_ids=ancestor_ids,
        descendant_ids=my_descendants,
        relation_map=relation_map,
        event_map_json=event_map_json,
    ))


def _render_cemeteries_page(ctx):
    config = ctx['config']
    all_places = ctx['all_places']
    place_event_index = ctx['place_event_index']
    root_dir = ctx['root_dir']
    render = ctx['render']

    cemeteries = []
    for handle, pdata in all_places.items():
        is_cemetery_type = pdata['type'].lower() == 'cemetery'
        is_cemetery_name = 'cemetery' in pdata['name'].lower()
        if not (is_cemetery_type or is_cemetery_name):
            continue
        burial_count = sum(
            1 for e in place_event_index.get(handle, [])
            if e['type'] == 'Burial'
        )
        cemeteries.append({**pdata, 'burial_count': burial_count})

    cemeteries.sort(key=lambda p: p['name'].lower())

    mappable = [p for p in cemeteries if p['lat'] and p['lon']]
    mappable_json = json.dumps([
        {'lat': p['lat'], 'lon': p['lon'], 'name': p['name'],
         'url': f'{p["gramps_id"]}/', 'count': p['burial_count']}
        for p in mappable
    ])

    cemeteries_dir = root_dir / 'cemeteries'
    cemeteries_dir.mkdir(exist_ok=True)
    (cemeteries_dir / 'index.html').write_text(
        render('cemeteries', page_title=f'Cemeteries — {config.site_title}',
               cemeteries=cemeteries, mappable_json=mappable_json)
    )
    print(f'Built cemeteries/index.html ({len(cemeteries)} cemeteries)')


def _render_ancestor_records_page(ctx):
    config = ctx['config']
    db = ctx['db']
    me = ctx['me']
    all_people = ctx['all_people']
    render = ctx['render']
    root_dir = ctx['root_dir']
    root_id = ctx['root_id']

    ancestor_distances = ctx['me_ancestor_distances']
    ahnentafel = ancestors_with_ahnentafel(db, me)

    def _has_event(person, etype):
        return any(
            int(db.get_event_from_handle(er.get_reference_handle()).get_type()) == etype
            for er in person.get_event_ref_list()
        )

    def _has_marriage(person):
        for fam_handle in person.get_family_handle_list():
            family = db.get_family_from_handle(fam_handle)
            for er in family.get_event_ref_list():
                if int(db.get_event_from_handle(er.get_reference_handle()).get_type()) == EventType.MARRIAGE:
                    return True
        return False

    generations = {}
    for gid, dist in ancestor_distances.items():
        if dist == 0:
            continue
        person = db.get_person_from_gramps_id(gid)
        if not person:
            continue
        d = all_people[gid]
        father, mother = get_parents(db, person)
        row = {
            'gramps_id': gid,
            'full_name': d['full_name'],
            'gender': d['gender'],
            'birth_year': d['birth_year'],
            'birth':    _has_event(person, EventType.BIRTH),
            'baptism':  _has_event(person, EventType.BAPTISM),
            'marriage': _has_marriage(person),
            'death':    _has_event(person, EventType.DEATH),
            'burial':   _has_event(person, EventType.BURIAL),
            'has_father': father is not None,
            'has_mother': mother is not None,
            'ancestry_url': d['ancestry_url'],
            'grave_url': d['grave_url'],
        }
        generations.setdefault(dist, []).append(row)

    gen_list = []
    for dist in sorted(generations):
        people = sorted(generations[dist], key=lambda r: ahnentafel.get(r['gramps_id'], 9999))
        label = relationship_label(dist, 0).capitalize() + 's'
        gen_list.append({'dist': dist, 'label': label, 'people': people})

    records_dir = root_dir / 'ancestor-records'
    records_dir.mkdir(exist_ok=True)
    (records_dir / 'index.html').write_text(
        render('ancestor_records', page_title=f'Ancestor Records — {config.site_title}',
               gen_list=gen_list)
    )
    print(f'Built ancestor-records/index.html ({sum(len(g["people"]) for g in gen_list)} ancestors)')


def _render_ancestor_census_page(ctx):
    config = ctx['config']
    db = ctx['db']
    me = ctx['me']
    all_people = ctx['all_people']
    render = ctx['render']
    root_dir = ctx['root_dir']
    root_id = ctx['root_id']

    ancestor_distances = ctx['me_ancestor_distances']
    ahnentafel = ancestors_with_ahnentafel(db, me)
    census_years = sorted(CENSUS_DATES.keys())

    event_person_count = {}
    person_census_events = {}
    for person in db.iter_people():
        gid = person.get_gramps_id()
        for eref in person.get_event_ref_list():
            h = eref.get_reference_handle()
            event_person_count[h] = event_person_count.get(h, 0) + 1
            event = db.get_event_from_handle(h)
            if int(event.get_type()) == EventType.CENSUS:
                year = event.get_date_object().get_year() or None
                if year:
                    person_census_events.setdefault(gid, {}).setdefault(year, []).append(h)

    person_census_counts = {
        gid: {year: max(event_person_count.get(h, 1) for h in handles)
              for year, handles in years.items()}
        for gid, years in person_census_events.items()
    }

    generations = {}
    for gid, dist in ancestor_distances.items():
        if dist == 0:
            continue
        d = all_people.get(gid)
        if not d:
            continue
        birth_year = d['birth_year']
        death_year = d['death_year']
        census_status = {}
        for year in census_years:
            if birth_year and birth_year > year:
                census_status[year] = {'type': 'unborn', 'count': 0}
            elif death_year and death_year < year:
                census_status[year] = {'type': 'deceased', 'count': 0}
            else:
                count = person_census_counts.get(gid, {}).get(year, 0)
                handles = person_census_events.get(gid, {}).get(year, [])
                num_events = len(handles)
                event_url = event_url_slug(db.get_event_from_handle(handles[0]).get_gramps_id()) if handles else None
                photo_url = None
                for h in handles:
                    event_obj = db.get_event_from_handle(h)
                    if any(
                        db.get_media_from_handle(ref.get_reference_handle()).get_mime_type().startswith('image/')
                        for ref in event_obj.get_media_list()
                    ):
                        photo_url = event_url_slug(event_obj.get_gramps_id())
                        break
                census_status[year] = {'type': 'found' if count else 'missing', 'count': count, 'duplicate': num_events > 1, 'event_url': event_url, 'photo_url': photo_url}
        generations.setdefault(dist, []).append({
            'gramps_id': gid,
            'full_name': d['full_name'],
            'gender': d['gender'],
            'birth_year': birth_year,
            'death_year': death_year,
            'ancestry_url': d['ancestry_url'],
            'census': census_status,
        })

    gen_list = []
    for dist in sorted(generations):
        people = sorted(generations[dist], key=lambda r: ahnentafel.get(r['gramps_id'], 9999))
        label = relationship_label(dist, 0).capitalize() + 's'
        gen_list.append({'dist': dist, 'label': label, 'people': people})

    records_dir = root_dir / 'census-records'
    records_dir.mkdir(exist_ok=True)
    (records_dir / 'index.html').write_text(
        render('census_records', page_title=f'Census Records — {config.site_title}',
               gen_list=gen_list, census_years=census_years)
    )
    total = sum(len(g['people']) for g in gen_list)
    print(f'Built census-records/index.html ({total} ancestors)')


def _report(label, total, errors, elapsed):
    err_str = f' ({len(errors)} error{"s" if len(errors) != 1 else ""})' if errors else ''
    ok = total - len(errors)
    count_str = f'{ok}/{total}' if errors else str(total)
    print(f'  Built {count_str} {label} in {elapsed:.1f}s{err_str}')
    for e in errors:
        print(f'    ERROR {e}')


def _render_surname_pages(ctx):
    """Render the surnames index and one page per surname."""
    config = ctx['config']
    all_people = ctx['all_people']
    my_ancestors = ctx['my_ancestors']
    my_descendants = ctx['my_descendants']
    by_surname = ctx['by_surname']
    married_by_surname = ctx['married_by_surname']
    root_id = ctx['root_id']
    root_dir = ctx['root_dir']
    render = ctx['render']

    surnames_dir = root_dir / 'surnames'
    surnames_dir.mkdir(exist_ok=True)
    surnames_list = sorted(
        [{'surname': s, 'count': len(gids), 'slug': surname_slug(s)} for s, gids in by_surname.items()],
        key=lambda x: (-x['count'], x['surname']),
    )
    (surnames_dir / 'index.html').write_text(
        render('surnames', page_title=f'Surnames — {config.site_title}', surnames=surnames_list)
    )
    print(f'Building {len(by_surname)} surname pages...')
    t = time.time()
    surname_errors = []
    for surname, gids in by_surname.items():
        married_gids = married_by_surname.get(surname, set())
        people_on_page = sorted(
            [{**all_people[gid], 'is_ancestor': gid in my_ancestors and gid != root_id,
              'is_descendant': gid in my_descendants, 'is_me': gid == root_id,
              'married_name': gid in married_gids} for gid in gids],
            key=lambda p: (p['birth_year'] or 9999, p['surname'], p['given']),
        )
        slug = surname_slug(surname)
        surname_out = surnames_dir / slug
        surname_out.mkdir(exist_ok=True)
        try:
            (surname_out / 'index.html').write_text(
                render('surname', page_title=f'{surname} — {config.site_title}',
                       surname=surname, people=people_on_page)
            )
        except Exception as e:
            surname_errors.append(f'{surname!r}: {type(e).__name__}: {e}')
    _report('surname pages', len(by_surname), surname_errors, time.time() - t)


def _pdf_gen_counts(ctx):
    """Return (ancestor_gens, descendant_gens, hourglass_anc, hourglass_desc)."""
    my_ancestors = ctx['my_ancestors']
    my_descendants_data = ctx['my_descendants_data']

    ancestor_gens = min(6, max(
        (data['generation'] for data in my_ancestors.values()),
        default=0,
    ))
    descendant_gens = min(6, max(
        (data['generation'] for data in my_descendants_data.values()),
        default=0,
    ))

    hourglass_desc = min(descendant_gens, 5) if ancestor_gens else descendant_gens
    hourglass_anc = min(ancestor_gens, 6 - hourglass_desc)

    return ancestor_gens, descendant_gens, hourglass_anc, hourglass_desc


def _build_pdfs(ctx):
    db = ctx['db']
    root_id = ctx['root_id']
    root_dir = ctx['root_dir']
    page_size = pagesizes.A4

    ancestor_gens, descendant_gens, hourglass_anc, hourglass_desc = _pdf_gen_counts(ctx)

    links = []
    if ancestor_gens:
        generate_ancestor_pdf(db, root_id, ancestor_gens + 1, root_dir / 'ancestors.pdf', color=True, page_size=page_size)
        links.append({'label': 'Ancestor tree', 'filename': 'ancestors.pdf'})
        print(f'Built {root_id}/ancestors.pdf ({ancestor_gens} generations)')

    if descendant_gens:
        generate_descendant_pdf(db, root_id, descendant_gens + 1, root_dir / 'descendants.pdf', color=True, page_size=page_size)
        links.append({'label': 'Descendant tree', 'filename': 'descendants.pdf'})
        print(f'Built {root_id}/descendants.pdf ({descendant_gens} generations)')

        if ancestor_gens:
            generate_hourglass_pdf(db, root_id, hourglass_anc + 1, hourglass_desc + 1, root_dir / 'hourglass.pdf', color=True, page_size=page_size)
            links.append({'label': 'Hourglass tree', 'filename': 'hourglass.pdf'})
            print(f'Built {root_id}/hourglass.pdf ({hourglass_anc}+{hourglass_desc} generations)')

    return links


def _build_root(ctx):
    """Build all pages for one root person."""
    config = ctx['config']
    db = ctx['db']
    all_people = ctx['all_people']
    my_ancestors = ctx['my_ancestors']
    my_descendants = ctx['my_descendants']
    my_descendants_data = ctx['my_descendants_data']
    me_ancestor_distances = ctx['me_ancestor_distances']
    all_places = ctx['all_places']
    place_lat_lon = ctx['place_lat_lon']
    root_id = ctx['root_id']
    root_dir = ctx['root_dir']
    render = ctx['render']

    print(f'\nBuilding root {root_id}...')

    # index.html
    surnames = Counter(_clean_name_token(d['surname']) for d in all_people.values() if d['surname'] and _clean_name_token(d['surname']))
    given_name_genders = {}
    for d in all_people.values():
        if d['given']:
            first = _clean_name_token(d['given'].split()[0])
            if not first:
                continue
            given_name_genders.setdefault(first, Counter())
            given_name_genders[first][d['gender']] += 1
    male_given = Counter()
    female_given = Counter()
    for name, genders in given_name_genders.items():
        total = sum(genders.values())
        if genders.get(1, 0) >= genders.get(0, 0):
            male_given[name] = total
        else:
            female_given[name] = total
    all_years = [y for d in all_people.values() for y in [d['birth_year'], d['death_year']] if y]
    pdf_links = _build_pdfs(ctx)
    summary = {
        'total_people': len(all_people),
        'total_ancestors': sum(1 for gid in my_ancestors if gid != root_id),
        'total_descendants': len(my_descendants_data),
        'total_places': len(all_places),
        'total_events': sum(1 for _ in db.iter_events()),
        'year_from': min(all_years) if all_years else None,
        'year_to': max(all_years) if all_years else None,
        'top_surnames': [(s, c, surname_slug(s)) for s, c in surnames.most_common(10)],
        'top_male_given': male_given.most_common(10),
        'top_female_given': female_given.most_common(10),
        'generations': group_by_generation(my_ancestors),
        'descendant_generations': group_descendants_by_generation(my_descendants_data),
    }
    _root_full_name = ctx['root_full_name']
    apostrophe = "'" if _root_full_name[-1].lower() == 's' else "'s"
    index_title = f"{_root_full_name}{apostrophe} family tree"
    (root_dir / 'index.html').write_text(
        render('index', page_title=index_title, summary=summary, pdf_links=pdf_links)
    )
    print('Built index.html')

    # Person pages
    print(f'Building {len(all_people)} person pages...')
    t = time.time()
    search_rows = []
    relation_map = {}
    person_errors = []
    for gid, data in all_people.items():
        p = db.get_person_from_gramps_id(gid)
        relation = get_relation_to_me(db, me_ancestor_distances, p, data['gender'])
        marriage_relation = None
        if not relation and gid != root_id:
            marriage_relation = get_by_marriage_relation(db, me_ancestor_distances, p, data['gender'])
        by_marriage = not relation and gid != root_id and (marriage_relation is not None or is_related_by_marriage(db, me_ancestor_distances, p))
        relation_map[gid] = relation
        try:
            search_row = _render_person_pages(ctx, gid, relation, by_marriage, marriage_relation)
        except Exception as e:
            person_errors.append(f'{gid}: {type(e).__name__}: {e}')
            search_row = {**data, 'num_children': 0, 'num_spouses': 0,
                          'is_ancestor': gid in my_ancestors and gid != root_id,
                          'is_descendant': gid in my_descendants,
                          'alt_surnames': [n['surname'] for n in data['alt_names'] if n['surname']]}
        search_rows.append(search_row)
    _report('person pages', len(all_people), person_errors, time.time() - t)

    search_rows.sort(key=lambda r: (r['surname'], r['given']))
    people_dir = ctx['people_dir']
    (people_dir / 'index.html').write_text(
        render('search', page_title=f'People — {config.site_title}', rows=search_rows)
    )
    print('Built people/index.html')

    # Place pages
    print(f'Building {len(all_places)} place pages...')
    t = time.time()
    places_with_events, place_events = _compute_place_events(ctx)
    place_errors = []
    for handle in all_places:
        pdata = all_places[handle]
        try:
            _render_place_page(ctx, handle, place_events[handle])
        except Exception as e:
            place_errors.append(f'{pdata["gramps_id"]}: {type(e).__name__}: {e}')
    _render_places_index(ctx, places_with_events)
    _report('place pages', len(all_places), place_errors, time.time() - t)

    # Events list page
    events_dir = ctx['events_dir']
    ancestor_events = [
        {**e, 'is_descendant_event': any(p['gramps_id'] in my_descendants for p in e['people'])}
        for e in build_event_list(db, set(my_ancestors) - {root_id})
    ]
    (events_dir / 'index.html').write_text(
        render('events', page_title=f'Events — {config.site_title}',
               events=ancestor_events, relation_map=relation_map)
    )
    print(f'Built events/index.html ({len(ancestor_events)} events)')

    # Individual event pages
    all_event_data = build_event_pages_data(db)
    valid_events = {slug: ed for slug, ed in all_event_data.items() if slug}
    print(f'Building {len(valid_events)} event pages...')
    t = time.time()
    event_errors = []
    for slug, event_data in valid_events.items():
        try:
            _render_event_page(ctx, slug, event_data, relation_map)
        except Exception as e:
            event_errors.append(f'{event_data["gramps_id"]}: {type(e).__name__}: {e}')
    _report('event pages', len(valid_events), event_errors, time.time() - t)

    # Birthdays page
    birthdays_dir = root_dir / 'birthdays'
    birthdays_dir.mkdir(exist_ok=True)
    birthday_months = build_birthday_list(db)
    total_birthdays = sum(len(d['people']) for m in birthday_months for d in m['days'])
    (birthdays_dir / 'index.html').write_text(
        render('birthdays', page_title=f'Birthdays — {config.site_title}',
               birthday_months=birthday_months, total_birthdays=total_birthdays,
               ancestor_ids=set(my_ancestors) - {root_id},
               descendant_ids=my_descendants)
    )
    print(f'Built birthdays/index.html ({total_birthdays} birthdays)')

    # Surname pages
    _render_surname_pages(ctx)

    # Census pages
    census_data = build_census_data(db)
    for events_list in census_data.values():
        for event in events_list:
            pid = event['place_id']
            lat, lon = place_lat_lon.get(pid, (None, None)) if pid else (None, None)
            event['lat'] = lat
            event['lon'] = lon
    census_dir = root_dir / 'census'
    census_dir.mkdir(exist_ok=True)
    ancestor_ids = set(my_ancestors) - {root_id}
    print(f'Building {len(census_data)} census year pages...')
    t = time.time()
    census_errors = []
    census_years_list = []
    for year in sorted(census_data):
        events = census_data[year]
        day, month, _ = CENSUS_DATES.get(year, (None, None, None))
        date_str = f'{day} {MONTHS[month]} {year}' if day and month else str(year)
        people_count = len({p['gramps_id'] for e in events for p in e['people']})
        census_years_list.append({'year': year, 'date': date_str, 'count': len(events), 'people_count': people_count})
        year_dir = census_dir / str(year)
        year_dir.mkdir(exist_ok=True)
        try:
            (year_dir / 'index.html').write_text(render(
                'census_year', page_title=f'{year} Census — {config.site_title}',
                year=year, date=date_str, events=events,
                ancestor_ids=ancestor_ids, descendant_ids=my_descendants, relation_map=relation_map,
            ))
        except Exception as e:
            census_errors.append(f'{year}: {type(e).__name__}: {e}')
    (census_dir / 'index.html').write_text(render(
        'census_index', page_title=f'Census Records — {config.site_title}',
        census_years=census_years_list,
    ))
    _report('census pages', len(census_data), census_errors, time.time() - t)
    print('Built census/index.html')

    _render_cemeteries_page(ctx)
    _render_ancestor_records_page(ctx)
    _render_ancestor_census_page(ctx)

    return all_people[root_id]


def _render_global_index(config, shared):
    """Render the top-level index listing all root people."""
    templates = shared['templates']
    all_people = shared['all_people']
    roots = [all_people[root_id] for root_id in config.roots if root_id in all_people]
    html = templates['global_index.pt'](page_title=config.site_title, roots=roots, has_custom_css=shared['has_custom_css'])
    (config.output_dir / 'index.html').write_text(html)
    print('Built index.html')


def _copy_static(config):
    for f in (_PACKAGE_DIR / 'static').iterdir():
        shutil.copy2(f, config.output_dir / f.name)
    if config.static_dir:
        for f in config.static_dir.iterdir():
            shutil.copy2(f, config.output_dir / f.name)


def build():
    config = get_config()
    db = open_db()

    shared = _make_shared_ctx(config, db)

    _copy_static(config)
    shared['has_custom_css'] = (config.output_dir / 'custom.css').exists()

    for root_id in config.roots:
        ctx = _make_root_ctx(shared, root_id)
        _build_root(ctx)

    _render_global_index(config, shared)

    db.close()


NAMED_PAGES = {'places', 'people', 'events', 'census', 'index', 'ancestor-records', 'census-records', 'birthdays', 'surnames', 'cemeteries', 'global-index'}


def _rebuild_root_pages(ctx, ids):
    """Rebuild specific pages under one root."""
    config = ctx['config']
    db = ctx['db']
    all_people = ctx['all_people']
    all_places = ctx['all_places']
    my_ancestors = ctx['my_ancestors']
    my_descendants = ctx['my_descendants']
    my_descendants_data = ctx['my_descendants_data']
    me_ancestor_distances = ctx['me_ancestor_distances']
    root_id = ctx['root_id']
    root_dir = ctx['root_dir']

    named = {i.lower() for i in ids if i.lower() in NAMED_PAGES}
    person_ids = [i for i in ids if i.startswith('I')]
    event_ids = [i for i in ids if i.startswith('E')]
    place_ids = [i for i in ids if i.startswith('P')]
    unknown = [i for i in ids if i.lower() not in NAMED_PAGES and not i.startswith(('I', 'E', 'P'))]
    for i in unknown:
        print(f'Unknown page {i!r} — expected a person ID (I…), event ID (E…), place ID (P…), or one of: {", ".join(sorted(NAMED_PAGES))}')

    for gid in person_ids:
        if gid not in all_people:
            print(f'Person {gid!r} not found')
            continue
        p = db.get_person_from_gramps_id(gid)
        relation = get_relation_to_me(db, me_ancestor_distances, p, all_people[gid]['gender'])
        marriage_relation = None
        if not relation and gid != root_id:
            marriage_relation = get_by_marriage_relation(db, me_ancestor_distances, p, all_people[gid]['gender'])
        by_marriage = not relation and gid != root_id and (marriage_relation is not None or is_related_by_marriage(db, me_ancestor_distances, p))
        _render_person_pages(ctx, gid, relation, by_marriage, marriage_relation)

    if root_id in person_ids:
        _build_pdfs(ctx)

    if event_ids or 'events' in named:
        relation_map = {
            gid: get_relation_to_me(db, me_ancestor_distances, db.get_person_from_gramps_id(gid), data['gender'])
            for gid, data in all_people.items()
        }
        if 'events' in named:
            events_dir = ctx['events_dir']
            render = ctx['render']
            ancestor_events = [
                {**e, 'is_descendant_event': any(p['gramps_id'] in my_descendants for p in e['people'])}
                for e in build_event_list(db, set(my_ancestors) - {root_id})
            ]
            (events_dir / 'index.html').write_text(
                render('events', page_title=f'Events — {config.site_title}',
                       events=ancestor_events, relation_map=relation_map)
            )
            all_event_data = build_event_pages_data(db)
            valid_events = {slug: ed for slug, ed in all_event_data.items() if slug}
            t = time.time()
            event_errors = []
            for slug, event_data in valid_events.items():
                try:
                    _render_event_page(ctx, slug, event_data, relation_map)
                except Exception as e:
                    event_errors.append(f'{event_data["gramps_id"]}: {type(e).__name__}: {e}')
            _report('event pages', len(valid_events), event_errors, time.time() - t)
            print(f'Rebuilt events/index.html [{root_id}]')
        else:
            all_event_data = build_event_pages_data(db)
            by_gramps_id = {ed['gramps_id']: (slug, ed) for slug, ed in all_event_data.items() if slug}
            for event_id in event_ids:
                if event_id not in by_gramps_id:
                    print(f'Event {event_id!r} not found')
                    continue
                slug, event_data = by_gramps_id[event_id]
                _render_event_page(ctx, slug, event_data, relation_map)

    if place_ids or 'places' in named:
        places_with_events, place_events = _compute_place_events(ctx)
        handle_by_id = {pdata['gramps_id']: handle for handle, pdata in all_places.items()}
        if 'places' in named:
            t = time.time()
            place_errors = []
            for handle in all_places:
                try:
                    _render_place_page(ctx, handle, place_events[handle])
                except Exception as e:
                    place_errors.append(f'{all_places[handle]["gramps_id"]}: {type(e).__name__}: {e}')
            _report('place pages', len(all_places), place_errors, time.time() - t)
            _render_places_index(ctx, places_with_events)
            print(f'Rebuilt places/index.html [{root_id}]')
        else:
            for pid in place_ids:
                handle = handle_by_id.get(pid)
                if not handle:
                    print(f'Place {pid!r} not found')
                    continue
                _render_place_page(ctx, handle, place_events[handle])

    if 'people' in named:
        search_rows = []
        for gid, data in all_people.items():
            p = db.get_person_from_gramps_id(gid)
            relation = get_relation_to_me(db, me_ancestor_distances, p, data['gender'])
            marriage_relation = None
            if not relation and gid != root_id:
                marriage_relation = get_by_marriage_relation(db, me_ancestor_distances, p, data['gender'])
            by_marriage = not relation and gid != root_id and (marriage_relation is not None or is_related_by_marriage(db, me_ancestor_distances, p))
            row = _render_person_pages(ctx, gid, relation, by_marriage, marriage_relation)
            search_rows.append(row)
        search_rows.sort(key=lambda r: (r['surname'], r['given']))
        people_dir = ctx['people_dir']
        render = ctx['render']
        (people_dir / 'index.html').write_text(
            render('search', page_title=f'People — {config.site_title}', rows=search_rows)
        )
        print(f'Rebuilt people/index.html [{root_id}]')

    if 'census' in named:
        render = ctx['render']
        census_data = build_census_data(db)
        place_lat_lon = ctx['place_lat_lon']
        for events_list in census_data.values():
            for event in events_list:
                pid = event['place_id']
                lat, lon = place_lat_lon.get(pid, (None, None)) if pid else (None, None)
                event['lat'] = lat
                event['lon'] = lon
        census_dir = root_dir / 'census'
        census_dir.mkdir(exist_ok=True)
        ancestor_ids = set(my_ancestors) - {root_id}
        relation_map = {
            gid: get_relation_to_me(db, me_ancestor_distances, db.get_person_from_gramps_id(gid), data['gender'])
            for gid, data in all_people.items()
        }
        census_years_list = []
        for year in sorted(census_data):
            events = census_data[year]
            day, month, _ = CENSUS_DATES.get(year, (None, None, None))
            date_str = f'{day} {MONTHS[month]} {year}' if day and month else str(year)
            people_count = len({p['gramps_id'] for e in events for p in e['people']})
            census_years_list.append({'year': year, 'date': date_str, 'count': len(events), 'people_count': people_count})
            year_dir = census_dir / str(year)
            year_dir.mkdir(exist_ok=True)
            (year_dir / 'index.html').write_text(render(
                'census_year', page_title=f'{year} Census — {config.site_title}',
                year=year, date=date_str, events=events,
                ancestor_ids=ancestor_ids, descendant_ids=my_descendants, relation_map=relation_map,
            ))
        (census_dir / 'index.html').write_text(render(
            'census_index', page_title=f'Census Records — {config.site_title}',
            census_years=census_years_list,
        ))
        print(f'Rebuilt census/index.html [{root_id}]')

    if 'index' in named:
        render = ctx['render']
        surnames = Counter(_clean_name_token(d['surname']) for d in all_people.values() if d['surname'] and _clean_name_token(d['surname']))
        given_name_genders = {}
        for d in all_people.values():
            if d['given']:
                first = _clean_name_token(d['given'].split()[0])
                if not first:
                    continue
                given_name_genders.setdefault(first, Counter())
                given_name_genders[first][d['gender']] += 1
        male_given = Counter()
        female_given = Counter()
        for name, genders in given_name_genders.items():
            total = sum(genders.values())
            if genders.get(1, 0) >= genders.get(0, 0):
                male_given[name] = total
            else:
                female_given[name] = total
        all_years = [y for d in all_people.values() for y in [d['birth_year'], d['death_year']] if y]
        summary = {
            'total_people': len(all_people),
            'total_ancestors': sum(1 for gid in my_ancestors if gid != root_id),
            'total_descendants': len(my_descendants_data),
            'total_places': len(all_places),
            'total_events': sum(1 for _ in db.iter_events()),
            'year_from': min(all_years) if all_years else None,
            'year_to': max(all_years) if all_years else None,
            'top_surnames': [(s, c, surname_slug(s)) for s, c in surnames.most_common(10)],
            'top_male_given': male_given.most_common(10),
            'top_female_given': female_given.most_common(10),
            'generations': group_by_generation(my_ancestors),
            'descendant_generations': group_descendants_by_generation(my_descendants_data),
        }
        ancestor_gens, descendant_gens, _, _ = _pdf_gen_counts(ctx)
        pdf_links = []
        if ancestor_gens:
            pdf_links.append({'label': 'Ancestor tree', 'filename': 'ancestors.pdf'})
        if descendant_gens:
            pdf_links.append({'label': 'Descendant tree', 'filename': 'descendants.pdf'})
        if ancestor_gens and descendant_gens:
            pdf_links.append({'label': 'Hourglass tree', 'filename': 'hourglass.pdf'})
        _root_full_name = ctx['root_full_name']
        apostrophe = "'" if _root_full_name[-1].lower() == 's' else "'s"
        index_title = f"{_root_full_name}{apostrophe} family tree"
        (root_dir / 'index.html').write_text(
            render('index', page_title=index_title, summary=summary, pdf_links=pdf_links)
        )
        print(f'Rebuilt index.html [{root_id}]')

    if 'cemeteries' in named:
        _render_cemeteries_page(ctx)

    if 'ancestor-records' in named:
        _render_ancestor_records_page(ctx)

    if 'census-records' in named:
        _render_ancestor_census_page(ctx)

    if 'surnames' in named:
        _render_surname_pages(ctx)
        print(f'Rebuilt surnames/index.html [{root_id}]')

    if 'birthdays' in named:
        render = ctx['render']
        birthdays_dir = root_dir / 'birthdays'
        birthdays_dir.mkdir(exist_ok=True)
        birthday_months = build_birthday_list(db)
        total_birthdays = sum(len(d['people']) for m in birthday_months for d in m['days'])
        (birthdays_dir / 'index.html').write_text(
            render('birthdays', page_title=f'Birthdays — {config.site_title}',
                   birthday_months=birthday_months, total_birthdays=total_birthdays,
                   ancestor_ids=set(my_ancestors) - {root_id},
                   descendant_ids=my_descendants)
        )
        print(f'Rebuilt birthdays/index.html [{root_id}]')


def rebuild_pages(ids):
    """Rebuild specific pages by ID or name and copy static files.

    Accepts person IDs (I…), event IDs (E…), place IDs (P…), and named
    pages: places, people, events, census, index, birthdays, surnames, ancestor-records, census-records, global-index.
    """
    config = get_config()
    db = open_db()

    shared = _make_shared_ctx(config, db)

    _copy_static(config)
    shared['has_custom_css'] = (config.output_dir / 'custom.css').exists()

    non_global_ids = [i for i in ids if i != 'global-index']
    if non_global_ids:
        for root_id in config.roots:
            ctx = _make_root_ctx(shared, root_id)
            _rebuild_root_pages(ctx, non_global_ids)

    if 'global-index' in ids:
        _render_global_index(config, shared)

    db.close()


if __name__ == '__main__':
    build()
