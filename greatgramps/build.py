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
    ancestors_with_distances, get_relation_to_me,
    get_photos, get_occupations, place_data, build_place_event_index, build_event_list,
    build_event_pages_data, build_birthday_list, person_data,
    collect_ancestor_tree, collect_descendant_tree, count_descendants,
    collect_all_descendants, group_descendants_by_generation,
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

    return f'../../media/{filename}'


def surname_slug(name):
    slug = re.sub(r"['’]", '', name)
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


def build():
    config = get_config()
    db = open_db()
    me = db.get_person_from_gramps_id(config.me)

    all_people = collect_all_people(db)
    my_ancestors = collect_ancestors(db, me)
    me_ancestor_distances = ancestors_with_distances(db, me)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    for f in config.static_dir.iterdir():
        shutil.copy2(f, config.output_dir / f.name)

    people_dir = config.output_dir / 'people'
    people_dir.mkdir(parents=True, exist_ok=True)
    media_dir = config.output_dir / 'media'
    media_dir.mkdir(exist_ok=True)

    # Build place event index (used by person pages and place pages)
    place_event_index = build_place_event_index(db)

    # Build a place_handle -> place page URL map for linking from person pages
    places_dir = config.output_dir / 'places'
    places_dir.mkdir(exist_ok=True)
    all_places = {p.get_handle(): place_data(p) for p in db.iter_places()}

    # Build enclosing chain and sub_places for each place
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

    place_url = {d['gramps_id']: f'../../places/{d["gramps_id"]}/' for d in all_places.values()}
    place_lat_lon = {
        d['gramps_id']: (d['lat'], d['lon'])
        for d in all_places.values()
        if d['lat'] and d['lon']
    }

    # Precompute geocoded event places per person (for ancestor maps)
    person_place_events = {}
    for _gid, _pdata in all_people.items():
        _p = db.get_person_from_gramps_id(_gid)
        person_place_events[_gid] = [
            {'place_id': e['place_id'], 'place': e['place'], 'type': e['type']}
            for e in get_all_events(db, _p)
            if e.get('place_id') and e['place_id'] in place_lat_lon
        ]

    me_id = config.me

    # Build surname slug map and URL map (relative to person pages at people/{id}/)
    surnames_dir = config.output_dir / 'surnames'
    surnames_dir.mkdir(exist_ok=True)
    by_surname = {}
    for gid, data in all_people.items():
        s = data['surname']
        if s:
            by_surname.setdefault(s, []).append(gid)
    surname_page_url = {s: f'../../surnames/{surname_slug(s)}/' for s in by_surname}

    # Compute summary stats
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

    # Load templates
    templates = PageTemplateLoader(str(config.templates_dir))
    layout = templates['layout.pt'].macros['layout']

    def render(template_name, base, page_title, **kwargs):
        return templates[f'{template_name}.pt'](
            layout=layout, base=base, page_title=page_title, me_id=me_id, **kwargs
        )

    # Build index
    (config.output_dir / 'index.html').write_text(
        render('index', base='', page_title='Family Tree', summary=summary)
    )
    print('Built index.html')

    # Build a page for every person
    search_rows = []
    relation_map = {}
    for gid, data in all_people.items():
        p = db.get_person_from_gramps_id(gid)
        father_p, mother_p = get_parents(db, p)
        children_p = get_children(db, p)
        spouses = get_spouses(db, p)
        person_ancestors = collect_ancestors(db, p)
        relation = get_relation_to_me(db, me_ancestor_distances, p, data['gender'])
        relation_map[gid] = relation
        photos = [
            {**photo, 'url': process_photo(photo, media_dir, gid)}
            for photo in get_photos(db, p)
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
                        'url': f'../../places/{pid}/',
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
        html = render(
            'person',
            base='../../',
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
            photos=photos,
            occupations=occupations,
            place_url=place_url,
            generations=group_by_generation(person_ancestors),
            descendant_generations=descendant_generations,
            event_map_json=event_map_json,
            surname_url=surname_page_url.get(data['surname']),
            current_year=date.today().year,
            num_ancestors=num_ancestors,
            num_descendants=num_descendants,
        )
        person_out = people_dir / gid
        person_out.mkdir(exist_ok=True)
        (person_out / 'index.html').write_text(html)

        tree_nodes, tree_rows, tree_cols = collect_ancestor_tree(db, p)
        tree_grid_style = (
            f'grid-template-rows:repeat({tree_rows},minmax(2.5rem,auto));'
            f'grid-template-columns:repeat({tree_cols},minmax(140px,1fr))'
        )
        tree_surname_url = f'../../../surnames/{surname_slug(data["surname"])}/' if data['surname'] else None
        tree_base = '../../../'
        ancestors_map_json = _make_map_json(person_place_events, person_ancestors, place_lat_lon, tree_base)
        ancestors_dir = person_out / 'ancestors'
        ancestors_dir.mkdir(exist_ok=True)
        (ancestors_dir / 'index.html').write_text(render(
            'tree',
            base=tree_base,
            page_title=f"{data['full_name']} — Ancestor Tree",
            person=data,
            nodes=tree_nodes,
            tree_grid_style=tree_grid_style,
            num_ancestors=num_ancestors,
            num_descendants=num_descendants,
            is_ancestor=gid in my_ancestors and gid != config.me,
            is_me=gid == config.me,
            relation=relation,
            surname_url=tree_surname_url,
            current_year=date.today().year,
            ancestors_map_json=ancestors_map_json,
        ))

        desc_nodes, desc_rows, desc_cols = collect_descendant_tree(db, p)
        desc_grid_style = (
            f'grid-template-columns:repeat({desc_cols},minmax(140px,1fr));'
            f'grid-template-rows:repeat({desc_rows},minmax(2.5rem,auto))'
        )
        desc_surname_url = f'../../../surnames/{surname_slug(data["surname"])}/' if data['surname'] else None
        descendants_map_json = _make_map_json(person_place_events, all_descendants, place_lat_lon, tree_base)
        descendants_dir = person_out / 'descendants'
        descendants_dir.mkdir(exist_ok=True)
        (descendants_dir / 'index.html').write_text(render(
            'descendants_tree',
            base=tree_base,
            page_title=f"{data['full_name']} — Descendant Tree",
            person=data,
            nodes=desc_nodes,
            tree_grid_style=desc_grid_style,
            num_ancestors=num_ancestors,
            num_descendants=num_descendants,
            is_ancestor=gid in my_ancestors and gid != config.me,
            is_me=gid == config.me,
            relation=relation,
            surname_url=desc_surname_url,
            current_year=date.today().year,
            descendants_map_json=descendants_map_json,
        ))

        search_rows.append({**data, 'num_children': len(children_p), 'num_spouses': len(spouses),
                            'is_ancestor': gid in my_ancestors and gid != config.me})

    print(f'Built {len(all_people)} person pages')

    # Build search page
    search_rows.sort(key=lambda r: (r['surname'], r['given']))
    (people_dir / 'index.html').write_text(
        render('search', base='../', page_title='People — Family Tree', rows=search_rows)
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
            base='../../',
            page_title=f"{pdata['name']} — Family Tree",
            place=pdata,
            events=events,
            ancestor_ids=set(my_ancestors) - {config.me},
        )
        place_out = places_dir / pdata['gramps_id']
        place_out.mkdir(exist_ok=True)
        (place_out / 'index.html').write_text(html)

    places_with_events.sort(key=lambda p: -p['event_count'])
    mappable = [
        p for p in places_with_events
        if p['lat'] and p['lon']
    ]
    mappable_json = json.dumps([
        {'lat': p['lat'], 'lon': p['lon'], 'name': p['name'],
         'url': f'{p["gramps_id"]}/', 'count': p['event_count']}
        for p in mappable
    ])
    (places_dir / 'index.html').write_text(
        render('places', base='../', page_title='Places — Family Tree',
               places=places_with_events, mappable_json=mappable_json)
    )
    print(f'Built {len(all_places)} place pages')

    # Build events page (ancestor events only)
    events_dir = config.output_dir / 'events'
    events_dir.mkdir(exist_ok=True)
    ancestor_events = build_event_list(db, set(my_ancestors) - {config.me})
    (events_dir / 'index.html').write_text(
        render('events', base='../', page_title='Events — Family Tree',
               events=ancestor_events, relation_map=relation_map)
    )
    print(f'Built events/index.html ({len(ancestor_events)} events)')

    # Build individual event pages
    ancestor_ids = set(my_ancestors) - {config.me}
    all_event_data = build_event_pages_data(db)
    for slug, event_data in all_event_data.items():
        if not slug:
            continue
        is_ancestor_event = any(p['gramps_id'] in ancestor_ids for p in event_data['people'])
        pid = event_data['place_id']
        if pid and pid in place_lat_lon:
            lat, lon = place_lat_lon[pid]
            event_map_json = json.dumps([{
                'lat': lat, 'lon': lon,
                'name': event_data['place'],
                'url': f'../../places/{pid}/',
            }])
        else:
            event_map_json = '[]'
        photos = [
            {**photo, 'url': process_photo(photo, media_dir, event_data['gramps_id'])}
            for photo in event_data['photos']
        ]
        couple_photos = []
        for pd in filter(None, event_data.get('couple') or []):
            person_obj = db.get_person_from_gramps_id(pd['gramps_id'])
            if person_obj:
                for photo in get_photos(db, person_obj):
                    couple_photos.append({**photo, 'url': process_photo(photo, media_dir, pd['gramps_id'])})
        event_out = events_dir / slug
        event_out.mkdir(exist_ok=True)
        date_str = f' {event_data["date"]}' if event_data['date'] else ''
        people = event_data.get('people', [])
        if len(people) == 1:
            person_str = f' of {people[0]["full_name"]}'
        else:
            person_str = ''
        (event_out / 'index.html').write_text(render(
            'event',
            base='../../',
            page_title=f"{event_data['type']}{person_str}{date_str} — Family Tree",
            event=event_data,
            photos=photos,
            couple_photos=couple_photos,
            children=event_data.get('children', []),
            is_ancestor_event=is_ancestor_event,
            ancestor_ids=ancestor_ids,
            relation_map=relation_map,
            event_map_json=event_map_json,
        ))
    print(f'Built {len(all_event_data)} event pages')

    # Build birthdays page
    birthdays_dir = config.output_dir / 'birthdays'
    birthdays_dir.mkdir(exist_ok=True)
    birthday_months = build_birthday_list(db)
    total_birthdays = sum(len(d['people']) for m in birthday_months for d in m['days'])
    (birthdays_dir / 'index.html').write_text(
        render('birthdays', base='../', page_title='Birthdays — Family Tree',
               birthday_months=birthday_months, total_birthdays=total_birthdays,
               ancestor_ids=set(my_ancestors) - {config.me})
    )
    print(f'Built birthdays/index.html ({total_birthdays} birthdays)')

    # Build surname pages and index
    surnames_list = sorted(
        [{'surname': s, 'count': len(gids), 'slug': surname_slug(s)} for s, gids in by_surname.items()],
        key=lambda x: x['surname'],
    )
    (surnames_dir / 'index.html').write_text(
        render('surnames', base='../', page_title='Surnames — Family Tree', surnames=surnames_list)
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
            render('surname', base='../../', page_title=f'{surname} — Family Tree',
                   surname=surname, people=people_on_page)
        )
    print(f'Built {len(by_surname)} surname pages')

    db.close()


if __name__ == '__main__':
    build()
