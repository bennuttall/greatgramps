PYTHON=python3
GREATGRAMPS_CONFIG=config.yml

.PHONY: generate html serve clean

generate:
	$(PYTHON) scripts/populate.py

html:
	GREATGRAMPS_CONFIG=$(GREATGRAMPS_CONFIG) grgr build

clean:
	rm -rf www/I*

serve:
	$(PYTHON) -m http.server -d www
