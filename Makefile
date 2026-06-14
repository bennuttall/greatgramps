PYTHON=python3
GREATGRAMPS_CONFIG=config.yml
POETRY=poetry

.PHONY: develop html serve clean build release

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