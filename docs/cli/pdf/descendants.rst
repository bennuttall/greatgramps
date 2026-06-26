====================
grgr pdf descendants
====================

.. program:: grgr-pdf-descendants

Generate a printable PDF descendant tree chart.

.. code-block:: text

    Usage: grgr pdf descendants [OPTIONS] PERSON_ID GENERATIONS [OUTPUT]

Arguments
=========

.. option:: PERSON_ID

    Person ID — the root of the descendant chart.

.. option:: GENERATIONS

    Number of generations to show (minimum 2).

.. option:: OUTPUT

    Output PDF filename. Defaults to ``descendant_tree_PERSONID_Ngen.pdf``.

Options
=======

.. option:: --color, --no-color

    Use colour boxes (default: color).

.. option:: --paper TEXT

    Paper size: one of ``A0``, ``A1``, ``A2``, ``A3``, ``A4``, ``A5``, ``letter``, ``legal``,
    ``ledger`` (default: ``A4``).

Demo
====

`https://gramps.bennuttall.com/I0000/descendants.pdf <https://gramps.bennuttall.com/I0000/descendants.pdf>`_
