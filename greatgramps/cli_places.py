import json
import sys
import urllib.parse
import urllib.request

from gramps.gen.db import DBMODE_R, DBMODE_W, DbTxn
from gramps.gen.lib import Place, PlaceName, PlaceType
from gramps.plugins.db.dbapi.sqlite import SQLite

from .settings import get_config


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "greatgramps/0.1 (family tree tool)"

NOMINATIM_TYPE_MAP = {
    'city': PlaceType.CITY,
    'town': PlaceType.TOWN,
    'village': PlaceType.VILLAGE,
    'hamlet': PlaceType.HAMLET,
    'county': PlaceType.COUNTY,
    'state': PlaceType.STATE,
    'country': PlaceType.COUNTRY,
    'parish': PlaceType.PARISH,
    'municipality': PlaceType.MUNICIPALITY,
    'borough': PlaceType.BOROUGH,
    'district': PlaceType.DISTRICT,
    'region': PlaceType.REGION,
    'province': PlaceType.PROVINCE,
    'locality': PlaceType.LOCALITY,
    'neighbourhood': PlaceType.NEIGHBORHOOD,
    'suburb': PlaceType.NEIGHBORHOOD,
    'farm': PlaceType.FARM,
}


def _geocode(query):
    params = urllib.parse.urlencode({'q': query, 'format': 'json', 'limit': 5})
    url = f"{NOMINATIM_URL}?{params}"
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:
        results = json.loads(resp.read().decode())
    return results


def _open_db(write=False):
    config = get_config()
    db_path = config.validated_db_path
    db = SQLite()
    db.load(str(db_path), mode=DBMODE_W if write else DBMODE_R)
    return db


def _print_place(place):
    print(f"  ID:   {place.get_gramps_id()}")
    print(f"  Name: {place.get_name().get_value()}")
    print(f"  Type: {place.get_type()}")
    lat = place.get_latitude()
    lon = place.get_longitude()
    print(f"  Lat:  {lat if lat else '(none)'}")
    print(f"  Lon:  {lon if lon else '(none)'}")


def add_place(args=None):
    if args is None:
        args = sys.argv[1:]
    if not args:
        print("Usage: add-place <location query>")
        print("Example: add-place \"sheffield england\"")
        sys.exit(1)

    query = ' '.join(args)
    print(f"Geocoding: {query!r}")

    results = _geocode(query)
    if not results:
        print(f"No results found for {query!r}")
        sys.exit(1)

    result = results[0]
    lat = result['lat']
    lon = result['lon']
    display_name = result['display_name']
    osm_type = result.get('type', '')
    addresstype = result.get('addresstype', osm_type)
    place_type_int = NOMINATIM_TYPE_MAP.get(addresstype, NOMINATIM_TYPE_MAP.get(osm_type, PlaceType.UNKNOWN))

    # Use the first part of display_name as the place name
    name = display_name.split(',')[0].strip()

    print(f"Found: {display_name}")
    print(f"  Lat: {lat}, Lon: {lon}, Type: {addresstype}")
    print()

    db = _open_db(write=True)
    try:
        place = Place()
        pn = PlaceName()
        pn.set_value(name)
        place.set_name(pn)
        place.set_latitude(str(lat))
        place.set_longitude(str(lon))
        place.set_type(PlaceType(place_type_int))

        with DbTxn('Add place', db) as trans:
            db.add_place(place, trans)

        print("Place added:")
        _print_place(place)
    finally:
        db.close()


def search_places(args=None):
    if args is None:
        args = sys.argv[1:]
    if not args:
        print("Usage: search-place <search term>")
        print("Example: search-place sheff")
        sys.exit(1)

    query = ' '.join(args).lower()
    db = _open_db(write=False)
    try:
        matches = []
        for handle in db.get_place_handles():
            place = db.get_place_from_handle(handle)
            if query in place.get_name().get_value().lower():
                matches.append(place)

        if not matches:
            print(f"No places found matching {query!r}")
            return

        print(f"{len(matches)} place(s) matching {query!r}:")
        for place in sorted(matches, key=lambda p: p.get_name().get_value().lower()):
            print()
            _print_place(place)
    finally:
        db.close()
