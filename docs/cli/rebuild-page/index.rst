=================
grgr rebuild-page
=================

.. program:: grgr-rebuild-page

Copy static files and rebuild specific pages by ID or name.

`Demo <https://gramps.bennuttall.com/I0000/>`_

Accepts person IDs (``I…``), event IDs (``E…``), place IDs (``P…``), and named pages:
``places``, ``people``, ``events``, ``census``, ``index``, ``birthdays``, ``surnames``,
``ancestor-records``, ``census-records``, ``global-index``.

For ``places``, ``people``, ``events``, ``census``, and ``surnames``, this rebuilds every
individual page of that type (not just the index page) — e.g. ``grgr rebuild-page places``
rebuilds every place page as well as the places index.

.. code-block:: text

    Usage: grgr rebuild-page [OPTIONS] IDS...

Arguments
=========

.. option:: IDS

    IDs or page names to rebuild, e.g. ``I0061 E0315 P0012 places``.
