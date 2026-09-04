============
grgr orphans
============

.. program:: grgr-orphans

Find orphaned people: those linked to nobody else, including people alone in an empty family.

A person is orphaned when no family connects them to another person. This covers people with no
families at all, and people who are the only remaining member of a family (for example a spouse
left behind after the other spouse was deleted or merged).

The command also reports groups of people who are linked to each other but not to any of the
configured root people. These usually need reconnecting rather than removing, so they are only
listed unless ``--delete-groups`` is given, in which case each group is confirmed separately.

.. code-block:: text

    Usage: grgr orphans [OPTIONS]

    ╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
    │ --delete               Delete orphaned people and any families left empty              │
    │ --delete-groups        Offer to delete each disconnected group, confirming one group   │
    │                        at a time                                                       │
    │ --yes           -y     Skip confirmation prompts                                       │
    │ --help                 Show this message and exit.                                     │
    ╰────────────────────────────────────────────────────────────────────────────────────────╯

Options
=======

.. option:: --delete

    Delete the orphaned people after listing them. Any family left with no members is removed
    too. Disconnected groups are not affected.

.. option:: --delete-groups

    Offer to delete each disconnected group in turn. Each group is shown and asked about
    separately, so you can remove one group and keep another. Can be combined with
    ``--delete``.

.. option:: -y, --yes

    Skip confirmation prompts. With ``--delete-groups`` this deletes every disconnected group
    without asking.
