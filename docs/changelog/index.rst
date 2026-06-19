=========
Changelog
=========

0.1.0 (2026-06-14)
==================

* First release of the project. This version includes the initial implementation of core features
  and functionalities.

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