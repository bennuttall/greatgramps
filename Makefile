PYTHON = /home/ben/.virtualenvs/gramps/bin/python

.PHONY: html serve

html:
	$(PYTHON) -m greatgramps.build

serve:
	$(PYTHON) -m http.server -d www
