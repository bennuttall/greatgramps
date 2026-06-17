==============
grgr rm-people
==============

.. program:: grgr-rm-people

Delete one or more people from the database, cleaning up family relationships.

.. code-block:: text

    Usage: grgr rm-people [OPTIONS] PERSON_IDS...

Arguments
=========

.. option:: PERSON_IDS

    One or more person IDs to delete.

Options
=======

.. option:: -d, --descendants

    Also delete all descendants of the specified people.

.. option:: -y, --yes

    Skip confirmation prompt.
