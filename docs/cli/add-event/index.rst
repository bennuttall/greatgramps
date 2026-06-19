==============
grgr add-event
==============

.. program:: grgr-add-event

Add an event and link it to one or more people.

.. code-block:: text

    Usage: grgr add-event [OPTIONS] EVENT_TYPE PERSON_IDS...

Arguments
=========

.. option:: EVENT_TYPE

    Event type. One of: ``birth``, ``death``, ``burial``, ``baptism``,
    ``confirmation``, ``marriage``, ``divorce``, ``occupation``, ``residence``,
    ``census``, ``military``, ``education``, ``graduation``, ``retirement``,
    ``immigration``, ``emigration``, ``award``, ``probate``, ``conviction``,
    ``sentencing``.

.. option:: PERSON_IDS

    One or more person IDs to link to the event.

Options
=======

.. option:: --date TEXT

    Event date. Accepts year (``1950``), ``DD Mon YYYY`` (``1 Jan 1950``), or
    ``YYYY-MM-DD``.

.. option:: --place TEXT

    Place name or ID.

.. option:: --gallery PATH

    Media file to attach to the event.

.. option:: -y, --yes

    Skip confirmation prompt.
