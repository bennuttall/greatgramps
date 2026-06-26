==================
grgr pdf ancestors
==================

.. program:: grgr-pdf-ancestors

Generate a printable PDF ancestor pedigree chart.

.. code-block:: text

    Usage: grgr pdf ancestors [OPTIONS] PERSON_ID GENERATIONS [OUTPUT]

Arguments
=========

.. option:: PERSON_ID

    Person ID — the root of the pedigree chart.

.. option:: GENERATIONS

    Number of generations to show (minimum 2).

.. option:: OUTPUT

    Output PDF filename. Defaults to ``ancestor_tree_PERSONID_Ngen.pdf``.

Options
=======

.. option:: --color, --no-color

    Use colour boxes (default: color).

.. option:: --paper TEXT

    Paper size: one of ``A0``, ``A1``, ``A2``, ``A3``, ``A4``, ``A5``, ``letter``, ``legal``,
    ``ledger`` (default: ``A4``).

Demo
====

`https://gramps.bennuttall.com/I0000/ancestors.pdf <https://gramps.bennuttall.com/I0000/ancestors.pdf>`_
