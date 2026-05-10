PYTHON = /home/ben/.virtualenvs/gramps/bin/python
GREATGRAMPS_CONFIG=config.yaml

.PHONY: html serve

html:
	GREATGRAMPS_CONFIG=$(GREATGRAMPS_CONFIG) $(PYTHON) -m greatgramps.build

serve:
	$(PYTHON) -m http.server -d www
