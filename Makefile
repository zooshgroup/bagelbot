.PHONY: clean-pyc clean-build clean
define BROWSER_PYSCRIPT
import os, webbrowser, sys
try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT
BROWSER := python -c "$$BROWSER_PYSCRIPT"

ifeq ($(OS),Windows_NT)
		RM := "rm" -rf
		FIND := "C:\Program Files\Git\usr\bin\find.exe"
else
		RM := rm -rf
		FIND := find
endif

help:
	@echo "clean - remove all build, test, coverage and Python artifacts"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "lint - check style with flake8"
	@echo "install - install bagelbot's dependencies to the active Python's site-packages"
	@echo "install-dev - install bagelbot's dependencies to the active Python's site-packages plus debug tools for local development"

clean: clean-build clean-pyc

clean-build:
	pyenv uninstall -f bagelbot
	$(RM) build
	$(RM) dist
	$(RM) .eggs
	$(FIND) . -name '*.egg-info' -exec rm -fr {} +
	$(FIND) . -name '*.egg' -exec rm -fr {} +

clean-pyc:
	$(FIND) . -name '*.pyc' -exec rm -f {} +
	$(FIND) . -name '*.pyo' -exec rm -f {} +
	$(FIND) . -name '*~' -exec rm -f {} +
	$(FIND) . -name '__pycache__' -exec rm -fr {} +

install: clean
	pyenv install 3.6.5 || true
	pyenv virtualenv 3.6.5 bagelbot
	pip install --upgrade -r requirements.txt

install-dev: clean
	pyenv virtualenv 3.6.5 bagelbot
	pip install --upgrade -r requirements_dev.txt

lint:
	pylint *.py
