#!/home/ben/.virtualenvs/gramps/bin/python
from chameleon import PageTemplateFile
from greatgramps.gramps_data import (
    open_db, collect_all_people, collect_ancestors,
    get_parents, get_children, get_siblings, get_spouses, get_all_events,
    ancestors_with_distances, get_relation_to_me,
    person_data,
)
from greatgramps.settings import get_config


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

    # Build index — my ancestors grouped by generation
    index_tmpl = PageTemplateFile(str(config.templates_dir / 'index.pt'))
    (config.output_dir / 'index.html').write_text(
        index_tmpl(generations=group_by_generation(my_ancestors))
    )
    print('Built index.html')

    # Build a page for every person
    person_tmpl = PageTemplateFile(str(config.templates_dir / 'person.pt'))
    for gid, data in all_people.items():
        p = db.get_person_from_gramps_id(gid)
        father_p, mother_p = get_parents(db, p)
        children_p = get_children(db, p)
        person_ancestors = collect_ancestors(db, p)
        relation = get_relation_to_me(db, me_ancestor_distances, p, data['gender'])
        html = person_tmpl(
            person=data,
            father=person_data(db, father_p) if father_p else None,
            mother=person_data(db, mother_p) if mother_p else None,
            children=[person_data(db, c) for c in children_p],
            siblings=get_siblings(db, p),
            spouses=get_spouses(db, p),
            events=get_all_events(db, p),
            is_ancestor=gid in my_ancestors and gid != config.me,
            is_me=gid == config.me,
            relation=relation,
            generations=group_by_generation(person_ancestors),
        )
        (people_dir / f'{gid}.html').write_text(html)

    print(f'Built {len(all_people)} person pages')
    db.close()


if __name__ == '__main__':
    build()
