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

People
======

Search for people in the tree by name. Names can be filtered and sorted.

`Demo <https://gramps.bennuttall.com/I0000/people/>`_

Person
======

A person's page shows their names and birth/death years, their age, their relationship to the
selected root person, and includes a set of tabs:

Profile
-------

View a person's details, including their parents, siblings, relationships and children. This page
includes a filterable list of life events, a map of associated places, and a list of ancestors and
descendants.

The biographical information section also includes any external links associated with the person,
starting with their **Ancestry.com** and **findagrave.com** links if available. Other links can
be added in GRAMPS.

Ancestors
---------

An interactive tree view of a person's ancestors. Navigate between people in the tree view by
clicking on each person.

Descendants
-----------

An interactive tree view of a person's descendants. Navigate between people in the tree view by
clicking on each person.

Pictures
--------

A collection of images associated with the person and their events. Click an image to view it full
size.

Places
======

View a list of places associated with events in the tree, and a map of those places. Click on a
place name to view the events associated with that place, search the people involved, and filter by
event type. Note places can be enclosed by other places, for example a town can be enclosed by a
county, which is enclosed by a country.

Events on a place's page show the same icons as the events list — a photo icon for events with
images, a link to Find a Grave for burial events, and tag icons for events marked interesting or
conflicting.

`Demo <https://gramps.bennuttall.com/I0000/places/>`_

.. note::

   Places require latitude and longitude coordinates to be displayed on the map. If a place does not
   have coordinates, it will not be displayed on the map. You can add coordinates to a place in
   GRAMPS, or using the :doc:`../cli/add-place/index` command.

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

Cemeteries
==========

View a list of cemeteries in the tree, showing the number of burials at each, along with a map.
Click on a cemetery name to view its place page.

`Demo <https://gramps.bennuttall.com/I0000/cemeteries/>`_

.. note::

   This page is populated from places with the type set to ``Cemetery`` in GRAMPS. Places whose
   name contains the word "cemetery" are also included. Coordinates are required for a cemetery to
   appear on the map.

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

Any tags used in GRAMPS are shown as filters so events can be filtered by tag. Some tags also have
an icon associated with them:

* Interesting - star icon
* Conflict - exclamation mark icon

Events with images
------------------

A photo icon is shown next to events to indicate that there are images associated with that event.