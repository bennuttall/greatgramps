===========
grgr config
===========

.. program:: grgr-config

Interactively generate a config file (``config.yml`` by default) and ``.env`` for this project.

The command walks through the required settings step by step:

1. Prompts for the config file name, defaulting to ``config.yml``.
2. Discovers Gramps databases in the default location and lets you pick one, or enter a custom path.
3. Lets you search for and choose root people (the starting points for the site).
4. Prompts for site title, Ancestry tree ID, output directory, and site root.
5. Writes the config file and creates a ``.env`` file pointing to it.

.. code-block:: text

    Usage: grgr config [OPTIONS]

    ╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
    │ --output  -o      PATH  Path to write the config file (skips the prompt)               │
    │ --yes     -y            Overwrite existing config without prompting                    │
    │ --help                  Show this message and exit.                                    │
    ╰────────────────────────────────────────────────────────────────────────────────────────╯

Options
=======

.. option:: --output, -o PATH

    Path to write the config file. When given, the interactive prompt for the file name is
    skipped. Otherwise the command asks for a name, defaulting to ``config.yml`` in the current
    directory.

.. option:: --yes, -y

    Overwrite an existing config file without prompting for confirmation.
