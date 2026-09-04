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
     - ``[home, my-tree, me, people, places, events, census, cemeteries, birthdays, surnames]``
   * - ``exclude_pages``
     - no
     - ``[]``
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

Which links to show in the nav bar, and in what order. ``home`` links to the global index (see
:doc:`../features/index`), ``my-tree`` links to the current root's homepage, and ``me`` links to
the root person's own page. All pages are included by default; remove any you don't want from the
nav. To leave a page out of the build altogether, use ``exclude_pages`` instead, which also removes
it from the nav. For example, to show a shorter nav:

.. code-block:: yaml

    nav_pages:
    - home
    - my-tree
    - me
    - people
    - places
    - events
    - birthdays
    - surnames

``exclude_pages``
-----------------

Pages to leave out of the build entirely. Excluded pages are also dropped from the nav bar, so
there is no need to remove them from ``nav_pages`` as well. For example, if your database has no
census events and you don't want the research pages:

.. code-block:: yaml

    exclude_pages:
    - census
    - ancestor-records
    - census-records

The pages that can be excluded, and what each skips:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Page
     - What is skipped
   * - ``people``
     - The people list page. Individual person pages are always built.
   * - ``places``
     - The places list page. Individual place pages are always built, since events link to them.
   * - ``events``
     - The events list page. Individual event pages are always built, since people link to them.
   * - ``census``
     - The census index and the per-year census pages.
   * - ``cemeteries``
     - The cemeteries page.
   * - ``birthdays``
     - The birthdays page.
   * - ``surnames``
     - The surnames index and the per-surname pages. Surnames are shown without links.
   * - ``ancestor-records``
     - The ancestor records research page.
   * - ``census-records``
     - The census records research page.

``grgr rebuild-page`` also skips any excluded page it is asked for.

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
