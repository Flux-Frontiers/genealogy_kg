.PHONY: help setup install test lint format type build-kg clean all

help:
	@echo "GenealogyKG development commands"
	@echo "--------------------------------------------------------"
	@echo "  make setup      Install dependencies with Poetry (dev group)"
	@echo "  make install    Install core runtime only"
	@echo "  make test       Run the pytest suite with coverage"
	@echo "  make lint       Lint with ruff"
	@echo "  make format     Format with ruff"
	@echo "  make type       Type check with ty"
	@echo "  make build-kg   Build the PyCodeKG + DocKG indices of this repo"
	@echo "  make clean      Remove build artifacts"
	@echo "--------------------------------------------------------"

setup:
	@./scripts/setup.sh

install:
	poetry install

test:
	poetry run pytest tests -v --cov=genealogy_kg

lint:
	poetry run ruff check src tests conftest.py

format:
	poetry run ruff format src tests conftest.py

type:
	poetry run ty check src

build-kg:
	poetry run pycodekg build --repo .
	poetry run dockg build --repo .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info

all: setup test lint type
