# GenealogyKG design plan

Author: Eric G. Suchanek, PhD
Status: Phase 0 and Phase 1 complete (2026-08-23). Phase 2 not started.

GenealogyKG turns a GEDCOM file into a KGModule: a SQLite graph of people,
families, events, places and sources, a sqlite-vec index over prose summaries
of each record, and the standard fleet surfaces on top (CLI, MCP server,
KGRAG adapter, snapshots). Nothing in the storage, query or packing layers is
new. The whole module is a `KGExtractor` that yields `NodeSpec`/`EdgeSpec`
objects, a few lineage helpers over `GraphStore`, and one function that maps
GEDCOM dates onto the fleet's temporal contract.

## What the reader gets

- `genealogykg build --source family.ged` produces `.genealogykg/graph.sqlite`
  and `.genealogykg/vectors.sqlite`.
- `genealogykg query "chemists born in Cincinnati"` returns ranked person,
  event and place nodes, expanded one hop through family links.
- `genealogykg pack "Hartwell emigration"` returns the raw GEDCOM records
  behind each hit, with line numbers, ready for an LLM context window.
- `genealogykg ancestors I7 --generations 3` and `descendants` walk the graph
  without a semantic query.
- `genealogykg-mcp` exposes the same operations to Claude Code and other MCP
  clients.
- A federated `kgrag query --from 1840 --to 1900` includes genealogy hits,
  because every dated node carries `occurred_start` / `occurred_end`.

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
reveal it. A living-person filter is Phase 3 work, not a Phase 1 promise.

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
| `WITHIN` | place | place | comma-split hierarchy. Phase 3. |

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
| Julian, Hebrew, French Republican | `{}` in Phase 1; convert in Phase 3 |

Person nodes get `occurred_start` from `BIRT` (fallback `BAPM`, `CHR`) and
`occurred_end` from `DEAT` (fallback `BURI`). Family nodes get `MARR`. Event
nodes get their own `DATE`. `recorded_at` is the `HEAD.DATE` of the file when
present. The raw `DATE` string is always kept beside the derived keys.

## Package layout

```
src/genealogy_kg/
  __init__.py       GenealogyKG, GedcomExtractor, __version__
  gedcom.py         thin reader over ged4py: records, line spans, name/place/date helpers
  temporal.py       temporal_keys(): ged4py DateValue -> kg_utils.temporal
  extractor.py      GedcomExtractor(KGExtractor): the graph model above
  module.py         GenealogyKG(KGModule): kind(), analyze(), rels defaults, lineage helpers
  lineage.py        ancestors(), descendants(), kinship_path() over GraphStore
  config.py         [tool.genealogykg] sources + .genealogykg/config.json
  snapshots.py      GenealogySnapshotManager over kg_utils.snapshots
  mcp_server.py     FastMCP: query_genealogy, pack_genealogy, get_person,
                    ancestors, descendants, graph_stats, analyze_genealogy
  adapter.py        GenealogyKGAdapter for KGRAG (optional extra `adapter`)
  cli/
    group.py        root click group (`genealogykg`)
    options.py      shared --repo/--db/--vectors/--model/-k options
    cmd_build.py    build
    cmd_query.py    query, pack
    cmd_lineage.py  ancestors, descendants
    cmd_analyze.py  analyze
    cmd_status.py   status
    cmd_snapshot.py snapshot save|list|show|diff
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

### Phase 2: lineage and federation (0.2.0)

1. `lineage.py`: `ancestors`, `descendants` (bounded by generations),
   `kinship_path` (shortest path over `PARENT_OF`/`MARRIED_TO`, returned as
   a readable chain).
2. `cli/cmd_lineage.py` and the MCP tools.
3. `adapter.py` in this repo; in kg-rag: `KGKind.GENEALOGY`, the
   `.genealogykg` directory mapping in `cmd_registry.py`, a lazy
   `genealogy_adapter.py`, a colour and glyph in `app.py`. File that as a
   kgrag_priv sweep item, not a public TODO.
4. `tests/test_temporal_contract.py` modelled on ftree_kg's: a federated
   time-scoped query must return the person nodes and nothing undated.

### Phase 3: hygiene and analysis (0.3.0)

1. `WITHIN` place hierarchy.
2. Living-person filter: `[tool.genealogykg] living_cutoff_years = 100`
   redacts names and dates of anyone without a death event born after the
   cutoff. Off by default; documented as the switch to flip before sharing a
   store.
3. Julian calendar conversion via `convertdate` (already a ged4py dependency).
4. `analyze()` report: generation depth, surname distribution, date coverage
   per kind, people with no family links, places with no hierarchy.
5. `snapshots.py` and `genealogykg install-hooks` for corpus repos.

### Phase 4: the family tree, literally

Grow the graph with `kg_utils.viz3d.organic` and render a quilt with
`quiltwright`: the root couple as trunk, each family a limb, each person a
leaf placed by birth year along the limb. The domain glue is per-repo
(VISUALIZATION_STACK.md); nothing below it is reimplemented. Not scheduled.

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
