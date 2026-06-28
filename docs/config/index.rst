=============
Configuration
=============

greatgramps is configured using a YAML file.

Run :doc:`grgr config <../cli/config/index>` to generate ``config.yml`` and ``.env``
interactively, or create them manually as described below.

Create a ``config.yml`` pointing at your Gramps database and listing the Gramps IDs of the root
people you want to browse the tree as:

.. code-block:: yaml

    db_path: /path/to/your/grampsdb/xxxxxxxx
    roots:
    - I0001
    - I0002

The location of the config file must be set with an environment variable:

.. code-block::

    GREATGRAMPS_CONFIG=config.yml

Config file reference
=====================

Relative paths are resolved relative to the config file's directory.

.. list-table::
   :header-rows: 1
   :widths: 20 10 15

   * - Key
     - Required
     - Default
   * - ``db_path``
     - yes
     - —
   * - ``roots``
     - yes
     - —
   * - ``output_dir``
     - no
     - ``www``
   * - ``ancestry_tree_id``
     - no
     - —
   * - ``templates_dir``
     - no
     - —
   * - ``static_dir``
     - no
     - —
   * - ``nav_pages``
     - no
     - ``[people, places, events, census, cemeteries, birthdays, surnames]``
   * - ``site_title``
     - no
     - ``Family tree``
   * - ``site_root``
     - no
     - ``/``

``db_path``
-----------

Path to your Gramps sqlite database directory.

``roots``
---------

Gramps IDs of the people to build root views for.

``output_dir``
--------------

Directory to write the built site into. Defaults to ``www``.

``ancestry_tree_id``
--------------------

Ancestry.com tree ID, used to generate profile links for people in the tree.

``templates_dir``
-----------------

Directory of custom Chameleon templates. Any template found here takes precedence over the bundled
one of the same name. See :doc:`../templates/index`.

``static_dir``
--------------

Directory of custom static files (CSS etc.). Files here are copied into the output on top of the
bundled ones. See :doc:`../templates/index`.

``nav_pages``
-------------

Which pages to show in the nav bar alongside **Me**, and in what order. All pages are included by
default; remove any that your database doesn't make use of. For example, omit ``cemeteries`` if
you have no places of type Cemetery, or ``census`` if you have no census events:

.. code-block:: yaml

    nav_pages:
    - people
    - places
    - events
    - birthdays
    - surnames

``site_title``
--------------

Title used in the HTML ``<title>`` and the ``<h1>`` on the top-level index page. Defaults to
``Family tree``:

.. code-block:: yaml

    site_title: The Nuttall Family

``site_root``
-------------

URL root of the site. Set this when the site is served from a subdirectory rather than the domain
root. Defaults to ``/``. A leading and trailing ``/`` are added automatically if omitted.

This controls URL generation only — set ``output_dir`` independently to write files into the
matching subdirectory. For example, to serve the site at ``/family/``:

.. code-block:: yaml

    output_dir: www/family/
    site_root: /family/
