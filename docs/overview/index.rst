========
Overview
========

If you have a `GRAMPS <https://www.gramps-project.org>`_ family tree, you can use greatgramps to
build a static HTML website from it, making it easy to browse yourself, and share with family.

Build your tree
===============

If you're looking to get started building your tree, check out the `GRAMPS documentation
<https://www.gramps-project.org/wiki/index.php/Main_page>`_.

GRAMPS supports importing a tree from a GEDCOM file, which is a common format for exchanging
genealogical data, so if you have a tree from another source (like Ancestry.com), you can import it
into GRAMPS and then use greatgramps to build your site. You may wish to make use of the GRAMPS
:doc:`features/index` supported by greatgramps, such as media, shared events and tags.

Configure your site build
=========================

You'll need to know:

* Your GRAMPS database location
* The IDs of any people you wish to build the tree for

GRAMPS database location
------------------------

Find the location of your GRAMPS database. Default locations on different systems are:

* ``~/.gramps/grampsdb``
* ``~/.local/gramps/grampbsdb``
* ``~/Library/Application Support/gramps/grampsdb``

Within this directory will be a directory with 8-character name for each of your GRAMPS trees. Use
the full path to the desired tree.

If you need help finding your database location, open the **Family Trees** box in GRAMPS, and click
**Info** on the desired tree. See the **Path** field for the full path.

Config file
-----------

Create a ``config.yml`` file with the contents:

.. code-block:: yaml

    db_path: /path/to/your/grampsdb/xxxxxxxx
    roots:
    - I0001
    - I0002

Create a ``.env`` file with an environment variable setting your config file:

.. code-block::

    GREATGRAMPS_CONFIG=config.yml

Build your site
===============

Run ``grgr build`` to build your site into ``www``.

Serving locally
===============

Serve your site locally with e.g. ``python -m http.server -d www``. This will start a local web
server at ``http://localhost:8000``. Alternatively, use a web server of your choice to serve the
``www`` directory.

Hosting your site
=================

You can host your site on any web server that serves static files. Bundle the ``www`` directory and
upload it to your web server. You may wish to put the site behind a password-protected virtual host
or similar.