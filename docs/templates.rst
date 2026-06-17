=========
Templates
=========

greatgramps ships with a default set of Chameleon page templates. You can override any of them — or
all of them — without touching the others.

Point ``templates_dir`` in your config at a directory containing your custom templates:

.. code-block:: yaml

    templates_dir: templates

Any template file found in that directory takes precedence over the bundled one of the same name.
Templates you don't provide fall back to the bundled defaults, so you can override just one file if
that's all you need.

The bundled templates live in ``greatgramps/templates/`` in the source tree and can be used as a
reference.

The same layered approach applies to static files (CSS etc.). Point ``static_dir`` at a directory
and its files will be copied into the output on top of the bundled ones:

.. code-block:: yaml

    static_dir: static