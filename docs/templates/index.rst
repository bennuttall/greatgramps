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

Custom CSS
==========

If a file named ``custom.css`` is found in your ``static_dir``, it's copied into the output and
linked from every page, right after the bundled ``style.css``. This lets you override or extend the
default styles without having to override ``style.css`` itself:

.. code-block:: yaml

    static_dir: static

.. code-block:: css

    /* static/custom.css */
    body { background: #fafafa; }

If ``custom.css`` isn't present, no extra stylesheet link is added.

404 page
========

A bundled ``404.html`` is copied into the output alongside the other static files. It can be
overridden the same way as any other static file, by placing your own ``404.html`` in
``static_dir``.