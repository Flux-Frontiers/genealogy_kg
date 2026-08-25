# Usage Guide

A complete walkthrough of GenealogyKG's CLI and MCP server. For the graph
model, phased build history and design rationale, see
[docs/DESIGN.md](DESIGN.md). For what each test corpus is and what it
exercises, see [docs/CORPORA.md](CORPORA.md).

## Installation

```bash
pip install genealogy-kg                     # core: build, query, pack, lineage, MCP
pip install "genealogy-kg[adapter]"           # + kg-rag, for KGRAG federation
pip install "genealogy-kg[viz]"               # + plotly/pyvis, for `genkg viz`
pip install "genealogy-kg[viz3d]"             # + PyVista/PyQt5, for `genkg quilt`/`viz3d`
```

Extras compose: `pip install "genealogy-kg[adapter,viz,viz3d]"` gets everything.

## Building a store

```bash
genkg build --source family.ged
```

Creates `.genealogykg/` in the current directory (`graph.sqlite` +
`vectors.sqlite`) and records `family.ged` in `.genealogykg/config.json`, so
every later command run from the same `--repo` finds it automatically:

```bash
genkg build                    # rebuilds using the recorded source
genkg build --no-wipe          # keep existing data instead of wiping first
genkg build --db /path/to/graph.sqlite --vectors /path/to/vectors.sqlite
genkg build --model sentence-transformers/all-MiniLM-L6-v2
```

Multiple sources: repeat `--source`. Or pin sources in `pyproject.toml`
instead of passing `--source` every time:

```toml
[tool.genealogykg]
sources = ["family.ged"]
```

Precedence: `--source` on the command line > `.genealogykg/config.json` from
the last build > `[tool.genealogykg] sources` in `pyproject.toml`.

`*.ged` is gitignored everywhere except `tests/fixtures/` and
`corpora/entries/` (see [The curated corpus](#the-curated-corpus) below) --
GEDCOM exports contain personal data about living people and don't belong in
version control by default.

## Searching: query and pack

```bash
genkg query "emigrated from Yorkshire"
genkg query "chemist" -k 20 --hop 2
```

`query` returns ranked nodes as JSON: a hybrid of vector similarity over a
prose summary of each record and graph expansion along lineage/event/place
edges. `-k`/`--k` bounds the result count (1-100, default 8); `--hop` bounds
graph expansion from each seed (0-5, default 1).

```bash
genkg pack "Hartwell marriages" --output context.md
genkg pack "chemist" -k 15
```

`pack` returns the *original GEDCOM record* behind each hit -- with line
numbers -- as a Markdown snippet pack ready to drop into an LLM context
window. It reads the source `.ged` file in place at query time rather than
copying it into the store, so a built `.genealogykg/` directory can be
shared without the source file traveling with it -- unless [living-person
redaction](#living-person-privacy) is on, in which case it must.

## Lineage: ancestors and descendants

```bash
genkg ancestors I7 --generations 3
genkg descendants I1
```

Prints a pure-ASCII family tree (no Unicode box-drawing), nearest generation
first, with spouses and life spans inline:

```
John Hartwell (1820-1891) m. Mary Ashcombe
+-- William Hartwell (1848-1922) m. Anna Kessler
|   `-- Robert Hartwell (1876-1949) m. Louise Brandt
`-- Eliza Hartwell (b. 1851) m. Samuel Pryce
```

`XREF` accepts three forms interchangeably everywhere in the CLI and MCP
server: `I7`, `@I7@` (GEDCOM's own pointer syntax), and `person:I7` (a node
id echoed back from a previous `query`/`pack` result). `--generations` is
bounded 1-50 (default 4).

## Visualization

### 2-D: `viz` (needs the `viz` extra)

```bash
genkg viz I1 --output tree.html                                    # pedigree/descent chart
genkg viz I1 --view network --color-by generation --output family.html
```

Writes a single self-contained HTML file -- the rendering library is
inlined, so it opens straight from the filesystem and can be sent to
someone with neither the GEDCOM file nor Python installed. `--view pedigree`
(default) draws the descent chart, the visual upgrade path from
`ancestors`/`descendants`'s ASCII tree; `--view network` draws the
person/family graph, bounded by `--max-nodes` (2-5000, default 250) since it
gets unreadable well below that ceiling.

### 3-D: `quilt` and `viz3d` (need the `viz3d` extra)

```bash
genkg quilt I1                          # render a Looking Glass quilt to renders/
genkg quilt I1 --cast                   # ...and push it to Looking Glass Bridge
genkg viz3d I1                          # open an interactive orbit/zoom/pan viewer
```

Both grow `xref`'s descent line as a real 3-D tree via space colonization
(the canopy's shape *is* the data, not an L-system): `xref` plus every
spouse as the trunk, each family a limb, each person a leaf clustered
around their birth family's limb tip. `xref`'s *ancestors* are not grown --
a GEDCOM can hold several unrelated lines with no single well-defined
progenitor to auto-detect. Pass `--schematic` for the cheap straight-line
layout instead of organic growth. `XREF` can be omitted if
`[tool.genealogykg] default_xref` is set in `pyproject.toml`.

`quilt` needs `pyvista`+`quiltwright`; `viz3d` additionally needs
`PyQt5`+`pyvistaqt` for the interactive window.

## Analysis and status

```bash
genkg status               # per-genre entries/built/registered/node/edge counts for corpora/entries/
genkg status --json        # same, machine-readable
genkg analyze               # generation depth, surnames, date coverage, orphans
genkg analyze --output report.md
```

`status` reads `<repo>/corpora/entries/` (override with `--root`) and shows a
table like `genkg corpus survey`, but rolled up per genre with node/edge
totals read straight from each entry's own `.genealogykg/graph.sqlite`, plus
registration counts from the KGRAG registry when the `adapter` extra is
installed. If no `corpora/entries/` tree is present -- e.g. a plain
`--repo`/`--source` dev store -- it falls back to reporting that single
store's build state, sources and counts instead.

## Snapshots

```bash
genkg snapshot save                      # capture current metrics, keyed by git tree hash
genkg snapshot list
genkg snapshot show <key>
genkg snapshot diff <key-a> <key-b>
```

Snapshots live in `.genealogykg/snapshots/` and are meant to be tracked in
git, so a repo's history shows how the graph grew over time. `genkg
install-hooks` wires this into a `pre-commit` hook automatically (below).

## The curated corpus

`corpora/entries/<genre>/<slug>/*.ged` is a committed, curated set of public
GEDCOM trees -- unlike the benchmark corpora below, these ship *in the repo*
and are safe to build against directly. Genres span royalty, US presidents,
corporations, fictional-character trees, religious figures, and more; see
[corpora/entries/NOTICE.md](../corpora/entries/NOTICE.md) for provenance and
licensing. Safety is enforced at the query/pack/MCP boundary (the
living-person filter, on by default for anyone plausibly still alive), not
by curating which files are allowed in.

```bash
genkg corpus survey                       # which entries are built, by genre
genkg corpus survey --genre royalty
genkg corpus ingest --dry-run             # preview: build + register every unbuilt entry
genkg corpus ingest --genre samples       # build (and register with KGRAG) just one genre
```

`ingest` builds each entry's own `.genealogykg/` store, then registers it
with the shared KGRAG registry as `genealogy-<genre>-<slug>`, grouped into
`genealogy-<genre>` and `genealogy-all` corpora -- registration needs the
`adapter` extra; pass `--no-register` to build without it.

## Living-person privacy

Before sharing a store, turn on the living-person filter and rebuild:

```toml
[tool.genealogykg]
sources = ["family.ged"]
living_cutoff_years = 100
unknown_birth_policy = "redact"
```

Anyone with no death or burial record who was born within the last 100
years is stored as a bare `person` node named `Living`: lineage edges and
sex are kept so trees still walk through them, but name, dates, events,
notes and citations are dropped, and the name is withheld from every
family, spouse and parent mention too. A family with a living spouse keeps
its members but not its marriage details. `pack()`'s own source-grounding
is covered too -- no snippet returned by `pack`/`pack_genealogy` contains a
line from a redacted person's real GEDCOM record, even when a neighbor's
context padding would otherwise run into it.

`unknown_birth_policy` controls records with neither a usable birth date
nor a death/burial record. The default, `"keep"`, preserves historical data
completeness. The conservative `"redact"` mode withholds those too -- this
may also hide historical people whose dates are simply incomplete. A death
or burial record always counts as affirmative evidence that someone is not
living, regardless of policy.

`pack` reads the GEDCOM file in place at query time, so a `.genealogykg/`
store built with redaction on can be shared *without* the `.ged` file --
and should be, since the redaction guarantee depends on the source file
being unreachable to whoever receives the store.

## MCP server

```bash
genkg-mcp --repo .                          # stdio transport (default)
genkg-mcp --repo . --transport sse          # SSE, for a remote/networked client
```

Exposes seven tools, all validated the same way the CLI is (bounded ranges,
normalized `xref`, non-empty queries) -- a malformed call returns a clear
tool error rather than a stack trace or silently-wrong result:

| Tool | Arguments | Returns |
|---|---|---|
| `query_genealogy` | `q`, `k` (1-100) | Ranked nodes as JSON |
| `pack_genealogy` | `q`, `k` (1-100), `max_nodes` (1-500) | GEDCOM snippet pack (Markdown) |
| `get_person` | `xref` | One person node as JSON, or `null` |
| `ancestors` | `xref`, `generations` (1-50) | Ancestors, nearest generation first (JSON) |
| `descendants` | `xref`, `generations` (1-50) | Descendants, nearest generation first (JSON) |
| `family_tree` | `xref`, `direction`, `generations` (1-50) | ASCII tree (plain text) |
| `graph_stats` | -- | Node/edge counts as JSON |
| `analyze_genealogy` | -- | Markdown analysis report |

Configure it in an MCP client (e.g. Claude Code's `.mcp.json`):

```json
{
  "mcpServers": {
    "genealogykg": {
      "command": "genkg-mcp",
      "args": ["--repo", "/path/to/your/repo"]
    }
  }
}
```

The server closes its SQLite connection on shutdown via FastMCP's
`lifespan` hook, on both the stdio and SSE transports.

## KGRAG federation

GenealogyKG registers with [kg-rag](https://github.com/Flux-Frontiers/kgrag)
as kind `genealogy` (`KGKind.GENEALOGY`); `genkg corpus ingest` is the usual
way entries get registered (above). Once registered, `kgrag query` and
`kgrag pack` include people, families and events from every registered
GenealogyKG store alongside the fleet's other knowledge graphs, and a
federated query can scope by time using the `occurred_start`/`occurred_end`
metadata derived from birth, death and marriage dates.

## Storage layout

```
.genealogykg/
  graph.sqlite     nodes and edges
  vectors.sqlite   sqlite-vec index (BAAI/bge-small-en-v1.5, 384-d)
  snapshots/       point-in-time metrics, tracked in git
  config.json      source path(s) used by the last build
```

## Git hook

```bash
genkg install-hooks
```

Writes a `pre-commit` hook that runs the repo's own `pre-commit` checks on
every commit. Set `GENKG_SNAPSHOT=1` on a commit to also rebuild the store
and save a snapshot; that's off by default because a snapshot staged into
the commit it describes can never carry that commit's own tree hash.

## Test corpora (benchmarks, not shipped)

`./scripts/fetch_corpora.sh` downloads public GEDCOM files -- the 1992
European royalty file, the US presidents file, the GEDCOM 5.5 torture test,
and a 200,000-person scale benchmark -- into the gitignored `corpora/`
directory (everything under it except `corpora/entries/`, which is
committed). [docs/CORPORA.md](CORPORA.md) lists each file, its provenance
and license, and what it exercises. Tests that need these are marked
`integration` and skip automatically when the files aren't present.
