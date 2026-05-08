#!/home/ben/.virtualenvs/gramps/bin/python
import json
import re
import shutil
from collections import Counter
from PIL import Image
from chameleon import PageTemplateFile
from greatgramps.gramps_data import (
    open_db, collect_all_people, collect_ancestors,
    get_parents, get_children, get_siblings, get_spouses, get_all_events,
    ancestors_with_distances, get_relation_to_me,
    get_photos, place_data, build_place_event_index, person_data,
)
from greatgramps.settings import get_config


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
    place_url = {d['gramps_id']: f'../../places/{d["gramps_id"]}/' for d in all_places.values()}
    place_lat_lon = {
        d['gramps_id']: (d['lat'], d['lon'])
        for d in all_places.values()
        if d['lat'] and d['lon']
    }

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
        'year_from': min(all_years) if all_years else None,
        'year_to': max(all_years) if all_years else None,
        'top_surnames': [(s, c, surname_slug(s)) for s, c in surnames.most_common(15)],
        'top_given': given_names.most_common(15),
        'generations': group_by_generation(my_ancestors),
    }

    # Build index
    index_tmpl = PageTemplateFile(str(config.templates_dir / 'index.pt'))
    (config.output_dir / 'index.html').write_text(
        index_tmpl(summary=summary, me_id=me_id)
    )
    print('Built index.html')

    # Build a page for every person
    person_tmpl = PageTemplateFile(str(config.templates_dir / 'person.pt'))
    search_rows = []
    for gid, data in all_people.items():
        p = db.get_person_from_gramps_id(gid)
        father_p, mother_p = get_parents(db, p)
        children_p = get_children(db, p)
        spouses = get_spouses(db, p)
        person_ancestors = collect_ancestors(db, p)
        relation = get_relation_to_me(db, me_ancestor_distances, p, data['gender'])
        photos = [
            {**photo, 'url': process_photo(photo, media_dir, gid)}
            for photo in get_photos(db, p)
        ]
        events = get_all_events(db, p)
        map_points = {}
        for event in events:
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
        html = person_tmpl(
            person=data,
            father=person_data(db, father_p) if father_p else None,
            mother=person_data(db, mother_p) if mother_p else None,
            children=[person_data(db, c) for c in children_p],
            siblings=get_siblings(db, p),
            spouses=spouses,
            events=events,
            is_ancestor=gid in my_ancestors and gid != config.me,
            is_me=gid == config.me,
            relation=relation,
            photos=photos,
            place_url=place_url,
            generations=group_by_generation(person_ancestors),
            me_id=me_id,
            event_map_json=event_map_json,
            surname_url=surname_page_url.get(data['surname']),
        )
        person_out = people_dir / gid
        person_out.mkdir(exist_ok=True)
        (person_out / 'index.html').write_text(html)
        search_rows.append({**data, 'num_children': len(children_p), 'num_spouses': len(spouses)})

    print(f'Built {len(all_people)} person pages')

    # Build search page
    search_rows.sort(key=lambda r: (r['surname'], r['given']))
    search_tmpl = PageTemplateFile(str(config.templates_dir / 'search.pt'))
    (people_dir / 'index.html').write_text(search_tmpl(rows=search_rows, me_id=me_id))
    print('Built people/index.html')

    # Build place pages
    place_tmpl = PageTemplateFile(str(config.templates_dir / 'place.pt'))
    places_index_tmpl = PageTemplateFile(str(config.templates_dir / 'places.pt'))

    places_with_events = []
    for handle, pdata in all_places.items():
        events = place_event_index.get(handle, [])
        if events:
            places_with_events.append({**pdata, 'event_count': len(events)})
        html = place_tmpl(place=pdata, events=events, me_id=me_id)
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
        places_index_tmpl(places=places_with_events, mappable_json=mappable_json, me_id=me_id)
    )
    print(f'Built {len(all_places)} place pages')

    # Build surname pages and index
    surname_tmpl = PageTemplateFile(str(config.templates_dir / 'surname.pt'))
    surnames_index_tmpl = PageTemplateFile(str(config.templates_dir / 'surnames.pt'))
    surnames_list = sorted(
        [{'surname': s, 'count': len(gids), 'slug': surname_slug(s)} for s, gids in by_surname.items()],
        key=lambda x: x['surname'],
    )
    (surnames_dir / 'index.html').write_text(
        surnames_index_tmpl(surnames=surnames_list, me_id=me_id)
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
            surname_tmpl(surname=surname, people=people_on_page, me_id=me_id)
        )
    print(f'Built {len(by_surname)} surname pages')

    db.close()


if __name__ == '__main__':
    build()
