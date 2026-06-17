===
CLI
===

.. program:: grgr

The ``grgr`` command-line interface provides commands for building the site and managing the GRAMPS
database directly — adding people, events, census records, places, families, and more.
Run ``grgr --help`` for a list of available commands and options.

.. code-block:: console

    $ grgr

     Usage: grgr [OPTIONS] COMMAND [ARGS]...

     Greatgramps — manage your Gramps family tree database.

    ╭─ Options ────────────────────────────────────────────────────────────────╮
    │ --install-completion          Install completion for the current shell.  │
    │ --show-completion             Show completion for the current shell, to  │
    │                               copy it or customize the installation.     │
    │ --help                        Show this message and exit.                │
    ╰──────────────────────────────────────────────────────────────────────────╯
    ╭─ Commands ───────────────────────────────────────────────────────────────╮
    │ add-ancestry-link   Add an Ancestry URL to a person.                     │
    │ add-census          Add a census event and link people to it.            │
    │ add-child           Link an existing person as a child to one or two     │
    │                     parents.                                             │
    │ add-event           Add an event and link it to one or more people.      │
    │ add-event-people    Link people to an existing event.                    │
    │ add-event-place     Set the place on an existing event.                  │
    │ add-family          Create a family for one or two parents, optionally   │
    │                     adding children.                                     │
    │ add-grave-link      Add a Find A Grave URL to a person.                  │
    │ add-parents         Link a child to one or two parents, filling a        │
    │                     missing parent slot in an existing family if         │
    │                     possible.                                            │
    │ add-person          Add a new person to the database.                    │
    │ add-place           Geocode a location and add it as a Place in the      │
    │                     database.                                            │
    │ build               Build the full site.                                 │
    │ census-check        Show census years this person should have a record   │
    │                     for, and whether they do.                            │
    │ enclose-place       Set one place as enclosed by another (GRAMPS         │
    │                     'Enclosed by' relationship).                         │
    │ list-ancestors      List ancestors of a person grouped by generation.    │
    │ list-children       List a person's children.                            │
    │ list-event-people   List people attached to an event.                    │
    │ list-parents        List a person's parents.                             │
    │ list-person-events  List all events for a person.                        │
    │ list-unconnected    List people with no family connections (not a        │
    │                     parent, spouse, or child in any family).             │
    │ rebuild-page        Copy static files and rebuild specific pages by ID   │
    │                     or name.                                             │
    │ rm-event            Delete one or more events, removing all references   │
    │                     from people and families.                            │
    │ rm-event-people     Remove one or more people from an event.             │
    │ rm-people           Delete one or more people from the database,         │
    │                     cleaning up family relationships.                    │
    │ search-place        Search for places in the database by name.           │
    │ update-person       Set or update event dates and places on a person.    │
    ╰──────────────────────────────────────────────────────────────────────────╯

.. toctree::
   :maxdepth: 1

   add-ancestry-link
   add-census
   add-child
   add-event
   add-event-people
   add-event-place
   add-family
   add-grave-link
   add-parents
   add-person
   add-place
   build
   census-check
   enclose-place
   list-ancestors
   list-children
   list-event-people
   list-parents
   list-person-events
   list-unconnected
   rebuild-page
   rm-event
   rm-event-people
   rm-people
   search-place
   update-person
