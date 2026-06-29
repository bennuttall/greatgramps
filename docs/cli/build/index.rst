==========
grgr build
==========

.. program:: grgr-build

Build the full site.

`Demo <https://gramps.bennuttall.com/I0000/>`_

.. code-block:: text

    Usage: grgr build [OPTIONS]

If you only have the ``html`` extra installed (no ``cli``), run
``python -m greatgramps.build`` instead — it has no dependency on ``typer``/``rich``.

If the ``pdf`` extra is not installed, PDF generation is skipped and a warning is printed. Install
``greatgramps[pdf]`` to enable PDF chart generation.
