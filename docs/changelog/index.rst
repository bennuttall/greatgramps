=========
Changelog
=========

0.3.8 (2026-07-06)
==================

* Fix cemetery map popups linking to the cemetery listing page instead of the place page
* Fix switching root person from a page other than the homepage returning to that root's homepage
  instead of the equivalent page
* Show the visitor's relation to the root person (e.g. "your daughter") on event, census, and
  marriage pages, including the marriage Children table
* Remove the redundant "Me" row from the homepage's Ancestors table
* Use count-sized circle markers on the events and census year maps, matching the rest of the
  site's maps
* Document how to add the Cemetery place type and hide unused pages from the nav bar
* Add ``home``, ``my-tree`` and ``me`` to ``nav_pages``, so the Home, My tree and Me links can be
  reordered or removed like any other nav item; all nav links now share the same style
* Fix "Viewing as…" wrapping onto its own line without staying right-aligned

0.3.7 (2026-07-05)
==================

* Fit the Places and Cemeteries page maps to their markers instead of a hard-coded UK view
* Hide the empty profile overview box on person pages with no family details, external links or
  occupations

0.3.6 (2026-07-04)
==================

* Fix relative media paths being resolved against the database directory instead of Gramps'
  configured base media path
* Thread config/db explicitly through the site-build core instead of relying on the cached global
  config

0.3.5 (2026-06-30)
==================

* Fix site build failing with ``ValueError`` when using the fallback template loader
* Add Event column to cemetery place pages, linking to the burial event

0.3.4 (2026-06-29)
==================

* Fix site build failing with ``ImportError`` when the ``pdf`` extra is not installed; PDF
  generation is now skipped with a warning instead

0.3.3 (2026-06-28)
==================

* Fix PDF compression failing with cross-device rename error when ``/tmp`` is on a separate
  filesystem
* Replace ``GRAMPS`` with ``Gramps`` throughout docs and templates

0.3.2 (2026-06-27)
==================

* Fix nav dropdown rendering beneath Leaflet maps by containing map z-indices with ``isolation:
  isolate``
* Fix cemeteries page Ancestors filter not updating the map
* Fix homepage map showing markers with empty popups when ancestor and birth filters are combined
* Update person profile map to respond to life event type filters; fix map jumping when events are
  filtered
* Add Events column to the People page

0.3.1 (2026-06-27)
==================

* Add ``grgr config`` command to interactively generate ``config.yml`` and ``.env``; discovers
  Gramps databases automatically and supports searching for root people by name or ID

0.3.0 (2026-06-26)
==================

* Add a ``site_root`` config option for sites served from a subdirectory rather than the domain root
* Add a **More** tab to person pages showing notes and attributes recorded in Gramps; attributes are
  grouped by type
* Show alternative names and notes on place pages

0.2.2 (2026-06-26)
==================

* Add a root-switching dropdown to the nav bar; switching from within a page takes you to the same
  page in the other root's view
* Add a cemeteries page listing burial counts per cemetery with a map, search, sortable columns,
  and an ancestors filter
* Add a map to the root person's homepage, filterable by ancestors, descendants, and birth events
* Add tag filter buttons and tag icons to the People page
* Add PDF chart links to the root person's homepage (hidden when no ancestors or descendants exist)
* Add ``--latlong`` and ``--type`` options to ``grgr add-place``
* Fix homepage ``<title>`` to match the ``<h1>``

0.2.1 (2026-06-19)
==================

* Add a ``site_title`` config option to customise the site name shown in every page's ``<title>``
  and the home page's ``<h1>``
* Hide the ancestor/descendant badge on person profiles when it's already obvious from context
* Replace gender colour-coding on names with a small symbol, so it no longer reads as a
  visited/unvisited link

0.2.0 (2026-06-19)
==================

* Add a descendants summary and personalized title to the home page
* Add a configurable nav bar (``nav_pages``) to control links and order
* Support surname married-name matching, with sortable/filterable surname pages
* Add place search and has-photo/grave/interesting/conflict status icons
* Add ancestor/descendant/living filter buttons and descendant badges throughout
* Add a 404 page and support for optional custom CSS
* Add ``grgr pdf`` command group (``ancestors``, ``descendants``, ``hourglass``) for generating PDF
  charts
* Split installation into ``cli``, ``pdf``, and ``html`` extras so each install only pulls in what
  it needs
* Add a Sphinx documentation site

0.1.0 (2026-06-14)
==================

* First release of the project. This version includes the initial implementation of core features
  and functionalities.