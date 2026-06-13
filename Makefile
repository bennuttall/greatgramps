PYTHON=python3
GREATGRAMPS_CONFIG=config.yml

.PHONY: html serve clean

html:
	GREATGRAMPS_CONFIG=$(GREATGRAMPS_CONFIG) grgr build

clean:
	rm -rf www/I*

serve:
	$(PYTHON) -m http.server -d www
