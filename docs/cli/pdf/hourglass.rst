==================
grgr pdf hourglass
==================

.. program:: grgr-pdf-hourglass

Generate a printable PDF hourglass chart: ancestors above, descendants below the given person.

.. code-block:: text

    Usage: grgr pdf hourglass [OPTIONS] PERSON_ID ANCESTOR_GENERATIONS
                               DESCENDANT_GENERATIONS [OUTPUT]

Arguments
=========

.. option:: PERSON_ID

    Person ID — the root of the hourglass chart.

.. option:: ANCESTOR_GENERATIONS

    Number of ancestor generations to show, above the root (minimum 2).

.. option:: DESCENDANT_GENERATIONS

    Number of descendant generations to show, below the root (minimum 2).

.. option:: OUTPUT

    Output PDF filename. Defaults to ``hourglass_PERSONID_AxDgen.pdf``.

Options
=======

.. option:: --color, --no-color

    Use colour boxes (default: color).

.. option:: --paper TEXT

    Paper size: one of ``A0``, ``A1``, ``A2``, ``A3``, ``A4``, ``A5``, ``letter``, ``legal``,
    ``ledger`` (default: ``A4``). The chart is rendered in portrait orientation.
