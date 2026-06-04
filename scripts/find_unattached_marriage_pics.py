#!/home/ben/.virtualenvs/gramps/bin/python
"""Find images in Gallery/Marriages not attached to any marriage event."""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / '.env')
_cfg = os.environ.get('GREATGRAMPS_CONFIG', 'config.yml')
if not Path(_cfg).is_absolute():
    os.environ['GREATGRAMPS_CONFIG'] = str(REPO_ROOT / _cfg)

from gramps.gen.lib.eventtype import EventType
from greatgramps.gramps_data import open_db

GALLERY_DIR = '/home/ben/.gramps/grampsdb/678295e2/Gallery/Marriages'

db = open_db()

attached_paths = set()
for event in db.iter_events():
    if int(event.get_type()) != EventType.MARRIAGE:
        continue
    for ref in event.get_media_list():
        media = db.get_media_from_handle(ref.get_reference_handle())
        attached_paths.add(os.path.basename(media.get_path()))

db.close()

all_files = set(os.listdir(GALLERY_DIR))
unattached = sorted(all_files - attached_paths)

if unattached:
    print(f'{len(unattached)} unattached file(s):')
    for f in unattached:
        print(f'  {f}')
else:
    print('All files are attached to marriage events.')
