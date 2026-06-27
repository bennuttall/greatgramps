===========
grgr config
===========

.. program:: grgr-config

Interactively generate a ``config.yml`` and ``.env`` for this project.

The command walks through the required settings step by step:

1. Discovers GRAMPS databases in the default location and lets you pick one, or enter a custom path.
2. Lets you search for and choose root people (the starting points for the site).
3. Prompts for optional settings such as site title and Ancestry tree ID.
4. Writes ``config.yml`` and creates a ``.env`` file pointing to it.

.. code-block:: text

    Usage: grgr config [OPTIONS]

Options
=======

.. option:: --output, -o PATH

    Path to write the config file. Defaults to ``config.yml`` in the current directory.
