============
grgr orphans
============

.. program:: grgr-orphans

Find orphaned people, unattached events and unused places.

A person is orphaned when no family connects them to another person. This covers people with no
families at all, and people who are the only remaining member of a family (for example a spouse
left behind after the other spouse was deleted or merged).

An event is unattached when no person or family references it, which is usually what is left
behind after the people it belonged to were deleted. These show on the events list with an empty
person column.

A place is unused when it has no events, and neither does any place it encloses at any depth. A
county with no events of its own is still in use if a town inside it has events, so it is not
flagged. Where a whole branch of the place hierarchy has no events, every place in that branch
is listed.

The command also reports groups of people who are linked to each other but not to any of the
configured root people. These usually need reconnecting rather than removing, so they are only
listed unless ``--delete-groups`` is given, in which case each group is confirmed separately.

.. code-block:: text

    Usage: grgr orphans [OPTIONS]

    ╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
    │ --delete               Delete orphaned people (and any families left empty),           │
    │                        unattached events and unused places                             │
    │ --delete-groups        Offer to delete each disconnected group, confirming one group   │
    │                        at a time                                                       │
    │ --yes           -y     Skip confirmation prompts                                       │
    │ --help                 Show this message and exit.                                     │
    ╰────────────────────────────────────────────────────────────────────────────────────────╯

Options
=======

.. option:: --delete

    Delete the orphaned people, unattached events and unused places after listing them. Any
    family left with no members is removed too. Disconnected groups are not affected.

.. option:: --delete-groups

    Offer to delete each disconnected group in turn. Each group is shown and asked about
    separately, so you can remove one group and keep another. Can be combined with
    ``--delete``.

.. option:: -y, --yes

    Skip confirmation prompts. With ``--delete-groups`` this deletes every disconnected group
    without asking.
