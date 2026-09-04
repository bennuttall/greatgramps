=========
Templates
=========

greatgramps ships with a default set of Chameleon page templates. You can override any of them — or
all of them — without touching the others.

Point ``templates_dir`` in your config at a directory containing your custom templates:

.. code-block:: yaml

    templates_dir: templates

Any template file found in that directory takes precedence over the bundled one of the same name.
Templates you don't provide fall back to the bundled defaults, so you can override just one file if
that's all you need.

The bundled templates live in ``greatgramps/templates/`` in the source tree and can be used as a
reference.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Template
     - Description
   * - ``ancestor_records.pt``
     - Ancestor records research page. Table of the root person's ancestors grouped by generation,
       with icons showing which key records are available for each person.
   * - ``birthdays.pt``
     - Birthdays page. Calendar dates with birthdays of people in the tree, filterable by
       ancestors, descendants, and living people.
   * - ``cemeteries.pt``
     - Cemeteries list page. Sortable table of cemeteries with burial counts and enclosing place,
       plus search, ancestors filter, and a map.
   * - ``cemetery_place.pt``
     - Cemetery place page. Variant of ``place.pt`` used for places of type Cemetery, with a
       Burials heading and a Find A Grave column in the events table.
   * - ``census.pt``
     - Individual census event page. Lists the people in a census record, with an optional map.
   * - ``census_index.pt``
     - Census index page. Summary table of census years with record and people counts.
   * - ``census_records.pt``
     - Census records research page. Table of the root person's ancestors grouped by generation,
       with icons showing the state of census records for each person.
   * - ``census_year.pt``
     - Census year page. Lists census events for a specific year with a map and filters.
   * - ``descendants_tree.pt``
     - Person descendants tab. Interactive tree view of a person's descendants.
   * - ``event.pt``
     - Individual event page. Event details, people involved, optional map, and gallery images.
   * - ``events.pt``
     - Events list page. Searchable, filterable, and sortable table of events with a map.
   * - ``global_index.pt``
     - Site homepage. Lists all people the site is built for. Uses ``layout.pt`` like every
       other page, but with no nav header since there is no current root person.
   * - ``index.pt``
     - Root person homepage. Tree stats, PDF chart links, and a map filterable by ancestors,
       descendants, and birth events.
   * - ``layout.pt``
     - Base layout macro. Defines the shared HTML shell (nav, header, footer) used by all page
       templates via ``metal:use-macro``, including the site homepage. Override this one file to
       add something to every page, such as a banner or authentication bar. The nav header is
       only rendered on pages with a current root person.
   * - ``marriage.pt``
     - Marriage event page. Details of a marriage between two people, with an optional map.
   * - ``person.pt``
     - Person profile tab. Parents, siblings, relationships, children, filterable events list,
       places map, and ancestor/descendant summary.
   * - ``person_header.pt``
     - Person header macro. Reusable header with name, birth/death years, age, and relationship
       to the root person. Used by all person tab templates.
   * - ``pictures.pt``
     - Person pictures tab. Gallery of images associated with the person and their events.
   * - ``place.pt``
     - Place page. Events at a place with a map, filterable by event type.
   * - ``places.pt``
     - Places list page. Searchable table of places with a map.
   * - ``search.pt``
     - People list page. Searchable, filterable, and sortable table of people.
   * - ``surname.pt``
     - Individual surname page. People with a given surname, searchable and filterable.
   * - ``surnames.pt``
     - Surnames list page. Searchable and sortable table of surnames with people counts.
   * - ``tree.pt``
     - Person ancestors tab. Interactive tree view of a person's ancestors.

The same layered approach applies to static files (CSS etc.). Point ``static_dir`` at a directory
and its files will be copied into the output on top of the bundled ones:

.. code-block:: yaml

    static_dir: static

Custom CSS
==========

If a file named ``custom.css`` is found in your ``static_dir``, it's copied into the output and
linked from every page, right after the bundled ``style.css``. This lets you override or extend the
default styles without having to override ``style.css`` itself:

.. code-block:: yaml

    static_dir: static

.. code-block:: css

    /* static/custom.css */
    body { background: #fafafa; }

If ``custom.css`` isn't present, no extra stylesheet link is added.

404 page
========

A bundled ``404.html`` is copied into the output alongside the other static files. It can be
overridden the same way as any other static file, by placing your own ``404.html`` in
``static_dir``.

You can configure your web server to serve this page for any 404 errors. For example, with
nginx:

.. code-block:: nginx

    error_page 404 /404.html;

Or with Apache:

.. code-block:: apache

    ErrorDocument 404 /404.html