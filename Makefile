.PHONY: help setup install test lint format type build-kg clean all \
	fetch-corpora famous-bronte famous-kennedy famous-royal famous-trees

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
	@echo "  make famous-trees    Build + open all famous-tree demos below"
	@echo "  make famous-bronte   The Brontes (9 people; quick smoke test)"
	@echo "  make famous-kennedy  The Kennedys (66 people)"
	@echo "  make famous-royal    English royalty from William the Conqueror"
	@echo "                       (1756 people, 30 generations)"
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

# ---------------------------------------------------------------------------
# Famous family trees -- build + open a genkg viz3d demo against a public
# GEDCOM sample. Requires the viz3d extra: poetry install -E viz3d
# Corpora are fetched by scripts/fetch_corpora.sh and gitignored whole; each
# demo's .genealogykg store lives alongside its GEDCOM, also gitignored.
# Uses --schematic (straight-line layout) for speed; drop it in the genkg
# command below for the slower organic-growth render.
# ---------------------------------------------------------------------------
CORPORA := corpora/gedcom-samples

fetch-corpora:
	./scripts/fetch_corpora.sh

famous-bronte: fetch-corpora
	@test -f $(CORPORA)/.genealogykg/graph.sqlite || \
		poetry run genkg build --repo $(CORPORA) --source $(CORPORA)/bronte.ged
	poetry run genkg viz3d I0001 --repo $(CORPORA) --schematic

famous-kennedy: fetch-corpora
	@test -f $(CORPORA)/sample-kennedy/.genealogykg/graph.sqlite || \
		poetry run genkg build --repo $(CORPORA)/sample-kennedy \
			--source $(CORPORA)/sample-kennedy/kennedy.ged
	poetry run genkg viz3d I105 --repo $(CORPORA)/sample-kennedy --schematic

famous-royal: fetch-corpora
	@test -f $(CORPORA)/royal/.genealogykg/graph.sqlite || \
		poetry run genkg build --repo $(CORPORA)/royal \
			--source $(CORPORA)/royal/royal92.ged
	poetry run genkg viz3d I1380 --repo $(CORPORA)/royal --schematic

famous-trees: famous-bronte famous-kennedy famous-royal
