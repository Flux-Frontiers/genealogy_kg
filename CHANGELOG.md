# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `GenealogyKGAdapter.query()` and `pack()` raised `AttributeError` on every
  call: they name `KGKind.GENEALOGY`, which only arrived in kg-rag 0.15.0,
  while the `adapter` extra floored at `>=0.14.0` and resolved to 0.14.0. The
  adapter imported cleanly and failed on first use, so nothing caught it
  through Phases 1-3 -- it has no test coverage. Floor raised to
  `kg-rag>=0.15.0`, which also makes `ty` pass again.

### Changed

- The `viz` extra pulls `kgmodule-utils[viz]` rather than hand-listing
  `pyvis`. The renderer is `kg_utils.viz.build_graph_html`, so the SDK owns
  that dependency; hand-listing a render stack while never depending on the
  SDK extra where the code lives is what left `diary_kg`'s `viz3d` extra
  dead (`FLEET_STANDARDS.md`).
- `lineage.tree_data()` is extracted from `ascii_tree()`, which now renders
  it, and `life_span()` is public. The pedigree chart draws the same walk, so
  the ASCII art and the 2-D chart agree by construction instead of being two
  independent walks kept in step by hand. `--generations` moves to
  `cli/options.py`, shared with `viz`. ASCII output is unchanged.
- `renders/` is gitignored: `genkg viz` output runs to megabytes because the
  rendering library is inlined, and it is reproducible from the corpus.
- Console scripts are `genkg` and `genkg-mcp`, following `gutenkg`'s short
  form; `genealogykg`/`genealogykg-mcp` never shipped. The hook's opt-in
  variables are `GENKG_SNAPSHOT` / `GENKG_SKIP_SNAPSHOT`. The package
  (`genealogy_kg`), store directory (`.genealogykg`) and
  `[tool.genealogykg]` table are unchanged; kg-rag keys on the directory.
- `.gitignore` drops the `**/.<kind>kg/lancedb*` patterns, a leftover from
  before the fleet moved to sqlite-vec; nothing writes those paths any
  more. First PyCodeKG and DocKG snapshots of this repo are checked in
  under `.pycodekg/snapshots/` and `.dockg/snapshots/`.

### Added

- Phase 4: 2-D family-tree diagrams, behind the `viz` extra. `viz.py` supplies
  only the genealogy vocabulary -- kinds, colours, shapes, tooltip fields --
  over the fleet's shared renderer, the same split `pycode_kg.graph_html` uses
  for a code graph. `network_html()` draws the ontological view: the
  person/family topology around someone, grown by hops from a root rather than
  truncated to an arbitrary slice, with each relation its own edge colour and
  the membership edges muted beneath `PARENT_OF`/`MARRIED_TO`.
  `pedigree_figure()` draws the semantic view, a plotly descent chart in the
  same orientation as `ascii_tree()` -- root on top, a row per generation, one
  box per person with name and lifespan. `genkg viz <xref> --output tree.html`
  writes either, self-contained, with `--view pedigree|network`,
  `--direction`, `--generations`, `--color-by sex|generation` and
  `--max-nodes`. `GenealogyKGAdapter.display()` renders both into a KGRAG
  viewport (`SEMANTIC` the descent chart from a progenitor, `ONTOLOGICAL` the
  network), falling back to the base placeholder card on non-Streamlit
  backends and when the extra is absent rather than failing the visualizer.
  Nothing in `viz.py` is imported outside those two entry points, so a bare
  install never pulls `plotly` or `pyvis`; a subprocess test asserts it,
  because this environment has the extra installed and would otherwise hide
  the regression.
- Phase 4 colours are chosen against colour-vision deficiency and tested for
  it, not reviewed by eye. Sex uses Okabe-Ito blue/orange: the obvious
  blue/rose pairing measures fine on a normal-vision monitor and collapses to
  dE 7 -- one colour -- for a protanope, where blue/orange holds dE 30 across
  all three dichromacies and survives greyscale printing. Generation uses
  ColorBrewer RdBu with a neutral pivot, diverging in luminance per arm rather
  than hue alone, lifting the worst adjacent step from dE 9 to dE 16. Shape
  carries sex independently of colour, always, including under `--color-by
  generation`: square for male, circle for female, as printed pedigrees have
  done for a century. Tests simulate each dichromacy (Machado 2009) and assert
  a CIELAB floor between any two swatches a reader must separate. 33 new tests
  (116 total).
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
  people/families/events/places deltas; `genkg snapshot
  save|list|show|diff` and `genkg install-hooks` (quality checks on
  every commit, snapshot only under `GENKG_SNAPSHOT=1`). 25 new
  tests (83 total).
- Phase 2: `ancestors`/`descendants`/`kinship_path` lineage walks over
  `GraphStore`, and `ascii_tree()`/`FamilyTree` -- a pure-ASCII
  (`+--`/`` `-- ``/`|`, never Unicode box-drawing) family-tree renderer
  whose `__repr__`/`__str__` print the tree directly. `genkg
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
