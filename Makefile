PIP=pip3
PYTHON=python3
GREATGRAMPS_CONFIG=config.yml
HTML_DOCS=docs/_build/html
VERSION=$(shell $(PYTHON) -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')

.PHONY: develop config html serve clean build release doc doc-serve freeze-rtd-requirements

develop:
	$(PIP) install -U pip
	$(PIP) install -e ".[cli,html,pdf]" --group dev
	grgr --install-completion

config:
	grgr config

html:
	GREATGRAMPS_CONFIG=$(GREATGRAMPS_CONFIG) grgr build

clean:
	rm -rf www/I*

serve:
	$(PYTHON) -m http.server -d www

build:
	rm -rf dist
	$(PYTHON) -m build

# Tag the version in pyproject.toml and push the tag; GitHub Actions builds and publishes to PyPI
release:
	@test -z "$$(git status --porcelain)" || (echo "Working tree is not clean" && exit 1)
	git tag -a "v$(VERSION)" -m "Release $(VERSION)"
	git push origin main "v$(VERSION)"

doc:
	sphinx-build -b html docs $(HTML_DOCS)

doc-serve:
	$(PYTHON) -m http.server -d $(HTML_DOCS)

freeze-rtd-requirements:
	echo "." > rtd_requirements.txt
	$(PIP) freeze | grep -iE "sphinx|autodoc" >> rtd_requirements.txt
