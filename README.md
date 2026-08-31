# GenealogyKG

[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: Elastic-2.0](https://img.shields.io/badge/License-Elastic%202.0-blue.svg)](https://www.elastic.co/licensing/elastic-license)
[![PyPI](https://img.shields.io/pypi/v/genealogy-kg.svg)](https://pypi.org/project/genealogy-kg/)
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/Flux-Frontiers/genealogy_kg/releases)
[![CI](https://github.com/Flux-Frontiers/genealogy_kg/actions/workflows/ci.yml/badge.svg)](https://github.com/Flux-Frontiers/genealogy_kg/actions/workflows/ci.yml)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.22182369-blue.svg)](https://doi.org/10.5281/zenodo.22182369)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Corpus](https://img.shields.io/badge/corpus-97%20trees-orange.svg)](corpora/entries/NOTICE.md)
[![People](https://img.shields.io/badge/people-13.8k-green.svg)](corpora/entries/NOTICE.md)
[![Families](https://img.shields.io/badge/families-6.1k-green.svg)](corpora/entries/NOTICE.md)

A knowledge graph over GEDCOM family-history files: people, families, events,
places and sources as nodes, lineage as edges, and a sqlite-vec index for
natural-language search. Built on the KGRAG fleet's shared `kgmodule-utils`
SDK, so it federates with the other knowledge graphs and speaks the fleet's
temporal contract.

**See [docs/USAGE.md](docs/USAGE.md) for the complete guide** -- every CLI
command, the MCP server's tool reference, the curated corpus, and the
living-person privacy model, with real examples.

*Author: Eric G. Suchanek, PhD -- Flux-Frontiers, Liberty TWP, OH*

> **Status: pre-alpha.** `build`, `query`, `pack`, `analyze`, `status`,
> ASCII lineage trees (`ancestors`/`descendants`), KGRAG federation, the
> place hierarchy, the living-person filter, snapshots, the 2-D `viz` charts
> and the 3-D `quilt`/`viz3d` renderer all work end to end (Phase 1-5). Since
> then: a curated, committed corpus (`corpora/entries/`, 97 trees across 10
> genres) with `genkg corpus survey`/`ingest` to build and register it;
> bounded, normalized CLI and MCP inputs; deterministic resource cleanup and
> an MCP shutdown hook; a full MCP behavioral test suite and an enforced
> coverage floor; and field parity with kg-rag's own federation adapter. See
> [docs/DESIGN.md](docs/DESIGN.md) for the phased build history.

## Overview

GenealogyKG reads a GEDCOM 5.5 or 5.5.1 file and builds:

- a SQLite graph (`.genealogykg/graph.sqlite`) with `person`, `family`,
  `event`, `place` and `source` nodes linked by `CHILD_IN`, `SPOUSE_IN`,
  `PARENT_OF`, `MARRIED_TO`, `HAS_EVENT`, `OCCURRED_AT`, `CITES` and
  `WITHIN` (place hierarchy: `Cincinnati, Hamilton, Ohio, USA` is `WITHIN`
  `Hamilton, Ohio, USA`, and so on up to `USA`) edges
- a sqlite-vec index (`.genealogykg/vectors.sqlite`) over a prose summary of
  every record, so "chemists born in Cincinnati" finds Robert Hartwell
- `occurred_start` / `occurred_end` metadata derived from birth, death and
  marriage dates, so a federated KGRAG query can scope the graph by time

`pack` returns the original GEDCOM record behind each hit, with line numbers.
The source file is read in place and never copied into the store.

## Quick start

```bash
pip install genealogy-kg

# Build the graph (creates .genealogykg/ in the current directory)
genkg build --source family.ged

# Search
genkg query "emigrated from Yorkshire"

# Source-grounded snippets for an LLM context window
genkg pack "Hartwell marriages" --output context.md

# Lineage walks
genkg ancestors I7 --generations 3
genkg descendants I1

# Family trees as self-contained HTML (needs the `viz` extra)
genkg viz I1 --output tree.html
genkg viz I1 --view network --color-by generation --output family.html

# Generation depth, surnames, date coverage, people with no family links
genkg analyze

# Point-in-time metrics, tracked in git
genkg snapshot save
genkg snapshot list

# MCP server for Claude Code and other MCP clients
genkg-mcp --repo .

# No GEDCOM of your own? Build one of the 97 curated trees shipped in this
# repo -- see "The curated corpus" below.
genkg corpus ingest --genre samples --no-register
genkg descendants I0001 --repo corpora/entries/samples/bronte   # the Brontë family
```

## Installation

### From PyPI

```bash
pip install genealogy-kg
pip install "genealogy-kg[adapter]"   # + kg-rag, for KGRAG federation
pip install "genealogy-kg[viz]"       # + plotly/pyvis, for `genkg viz`
pip install "genealogy-kg[viz3d]"     # + PyVista/PyQt5, for `genkg quilt`/`viz3d`
```

### Local development

```bash
git clone https://github.com/Flux-Frontiers/genealogy_kg.git
cd genealogy_kg
poetry install --with dev
poetry run pytest
```

Dev tooling is a Poetry group, not an extra: `pip install genealogy-kg[dev]`
does not exist. To also get the `dockg` and `pycodekg` CLIs that index this
repo itself, run `poetry install --with dev,kg`.

## Configuration

`genkg build --source` records the file it used in
`.genealogykg/config.json`; later builds reuse it. To pin sources in the
project instead, list them in `pyproject.toml`:

```toml
[tool.genealogykg]
sources = ["family.ged"]
```

`.gitignore` excludes `*.ged` outside `tests/fixtures/`. GEDCOM exports
contain personal data about living people; keep them out of version control.

### Living people

Before sharing a store, turn on the living-person filter and rebuild:

```toml
[tool.genealogykg]
sources = ["family.ged"]
living_cutoff_years = 100
unknown_birth_policy = "redact"
```

Anyone with no death or burial record who was born within the last 100
years is then stored as a bare `person` node named `Living`: their lineage
edges and sex are kept so trees still walk through them, but their name,
dates, events, notes and citations are dropped, and their name is withheld
from every family, spouse and parent mention too. A family with a living
spouse keeps its members but not its marriage details.

`unknown_birth_policy` controls records that have neither a usable birth
date nor a death/burial record. The default, `"keep"`, preserves historical
data completeness and existing behavior. The conservative `"redact"` mode
withholds those uncertain records; this may also hide historical people whose
dates are simply incomplete. A death or burial record always counts as
affirmative evidence that the person is not living.

`pack` reads the GEDCOM file in place, so share the `.genealogykg/` store
without the `.ged` file.

### Git hook

`genkg install-hooks` writes a `pre-commit` hook that runs the repo's
`pre-commit` checks on every commit. Set `GENKG_SNAPSHOT=1` on a
commit to also rebuild the store and save a snapshot; that is off by
default because a snapshot staged into the commit it describes can never
carry that commit's tree hash.

### The curated corpus

`corpora/entries/<genre>/<slug>/*.ged` is a committed, curated set of 97
public GEDCOM trees across 10 genres (royalty, US presidents, corporations,
fictional characters, and more) -- unlike the benchmark corpora below,
these ship *in the repo* and are safe to build against directly, since
safety is enforced at the query/pack/MCP boundary rather than by curating
which files are let in. See
[corpora/entries/NOTICE.md](corpora/entries/NOTICE.md) for provenance and
licensing.

```bash
genkg corpus survey                    # which entries are built, by genre
genkg corpus ingest --genre samples    # build (and register with KGRAG)
```

See [docs/USAGE.md](docs/USAGE.md#the-curated-corpus) for the full
`genkg corpus` reference.

### Benchmark corpora

`./scripts/fetch_corpora.sh` downloads public GEDCOM files (the 1992
European royalty file, the US presidents file, the GEDCOM 5.5 torture test,
and a 200,000-person scale benchmark) into the gitignored `corpora/`
directory -- everything under it except `corpora/entries/`, which is
committed. [docs/CORPORA.md](docs/CORPORA.md) lists each file, its
provenance and licence, and what it exercises.

## Storage

```
.genealogykg/
  graph.sqlite     nodes and edges
  vectors.sqlite   sqlite-vec index (BAAI/bge-small-en-v1.5, 384-d)
  snapshots/       point-in-time metrics, tracked in git
  config.json      source path used by the last build
```

## KGRAG federation

GenealogyKG registers with [kg-rag](https://github.com/Flux-Frontiers/kgrag)
as kind `genealogy` (`KGKind.GENEALOGY`) -- `genkg corpus ingest` is the
usual way entries get registered. Once registered, `kgrag query` and `kgrag
pack` include people, families and events from every registered
GenealogyKG store alongside the fleet's other knowledge graphs, and a
federated query can scope by time using the `occurred_start`/`occurred_end`
metadata derived from birth, death and marriage dates.

## Citation

```
Suchanek, E. G. (2026). GenealogyKG: Genealogical Knowledge Graph
(Version 0.1.0) [Software]. Flux-Frontiers. https://doi.org/10.5281/zenodo.22182369
```

```bibtex
@software{suchanek_genealogykg_2026,
  author    = {Suchanek, Eric G.},
  title     = {GenealogyKG: Genealogical Knowledge Graph},
  year      = {2026},
  version   = {0.1.0},
  url       = {https://github.com/Flux-Frontiers/genealogy_kg},
  doi       = {10.5281/zenodo.22182369},
}
```

## License

Elastic License 2.0. See [LICENSE](LICENSE).
