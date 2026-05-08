#!/home/ben/.virtualenvs/gramps/bin/python
from PIL import Image
from chameleon import PageTemplateFile
from greatgramps.gramps_data import (
    open_db, collect_all_people, collect_ancestors,
    get_parents, get_children, get_siblings, get_spouses, get_all_events,
    ancestors_with_distances, get_relation_to_me,
    get_photos, person_data,
)
from greatgramps.settings import get_config


def process_photo(photo, media_dir, person_id):
    """Copy or crop a photo into media_dir, return the web path."""
    src = photo['src']
    rect = photo['rect']
    filename = f"{person_id}_{photo['media_id']}{src.suffix}"
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
        img.save(dest)

    return f'../media/{filename}'


def group_by_generation(ancestors):
    by_gen = {}
    for gid, data in ancestors.items():
        by_gen.setdefault(data['generation'], []).append(data)
    return [{'gen': g, 'people': by_gen[g]} for g in sorted(by_gen)]


def build():
    config = get_config()
    db = open_db()
    me = db.get_person_from_gramps_id(config.me)

    all_people = collect_all_people(db)
    my_ancestors = collect_ancestors(db, me)
    me_ancestor_distances = ancestors_with_distances(db, me)

    people_dir = config.output_dir / 'people'
    people_dir.mkdir(parents=True, exist_ok=True)
    media_dir = config.output_dir / 'media'
    media_dir.mkdir(exist_ok=True)

    # Build index — my ancestors grouped by generation
    index_tmpl = PageTemplateFile(str(config.templates_dir / 'index.pt'))
    (config.output_dir / 'index.html').write_text(
        index_tmpl(generations=group_by_generation(my_ancestors))
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
        html = person_tmpl(
            person=data,
            father=person_data(db, father_p) if father_p else None,
            mother=person_data(db, mother_p) if mother_p else None,
            children=[person_data(db, c) for c in children_p],
            siblings=get_siblings(db, p),
            spouses=spouses,
            events=get_all_events(db, p),
            is_ancestor=gid in my_ancestors and gid != config.me,
            is_me=gid == config.me,
            relation=relation,
            photos=photos,
            generations=group_by_generation(person_ancestors),
        )
        (people_dir / f'{gid}.html').write_text(html)
        search_rows.append({**data, 'num_children': len(children_p), 'num_spouses': len(spouses)})

    print(f'Built {len(all_people)} person pages')

    # Build search page
    search_rows.sort(key=lambda r: (r['surname'], r['given']))
    search_tmpl = PageTemplateFile(str(config.templates_dir / 'search.pt'))
    (config.output_dir / 'search.html').write_text(search_tmpl(rows=search_rows))
    print('Built search.html')

    db.close()


if __name__ == '__main__':
    build()
