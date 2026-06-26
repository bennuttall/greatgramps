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
read-only, but it produces a rich browsable site for your tree. Once built, the site can be hosted
with ease, with no Python or GRAMPS installation required.

This approach lets you manage your own tree using open source software without relying on
subscription or proprietary services, while still making it easy to share your tree with your family
on the web.

![](https://raw.githubusercontent.com/bennuttall/greatgramps/refs/heads/main/img/walter_small.png)

## Demo

A demo is available at [gramps.bennuttall.com](https://gramps.bennuttall.com/I0000/people/I0000/)
which features a generated family tree showcasing what greatgramps can build from a GRAMPS database.

## Requirements

- Python 3.10+
- A GRAMPS sqlite database
- GRAMPS

## Installation

Install GRAMPS first. See the [GRAMPS installation instructions](https://gramps-project.org/wiki/index.php/Download).

Also install PyICU for locale-aware sorting, via your platform's package manager (otherwise GRAMPS
logs a warning and falls back to less accurate sorting of names and places). On Debian/Ubuntu:

```bash
sudo apt install python3-icu
```

Then install the project. The core package only handles reading the GRAMPS database; pick the
extras for the features you need:

```bash
pip install greatgramps[cli,html,pdf]
```

- `cli` — the `grgr` command-line tool
- `html` — the `grgr build` / `grgr rebuild-page` commands for generating the static site
- `pdf` — the `grgr pdf` commands (also requires [Ghostscript](https://www.ghostscript.com/))

If you only have the `html` extra installed (no `cli`), build the site with
`python -m greatgramps.build` instead of `grgr build` — it has no dependency on `typer` or `rich`.

## Links

- [PyPI](https://pypi.org/project/greatgramps/)
- [GitHub](https://github.com/bennuttall/greatgramps)
- [Demo](https://gramps.bennuttall.com/I0000/people/I0000/)
- [Documentation](https://greatgramps.readthedocs.io/)

## Licence

- [BSD-3-Clause](https://github.com/bennuttall/greatgramps/blob/main/LICENSE.txt)