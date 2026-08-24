# GenealogyKG project instructions

## Overview

GenealogyKG is a KGModule over GEDCOM family-history files. It subclasses
`kg_utils.pipeline.KGModule` and lets the shared SDK own storage, indexing,
query and pack. The design, graph model and phased plan live in
`docs/DESIGN.md`; read it before touching `src/`.

Fleet-wide rules (dependency conventions, hooks, releases, temporal contract)
are in `kgrag_priv/docs/FLEET_STANDARDS.md`. Cross-repo TODO items go in
`kgrag_priv/FLEET_SWEEP_PLAN.md`, never here.

## Development workflow

```bash
env -u VIRTUAL_ENV -u POETRY_ACTIVE poetry install --with dev
env -u VIRTUAL_ENV -u POETRY_ACTIVE poetry run pytest
env -u VIRTUAL_ENV -u POETRY_ACTIVE .venv/bin/pre-commit run --all-files
```

Always unset `VIRTUAL_ENV` for repo commands; an inherited venv from another
fleet repo hijacks `poetry run` silently.

Before any commit: run pre-commit on all files and fix what it reports. The
hook chain runs `ty` and the full test suite on every commit.

## Code style

- `:param:` docstrings
- ruff for format and lint (`E F W I UP`, line length 100), ty for types
- plain ASCII in prose, comments and docstrings: `--` not em dash, `->` not
  an arrow glyph

## Testing

- Tests live in `tests/`; the fixture GEDCOM is `tests/fixtures/sample.ged`
  (fictional, 12 people, 4 families). Use the `sample_ged` and `corpus_root`
  fixtures from `conftest.py`.
- Extraction must be deterministic: node IDs are `person:I1`, `family:F1`,
  `event:I1:BIRT`, `place:<slug>`, `source:S1` and must not change between
  builds of the same file.
- Never add a real GEDCOM to the repo. `*.ged` is gitignored outside
  `tests/fixtures/`.
- Public test corpora: `./scripts/fetch_corpora.sh` fills `corpora/`
  (gitignored). `docs/CORPORA.md` says which file exercises what. Tests
  that need them are marked `integration` and skip when `corpora/` is
  missing.

## Architecture

- `gedcom.py`: reader over ged4py; records, line spans, name/place helpers
- `temporal.py`: `temporal_keys()` is the only writer of `occurred_start` /
  `occurred_end` / `recorded_at`
- `extractor.py`: `GedcomExtractor(KGExtractor)`
- `module.py`: `GenealogyKG(KGModule)`, kind `genealogy`, store `.genealogykg/`
- `lineage.py`: ancestor/descendant/kinship walks over `GraphStore`
- `mcp_server.py`: `genealogykg-mcp`
- `cli/`: click group `genealogykg`, one module per command

## Indexing this repo

```bash
poetry install --with dev,kg
make build-kg          # pycodekg build + dockg build
```
