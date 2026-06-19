========
grgr pdf
========

.. program:: grgr-pdf

Generate PDF pedigree, descendant, and hourglass charts.

.. code-block:: console

    $ grgr pdf --help

     Usage: grgr pdf [OPTIONS] COMMAND [ARGS]...

     Generate PDF pedigree, descendant, and hourglass charts.

    ╭─ Options ────────────────────────────────────────────────────────────────╮
    │ --help          Show this message and exit.                              │
    ╰──────────────────────────────────────────────────────────────────────────╯
    ╭─ Commands ───────────────────────────────────────────────────────────────╮
    │ ancestors    Generate a printable PDF ancestor pedigree chart.           │
    │ descendants  Generate a printable PDF descendant tree chart.             │
    │ hourglass    Generate a printable PDF hourglass chart (ancestors above,  │
    │              descendants below).                                        │
    ╰──────────────────────────────────────────────────────────────────────────╯

.. note::

    All ``grgr pdf`` commands require `Ghostscript <https://www.ghostscript.com/>`_ to be
    installed, which is used to compress the generated PDF, and the ``pdf`` extra
    (``pip install greatgramps[pdf]``).

.. toctree::
   :maxdepth: 1

   ancestors.rst
   descendants.rst
   hourglass.rst
