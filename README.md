# greatgramps

A static site generator for [GRAMPS](https://www.gramps-project.org) family tree databases.

## What it is

greatgramps reads a GRAMPS database and builds a browsable static website from it. Each person in
the tree gets their own page with biographical details, family relationships, events, photos, and a
relationship label showing how they connect to a chosen root person. The site also includes index
pages for people, places, events, census records, birthdays, and surnames.

The site is generated once and served as plain HTML — no server-side code required.

## Requirements

- Python 3.10+
- A GRAMPS database (tested with the SQLite backend)
- [Poetry](https://python-poetry.org) for dependency management
- GRAMPS (install via your system package manager, not pip)

## Installation

Install GRAMPS first:

```bash
sudo apt install gramps
```

Then install the Python dependencies:

```bash
poetry install
```

## Configuration

Create a `config.yml` pointing at your GRAMPS database and listing the root person IDs (one per
person you want to view the tree as):

```yaml
db_path: /path/to/your/grampsdb/xxxxxxxx
roots:
  - I0001
```

Set the path to your config file via an environment variable or `.env` file:

```
GREATGRAMPS_CONFIG=config.yml
```

## Usage

Build the full site (output goes to `www/`):

```bash
grgr build
```

Rebuild a specific page (faster during development):

```bash
grgr rebuild-page people
grgr rebuild-page I0001
```

The output is written to `www/` by default.

## CLI

The `grgr` CLI has additional subcommands for managing the database directly — adding people,
events, census records, places, families, and more. Run `grgr --help` for the full list.
