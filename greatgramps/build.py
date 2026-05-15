#!/home/ben/.virtualenvs/gramps/bin/python
import json
import re
import shutil
from collections import Counter
from datetime import date
from PIL import Image
from chameleon import PageTemplateLoader
from .gramps_data import (
    open_db, collect_all_people, collect_ancestors,
    get_parents, get_children, get_siblings, get_spouses, get_all_events,
    ancestors_with_distances, get_relation_to_me, is_related_by_marriage, get_by_marriage_relation,
    get_photos, get_occupations, get_all_person_pictures, place_data, build_place_event_index, build_event_list,
    build_event_pages_data, build_birthday_list, person_data,
    collect_ancestor_tree, collect_descendant_tree, count_descendants,
    collect_all_descendants, group_descendants_by_generation,
    build_census_data, CENSUS_DATES, MONTHS,
)
from .settings import get_config


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


def _make_ctx(config, db):
    """Build shared context needed to render any page."""
    me = db.get_person_from_gramps_id(config.me)
    all_people = collect_all_people(db)
    my_ancestors = collect_ancestors(db, me)
    me_ancestor_distances = ancestors_with_distances(db, me)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    people_dir = config.output_dir / 'people'
    people_dir.mkdir(parents=True, exist_ok=True)
    media_dir = config.output_dir / 'media'
    media_dir.mkdir(exist_ok=True)
    events_dir = config.output_dir / 'events'
    events_dir.mkdir(exist_ok=True)
    places_dir = config.output_dir / 'places'
    places_dir.mkdir(exist_ok=True)

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

    place_url = {d['gramps_id']: f'/places/{d["gramps_id"]}/' for d in all_places.values()}
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
    for gid, data in all_people.items():
        s = data['surname']
        if s:
            by_surname.setdefault(s, []).append(gid)
    surname_page_url = {s: f'/surnames/{surname_slug(s)}/' for s in by_surname}

    templates = PageTemplateLoader(str(config.templates_dir))
    layout = templates['layout.pt'].macros['layout']
    person_header = templates['person_header.pt'].macros['person_header']
    me_id = config.me

    def render(template_name, base, page_title, **kwargs):
        return templates[f'{template_name}.pt'](
            layout=layout, base=base, page_title=page_title, me_id=me_id,
            person_header=person_header, **kwargs
        )

    return {
        'config': config,
        'db': db,
        'me': me,
        'all_people': all_people,
        'my_ancestors': my_ancestors,
        'me_ancestor_distances': me_ancestor_distances,
        'people_dir': people_dir,
        'media_dir': media_dir,
        'events_dir': events_dir,
        'places_dir': places_dir,
        'all_places': all_places,
        'place_url': place_url,
        'place_lat_lon': place_lat_lon,
        'place_event_index': place_event_index,
        'descendant_handles': descendant_handles,
        'person_place_events': person_place_events,
        'by_surname': by_surname,
        'surname_page_url': surname_page_url,
        'render': render,
    }


def _render_person_pages(ctx, gid, relation, by_marriage, marriage_relation=None):
    """Render profile, ancestors, and descendants pages for one person."""
    db = ctx['db']
    config = ctx['config']
    all_people = ctx['all_people']
    my_ancestors = ctx['my_ancestors']
    media_dir = ctx['media_dir']
    people_dir = ctx['people_dir']
    place_lat_lon = ctx['place_lat_lon']
    place_url = ctx['place_url']
    surname_page_url = ctx['surname_page_url']
    person_place_events = ctx['person_place_events']
    render = ctx['render']

    data = all_people[gid]
    p = db.get_person_from_gramps_id(gid)
    father_p, mother_p = get_parents(db, p)
    children_p = get_children(db, p)
    spouses = get_spouses(db, p)
    person_ancestors = collect_ancestors(db, p)
    photos = [
        {**photo, 'url': process_photo(photo, media_dir, gid)}
        for photo in get_photos(db, p)
    ]
    all_pictures = [
        {**pic, 'url': process_photo(pic, media_dir, gid)}
        for pic in get_all_person_pictures(db, p)
    ]
    occupations = get_occupations(p)
    events = get_all_events(db, p)
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
                    'url': f'/places/{pid}/',
                    'types': [],
                }
            map_points[pid]['types'].append(event['type'])
    event_map_json = json.dumps(list(map_points.values()))
    num_ancestors = len(person_ancestors) - 1
    all_descendants = collect_all_descendants(db, p)
    for desc_gid, desc_data in all_descendants.items():
        desc_data['is_ancestor'] = desc_gid in my_ancestors and desc_gid != config.me
        desc_data['is_me'] = desc_gid == config.me
    num_descendants = len(all_descendants)
    descendant_generations = group_descendants_by_generation(all_descendants)
    alt_surname_urls = {
        n['surname']: surname_page_url.get(n['surname'])
        for n in data['alt_names'] if n['surname']
    }
    html = render(
        'person',
        base='/',
        page_title=f"{data['full_name']} — Family Tree",
        person=data,
        father=person_data(db, father_p) if father_p else None,
        mother=person_data(db, mother_p) if mother_p else None,
        children=[{**person_data(db, c), 'is_ancestor': c.get_gramps_id() in my_ancestors} for c in children_p],
        siblings=get_siblings(db, p),
        spouses=spouses,
        events=events,
        is_ancestor=gid in my_ancestors and gid != config.me,
        is_me=gid == config.me,
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
    ancestors_map_json = _make_map_json(person_place_events, person_ancestors, place_lat_lon, '/')
    ancestors_dir = person_out / 'ancestors'
    ancestors_dir.mkdir(exist_ok=True)
    (ancestors_dir / 'index.html').write_text(render(
        'tree',
        base='/',
        page_title=f"{data['full_name']} — Ancestor Tree",
        person=data,
        nodes=tree_nodes,
        tree_grid_style=tree_grid_style,
        num_ancestors=num_ancestors,
        num_descendants=num_descendants,
        is_ancestor=gid in my_ancestors and gid != config.me,
        is_me=gid == config.me,
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
    descendants_map_json = _make_map_json(person_place_events, all_descendants, place_lat_lon, '/')
    descendants_dir = person_out / 'descendants'
    descendants_dir.mkdir(exist_ok=True)
    (descendants_dir / 'index.html').write_text(render(
        'descendants_tree',
        base='/',
        page_title=f"{data['full_name']} — Descendant Tree",
        person=data,
        nodes=desc_nodes,
        tree_grid_style=desc_grid_style,
        num_ancestors=num_ancestors,
        num_descendants=num_descendants,
        is_ancestor=gid in my_ancestors and gid != config.me,
        is_me=gid == config.me,
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
        base='/',
        page_title=f"{data['full_name']} — Pictures",
        person=data,
        pictures=all_pictures,
        num_ancestors=num_ancestors,
        num_descendants=num_descendants,
        is_ancestor=gid in my_ancestors and gid != config.me,
        is_me=gid == config.me,
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
            'is_ancestor': gid in my_ancestors and gid != config.me,
            'alt_surnames': [n['surname'] for n in data['alt_names'] if n['surname']]}


def _render_event_page(ctx, slug, event_data, relation_map):
    """Render a single event page."""
    db = ctx['db']
    config = ctx['config']
    my_ancestors = ctx['my_ancestors']
    media_dir = ctx['media_dir']
    events_dir = ctx['events_dir']
    place_lat_lon = ctx['place_lat_lon']
    render = ctx['render']

    ancestor_ids = set(my_ancestors) - {config.me}
    is_ancestor_event = any(p['gramps_id'] in ancestor_ids for p in event_data['people'])
    pid = event_data['place_id']
    if pid and pid in place_lat_lon:
        lat, lon = place_lat_lon[pid]
        event_map_json = json.dumps([{
            'lat': lat, 'lon': lon,
            'name': event_data['place'],
            'url': f'/places/{pid}/',
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
        page_title = f"{event_data['description']} — Family Tree"
    elif couple:
        names = ' and '.join(p['full_name'] for p in couple if p)
        person_str = f' of {names}' if names else ''
        page_title = f"{event_data['type']}{person_str} — Family Tree"
    elif len(people) == 1:
        page_title = f"{event_data['type']} of {people[0]['full_name']} — Family Tree"
    else:
        page_title = f"{event_data['type']} — Family Tree"
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
        base='/',
        page_title=page_title,
        event=event_data,
        photos=photos,
        couple_photos=[],
        couple_details=couple_details,
        children=event_data.get('children', []),
        is_ancestor_event=is_ancestor_event,
        ancestor_ids=ancestor_ids,
        relation_map=relation_map,
        event_map_json=event_map_json,
    ))


def build():
    config = get_config()
    db = open_db()

    for f in config.static_dir.iterdir():
        shutil.copy2(f, config.output_dir / f.name)

    ctx = _make_ctx(config, db)
    all_people = ctx['all_people']
    my_ancestors = ctx['my_ancestors']
    me_ancestor_distances = ctx['me_ancestor_distances']
    all_places = ctx['all_places']
    place_lat_lon = ctx['place_lat_lon']
    place_event_index = ctx['place_event_index']
    descendant_handles = ctx['descendant_handles']
    by_surname = ctx['by_surname']
    places_dir = ctx['places_dir']
    render = ctx['render']

    # Compute summary stats for index page
    surnames = Counter(d['surname'] for d in all_people.values() if d['surname'])
    given_names = Counter(
        d['given'].split()[0] for d in all_people.values() if d['given']
    )
    all_years = [y for d in all_people.values() for y in [d['birth_year'], d['death_year']] if y]
    summary = {
        'total_people': len(all_people),
        'total_ancestors': sum(1 for gid in my_ancestors if gid != config.me),
        'total_places': len(all_places),
        'total_events': sum(1 for _ in db.iter_events()),
        'year_from': min(all_years) if all_years else None,
        'year_to': max(all_years) if all_years else None,
        'top_surnames': [(s, c, surname_slug(s)) for s, c in surnames.most_common(15)],
        'top_given': given_names.most_common(15),
        'generations': group_by_generation(my_ancestors),
    }

    (config.output_dir / 'index.html').write_text(
        render('index', base='/', page_title='Family Tree', summary=summary)
    )
    print('Built index.html')

    # Build a page for every person
    search_rows = []
    relation_map = {}
    for gid, data in all_people.items():
        p = db.get_person_from_gramps_id(gid)
        relation = get_relation_to_me(db, me_ancestor_distances, p, data['gender'])
        marriage_relation = None
        if not relation and gid != config.me:
            marriage_relation = get_by_marriage_relation(db, me_ancestor_distances, p, data['gender'])
        by_marriage = not relation and gid != config.me and (marriage_relation is not None or is_related_by_marriage(db, me_ancestor_distances, p))
        relation_map[gid] = relation
        search_row = _render_person_pages(ctx, gid, relation, by_marriage, marriage_relation)
        search_rows.append(search_row)

    print(f'Built {len(all_people)} person pages')

    # Build search page
    search_rows.sort(key=lambda r: (r['surname'], r['given']))
    people_dir = ctx['people_dir']
    (people_dir / 'index.html').write_text(
        render('search', base='/', page_title='People — Family Tree', rows=search_rows)
    )
    print('Built people/index.html')

    # Build place pages
    places_with_events = []
    for handle, pdata in all_places.items():
        direct = [{**e, 'sub_place': None, 'sub_place_id': None}
                  for e in place_event_index.get(handle, [])]
        nested = [
            {**e, 'sub_place': all_places[h]['name'], 'sub_place_id': all_places[h]['gramps_id']}
            for h in descendant_handles(handle)
            for e in place_event_index.get(h, [])
        ]
        events = sorted(direct + nested, key=lambda e: e['year'] or 9999)
        if events:
            places_with_events.append({**pdata, 'event_count': len(events)})
        html = render(
            'place',
            base='/',
            page_title=f"{pdata['name']} — Family Tree",
            place=pdata,
            events=events,
            ancestor_ids=set(my_ancestors) - {config.me},
        )
        place_out = places_dir / pdata['gramps_id']
        place_out.mkdir(exist_ok=True)
        (place_out / 'index.html').write_text(html)

    places_with_events.sort(key=lambda p: -p['event_count'])
    mappable = [p for p in places_with_events if p['lat'] and p['lon']]
    mappable_json = json.dumps([
        {'lat': p['lat'], 'lon': p['lon'], 'name': p['name'],
         'url': f'{p["gramps_id"]}/', 'count': p['event_count']}
        for p in mappable
    ])
    (places_dir / 'index.html').write_text(
        render('places', base='/', page_title='Places — Family Tree',
               places=places_with_events, mappable_json=mappable_json)
    )
    print(f'Built {len(all_places)} place pages')

    # Build events list page
    events_dir = ctx['events_dir']
    ancestor_events = build_event_list(db, set(my_ancestors) - {config.me})
    (events_dir / 'index.html').write_text(
        render('events', base='/', page_title='Events — Family Tree',
               events=ancestor_events, relation_map=relation_map)
    )
    print(f'Built events/index.html ({len(ancestor_events)} events)')

    # Build individual event pages
    all_event_data = build_event_pages_data(db)
    for slug, event_data in all_event_data.items():
        if not slug:
            continue
        _render_event_page(ctx, slug, event_data, relation_map)
    print(f'Built {len(all_event_data)} event pages')

    # Build birthdays page
    birthdays_dir = config.output_dir / 'birthdays'
    birthdays_dir.mkdir(exist_ok=True)
    birthday_months = build_birthday_list(db)
    total_birthdays = sum(len(d['people']) for m in birthday_months for d in m['days'])
    (birthdays_dir / 'index.html').write_text(
        render('birthdays', base='/', page_title='Birthdays — Family Tree',
               birthday_months=birthday_months, total_birthdays=total_birthdays,
               ancestor_ids=set(my_ancestors) - {config.me})
    )
    print(f'Built birthdays/index.html ({total_birthdays} birthdays)')

    # Build surname pages and index
    surnames_dir = config.output_dir / 'surnames'
    surnames_dir.mkdir(exist_ok=True)
    surnames_list = sorted(
        [{'surname': s, 'count': len(gids), 'slug': surname_slug(s)} for s, gids in by_surname.items()],
        key=lambda x: x['surname'],
    )
    (surnames_dir / 'index.html').write_text(
        render('surnames', base='/', page_title='Surnames — Family Tree', surnames=surnames_list)
    )
    for surname, gids in by_surname.items():
        people_on_page = sorted(
            [{**all_people[gid], 'is_ancestor': gid in my_ancestors and gid != config.me,
              'is_me': gid == config.me} for gid in gids],
            key=lambda p: (p['birth_year'] or 9999, p['surname'], p['given']),
        )
        slug = surname_slug(surname)
        surname_out = surnames_dir / slug
        surname_out.mkdir(exist_ok=True)
        (surname_out / 'index.html').write_text(
            render('surname', base='/', page_title=f'{surname} — Family Tree',
                   surname=surname, people=people_on_page)
        )
    print(f'Built {len(by_surname)} surname pages')

    # Build census pages
    census_data = build_census_data(db)
    for events_list in census_data.values():
        for event in events_list:
            pid = event['place_id']
            lat, lon = place_lat_lon.get(pid, (None, None)) if pid else (None, None)
            event['lat'] = lat
            event['lon'] = lon
    census_dir = config.output_dir / 'census'
    census_dir.mkdir(exist_ok=True)
    ancestor_ids = set(my_ancestors) - {config.me}

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
            'census_year',
            base='/',
            page_title=f'{year} Census — Family Tree',
            year=year,
            date=date_str,
            events=events,
            ancestor_ids=ancestor_ids,
            relation_map=relation_map,
        ))

    (census_dir / 'index.html').write_text(render(
        'census_index',
        base='/',
        page_title='Census Records — Family Tree',
        census_years=census_years_list,
    ))
    print(f'Built census/index.html and {len(census_data)} census year pages')

    db.close()


def rebuild_pages(ids):
    """Rebuild specific pages by ID (e.g. I0061, E0315) and copy static files."""
    config = get_config()
    db = open_db()

    for f in config.static_dir.iterdir():
        shutil.copy2(f, config.output_dir / f.name)

    ctx = _make_ctx(config, db)
    all_people = ctx['all_people']
    my_ancestors = ctx['my_ancestors']
    me_ancestor_distances = ctx['me_ancestor_distances']

    person_ids = [i for i in ids if not i.startswith('E')]
    event_ids = [i for i in ids if i.startswith('E')]

    for gid in person_ids:
        if gid not in all_people:
            print(f'Person {gid!r} not found')
            continue
        p = db.get_person_from_gramps_id(gid)
        relation = get_relation_to_me(db, me_ancestor_distances, p, all_people[gid]['gender'])
        marriage_relation = None
        if not relation and gid != config.me:
            marriage_relation = get_by_marriage_relation(db, me_ancestor_distances, p, all_people[gid]['gender'])
        by_marriage = not relation and gid != config.me and (marriage_relation is not None or is_related_by_marriage(db, me_ancestor_distances, p))
        _render_person_pages(ctx, gid, relation, by_marriage, marriage_relation)
        print(f'Rebuilt {gid}')

    if event_ids:
        relation_map = {
            gid: get_relation_to_me(db, me_ancestor_distances, db.get_person_from_gramps_id(gid), data['gender'])
            for gid, data in all_people.items()
        }
        all_event_data = build_event_pages_data(db)
        by_gramps_id = {ed['gramps_id']: (slug, ed) for slug, ed in all_event_data.items() if slug}
        for event_id in event_ids:
            if event_id not in by_gramps_id:
                print(f'Event {event_id!r} not found')
                continue
            slug, event_data = by_gramps_id[event_id]
            _render_event_page(ctx, slug, event_data, relation_map)
            print(f'Rebuilt {event_id}')

    db.close()


if __name__ == '__main__':
    build()
