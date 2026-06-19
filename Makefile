PYTHON=python3
GREATGRAMPS_CONFIG=config.yml
POETRY=poetry
HTML_DOCS=docs/_build/html

.PHONY: develop html serve clean build release doc doc-serve freeze-rtd-requirements

develop:
	$(PIP) install -U pip
	$(PIP) install "poetry>2"
	$(POETRY) install --all-extras --with dev
	$(POETRY) run grgr --install-completion

html:
	GREATGRAMPS_CONFIG=$(GREATGRAMPS_CONFIG) grgr build

clean:
	rm -rf www/I*

serve:
	$(PYTHON) -m http.server -d www

build:
	rm -rf dist
	$(POETRY) build

release: build
	$(POETRY) run twine upload dist/*

doc:
	$(POETRY) run sphinx-build -b html docs $(HTML_DOCS)

doc-serve:
	$(POETRY) run python -m http.server -d $(HTML_DOCS)

freeze-rtd-requirements:
	echo "." > rtd_requirements.txt
	$(POETRY) run pip freeze | grep -iE "sphinx|autodoc" >> rtd_requirements.txt