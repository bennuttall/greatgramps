=========
Changelog
=========

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
  GRAMPS databases automatically and supports searching for root people by name or ID

0.3.0 (2026-06-26)
==================

* Add a ``site_root`` config option for sites served from a subdirectory rather than the domain root
* Add a **More** tab to person pages showing notes and attributes recorded in GRAMPS; attributes are
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