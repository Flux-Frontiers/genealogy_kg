# GenealogyKG design plan

Author: Eric G. Suchanek, PhD
Status: Phase 0 through 4 complete (Phase 4 on 2026-08-24) -- build/query/pack,
lineage walks, ASCII family trees, KGRAG federation, the `WITHIN` place
hierarchy, the living-person filter, Julian dates, the full `analyze()`
report, snapshots, `install-hooks` and the 2-D pedigree/network views all
work end to end. Phase 5 (viz3d/holographic) is roadmapped below but not
started.

Known defect, not introduced by Phase 4: `adapter.py` names
`KGKind.GENEALOGY`, which arrived in kg-rag 0.15.0 (kgrag commit `3dcb9ab`,
alongside `genealogy_adapter.py`). The `adapter` extra floors at
`kg-rag>=0.14.0`, so it resolves to 0.14.0 and `query()`/`pack()` raise
`AttributeError`. Raise the floor to `>=0.15.0` once that release is on PyPI.
The adapter has no test coverage, which is why this went unnoticed through
Phases 1-3.

GenealogyKG turns a GEDCOM file into a KGModule: a SQLite graph of people,
families, events, places and sources, a sqlite-vec index over prose summaries
of each record, and the standard fleet surfaces on top (CLI, MCP server,
KGRAG adapter, snapshots). Nothing in the storage, query or packing layers is
new. The whole module is a `KGExtractor` that yields `NodeSpec`/`EdgeSpec`
objects, a few lineage helpers over `GraphStore`, and one function that maps
GEDCOM dates onto the fleet's temporal contract.

## What the reader gets

- `genkg build --source family.ged` produces `.genealogykg/graph.sqlite`
  and `.genealogykg/vectors.sqlite`.
- `genkg query "chemists born in Cincinnati"` returns ranked person,
  event and place nodes, expanded one hop through family links.
- `genkg pack "Hartwell emigration"` returns the raw GEDCOM records
  behind each hit, with line numbers, ready for an LLM context window.
- `genkg ancestors I7 --generations 3` and `descendants I1` print an
  ASCII family tree -- no semantic query, no plotting library, works over
  SSH:

  ```
  John Hartwell (1820-1891) m. Mary Ashcombe
  +-- William Hartwell (1848-1922) m. Anna Kessler
  |   `-- Robert Hartwell (1876-1949) m. Louise Brandt
  `-- Eliza Hartwell (b. 1851) m. Samuel Pryce
  ```
- `genkg-mcp` exposes the same operations to Claude Code and other MCP
  clients, including `family_tree` for the ASCII rendering.
- A federated `kgrag query --from 1840 --to 1900` includes genealogy hits,
  because every dated node carries `occurred_start` / `occurred_end`, and
  `kgrag` itself knows the kind (`KGKind.GENEALOGY`, registered 2026-08-23).
- `genkg viz I1 --output tree.html` draws the descent chart; `--view network`
  draws the person/family topology around someone.
- Later: `genkg quilt I1` for a Looking Glass hologram (Phase 5).

## Decisions

### Parse with ged4py, do not write a parser

`ged4py` (MIT, 0.5.2, Python 3.11+) reads GEDCOM 5.5 and 5.5.1. It handles
the parts that look small and are not: ANSEL and UTF-8 codecs with BOM
detection, `CONT`/`CONC` continuation, `@xref@` pointer resolution, and the
full `DATE` grammar (`ABT`, `CAL`, `EST`, `BEF`, `AFT`, `BET ... AND`,
`FROM ... TO`, Julian and Hebrew calendars, free-text phrases). Every
`Record` carries its byte `offset` in the file, which is what lets `pack()`
return the original record text.

Rejected: `python-gedcom` is GPLv2 and cannot be a dependency of an
Elastic-2.0 package. `gedcom7` reads only GEDCOM 7, has no license metadata,
and no mainstream exporter emits GEDCOM 7 by default yet. A hand-rolled
parser would be a second implementation of the date grammar for no gain.

GEDCOM 7 support is deferred. Revisit when Ancestry or FamilySearch exports
change their default.

### Stay on the shared pipeline

The module subclasses `kg_utils.pipeline.KGModule` and lets `GraphStore`,
`SemanticIndex` and the default `query()`/`pack()` do the work. FTreeKG opted
out of `GraphStore` for raw SQL and was the one fleet module where the
temporal contract failed to reach callers (FLEET_STANDARDS.md, "Temporal
data"). This module does not repeat that.

Two overrides are needed:

- `index_meta_columns()` adds `text` to the vector metadata so query hits
  surface the prose summary as their `docstring`.
- `query()` and `pack()` default `rels` to the genealogy edge set instead of
  `DEFAULT_RELS` (`CONTAINS`, `CALLS`, ...), which would expand nothing.

### One KG kind, many people

The kind string is `genealogy`, the store directory is `.genealogykg`, the
KGRAG adapter kind is `KGKind.GENEALOGY`. kg-rag already carries a
`KGKind.PERSON` stub for a future single-person biographical KG. That is a
different thing (one subject, many facts) from this one (many subjects, few
facts each), and the two must not be conflated when the adapter is
registered.

### Source files are private by default

A GEDCOM file is personal data about living relatives. `.gitignore` excludes
`*.ged` everywhere except `tests/fixtures/`, and the fixture is fictional.
The build never copies the source into `.genealogykg/`; `pack()` reads it in
place, so deleting the file removes the data from every path that could
reveal it.

The living-person filter (Phase 3) is `[tool.genealogykg]
living_cutoff_years = N`, or `GenealogyKG(living_cutoff_years=N)`. Off
unless set. A person with no `DEAT`/`BURI` record whose birth (fallback
`BAPM`, `CHR`) falls within `N` years of today becomes a bare `person` node
named `Living`: xref, sex and lineage edges kept (so trees still walk
through them), name, dates, events, notes, citations and `surname` dropped,
and their name withheld from every other node's prose -- family names,
children lists, spouse phrases, parents. A family with a living spouse also
drops its `MARR` date, place, event and temporal keys. Two limits, both
documented rather than papered over: a person with no birth date at all is
never redacted (the rule needs a year to compare), and `pack()` reads the
GEDCOM file in place, so a redacted store must travel without the file.

## Graph model

### Node kinds

| kind | one per | `name` | `qualname` | `docstring` (embedded text) |
|---|---|---|---|---|
| `person` | `INDI` record | formatted name | `Surname, Given` | one prose paragraph: name, sex, birth and death with place, parents, spouses with marriage year, occupation, notes |
| `family` | `FAM` record | `Hartwell-Ashcombe family` | same | spouses, marriage date and place, children in order |
| `event` | dated sub-record (`BIRT`, `DEAT`, `BURI`, `BAPM`, `CHR`, `MARR`, `DIV`, `RESI`, `OCCU`, `IMMI`, `EMIG`, `CENS`) | `Birth of John Hartwell` | `I1.BIRT` | who, what, when, where |
| `place` | distinct `PLAC` string | the string as written | same | the place string plus the events that happened there |
| `source` | `SOUR` record | `TITL` | same | title, author, publication |

`node_id` is deterministic and readable: `person:I1`, `family:F1`,
`event:I1:BIRT`, `event:I1:RESI:2` (ordinal for repeated tags),
`place:leeds-yorkshire-england`, `source:S1`. IDs are stable across rebuilds
of the same file, which is what snapshots and cross-KG links need.

`source_path` is the GEDCOM file's repo-relative path. `lineno` and
`end_lineno` are the record's line span, computed once per build from ged4py's
byte offsets. That is all `pack()` needs to return the original record.

### Edge kinds

| relation | from | to | why it exists |
|---|---|---|---|
| `CHILD_IN` | person | family | `FAMC` |
| `SPOUSE_IN` | person | family | `FAMS` |
| `PARENT_OF` | person | person | derived from `FAM`: each `HUSB`/`WIFE` to each `CHIL`. Makes an ancestor walk one hop per generation instead of two. |
| `MARRIED_TO` | person | person | derived, `HUSB` to `WIFE`, one direction. `GraphStore.expand` is undirected so one edge serves both. |
| `HAS_EVENT` | person or family | event | |
| `OCCURRED_AT` | event | place | |
| `CITES` | person, family or event | source | `SOUR` pointers at any level |
| `WITHIN` | place | place | comma-split hierarchy: `Cincinnati, Hamilton, Ohio, USA` -> `Hamilton, Ohio, USA` -> `Ohio, USA` -> `USA`, each level its own `place` node, emitted the first time any string reaches it. Excluded from the default expansion rels, like `CITES`, so a hit on a country does not pull in every place inside it. |

Ancestors walk `PARENT_OF` inbound (`GraphStore.callers_of`), descendants
walk it outbound (`GraphStore.edges_from`). No second edge kind is needed.

### Temporal contract

One function, `genealogy_kg.temporal.temporal_keys(date_value)`, maps a
ged4py `DateValue` onto `kg_utils.temporal.temporal_metadata(...)` and
returns `{}` for anything it cannot place. It is the only writer of
`occurred_start`, `occurred_end` and `recorded_at`, per the "derive, don't
author twice" rule.

| GEDCOM | contract |
|---|---|
| `12 MAR 1901` | `occurred_start=1901-03-12` (day precision) |
| `MAR 1901`, `1901` | month, year precision |
| `ABT 1850`, `CAL 1850`, `EST 1850` | `occurred_start=1850`; qualifier kept in `date_qualifier` |
| `BEF 1857` | `occurred_end=1857` only |
| `AFT 1930` | `occurred_start=1930` only |
| `BET 1899 AND 1901`, `FROM 1846 TO 1850` | start and end |
| phrase (`(before the war)`) | `{}`; raw text stays in `date_raw` |
| `@#DJULIAN@ 1 MAR 1700` | `occurred_start=1700-03-12`: converted with `convertdate.julian` at day precision; Julian year and year-month pass through unchanged (the calendars differ by less than that) |
| Hebrew, French Republican, BC years | `{}`; still deferred |

Person nodes get `occurred_start` from `BIRT` (fallback `BAPM`, `CHR`) and
`occurred_end` from `DEAT` (fallback `BURI`). Family nodes get `MARR`. Event
nodes get their own `DATE`. `recorded_at` is the `HEAD.DATE` of the file when
present. The raw `DATE` string is always kept beside the derived keys.

## Package layout

```
src/genealogy_kg/
  __init__.py       GenealogyKG, GedcomExtractor, __version__
  gedcom.py         thin reader over ged4py: records, line spans, name/place/date helpers
  temporal.py       temporal_keys()/person_temporal_keys(): ged4py DateValue -> kg_utils.temporal
  extractor.py      GedcomExtractor(KGExtractor): the graph model above
  module.py         GenealogyKG(KGModule): kind(), analysis()/analyze(), rels defaults, tree()
  lineage.py        ancestors(), descendants(), kinship_path(), tree_data(), ascii_tree()/FamilyTree
  analysis.py       analyze_graph()/render_report(): the analyze() data and its Markdown
  config.py         [tool.genealogykg] sources + living_cutoff_years, .genealogykg/config.json
  snapshots.py      GenealogySnapshotManager over kg_utils.snapshots
  mcp_server.py     FastMCP: query_genealogy, pack_genealogy, get_person,
                    ancestors, descendants, family_tree, graph_stats, analyze_genealogy
  adapter.py        GenealogyKGAdapter for KGRAG (optional extra `adapter`)
  viz.py            2-D rendering: pedigree_figure() (plotly), network_html()
                    (the genealogy theme over kg_utils.viz.build_graph_html)
  scene.py          viz3d attractor/limb/leaf mapping for the holographic stack (Phase 5, not started)
  cli/
    group.py        root click group (`genkg`)
    options.py      shared --repo/--db/--vectors/--model/-k options
    cmd_build.py    build
    cmd_query.py    query, pack
    cmd_lineage.py  ancestors, descendants (both print an ASCII tree)
    cmd_analyze.py  analyze
    cmd_status.py   status
    cmd_snapshot.py snapshot save|list|show|diff
    cmd_hooks.py    install-hooks
    cmd_viz.py      viz (--view pedigree|network); quilt lands here in Phase 5
```

Storage: `.genealogykg/graph.sqlite`, `.genealogykg/vectors.sqlite`,
`.genealogykg/snapshots/` (tracked), `.genealogykg/config.json` (the source
path used by the last build).

## Phases

Each phase ends with a green suite and a release. Version numbers follow the
fleet's usual pace (a minor bump per phase).

### Phase 0: skeleton (done)

Repo structure per fleet conventions, CI (lint, type, test, wheel smoke
test), release workflow, fixture GEDCOM, this document. Source modules exist
with their public signatures and raise `NotImplementedError`.

### Phase 1: build, query, pack (0.1.0) -- done 2026-08-23

1. `gedcom.py`: open a file, iterate `INDI`/`FAM`/`SOUR`, compute line spans
   from offsets, format names and places.
2. `temporal.py` with a table-driven test covering every row above.
3. `extractor.py` emitting the node and edge kinds above. Test: node and edge
   counts on the fixture, ID stability across two extractions, every dated
   node carries the contract.
4. `module.py`: `kind()`, `index_meta_columns()`, rels defaults, a minimal
   `analyze()`.
5. `cli/cmd_build.py`, `cmd_query.py`, `cmd_status.py`. Test through
   `click.testing.CliRunner` on the fixture.
6. `pack()` returns the GEDCOM record for `person:I1` with the right line
   numbers. This is the acceptance test for the whole phase --
   `tests/test_build_query_pack.py::test_pack_returns_the_original_gedcom_record`.
7. Build `corpora/torture/TGC551LF.ged` (ANSEL, every 5.5 tag),
   `corpora/gedcom-samples/royal/royal92.ged` (no `GEDC` header) and
   `corpora/gedcom-samples/pres/pres2020.ged` (5.5.1, BOM) without error
   and with the node counts [CORPORA.md](CORPORA.md) lists. These run as
   `integration` tests, skipped when `corpora/` is absent.

### Phase 2: lineage and federation (0.2.0) -- done 2026-08-23

1. `lineage.py`: `ancestors`/`descendants` (bounded by generations, nearest
   first), `kinship_path` (shortest `PARENT_OF`/`MARRIED_TO` chain, BFS over
   both directions since `MARRIED_TO` is stored husband -> wife only but is
   conceptually symmetric).
2. **`ascii_tree()` / `FamilyTree`**, also in `lineage.py`. A recursive
   walk (children via `edges_from`, parents via `callers_of`, depth-bounded,
   cycle-safe on the current path) renders pure-ASCII connectors
   (`+--`/`` `-- ``/`|`, never Unicode box-drawing) with spouses and life
   spans inline:

   ```
   John Hartwell (1820-1891) m. Mary Ashcombe
   +-- William Hartwell (1848-1922) m. Anna Kessler
   |   +-- Robert Hartwell (1876-1949) m. Louise Brandt
   |   |   `-- Margaret Hartwell (1903-1990)
   |   `-- Clara Hartwell (b. 1879)
   +-- Eliza Hartwell (b. 1851) m. Samuel Pryce
   |   `-- Edith Pryce (b. 1874)
   `-- Thomas Hartwell (1855-1857)
   ```

   `FamilyTree.__repr__`/`__str__` both return the rendered text, so
   `kg.tree("I1")` prints the tree directly at a REPL prompt or in a
   notebook -- no plotting library, no build step. This is the zero-setup
   tier every heavier visualization in Phase 4/5 sits on top of: it works
   the moment `build` has run, on a laptop or over SSH, and it is what
   `genkg ancestors`/`descendants` print and what the `family_tree`
   MCP tool returns.
3. `GenealogyKG.tree()`; `cli/cmd_lineage.py`'s `ancestors`/`descendants`
   commands print it; MCP gained `family_tree` alongside the existing
   `ancestors`/`descendants` (which return the flat, generation-tagged JSON
   list `lineage.ancestors`/`descendants` produce, for callers that want
   data rather than art).
4. `adapter.py` in this repo, and in kg-rag: `KGKind.GENEALOGY`,
   `genealogy_adapter.py`, the `.genealogykg` directory mapping in
   `cmd_registry.py`, a colour and glyph in `app.py`, "genealogy" added to
   the three MCP tool kind-filter enums. Landed as `kgrag` commit
   `3dcb9ab`, not a public TODO.

   **A wrong finding, corrected the same day.** Writing
   `genealogy_adapter.py` required knowing the shape
   `kg_utils.pipeline.KGModule.query()`/`.pack()` return (`node["id"]`,
   `node["relevance"]["score"]`, `node["snippet"]`), and this document
   originally claimed `kg_rag.adapters.ftree_adapter.FTreeKGAdapter` was
   broken for still reading the older `node_id`/top-level-`score`/
   `.snippets` shape -- on the assumption that every `KGModule` subclass
   returns the shared base shape. It does not: `FileTreeKG` overrides
   `query()`/`pack()` itself and deliberately keeps the older shape for
   backward compatibility (its own `module.py` docstrings say so). A real
   `FileTreeKG` build confirmed `node_id` and `score` were already correct
   there. The one genuine defect: `FTreeKGAdapter.pack()` built
   `CrossSnippet` without `metadata=`, even though `FileTreeKG.pack()`
   populates it on every snippet and `query()`'s `CrossHit` already read
   it -- so a `time_range`-scoped `pack()` call saw every FTreeKG snippet
   as undated. Fixed in `kgrag` commit `4ecd0cc` (one line, two regression
   tests), CHANGELOG corrected there to retract the false claim.
   `diary_adapter.py` and `agent_adapter.py` were checked the same way
   (their backends' actual `query()`/`pack()` source, not assumed) and are
   correct: both genuinely return `node_id`/`score` at the top level by
   design, unrelated to `kg_utils.pipeline`'s shape.
5. Deliberately not built this phase: a dedicated federated
   time-scoped-query test (ftree_kg's `test_temporal_contract.py` pattern).
   That needs `kg-rag` installed, which is the `adapter` extra, not the
   `dev` group -- `ftree_kg/adapter.py` has the identical gap for the
   identical reason (confirmed: no test file references it, and its own
   `pyproject.toml` comment says nothing in the fleet imports it directly).
   Matching that precedent rather than inventing a one-off `kg` group entry
   for a single test. The adapter was smoke-tested by hand instead (a
   scratch venv with both packages installed editable, a real build, and a
   real query/pack/stats/analyze/snapshot round trip) -- confirmed working,
   just not wired into CI.

### Phase 3: hygiene and analysis (0.3.0) -- done 2026-08-23

1. `WITHIN` place hierarchy, emitted by the extractor as described in the
   edge table. On the fixture, `Ohio, USA` and `USA` appear once each and
   both Cincinnati and Dayton sit `WITHIN` them.
2. Living-person filter, as described under "Source files are private by
   default". Tested with a 200-year cutoff on the fixture: five people
   without death records born after 1826 are redacted, the two with
   `AFT`/plain death dates are not, and their names appear nowhere else
   in the graph.
3. Julian conversion in `temporal.iso_date()` via `convertdate.julian`,
   day precision only. ged4py rejects dual years (`1699/00`) outside the
   Gregorian calendar, so there is no dual-year case to handle. Hebrew and
   French Republican stay unplaced; `convertdate` can do both, but the
   month-name mapping deserves its own verified table rather than a
   drive-by.
4. `analysis.py`: `analyze_graph()` returns the data (counts, generation
   depth as the longest `PARENT_OF` chain with cycle cut-off, surname
   distribution from the new `surname` metadata key, date coverage per
   dated kind, people with no `CHILD_IN`/`SPOUSE_IN` edge, places with no
   `WITHIN` edge in either direction, redacted-person count) and
   `render_report()` the Markdown. `GenealogyKG.analysis()` exposes the
   dict; `analyze()` still never raises. Snapshots record the same numbers.
5. `snapshots.py`: `GenealogySnapshotManager.capture_genealogy(stats,
   analysis)` over `kg_utils.snapshots`, with people/families/events/places
   deltas beside the shared node/edge ones and the `diary_kg`-style
   `get_previous()` fallback so an unsaved capture already carries
   `vs_previous`. `genkg snapshot save|list|show|diff` and
   `genkg install-hooks` (quality checks on every commit; the
   rebuild-and-snapshot step only under `GENKG_SNAPSHOT=1`, per
   `kgrag_priv/docs/SNAPSHOT_STRATEGY.md`).

25 new tests (83 total).

### Phase 4: viz -- 2-D family-tree diagrams (0.4.0) -- done 2026-08-24

The fleet convention for a KG's optional 2-D visualization is a `viz` extra,
never hand-rolled per repo. This phase is that extra plus the domain glue that
turns a `GenealogyKG` into the shapes those libraries draw:

1. `viz.py`: `network_html()` renders the
   `person`/`family`/`CHILD_IN`/`SPOUSE_IN`/`MARRIED_TO` graph -- the
   ontological view. People are coloured by sex or by generation depth from a
   chosen root; each relation gets its own edge colour, with `PARENT_OF` and
   `MARRIED_TO` loud and the membership edges they derive from muted.
2. `pedigree_figure()` -- a `plotly` **pedigree/descent chart**, the semantic
   view and the direct visual upgrade path from `ascii_tree()`. Both now walk
   `lineage.tree_data()`, so they cannot drift into two independent layouts:
   the walk was extracted rather than duplicated, and the chart keeps the ASCII
   orientation (root on top, a row per generation).
3. `cli/cmd_viz.py`: `genkg viz <xref> --output tree.html`, with `--view
   pedigree|network`, `--direction`, `--generations`, `--color-by` and
   `--max-nodes`.
4. `KGAdapter.display()`: `SEMANTIC` draws the descent chart from a
   progenitor, `ONTOLOGICAL` the network. Non-Streamlit backends and a missing
   `viz` extra both fall back to the base placeholder card rather than failing
   the visualizer.
5. `pip install "genealogy-kg[viz]"`; nothing in `viz.py` is imported outside
   the `cli/cmd_viz.py` and `adapter.display()` entry points, so a bare install
   never pulls `plotly`/`pyvis`. A subprocess test asserts it, because this
   environment has the extra installed and would hide a regression otherwise.

Two things landed differently from the sketch above.

**The renderer is not hand-rolled `pyvis`.** `kg_utils.viz.build_graph_html`
already draws any KG's graph; what belongs here is only the genealogy
vocabulary -- kinds, colours, tooltip fields -- exactly as
`pycode_kg.graph_html` does for code. The `viz` extra therefore asks for
`kgmodule-utils[viz]` and does *not* hand-list `pyvis`. Hand-listing the
render stack while never depending on the SDK extra where the code lives is
what left `diary_kg`'s `viz3d` extra dead; see `FLEET_STANDARDS.md`.

**Only this repo's `adapter.py` got the override.** The second copy does
exist -- `kg_rag.adapters.genealogy_adapter`, added in kg-rag 0.15.0 -- but
that release was still unpublished when this landed, so the environment here
resolves 0.14.0, which has neither that module nor `KGKind.GENEALOGY`.
Porting `display()` into the kg-rag copy is a follow-up in that repo, and it
pairs with raising this repo's `adapter` floor to `>=0.15.0`. See the status
note at the top.

25 new tests (108 total).

### Phase 5: viz3d -- the family tree, literally (0.5.0)

Grow the graph with `kg_utils.viz3d.organic` and render a quilt with
`quiltwright`: the root couple as trunk, each family a limb, each person a
leaf placed by birth year along the limb, leaf colour by generation, canopy
density by branch fecundity (children per couple) -- attractors are real
genealogical data, so the canopy's shape *is* the family's shape, per the
visualization stack's own organic-growth premise. `scene.py` is the only
new code; layers 1-2 (`kg_utils.viz3d.organic`, `quiltwright`) are the
shared fleet stack and are never reimplemented here --
`kgrag_priv/docs/VISUALIZATION_STACK.md` is the canonical reference, and
`gutenberg_kg`'s `scene.py`/`cli/cmd_quilt.py` and `pycode_kg`'s
repo-to-trunk mapping are the pattern to follow.

1. `scene.py`: root couple -> trunk seed, each `family` node -> a limb
   attractor, each `person` leaf placed along its parent limb by
   `occurred_start` year (falls back to generation depth when undated).
2. `cli/cmd_viz.py` gains `quilt`: `genkg quilt <xref> --preset
   <name>` -> a Looking Glass light-field quilt via `render_quilt`.
3. `pip install "genealogy-kg[viz3d]"` (PyVista-backed, heavy); declare
   `"quiltwright>=0.4.0"` unmarked, per the fleet's current floor.

Not started. No target version beyond "after Phase 4 ships and there is a
`viz.py` layout worth lifting into 3-D" -- 3-D placement logic that has
never been checked against a working 2-D layout first is the way to
discover a coordinate-system bug at the most expensive possible point.

## Not in scope

- Writing or editing GEDCOM.
- Merging duplicate persons across files. One file, one graph.
- A web UI. The MCP server and KGRAG's app are the interfaces.
- GEDCOM X or GEDCOM 7 input.

## Decisions taken 2026-08-23

- **Event nodes exist from Phase 1.** A semantic hit on "marriage in Dayton
  1901" lands on the marriage event and expands to both spouses in one hop.
- **The kind is `genealogy`**, with its own `KGKind.GENEALOGY` in kg-rag.
  The `person` stub there stays reserved for a single-subject biography KG.
- **No real GEDCOM export exists yet.** Development runs against the fixture
  and the public corpora listed in [CORPORA.md](CORPORA.md), fetched by
  `scripts/fetch_corpora.sh` into the gitignored `corpora/` directory.

## Fleet checklist for the first release

- [ ] `poetry lock` committed; CI green on `main`
- [ ] CHANGELOG `## [0.1.0] - YYYY-MM-DD` (one ASCII hyphen)
- [ ] `release-notes.md` generated from the changelog section
- [ ] CITATION.cff `version:` and `date-released:`; DOI added after Zenodo
      mints it (use the `zenodo` skill, do not copy the DOI off the record page)
- [ ] README badge, APA and BibTeX versions
- [ ] Trusted publishing configured on PyPI for `genealogy-kg` before the tag
- [ ] `FLEET_REPOS` in `kgrag_priv/scripts/fleet_audit.py` and the roster in
      `~/.claude/CLAUDE.md` list `genealogy_kg` (done in Phase 0)
