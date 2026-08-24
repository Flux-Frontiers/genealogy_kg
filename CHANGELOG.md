# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 3: hygiene and analysis. `WITHIN` edges give every comma-separated
  `PLAC` level its own `place` node (`Cincinnati, Hamilton, Ohio, USA` ->
  `Hamilton, Ohio, USA` -> `Ohio, USA` -> `USA`), excluded from the
  default expansion rels like `CITES`. `[tool.genealogykg]
  living_cutoff_years` (or `GenealogyKG(living_cutoff_years=N)`) redacts
  people without a death record born within N years of today to a bare
  `Living` node, withholds their name from every other node's prose, and
  drops a living couple's marriage details; off unless set. Julian dates
  convert to Gregorian at day precision via `convertdate`. `person` nodes
  carry a `surname` metadata key. `analysis.py` and
  `GenealogyKG.analysis()` produce the data behind a fuller `analyze()`
  report: generation depth, surname distribution, date coverage per kind,
  people with no family links, places with no hierarchy, redacted count.
  `snapshots.py` records those metrics over `kg_utils.snapshots`, with
  people/families/events/places deltas; `genealogykg snapshot
  save|list|show|diff` and `genealogykg install-hooks` (quality checks on
  every commit, snapshot only under `GENEALOGYKG_SNAPSHOT=1`). 25 new
  tests (83 total).
- Phase 2: `ancestors`/`descendants`/`kinship_path` lineage walks over
  `GraphStore`, and `ascii_tree()`/`FamilyTree` -- a pure-ASCII
  (`+--`/`` `-- ``/`|`, never Unicode box-drawing) family-tree renderer
  whose `__repr__`/`__str__` print the tree directly. `genealogykg
  ancestors`/`descendants` and the new `family_tree` MCP tool both use
  it. `GenealogyKGAdapter` (this repo's `adapter` extra, and `kg-rag`'s
  own `KGKind.GENEALOGY` registration) reads `node["relevance"]["score"]`
  and `node["snippet"]`, the shape `kg_utils.pipeline.KGModule` actually
  returns -- verified live, and pinned with tests, against a sibling
  adapter that assumed the pre-refactor shape and silently degrades
  every federated hit (see `kgrag` CHANGELOG.md 0.14.0-successor entry).
  17 new tests (58 total).
- Phase 1: `build`, `query`, `pack`, `analyze` and `status` work end to
  end. `GedcomExtractor` emits the full graph model from docs/DESIGN.md
  (person/family/event/place/source nodes; CHILD_IN/SPOUSE_IN/PARENT_OF/
  MARRIED_TO/HAS_EVENT/OCCURRED_AT/CITES edges, derived exactly once from
  each FAM record). `temporal_keys()`/`person_temporal_keys()` derive the
  fleet temporal contract from every GEDCOM date qualifier (ABT/CAL/EST/
  BEF/AFT/BET/FROM/TO/PERIOD). 45 tests, including the acceptance test
  that `pack()` returns the original GEDCOM record with correct line
  numbers, and an integration suite against the torture-test (ANSEL,
  every 5.5 tag), royal92 (no GEDC header) and pres2020 (BOM) corpora.
- Repository skeleton per fleet conventions: Poetry/PEP 621 packaging with
  `dev` and `kg` groups, ruff/ty/pytest/detect-secrets pre-commit chain, CI
  with a wheel smoke test, tag-driven release workflow with PyPI trusted
  publishing.
- `docs/DESIGN.md`: graph model, temporal mapping, package layout and the
  phased plan.
- `tests/fixtures/sample.ged`: a fictional three-generation GEDCOM 5.5.1
  family exercising `ABT`, `BEF`, `AFT` and `BET ... AND` dates, `CONT`/`CONC`
  notes, hierarchical places and source citations.
- Source modules with their public signatures; bodies raise
  `NotImplementedError` until Phase 1.
- `scripts/fetch_corpora.sh` and `docs/CORPORA.md`: public GEDCOM test
  corpora (D-Jeffrey/gedcom-samples, the GEDitCOM torture test, the Gramps
  sample) fetched into the gitignored `corpora/`, with provenance, licence
  and a parse survey (105 of 108 files read by ged4py 0.5.2).
