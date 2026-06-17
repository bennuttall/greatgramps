=================
grgr rebuild-page
=================

.. program:: grgr-rebuild-page

Copy static files and rebuild specific pages by ID or name.

Accepts person IDs (``I…``), event IDs (``E…``), place IDs (``P…``), and named pages:
``places``, ``people``, ``events``, ``census``, ``index``, ``global-index``.

.. code-block:: text

    Usage: grgr rebuild-page [OPTIONS] IDS...

Arguments
=========

.. option:: IDS

    IDs or page names to rebuild, e.g. ``I0061 E0315 P0012 places``.
