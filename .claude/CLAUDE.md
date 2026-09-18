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

Always unset `VIRTUAL_ENV` for repo commands, `make` included; an inherited
venv from another fleet repo hijacks `poetry run` silently.

Before any commit: run pre-commit on all files and fix what it reports. The
hook chain runs `ty` and the full test suite on every commit.

## Make targets

`make help` prints the same list. Every target shells out to `poetry run`, so
prefix with `env -u VIRTUAL_ENV -u POETRY_ACTIVE`.

| target | what it runs |
| --- | --- |
| `setup` | `./scripts/setup.sh` -- Poetry install with the dev group |
| `install` | `poetry install` -- core runtime only, no dev group |
| `test` | `pytest tests -v --cov=genealogy_kg` (coverage floor is 80%) |
| `lint` | `ruff check src tests conftest.py` |
| `format` | `ruff format src tests conftest.py` |
| `type` | `ty check src` |
| `build-kg` | `pycodekg build` + `dockg build` over this repo (needs `--with kg`) |
| `clean` | remove `__pycache__`, `.pytest_cache`, `dist/`, `build/`, `*.egg-info` |
| `all` | `setup test lint type` |
| `fetch-corpora` | `./scripts/fetch_corpora.sh` -- fills the gitignored `corpora/` |
| `famous-bronte` | build + `genkg viz3d` the Brontes (9 people; quick smoke test) |
| `famous-kennedy` | same for the Kennedys (66 people) |
| `famous-royal` | same for `royal92.ged` (1756 people, 30 generations) |
| `famous-trees` | all three famous-tree demos in sequence |

The `famous-*` targets depend on `fetch-corpora`, need the `viz3d` extra
(`poetry install -E viz3d`), and open a Qt window. They pass `--schematic`
for speed; drop it in the Makefile for the slower organic-growth render.
Each demo's `.genealogykg/` store lives beside its GEDCOM and is gitignored.

## Code style

- `:param:` docstrings
- ruff for format and lint (`E F W I UP`, line length 100), ty for types
- plain ASCII in prose, comments and docstrings: `--` not em dash, `->` not
  an arrow glyph

## Testing

- Tests live in `tests/`; the fixture GEDCOM is `tests/fixtures/sample.ged`
  (fictional, 12 people, 4 families). Use the `sample_ged` and `corpus_root`
  fixtures from `conftest.py`. Markers: `slow`, `integration`, `unit`.
- Extraction must be deterministic: node IDs are `person:I1`, `family:F1`,
  `event:I1:BIRT`, `place:<slug>`, `source:S1` and must not change between
  builds of the same file.
- Never add a personal or living-family GEDCOM to the repo. `*.ged` is
  gitignored outside `tests/fixtures/` and `corpora/entries/` -- the latter
  is a curated, tracked corpus of 97 public GEDCOMs laid out as
  `<genre>/<slug>/<file>.ged` across ten genres (royalty, us-presidents,
  politicians-writers-scientists-etc, religious-figures-and-systems,
  fictional-characters, corporations, languages, samples, torture, misc).
  Read `corpora/entries/NOTICE.md` and `docs/CORPORA.md` before adding one.
- The safety boundary for that corpus is the living-person filter itself --
  `GedcomExtractor.is_living()`, enforced through `pack()` at the
  query/pack/MCP boundary -- not a curated allow-list of source files. The
  allow-list approach (audit each tree for anyone born after 1920 with no
  recorded death) hit its limit on `royal92.ged`, whose root looks historical
  (William the Conqueror, d. 1087) but whose descent line walks straight into
  the living modern royal families. That tree and the Kennedy one are in
  `corpora/entries/` today, admitted by the runtime filter rather than by an
  audit. Keep that filter honest -- it is now the only thing standing between
  a committed GEDCOM and a living person's record.
- Public test corpora: `make fetch-corpora` fills `corpora/` (gitignored,
  except `corpora/entries/`). `docs/CORPORA.md` says which file exercises
  what. Tests that need the fetched (untracked) ones are marked `integration`
  and skip when they're missing.

## Architecture

- `gedcom.py`: reader over ged4py; records, line spans, name/place helpers
- `temporal.py`: `temporal_keys()` is the only writer of `occurred_start` /
  `occurred_end` / `recorded_at`
- `extractor.py`: `GedcomExtractor(KGExtractor)`, including `is_living()`
- `module.py`: `GenealogyKG(KGModule)`, kind `genealogy`, store `.genealogykg/`
- `config.py`: resolves `[tool.genealogykg]` / `.genealogykg/config.json`
  (sources, `living_cutoff_years`, `unknown_birth_policy`)
- `lineage.py`: ancestor/descendant/kinship walks over `GraphStore`
- `corpus.py`: the `corpora/entries/` tree; `analysis.py`, `snapshots.py`:
  graph metrics and point-in-time snapshots
- `viz.py`: 2-D pedigree/network HTML; `scene.py` + `viz3d.py`: 3-D growth
  scene and the Qt viewer, over `kg_utils.viz3d.organic` and `quiltwright`
- `adapter.py`: kg-rag federation, `KGKind.GENEALOGY`
- `mcp_server.py`: `genkg-mcp`
- `cli/`: click group `genkg`, one `cmd_*.py` per command (build, query, pack,
  ancestors, descendants, analyze, corpus, snapshot, status, viz, viz3d,
  quilt, install-hooks), registered by `cli/main.py`

## Indexing this repo

```bash
poetry install --with dev,kg
make build-kg          # pycodekg build + dockg build
```
