.RECIPEPREFIX := >
.PHONY: setup lint test

setup:
> python3 -m venv .venv
> .venv/bin/python -m pip install --upgrade pip
> .venv/bin/python -m pip install -e '.[dev]'

lint:
> .venv/bin/ruff check .
> .venv/bin/ruff format --check .

test:
> .venv/bin/pytest -q -m 'not llm and not cluster'
