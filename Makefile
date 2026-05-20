.PHONY: setup test generate dist-clean dist-build dist-publish

setup:
	./repository-setup/rehome-repository
	./development/setup-environment

test:
	PYTHONPATH=source/packages .venv/bin/python -m unittest discover -s source/testroots/testbase/tests -v

generate:
	PYTHONPATH=source/packages .venv/bin/python -m automojo.pychestrate.rest.client.generation.pychestraterestclientgenerator

dist-clean:
	rm -fr dist

dist-build:
	poetry build

dist-publish:
	poetry publish
