==============
grgr add-place
==============

.. program:: grgr-add-place

Geocode a location and add it as a Place in the database.

Uses the Nominatim geocoding service to look up the location.

.. code-block:: text

    Usage: grgr add-place [OPTIONS] QUERY

Arguments
=========

.. option:: QUERY

    Location to geocode and add, e.g. ``'Manchester, England'``.

Options
=======

.. option:: --enclose TEXT

    Enclose the new place within this place ID or name.

.. option:: -y, --yes

    Skip confirmation prompt.
