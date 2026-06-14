# greatgramps

A static site generator for [GRAMPS](https://www.gramps-project.org) family tree databases.

greatgramps reads a GRAMPS database and builds a browsable static website from it. Each person in
the tree gets their own page with biographical details, family relationships, events, photos, and a
relationship label showing how they connect to a chosen root person. The site also includes index
pages for people, places, events, census records, birthdays, and surnames.

The site is built from the point of view of one or more root people — typically the living members
of a family who each want to browse the tree as themselves. Each root person gets their own section
of the site where relationship labels ("your grandmother", "your 2nd cousin") are calculated
relative to them. A top-level index page lets you switch between roots.

The site is generated once and served as plain HTML — no server-side code required. It's not a web
frontend for GRAMPS (like [gramps-web](https://github.com/gramps-project/gramps-web)), in that it's
read-only, but it produces a fairly rich browsable site for your tree. Once built, the site can be
hosted with ease, with no Python or GRAMPS installation required.

![](https://raw.githubusercontent.com/bennuttall/greatgramps/refs/heads/main/img/walter_small.png)

## Requirements

- Python 3.10+
- A GRAMPS sqlite database
- GRAMPS

## Installation

Install GRAMPS first:

```bash
sudo apt install gramps
```

Then install the project and its dependencies:

```bash
pip install greatgramps
```

## Configuration

Create a `config.yml` pointing at your GRAMPS database and listing the GRAMPS IDs of the root
people you want to browse the tree as:

```yaml
db_path: /path/to/your/grampsdb/xxxxxxxx
roots:
  - I0001
  - I0002
```

Root people are typically the living members of a family — for example, two siblings who both want
their own view of the tree. Each root gets their own section of the site where relationship labels
are calculated relative to them. You can add as many roots as you like; a top-level index page lets
you switch between them.

GRAMPS IDs (like `I0001`) are shown in GRAMPS on each person's record. You can also find them with
`grgr list-ancestors` or by searching the database.

Set the path to your config file via an environment variable or `.env` file:

```
GREATGRAMPS_CONFIG=config.yml
```

### Config file reference

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `db_path` | yes | — | Path to your GRAMPS sqlite database directory |
| `roots` | yes | — | GRAMPS IDs of the people to build root views for |
| `output_dir` | no | `www` | Directory to write the built site into |
| `ancestry_tree_id` | no | — | Ancestry.com tree ID, used to generate profile links |
| `templates_dir` | no | — | Directory of custom templates (see [Custom templates](#custom-templates)) |
| `static_dir` | no | — | Directory of custom static files (CSS etc.) |

Relative paths are resolved relative to the config file's directory.

## Usage

```bash
grgr build
```

Rebuild a specific page (faster during development):

```bash
grgr rebuild-page people
grgr rebuild-page I0001
```

The output is written to `www/` by default.

To browse the built site locally:

```bash
python -m http.server -d www
```

Then open http://localhost:8000 in your browser.

## Custom templates

greatgramps ships with a default set of [Chameleon](https://chameleon.readthedocs.io/) page
templates. You can override any of them — or all of them — without touching the others.

Point `templates_dir` in your config at a directory containing your custom templates:

```yaml
templates_dir: templates
```

Any template file found in that directory takes precedence over the bundled one of the same name.
Templates you don't provide fall back to the bundled defaults, so you can override just one file if
that's all you need.

The bundled templates live in `greatgramps/templates/` in the source tree and can be used as a
reference.

### Custom static files

The same layered approach applies to static files (CSS etc.). Point `static_dir` at a directory and
its files will be copied into the output on top of the bundled ones:

```yaml
static_dir: static
```

## CLI

The `grgr` CLI has additional subcommands for managing the database directly — adding people,
events, census records, places, families, and more. Run `grgr --help` for the full list:

```
 Usage: grgr [OPTIONS] COMMAND [ARGS]...                                                    
                                                                                            
 Greatgramps — manage your Gramps family tree database.                                     
                                                                                            
╭─ Options ────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.                  │
│ --show-completion             Show completion for the current shell, to copy it or       │
│                               customize the installation.                                │
│ --help                        Show this message and exit.                                │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────╮
│ add-ancestry-link   Add an Ancestry URL to a person.                                     │
│ add-census          Add a census event and link people to it.                            │
│ add-child           Link an existing person as a child to one or two parents.            │
│ add-event           Add an event and link it to one or more people.                      │
│ add-event-people    Link people to an existing event.                                    │
│ add-event-place     Set the place on an existing event.                                  │
│ add-family          Create a family for one or two parents, optionally adding children.  │
│ add-grave-link      Add a Find A Grave URL to a person.                                  │
│ add-parents         Link a child to one or two parents, filling a missing parent slot in │
│                     an existing family if possible.                                      │
│ add-person          Add a new person to the database.                                    │
│ add-place           Geocode a location and add it as a Place in the database.            │
│ build               Build the full site.                                                 │
│ census-check        Show census years this person should have a record for, and whether  │
│                     they do.                                                             │
│ enclose-place       Set one place as enclosed by another (GRAMPS 'Enclosed by'           │
│                     relationship).                                                       │
│ list-ancestors      List ancestors of a person grouped by generation.                    │
│ list-children       List a person's children.                                            │
│ list-event-people   List people attached to an event.                                    │
│ list-parents        List a person's parents.                                             │
│ list-person-events  List all events for a person.                                        │
│ list-unconnected    List people with no family connections (not a parent, spouse, or     │
│                     child in any family).                                                │
│ rebuild-page        Copy static files and rebuild specific pages by ID or name.          │
│ rm-event            Delete one or more events, removing all references from people and   │
│                     families.                                                            │
│ rm-event-people     Remove one or more people from an event.                             │
│ rm-people           Delete one or more people from the database, cleaning up family      │
│                     relationships.                                                       │
│ search-place        Search for places in the database by name.                           │
│ update-person       Set or update event dates and places on a person.                    │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
```