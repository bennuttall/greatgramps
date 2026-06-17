=============
Configuration
=============

greatgramps is configured using a YAML file.

Create a ``config.yml`` pointing at your GRAMPS database and listing the GRAMPS IDs of the root
people you want to browse the tree as:

.. code-block:: yaml

    db_path: /path/to/your/grampsdb/xxxxxxxx
    roots:
    - I0001
    - I0002

The location of the config file must be set as with an environment variable:

.. code-block::

    GREATGRAMPS_CONFIG=config.yml

Config file reference
=====================

.. list-table::
   :header-rows: 1
   :widths: 20 10 15 55

   * - Key
     - Required
     - Default
     - Description
   * - ``db_path``
     - yes
     - —
     - Path to your GRAMPS sqlite database directory
   * - ``roots``
     - yes
     - —
     - GRAMPS IDs of the people to build root views for
   * - ``output_dir``
     - no
     - ``www``
     - Directory to write the built site into
   * - ``ancestry_tree_id``
     - no
     - —
     - Ancestry.com tree ID, used to generate profile links
   * - ``templates_dir``
     - no
     - —
     - Directory of custom Chameleon templates
   * - ``static_dir``
     - no
     - —
     - Directory of custom static files (CSS etc.)

Relative paths are resolved relative to the config file's directory.