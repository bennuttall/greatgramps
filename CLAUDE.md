# greatgramps

Library for managing a GRAMPS family tree database and building a static website out of the data

## Python

Use virtualenv at `/home/ben/.virtualenvs/gramps/bin/python`

## git

Don't auto-commit

## Rewriting pages

When working on a page, rebuild the page after making changes so I can evaluate the changes quickly.
If one page of many is rewritten, provide a link. Use the command `grgr rebuild-page` within the venv.

## grgr commands

The library includes a CLI for managing parts of the project and making. This is a Typer CLI called
`grgr` with various subcommands. Additional commands should retain the conventions and style used
across `grgr`.

## scripts

One-off scripts or thing which are for my situation rather than something for the project should
live in `scripts/`

## Release

When doing a new release, update the version number in `pyproject.toml` and `docs/conf.py`. Add a
new section to `docs/changelog/index.rst` and add a concise set of bullet points describing the
changes since the last release.