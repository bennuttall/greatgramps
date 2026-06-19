======================
grgr add-ancestry-link
======================

.. program:: grgr-add-ancestry-link

Add an Ancestry URL to a person.

.. code-block:: text

    Usage: grgr add-ancestry-link [OPTIONS] PERSON_ID URL

Arguments
=========

.. option:: PERSON_ID

    Person ID.

.. option:: URL

    Ancestry person ID or full URL. If a numeric ID is given, the full URL is
    constructed using ``ancestry_tree_id`` from the config.

Options
=======

.. option:: -y, --yes

    Skip confirmation prompt.
