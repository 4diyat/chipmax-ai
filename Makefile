VENV ?= .venv
PY ?= $(VENV)/bin/python

.PHONY: bootstrap install test lint format typecheck check run clean

bootstrap:
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

install:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

format:
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

typecheck:
	$(PY) tools/pyside6_typing.py
	$(PY) -m mypy

check: lint typecheck test

run:
	$(PY) -m jarvis_hands

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache .qt-stubs
