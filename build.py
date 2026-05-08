#!/home/ben/.virtualenvs/gramps/bin/python
from pathlib import Path
from chameleon import PageTemplateFile
from gramps_data import (
    open_db, collect_all_people, collect_ancestors,
    get_parents, get_children, person_data, ME,
)

TEMPLATES = Path(__file__).parent / 'templates'
OUTPUT = Path(__file__).parent / 'output'


def group_by_generation(ancestors):
    by_gen = {}
    for gid, data in ancestors.items():
        by_gen.setdefault(data['generation'], []).append(data)
    return [{'gen': g, 'people': by_gen[g]} for g in sorted(by_gen)]


def build():
    db = open_db()
    me = db.get_person_from_gramps_id(ME)

    all_people = collect_all_people(db)
    my_ancestors = collect_ancestors(db, me)

    people_dir = OUTPUT / 'people'
    people_dir.mkdir(parents=True, exist_ok=True)

    # Build index — my ancestors grouped by generation
    index_tmpl = PageTemplateFile(str(TEMPLATES / 'index.pt'))
    (OUTPUT / 'index.html').write_text(
        index_tmpl(generations=group_by_generation(my_ancestors))
    )
    print('Built index.html')

    # Build a page for every person
    person_tmpl = PageTemplateFile(str(TEMPLATES / 'person.pt'))
    for gid, data in all_people.items():
        p = db.get_person_from_gramps_id(gid)
        father_p, mother_p = get_parents(db, p)
        children_p = get_children(db, p)
        person_ancestors = collect_ancestors(db, p)
        html = person_tmpl(
            person=data,
            father=person_data(db, father_p) if father_p else None,
            mother=person_data(db, mother_p) if mother_p else None,
            children=[person_data(db, c) for c in children_p],
            is_ancestor=gid in my_ancestors and gid != ME,
            is_me=gid == ME,
            generations=group_by_generation(person_ancestors),
        )
        (people_dir / f'{gid}.html').write_text(html)

    print(f'Built {len(all_people)} person pages')
    db.close()


if __name__ == '__main__':
    build()
