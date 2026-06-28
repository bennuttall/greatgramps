===========
grgr config
===========

.. program:: grgr-config

Interactively generate a ``config.yml`` and ``.env`` for this project.

The command walks through the required settings step by step:

1. Discovers Gramps databases in the default location and lets you pick one, or enter a custom path.
2. Lets you search for and choose root people (the starting points for the site).
3. Prompts for site title, Ancestry tree ID, output directory, and site root.
4. Writes ``config.yml`` and creates a ``.env`` file pointing to it.

.. code-block:: text

    Usage: grgr config [OPTIONS]

    ╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
    │ --output  -o      PATH  Path to write the config file [default: config.yml]            │
    │ --yes     -y            Overwrite existing config without prompting                    │
    │ --help                  Show this message and exit.                                    │
    ╰────────────────────────────────────────────────────────────────────────────────────────╯

Options
=======

.. option:: --output, -o PATH

    Path to write the config file. Defaults to ``config.yml`` in the current directory.

.. option:: --yes, -y

    Overwrite an existing config file without prompting for confirmation.
