===============
grgr add-person
===============

.. program:: grgr-add-person

Add a new person to the database.

.. code-block:: text

    Usage: grgr add-person [OPTIONS] NAME

Arguments
=========

.. option:: NAME

    Full name, e.g. ``'John Smith'``.

Options
=======

.. option:: --birth TEXT

    Birth date, e.g. ``'1 Jan 1950'`` or ``1950``.

.. option:: --death TEXT

    Death date.

.. option:: --burial TEXT

    Burial date.

.. option:: --birth-place TEXT

    Birth place ID or name.

.. option:: --death-place TEXT

    Death place ID or name.

.. option:: --burial-place TEXT

    Burial place ID or name.

.. option:: --gender TEXT

    Gender: ``m``/``male``, ``f``/``female``, or ``u``/``unknown``. Inferred
    from the given name if not specified.

.. option:: --father TEXT

    Father's person ID.

.. option:: --mother TEXT

    Mother's person ID.

.. option:: -y, --yes

    Skip confirmation prompt.
