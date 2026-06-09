PYTHON = /home/ben/.virtualenvs/gramps/bin/python
GREATGRAMPS_CONFIG=config.yml

.PHONY: html serve clean

clean:
	find www -mindepth 1 -maxdepth 1 ! -name media -exec rm -rf {} +

html:
	GREATGRAMPS_CONFIG=$(GREATGRAMPS_CONFIG) $(PYTHON) -m greatgramps.build

serve:
	$(PYTHON) -m http.server -d www
