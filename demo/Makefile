PYTHON=python3
GREATGRAMPS_CONFIG=config.yml

.PHONY: generate html serve clean

generate:
	$(PYTHON) scripts/populate.py

html:
	GREATGRAMPS_CONFIG=$(GREATGRAMPS_CONFIG) grgr build

pdf:
	GREATGRAMPS_CONFIG=$(GREATGRAMPS_CONFIG) grgr tree-pdf I0000 6 www/ancestor-pedigree.pdf --color --paper A4

clean:
	rm -rf www/I*

serve:
	$(PYTHON) -m http.server -d www
