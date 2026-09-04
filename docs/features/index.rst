========
Features
========

View as
=======

The homepage includes a list of people the site is built for. Click a person's name to view the tree
from their point of view.

When viewing a tree, a dropdown in the nav bar shows the current root person and allows switching to
another root person's view. Switching from within a page (e.g. a person's ancestor tree) takes you
to the same page in the other root's view.

`Demo <https://gramps.bennuttall.com/>`_

My tree
=======

View the tree from the point of view of the selected root person. When browsing the tree, any
relationships are described relative to the selected root person. The homepage for a person includes
some stats about the tree and a summary of their ancestors and descendants.

PDF charts are generated for the root person's ancestors, descendants, and an hourglass view
combining both. Links to these charts are shown on the homepage.

The homepage also includes a map of all places associated with ancestors and descendants, filterable
by ancestors, descendants, and birth events.

* `Demo <https://gramps.bennuttall.com/I0000/>`_
* `Ancestor tree PDF <https://gramps.bennuttall.com/I0000/ancestors.pdf>`_
* `Descendant tree PDF <https://gramps.bennuttall.com/I0000/descendants.pdf>`_
* `Hourglass tree PDF <https://gramps.bennuttall.com/I0000/hourglass.pdf>`_

Explore
=======

An interactive view of the whole tree on one page. It starts centred on the root person with
their parents, grandparents and children shown. Every person has buttons to open or close their
parents and their children, so you can follow any branch as far as you like without leaving the
page. Click a name for their page, or the centre button to redraw the tree around them. A search
box jumps to any person, and the current view is kept in the URL so it can be bookmarked or
shared. The ancestors and descendants tabs on each person link into the explorer centred on them.

`Demo <https://gramps.bennuttall.com/I0000/explore/>`_

People
======

Search for people in the tree by name. Names can be filtered and sorted.

`Demo <https://gramps.bennuttall.com/I0000/people/>`_

Person
======

A person's page shows their names and birth/death years, their age, their relationship to the
selected root person, and includes a set of tabs. For relatives who are neither an ancestor nor a
descendant of the root person (cousins, aunts and uncles, and so on), the closest common ancestor
is shown with a link to their page. The profile also includes a "How you're related" section for
anyone related by blood or marriage, listing each person in the chain between the root person and
them, with how each links to the last.

`Demo <https://gramps.bennuttall.com/I0000/people/I0000/>`_

Profile
-------

View a person's details, including their parents, siblings, relationships and children. This page
includes a filterable list of life events, a map of associated places, and a list of ancestors and
descendants.

The biographical information section also includes any external links associated with the person,
starting with their **Ancestry.com** and **findagrave.com** links if available. Other links can
be added in Gramps.

`Demo <https://gramps.bennuttall.com/I0000/people/I0000/>`_

Ancestors
---------

An interactive tree view of a person's ancestors. Navigate between people in the tree view by
clicking on each person.

`Demo <https://gramps.bennuttall.com/I0000/people/I0000/ancestors/>`_

Descendants
-----------

An interactive tree view of a person's descendants. Navigate between people in the tree view by
clicking on each person.

`Demo <https://gramps.bennuttall.com/I0000/people/I0000/descendants/>`_

Pictures
--------

A collection of images associated with the person and their events. Click an image to view it full
size.

`Demo <https://gramps.bennuttall.com/I0000/people/I0000/pictures/>`_

More
----

Shown when a person has notes or attributes recorded in Gramps. Notes are displayed as-is, and
attributes are grouped by type with a heading for each.

Places
======

View a list of places associated with events in the tree, and a map of those places. Click on a
place name to view the events associated with that place, search the people involved, and filter by
event type. Note places can be enclosed by other places, for example a town can be enclosed by a
county, which is enclosed by a country.

Alternative names recorded in Gramps are shown below the place name as "Also known as: …". Notes
are shown below that.

Events on a place's page show the same icons as the events list — a photo icon for events with
images, a link to Find a Grave for burial events, and tag icons for events marked interesting or
conflicting.

`Demo <https://gramps.bennuttall.com/I0000/places/>`_

.. note::

   Places require latitude and longitude coordinates to be displayed on the map. If a place does not
   have coordinates, it will not be displayed on the map. You can add coordinates to a place in
   Gramps, or using the :doc:`../cli/add-place/index` command.

Events
======

View a list of events in the tree, and a map of event locations. Click on an event to view the
details associated with that event. Events can be filtered and sorted. Events with associated
gallery images are shown on the event page, and an icon indicates an event has associated images.

`Demo <https://gramps.bennuttall.com/I0000/events/>`_

Census
======

View a list of census events in the tree, and a summary of the records. Click a census year to list
the events for that year and see a map of event locations. Click on an event to view the people in
that census. Records can be filtered. Census events with associated gallery images are shown on the
event page, and an icon indicates an event has associated images.

`Demo <https://gramps.bennuttall.com/I0000/census/>`_

.. note::

   If you don't use this feature, you can remove ``census`` from ``nav_pages`` to drop it from
   the navigation entirely — see :doc:`../config/index`.

Cemeteries
==========

View a list of cemeteries in the tree showing the number of burials at each, the enclosing place,
and a map. Cemetery markers on the map are sized by burial count. Click a cemetery name to view its
place page. The list can be searched by name and sorted by column.

An **Ancestors** filter button is shown when any ancestor burials exist, allowing the list to be
filtered to cemeteries where ancestors are buried, with burial counts updated to reflect ancestors
only.

`Demo <https://gramps.bennuttall.com/I0000/cemeteries/>`_

.. note::

   This page is populated from places with the type set to ``Cemetery`` in Gramps. Coordinates are
   required for a cemetery to appear on the map.

   ``Cemetery`` is a custom place type, not one of the built-in Gramps types, and Gramps has no way
   to add a custom type directly. The easiest way to add it is to create one place with this type
   using the :doc:`../cli/add-place/index` command, e.g. ``grgr add-place "Example Cemetery" --type
   Cemetery``. Once the type exists in the database, you can select it from the type dropdown for
   any place in Gramps.

   If you don't use this feature, you can remove ``cemeteries`` from ``nav_pages`` to drop it from
   the navigation entirely — see :doc:`../config/index`.

Birthdays
=========

List all calendar dates with birthdays of people in the tree. Names can be filtered to show
ancestors or descendants only, and living people only. People without a full birth date are not
included in the list.

`Demo <https://gramps.bennuttall.com/I0000/birthdays/>`_

Surnames
========

View a list of surnames in the tree. Click on a surname to view the people with that surname,
including people who have it as a married name. Names can be filtered and sorted.

`Demo <https://gramps.bennuttall.com/I0000/surnames/>`_

Hidden research pages
=====================

Extra pages not included in the nav bar, but accessible directly. These are to aid research rather
than for general tree browsing.

Ancestor records
----------------

The Ancestor records page shows a table of the root person's ancestors grouped by generation, and a
set of icons reflecting which key records are available for that person, as a way to aid research
completion by highlighting missing records.

`Demo <https://gramps.bennuttall.com/I0000/ancestor-records/>`_

Census records
--------------

The Census records page shows a table of the root person's ancestors grouped by generation, and a
set of icons reflecting the state of records relating to that person, as a way to aid research
completion by highlighting conflicting or missing Census records during a person's lifetime.

`Demo <https://gramps.bennuttall.com/I0000/census-records/>`_

More
====

Tags
----

Any tags used in Gramps are shown as filters so events can be filtered by tag. Some tags also have
an icon associated with them:

* Interesting - star icon
* Conflict - exclamation mark icon

Events with images
------------------

A photo icon is shown next to events to indicate that there are images associated with that event.