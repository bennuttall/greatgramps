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

    Location to geocode and add, e.g. ``'Manchester, England'``. Used as the place
    name verbatim when :option:`--latlong` is given.

Options
=======

.. option:: --enclose TEXT

    Enclose the new place within this place ID or name.

.. option:: --latlong TEXT

    Skip geocoding and use these coordinates instead, as ``lat,lon``, e.g.
    ``'53.4808,-2.2426'``.

.. option:: --type TEXT

    Override the place type. Accepts a built-in GRAMPS place type (e.g.
    ``Town``, ``City``, case-insensitive) or any other value, which is saved
    as a custom type, e.g. ``Cemetery``.

.. option:: -y, --yes

    Skip confirmation prompt.
