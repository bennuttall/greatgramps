#!/usr/bin/env python3
"""
Populate a GRAMPS database with demo people for greatgramps.

Tree shape:
  - Root person: Alex Hartwell, born 1955
  - 8 generations of ancestors (fully filled for gen 1-3, sparser beyond)
  - Siblings added for some ancestors in generations 1-4
  - 2 children and 5 grandchildren of the root
"""

import calendar
import os
import random
from pathlib import Path

from gramps.gen.db import DBMODE_W, DbTxn
from gramps.gen.lib import (
    Attribute, AttributeType, ChildRef, Date, Event, EventRef, EventRoleType,
    EventType, Family, FamilyRelType, Media, MediaRef, Name, NameType, Person,
    Place, PlaceName, PlaceRef, PlaceType, Surname, Tag, Url, UrlType,
)
from gramps.plugins.db.dbapi.sqlite import SQLite

DB_PATH = "/home/ben/.gramps/grampsdb/6a2f3421"
ANCESTRY_TREE_ID = "1234567890"
CURRENT_YEAR = 2026

random.seed(42)

MALE_NAMES = [
    "Alfred", "Bernard", "Cecil", "Douglas", "Edgar", "Francis", "Geoffrey",
    "Herbert", "Ignatius", "Jerome", "Kenneth", "Leonard", "Maurice", "Norman",
    "Oswald", "Percy", "Quentin", "Reginald", "Stanley", "Theodore", "Ulric",
    "Victor", "Wallace", "Xavier", "Barnabas", "Clement",
]

FEMALE_NAMES = [
    "Agatha", "Beatrice", "Cecily", "Dorothea", "Edwina", "Felicity", "Griselda",
    "Harriet", "Imelda", "Josephine", "Lavinia", "Millicent", "Norah", "Octavia",
    "Prudence", "Rosalind", "Tabitha", "Ursula", "Venetia", "Winifred",
    "Araminta", "Clementine", "Eugenia", "Isolde", "Lettice",
]

SURNAMES = [
    "Ashford", "Blackwell", "Caldwell", "Dunmore", "Eastham", "Fernley",
    "Grimshaw", "Halcomb", "Ingleton", "Jarrow", "Kestrel", "Langford",
    "Merriweather", "Norbrook", "Oulton", "Pembridge", "Quinton", "Ravenswood",
    "Stanwick", "Thornbury", "Ulverston", "Vanthorpe", "Westgate", "Yarmouth",
    "Zelby", "Crowther", "Havelock", "Idsworth", "Drewett", "Foxwell",
]

# Per-generation probability of creating a parent pair (index = generation depth 0..7)
ANCESTOR_PROB  = [1.0, 1.0, 1.0, 0.85, 0.70, 0.50, 0.30, 0.20]

# Per-generation probability of adding 1-2 siblings to an ancestor
SIBLING_PROB   = [0.0, 0.75, 0.60, 0.45, 0.30, 0.0, 0.0, 0.0]

# Per-generation probability that only one parent is known (rather than both)
SINGLE_PARENT_PROB = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.30, 0.30]

# Exact dates of England & Wales censuses (day, month, year)
CENSUS_DATES = {
    1841: ( 6, 6, 1841),
    1851: (30, 3, 1851),
    1861: ( 7, 4, 1861),
    1871: ( 2, 4, 1871),
    1881: ( 3, 4, 1881),
    1891: ( 5, 4, 1891),
    1901: (31, 3, 1901),
    1911: ( 2, 4, 1911),
    1921: (19, 6, 1921),
    1939: (29, 9, 1939),
}
CENSUS_PROB = 0.60  # probability a qualifying family appears in a given census year

# Drawn from a real tree; years stripped (greatgramps strips them anyway).
MALE_OCCUPATIONS = [
    "Agricultural labourer", "Blacksmith", "Boiler fireman", "Boot & shoe maker",
    "Cabinet maker", "Carpenter", "Carter", "Clerk", "Coal miner", "Collier",
    "Cordwainer", "Cotton mixer", "Cotton weaver", "Cutler", "Delivery driver",
    "Dental mechanic", "Dentist", "Drayman",
    "Edge tool forger", "Farm bailiff", "Farmer", "Furnace man", "Gamekeeper",
    "Gardener", "Joiner", "Labourer", "Miller", "Miner", "Optician", "Porter",
    "Reporter", "Saddler", "Silver burnisher",
    "Steel furnaceman", "Steel worker", "Table knife cutler",
    "University lecturer", "Weaver",
]

FEMALE_OCCUPATIONS = [
    "Cotton weaver", "Dressmaker", "Housekeeper", "School mistress", "Seamstress",
    "Silver burnisher", "Weaver",
]

# (key, name, type, lat, lon, parent_key)
# Hierarchy drawn from a real England tree; parent_key=None means top-level.
ENGLAND_PLACES = [
    ("england",         "England",            "Country", "",         "",         None),
    ("yorkshire",       "Yorkshire",          "County",  "53.9591",  "-1.0792",  "england"),
    ("sheffield",       "Sheffield",          "City",    "53.3811",  "-1.4701",  "yorkshire"),
    ("leeds",           "Leeds",              "City",    "53.7974",  "-1.5438",  "yorkshire"),
    ("bradford",        "Bradford",           "City",    "53.7944",  "-1.7519",  "yorkshire"),
    ("hull",            "Kingston upon Hull", "City",    "53.7675",  "-0.3273",  "yorkshire"),
    ("doncaster",       "Doncaster",          "City",    "53.5229",  "-1.1312",  "yorkshire"),
    ("wakefield",       "Wakefield",          "City",    "53.6830",  "-1.4967",  "yorkshire"),
    ("goole",           "Goole",              "Town",    "53.7045",  "-0.8746",  "yorkshire"),
    ("whitby",          "Whitby",             "Town",    "54.4863",  "-0.6133",  "yorkshire"),
    ("snaith",          "Snaith",             "Town",    "53.6911",  "-1.0239",  "yorkshire"),
    ("lancashire",      "Lancashire",         "County",  "",         "",         "england"),
    ("manchester",      "Manchester",         "City",    "53.4808",  "-2.2426",  "lancashire"),
    ("liverpool",       "Liverpool",          "City",    "53.3933",  "-2.9166",  "lancashire"),
    ("preston",         "Preston",            "City",    "53.7632",  "-2.7031",  "lancashire"),
    ("lancaster",       "Lancaster",          "City",    "54.0488",  "-2.8013",  "lancashire"),
    ("blackburn",       "Blackburn",          "Town",    "53.7486",  "-2.4875",  "lancashire"),
    ("bolton",          "Bolton",             "Town",    "53.5769",  "-2.4282",  "lancashire"),
    ("bury",            "Bury",               "Town",    "53.5933",  "-2.2966",  "lancashire"),
    ("clitheroe",       "Clitheroe",          "Town",    "53.8711",  "-2.3931",  "lancashire"),
    ("london",          "London",             "City",    "51.5072",  "-0.1276",  "england"),
    ("islington",       "Islington",          "Borough", "51.5386",  "-0.1028",  "london"),
    ("southwark",       "Southwark",          "Borough", "51.5028",  "-0.0877",  "london"),
    ("westminster",     "Westminster",        "City",    "51.5072",  "-0.1277",  "london"),
    ("nottinghamshire", "Nottinghamshire",    "County",  "53.1285",  "-0.9031",  "england"),
    ("nottingham",      "Nottingham",         "City",    "52.9540",  "-1.1550",  "nottinghamshire"),
    ("retford",         "Retford",            "Town",    "53.3214",  "-0.9455",  "nottinghamshire"),
    ("lincolnshire",    "Lincolnshire",       "County",  "53.1823",  "-0.2031",  "england"),
    ("lincoln",         "Lincoln",            "City",    "53.2307",  "-0.5406",  "lincolnshire"),
    ("derbyshire",      "Derbyshire",         "County",  "53.1667",  "-1.5833",  "england"),
    ("buxton",          "Buxton",             "Town",    "53.2591",  "-1.9148",  "derbyshire"),
    ("chesterfield",    "Chesterfield",       "Town",    "53.2350",  "-1.4216",  "derbyshire"),
]

# Only cities/towns are used for individual events (not countries or counties)
EVENT_PLACE_KEYS = {key for key, _, ptype, *_ in ENGLAND_PLACES if ptype in ("City", "Town", "Borough")}


# ── GRAMPS helpers ────────────────────────────────────────────────────────────

def _make_date(year, month=0, day=0):
    d = Date()
    d.set_yr_mon_day(year, month, day)
    return d


def _random_date(year):
    """Return (year, month, day) with randomised precision."""
    r = random.random()
    if r < 0.25:
        return year, 0, 0
    elif r < 0.55:
        return year, random.randint(1, 12), 0
    else:
        month = random.randint(1, 12)
        return year, month, random.randint(1, calendar.monthrange(year, month)[1])


def _add_event(db, trans, etype, year, month=0, day=0, place_handle=None):
    event = Event()
    event.set_type(etype)
    event.set_date_object(_make_date(year, month, day))
    if place_handle:
        event.set_place_handle(place_handle)
    db.add_event(event, trans)
    return event.get_handle()


def _add_url(person, url_type_str, path):
    u = Url()
    u.set_type(UrlType(url_type_str))
    u.set_path(path)
    person.add_url(u)


def _make_person(db, trans, given, surname, gender, birth_year, death_year=None,
                 birth_place=None, death_place=None):
    person = Person()

    name = Name()
    name.set_type(NameType(NameType.BIRTH))
    name.set_first_name(given)
    surn = Surname()
    surn.set_surname(surname)
    name.set_surname_list([surn])
    person.set_primary_name(name)
    person.set_gender(gender)

    def _add(etype, year, month=0, day=0, place_handle=None):
        eref = EventRef()
        eref.set_reference_handle(_add_event(db, trans, etype, year, month, day, place_handle))
        eref.set_role(EventRoleType(EventRoleType.PRIMARY))
        person.add_event_ref(eref)

    birth_y, birth_m, birth_d = _random_date(birth_year)
    _add(EventType.BIRTH, birth_y, birth_m, birth_d, birth_place)

    if random.random() < 0.60:
        src_m = birth_m or random.randint(1, 12)
        bap_total = src_m + random.randint(1, 6)
        bap_y = birth_year + (bap_total - 1) // 12
        bap_m = ((bap_total - 1) % 12) + 1
        bap_d = random.randint(1, calendar.monthrange(bap_y, bap_m)[1]) if random.random() < 0.75 else 0
        _add(EventType.BAPTISM, bap_y, bap_m, bap_d, birth_place)

    has_burial = False
    if death_year:
        death_y, death_m, death_d = _random_date(death_year)
        _add(EventType.DEATH, death_y, death_m, death_d, death_place)

        src_m = death_m or random.randint(1, 12)

        if random.random() < 0.55:
            bur_total = src_m + random.randint(0, 1)
            bur_y = death_year + (bur_total - 1) // 12
            bur_m = ((bur_total - 1) % 12) + 1
            bur_d = random.randint(1, calendar.monthrange(bur_y, bur_m)[1]) if random.random() < 0.75 else 0
            _add(EventType.BURIAL, bur_y, bur_m, bur_d, death_place)
            has_burial = True

        if random.random() < 0.30:
            prob_total = src_m + random.randint(1, 6)
            prob_y = death_year + (prob_total - 1) // 12
            prob_m = ((prob_total - 1) % 12) + 1
            prob_d = random.randint(1, calendar.monthrange(prob_y, prob_m)[1]) if random.random() < 0.50 else 0
            _add(EventType.PROBATE, prob_y, prob_m, prob_d)

    if random.random() < 0.75:
        person_id = random.randint(10_000_000_000, 99_999_999_999)
        _add_url(person, 'Ancestry',
                 f'https://www.ancestry.co.uk/family-tree/person/tree/{ANCESTRY_TREE_ID}/person/{person_id}/')

    if has_burial and random.random() < 0.25:
        memorial_id = random.randint(10_000_000, 999_999_999)
        _add_url(person, 'Find a Grave', f'https://www.findagrave.com/memorial/{memorial_id}')

    occ_prob = 0.80 if gender == Person.MALE else 0.30
    occ_list = MALE_OCCUPATIONS if gender == Person.MALE else FEMALE_OCCUPATIONS
    if random.random() < occ_prob:
        attr = Attribute()
        attr.set_type(AttributeType(AttributeType.OCCUPATION))
        attr.set_value(random.choice(occ_list))
        person.add_attribute(attr)

    db.add_person(person, trans)
    return person


def _make_family(db, trans, father, mother, children, marriage_year=None, marriage_place=None):
    family = Family()
    family.set_relationship(FamilyRelType(FamilyRelType.MARRIED))
    if father:
        family.set_father_handle(father.get_handle())
    if mother:
        family.set_mother_handle(mother.get_handle())
    for child in children:
        cr = ChildRef()
        cr.set_reference_handle(child.get_handle())
        family.add_child_ref(cr)
    if marriage_year:
        mar_y, mar_m, mar_d = _random_date(marriage_year)
        eref = EventRef()
        eref.set_reference_handle(_add_event(db, trans, EventType.MARRIAGE, mar_y, mar_m, mar_d, marriage_place))
        eref.set_role(EventRoleType(EventRoleType.FAMILY))
        family.add_event_ref(eref)
    db.add_family(family, trans)

    fh = family.get_handle()
    for parent in [father, mother]:
        if parent:
            parent.add_family_handle(fh)
            db.commit_person(parent, trans)
    for child in children:
        child.add_parent_family_handle(fh)
        db.commit_person(child, trans)


# ── Place helpers ─────────────────────────────────────────────────────────────

def _make_place(db, trans, name, type_str, lat, lon, parent_handle=None):
    place = Place()
    pname = PlaceName()
    pname.set_value(name)
    place.set_name(pname)
    place.set_type(PlaceType(type_str))
    if lat:
        place.set_latitude(lat)
    if lon:
        place.set_longitude(lon)
    if parent_handle:
        pref = PlaceRef()
        pref.set_reference_handle(parent_handle)
        place.add_placeref(pref)
    db.add_place(place, trans)
    return place.get_handle()


def build_places(db, trans):
    """Create the England place hierarchy; return a dict of key -> handle."""
    handles = {}
    for key, name, type_str, lat, lon, parent_key in ENGLAND_PLACES:
        parent_handle = handles[parent_key] if parent_key else None
        handles[key] = _make_place(db, trans, name, type_str, lat, lon, parent_handle)
    event_handles = [handles[k] for k in EVENT_PLACE_KEYS]
    print(f"Built {len(handles)} places ({len(event_handles)} usable for events)")
    return event_handles


def _pick_place(event_place_handles, prob=0.70):
    if not event_place_handles or random.random() > prob:
        return None
    return random.choice(event_place_handles)


def _marriage_year(earliest_child_birth, prob=0.85):
    if random.random() > prob:
        return None
    return earliest_child_birth - random.randint(0, 3)


# ── Date helpers ──────────────────────────────────────────────────────────────

def _death_year(birth_year, latest_child_birth=None):
    """Return a plausible death year, or None if the person is probably still alive."""
    age = CURRENT_YEAR - birth_year
    if age < 30:
        return None
    if age < 60:
        if random.random() < 0.82:
            return None
        death_age = random.randint(30, age - 1)
    elif age < 80:
        if random.random() < 0.40:
            return None
        death_age = random.randint(55, min(age - 1, 88))
    else:
        death_age = random.randint(60, min(age - 1, 96))

    death_year = birth_year + death_age
    if latest_child_birth and death_year <= latest_child_birth:
        death_year = latest_child_birth + random.randint(1, 20)
    return death_year


# ── Database init ─────────────────────────────────────────────────────────────

def init_db(path):
    """Delete SQLite files so db.load() creates a fresh schema."""
    deleted = False
    for name in ('sqlite.db', 'sqlite.db-wal', 'sqlite.db-shm'):
        f = os.path.join(path, name)
        if os.path.exists(f):
            os.remove(f)
            deleted = True
    if deleted:
        print("Deleted existing database; will create fresh schema.")
    else:
        print("No existing database found; will create fresh schema.")


# ── Ancestor tree ─────────────────────────────────────────────────────────────

def build_ancestors(db, trans, root, root_birth, root_surname, place_handles=None):
    """Build up to 8 generations of ancestors using ahnentafel numbering.

    Ahnentafel: 1=root, 2=father, 3=mother, 2n=father of n, 2n+1=mother of n.
    Even numbers are always male (fathers), odd (except 1) always female (mothers).
    Surname passes through the paternal line; mothers have independent birth surnames.

    Returns (total_created, families) where families is a list of family records
    for use by build_census_events.
    """
    # tree entries: (person, birth_year, surname, death_year)
    tree = {1: (root, root_birth, root_surname, None)}
    total = 0
    families = []

    for gen in range(8):
        prob = ANCESTOR_PROB[gen]
        sibling_prob = SIBLING_PROB[gen]
        single_parent_prob = SINGLE_PARENT_PROB[gen]

        for ahn in range(2 ** gen, 2 ** (gen + 1)):
            if ahn not in tree:
                continue
            child, child_birth, child_surname, child_death = tree[ahn]

            if random.random() > prob:
                continue

            gap = random.randint(22, 33)
            father_birth = child_birth - gap + random.randint(-3, 3)
            mother_birth = father_birth + random.randint(-5, 5)

            father_surname = child_surname
            mother_surname = random.choice(SURNAMES)

            father_known = True
            mother_known = True
            if random.random() < single_parent_prob:
                if random.random() < 0.5:
                    father_known = False
                else:
                    mother_known = False

            siblings = []
            if random.random() < sibling_prob:
                for _ in range(random.randint(1, 2)):
                    sib_gender = random.choice([Person.MALE, Person.FEMALE])
                    sib_birth = child_birth + random.randint(-10, 10)
                    sib_birth = max(sib_birth, max(father_birth, mother_birth) + 18)
                    sib_death = _death_year(sib_birth)
                    sib = _make_person(
                        db, trans,
                        random.choice(MALE_NAMES if sib_gender == Person.MALE else FEMALE_NAMES),
                        child_surname, sib_gender, sib_birth, sib_death,
                        birth_place=_pick_place(place_handles),
                        death_place=_pick_place(place_handles),
                    )
                    siblings.append((sib, sib_birth, sib_death))
                    total += 1

            latest_child_birth = max([child_birth] + [b for _, b, _ in siblings])

            father = None
            father_death = None
            mother = None
            mother_death = None

            if father_known:
                father_death = _death_year(father_birth, latest_child_birth)
                father = _make_person(
                    db, trans,
                    random.choice(MALE_NAMES), father_surname, Person.MALE,
                    father_birth, father_death,
                    birth_place=_pick_place(place_handles),
                    death_place=_pick_place(place_handles),
                )
                tree[ahn * 2] = (father, father_birth, father_surname, father_death)
                total += 1

            if mother_known:
                mother_death = _death_year(mother_birth, latest_child_birth)
                mother = _make_person(
                    db, trans,
                    random.choice(FEMALE_NAMES), mother_surname, Person.FEMALE,
                    mother_birth, mother_death,
                    birth_place=_pick_place(place_handles),
                    death_place=_pick_place(place_handles),
                )
                tree[ahn * 2 + 1] = (mother, mother_birth, mother_surname, mother_death)
                total += 1

            _make_family(db, trans, father, mother, [child] + [s for s, _, _ in siblings],
                         marriage_year=_marriage_year(child_birth),
                         marriage_place=_pick_place(place_handles, prob=0.55))

            head = father if father else mother
            head_birth = father_birth if father else mother_birth
            head_death = father_death if father else mother_death
            spouse = mother if father else None
            spouse_birth = mother_birth if father else None
            spouse_death = mother_death if father else None
            all_children = [(child, child_birth, child_death)] + list(siblings)
            families.append({
                'head': head, 'head_birth': head_birth, 'head_death': head_death,
                'spouse': spouse, 'spouse_birth': spouse_birth, 'spouse_death': spouse_death,
                'children': all_children,
            })

            sib_desc = f" + {len(siblings)} sibling(s)" if siblings else ""
            father_desc = (f"{father.get_primary_name().get_first_name()} {father_surname} ({father_birth})"
                           if father_known else "unknown father")
            mother_desc = (f"{mother.get_primary_name().get_first_name()} {mother_surname} ({mother_birth})"
                           if mother_known else "unknown mother")
            print(f"  gen {gen+1:d}: {father_desc} + {mother_desc}{sib_desc}")

    return total, families


# ── Census events ─────────────────────────────────────────────────────────────

def build_census_events(db, trans, families, place_handles):
    total = 0
    for year, (day, month, _) in sorted(CENSUS_DATES.items()):
        # Collect handles of people who are heads of their own household this year
        # so they can be excluded from their parents' households.
        heads_this_year = set()
        for fam in families:
            hb, hd = fam['head_birth'], fam['head_death']
            if hb <= year - 18 and (not hd or hd > year):
                heads_this_year.add(fam['head'].get_handle())

        for fam in families:
            head, hb, hd = fam['head'], fam['head_birth'], fam['head_death']
            if hb > year - 18:
                continue
            if hd and hd <= year:
                continue
            if random.random() > CENSUS_PROB:
                continue

            members = [head]

            spouse, sb, sd = fam['spouse'], fam['spouse_birth'], fam['spouse_death']
            if spouse and sb <= year and (not sd or sd > year):
                members.append(spouse)

            for child, cb, cd in fam['children']:
                if cb > year:
                    continue  # not yet born
                if year - cb >= 20:
                    continue  # left home
                if cd and cd <= year:
                    continue  # deceased
                if child.get_handle() in heads_this_year:
                    continue  # head of own household
                members.append(child)

            head_name = head.get_primary_name()
            prefix = "1939 register" if year == 1939 else f"{year} census"
            description = f"{prefix} - {head_name.get_first_name()} {head_name.get_surname()} household"

            event = Event()
            event.set_type(EventType.CENSUS)
            event.set_description(description)
            event.set_date_object(_make_date(year, month, day))  # exact census date
            place_h = _pick_place(place_handles, prob=0.80)
            if place_h:
                event.set_place_handle(place_h)
            db.add_event(event, trans)

            for person in members:
                eref = EventRef()
                eref.set_reference_handle(event.get_handle())
                eref.set_role(EventRoleType(EventRoleType.PRIMARY))
                person.add_event_ref(eref)
                db.commit_person(person, trans)

            total += 1

    print(f"Built {total} census events")
    return total


# ── Photos ────────────────────────────────────────────────────────────────────

def _generate_photo(path, seed, gender):
    from PIL import Image, ImageDraw, ImageFilter

    rng = random.Random(seed)

    # Sepia tone varying per person
    r = rng.randint(185, 215)
    g = int(r * rng.uniform(0.80, 0.87))
    b = int(r * rng.uniform(0.52, 0.62))
    dark = (max(0, r - 55), max(0, g - 44), max(0, b - 28))
    mid  = (max(0, r - 20), max(0, g - 16), max(0, b - 10))

    img = Image.new('RGB', (160, 180), (r, g, b))
    draw = ImageDraw.Draw(img)

    # Head oval
    draw.ellipse([48, 16, 112, 86], fill=dark)
    # Shoulders/bust — slightly wider for male
    if gender == Person.MALE:
        draw.ellipse([5, 78, 155, 205], fill=dark)
    else:
        draw.ellipse([18, 82, 142, 205], fill=dark)

    # Thin border
    draw.rectangle([0, 0, 159, 179], outline=mid, width=3)

    img = img.filter(ImageFilter.GaussianBlur(radius=1.0))
    img.save(str(path), 'JPEG', quality=85)


def build_profile_photos(db, trans, media_dir, prob=0.80):
    media_dir = Path(media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)

    for old in media_dir.glob('portrait_*.jpg'):
        old.unlink()

    template = db.get_person_from_gramps_id('I0002')
    img_path = media_dir / 'portrait_I0002.jpg'
    _generate_photo(img_path, seed='I0002', gender=template.get_gender() if template else Person.UNKNOWN)

    total = 0
    for person in db.iter_people():
        birth_year = None
        for eref in person.get_event_ref_list():
            e = db.get_event_from_handle(eref.get_reference_handle())
            if int(e.get_type()) == EventType.BIRTH:
                birth_year = e.get_date_object().get_year() or None
                break

        if not birth_year or birth_year <= 1900:
            continue
        if random.random() > prob:
            continue

        media = Media()
        media.set_path(str(img_path))
        media.set_mime_type('image/jpeg')
        media.set_description('Portrait')
        db.add_media(media, trans)

        ref = MediaRef()
        ref.set_reference_handle(media.get_handle())
        person.add_media_reference(ref)
        db.commit_person(person, trans)

        total += 1

    print(f"Added profile photos for {total} people")


# ── Tags ──────────────────────────────────────────────────────────────────────

def _generate_event_photo(path):
    from PIL import Image, ImageDraw, ImageFilter

    bg   = (245, 239, 220)  # aged paper
    ink  = (110, 90,  60)   # faded ink
    rule = (195, 184, 158)  # faint ruled lines
    border = (170, 155, 125)

    img = Image.new('RGB', (320, 220), bg)
    draw = ImageDraw.Draw(img)

    # Left margin line
    draw.line([(48, 12), (48, 208)], fill=(210, 130, 120), width=1)

    # Title block: two short thick bars near the top
    draw.rectangle([58, 18, 230, 26], fill=ink)
    draw.rectangle([58, 32, 180, 38], fill=ink)

    # Body text lines (alternating full and short to suggest paragraphs)
    line_x = 58
    line_tops = [58, 72, 86, 100, 120, 134, 148, 162, 176]
    line_widths = [240, 200, 220, 160, 240, 210, 190, 230, 140]
    for y, w in zip(line_tops, line_widths):
        draw.rectangle([line_x, y, line_x + w, y + 5], fill=rule)

    # Outer border
    draw.rectangle([4, 4, 315, 215], outline=border, width=2)

    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
    img.save(str(path), 'JPEG', quality=85)


def build_event_photos(db, trans, media_dir, prob=0.50):
    media_dir = Path(media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)

    img_path = media_dir / 'event_placeholder.jpg'
    _generate_event_photo(img_path)

    total = 0
    for event in db.iter_events():
        if int(event.get_type()) == EventType.CENSUS:
            continue
        if random.random() > prob:
            continue

        media = Media()
        media.set_path(str(img_path))
        media.set_mime_type('image/jpeg')
        media.set_description('Event photo')
        db.add_media(media, trans)

        ref = MediaRef()
        ref.set_reference_handle(media.get_handle())
        event.add_media_reference(ref)
        db.commit_event(event, trans)

        total += 1

    print(f"Added event photos for {total} events")


def tag_interesting_events(db, trans, prob=0.10):
    tag = Tag()
    tag.set_name('Interesting')
    tag.set_color('#22AA22')
    db.add_tag(tag, trans)
    tag_handle = tag.get_handle()

    tagged = 0
    for event in db.iter_events():
        if int(event.get_type()) == EventType.CENSUS:
            continue
        if random.random() < prob:
            event.add_tag(tag_handle)
            db.commit_event(event, trans)
            tagged += 1

    print(f"Tagged {tagged} events as Interesting")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    init_db(DB_PATH)
    db = SQLite()
    db.load(DB_PATH, mode=DBMODE_W)

    with DbTxn("Populate demo database", db) as trans:
        print("Building places...")
        place_handles = build_places(db, trans)

        root_surname = "Hartwell"
        root_birth = 1955
        root = _make_person(db, trans, "Alex", root_surname, Person.MALE, root_birth,
                            birth_place=_pick_place(place_handles))
        print(f"Root: Alex Hartwell ({root_birth})")

        print("\nBuilding ancestor tree...")
        ancestor_count, families = build_ancestors(db, trans, root, root_birth, root_surname, place_handles)
        print(f"  → {ancestor_count} ancestors created")

        spouse_birth = root_birth + random.randint(-3, 5)
        spouse_death = _death_year(spouse_birth)
        spouse = _make_person(db, trans, "Diana", "Vanthorpe", Person.FEMALE,
                              spouse_birth, spouse_death,
                              birth_place=_pick_place(place_handles))

        child1_birth = root_birth + 28
        child1 = _make_person(db, trans, "Oliver", root_surname, Person.MALE, child1_birth,
                              birth_place=_pick_place(place_handles))

        child2_birth = root_birth + 31
        child2 = _make_person(db, trans, "Sophie", root_surname, Person.FEMALE, child2_birth,
                              birth_place=_pick_place(place_handles))

        _make_family(db, trans, root, spouse, [child1, child2],
                     marriage_year=_marriage_year(child1_birth),
                     marriage_place=_pick_place(place_handles, prob=0.55))
        families.append({
            'head': root, 'head_birth': root_birth, 'head_death': None,
            'spouse': spouse, 'spouse_birth': spouse_birth, 'spouse_death': spouse_death,
            'children': [(child1, child1_birth, None), (child2, child2_birth, None)],
        })

        oliver_spouse_birth = child1_birth + random.randint(-2, 3)
        oliver_spouse_death = _death_year(oliver_spouse_birth)
        oliver_spouse = _make_person(db, trans, "Clara", "Dunmore", Person.FEMALE,
                                     oliver_spouse_birth, oliver_spouse_death,
                                     birth_place=_pick_place(place_handles))

        gc1_birth = child1_birth + 29
        gc2_birth = gc1_birth + 2
        gc3_birth = gc2_birth + 3
        gc1 = _make_person(db, trans, "Leo",   root_surname, Person.MALE,   gc1_birth,
                           birth_place=_pick_place(place_handles))
        gc2 = _make_person(db, trans, "Iris",  root_surname, Person.FEMALE, gc2_birth,
                           birth_place=_pick_place(place_handles))
        gc3 = _make_person(db, trans, "Hugh",  root_surname, Person.MALE,   gc3_birth,
                           birth_place=_pick_place(place_handles))

        _make_family(db, trans, child1, oliver_spouse, [gc1, gc2, gc3],
                     marriage_year=_marriage_year(gc1_birth),
                     marriage_place=_pick_place(place_handles, prob=0.55))
        families.append({
            'head': child1, 'head_birth': child1_birth, 'head_death': None,
            'spouse': oliver_spouse, 'spouse_birth': oliver_spouse_birth, 'spouse_death': oliver_spouse_death,
            'children': [(gc1, gc1_birth, None), (gc2, gc2_birth, None), (gc3, gc3_birth, None)],
        })

        sophie_spouse_birth = child2_birth + random.randint(-2, 3)
        sophie_spouse_death = _death_year(sophie_spouse_birth)
        sophie_spouse = _make_person(db, trans, "Edmund", "Ashford", Person.MALE,
                                     sophie_spouse_birth, sophie_spouse_death,
                                     birth_place=_pick_place(place_handles))

        gc4_birth = child2_birth + 28
        gc5_birth = gc4_birth + 3
        gc4 = _make_person(db, trans, "Fern",  "Ashford", Person.FEMALE, gc4_birth,
                           birth_place=_pick_place(place_handles))
        gc5 = _make_person(db, trans, "Miles", "Ashford", Person.MALE,   gc5_birth,
                           birth_place=_pick_place(place_handles))

        _make_family(db, trans, sophie_spouse, child2, [gc4, gc5],
                     marriage_year=_marriage_year(gc4_birth),
                     marriage_place=_pick_place(place_handles, prob=0.55))
        families.append({
            'head': sophie_spouse, 'head_birth': sophie_spouse_birth, 'head_death': sophie_spouse_death,
            'spouse': child2, 'spouse_birth': child2_birth, 'spouse_death': None,
            'children': [(gc4, gc4_birth, None), (gc5, gc5_birth, None)],
        })

        print(f"\nDescendants:")
        print(f"  Alex + Diana → Oliver ({child1_birth}), Sophie ({child2_birth})")
        print(f"  Oliver + Clara → Leo ({gc1_birth}), Iris ({gc2_birth}), Hugh ({gc3_birth})")
        print(f"  Sophie + Edmund → Fern ({gc4_birth}), Miles ({gc5_birth})")

        print("\nBuilding census events...")
        build_census_events(db, trans, families, place_handles)

        media_dir = Path(__file__).parent.parent / 'media'
        print("Generating profile photos...")
        build_profile_photos(db, trans, media_dir)

        print("Generating event photos...")
        build_event_photos(db, trans, media_dir)

        print("Tagging interesting events...")
        tag_interesting_events(db, trans)

    db.close()
    print("\nDone. Root person ID: I0000")

    print("\nBuilding site...")
    config_path = Path(__file__).parent.parent / "config.yml"
    os.environ["GREATGRAMPS_CONFIG"] = str(config_path)
    from greatgramps.build import build
    build()


if __name__ == "__main__":
    main()
