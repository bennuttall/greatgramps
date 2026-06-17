===============
grgr add-census
===============

.. program:: grgr-add-census

Add a census event and link people to it.

.. code-block:: text

    Usage: grgr add-census [OPTIONS] PERSON_IDS...

Arguments
=========

.. option:: PERSON_IDS

    One or more person IDs to link to the census event.

Options
=======

.. option:: --gallery PATH

    Path to the census image file. The filename must begin with a year
    (e.g. ``1921_smith_jones.jpg``).

.. option:: --year INTEGER

    Census year (e.g. ``1911``). Uses the known full census date for that year.
    Required if ``--gallery`` is not provided.

.. option:: --name TEXT

    Head of household name, used to generate the event description
    (e.g. ``'John Smith'``). Required if ``--gallery`` is not provided.

.. option:: --place TEXT

    Place name or ID to attach to the event.

.. option:: -y, --yes

    Skip confirmation prompt.
