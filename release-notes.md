# Release Notes -- v0.4.0

> Released: 2026-10-26

GenealogyKG's MCP server now runs on the fleet's shared base, `kg_utils.mcp`,
so its first five tools have the same names on every fleet KG server: `stats`,
`query`, `pack`, `get_node` and `neighbors`. `get_person`, `ancestors`,
`descendants`, `family_tree` and `analyze_genealogy` keep their names.
Living-person redaction holds on every tool, and is now tested on each.

## What changed

**Canonical tool names.** `graph_stats` is `stats`, `query_genealogy` is
`query` and `pack_genealogy` is `pack`, with no aliases. `query` and `pack`
now take `hop`, `max_nodes` and `rels`. The new `get_node` returns any node by
id (`person:I7`, `family:F1`), and `neighbors` lists one node's families,
events and places.

**Privacy on every path.** A living person is redacted when the graph is
built, so `query`, `get_node`, `neighbors` and the lineage tools only ever see
`Living`; `pack` also strips the person's GEDCOM lines from every snippet. A
new test aims all four canonical tools at a redacted person over MCP and finds
no trace of the name or birth year.

**One command, standard flags.** `genkg mcp` takes the fleet's `--repo`,
`--db`, `--vectors`, `--model`, `--transport stdio|streamable-http`, `--host`,
`--port` and `--manifest`. `genkg-mcp` is the same command. The graph opens
per session and closes after, and a repo with no store is refused instead of
served empty.

**Statistics in the fleet shape.** `GenealogyKG.stats()` returns `kind`,
`nodes` (`total`, `by_kind`) and `edges` (`total`, `by_rel`). Snapshots,
`genkg status` and the analysis report show what they did before.

## Upgrading

Rename the tools in agent instructions and scripts (`graph_stats` -> `stats`,
`query_genealogy` -> `query`, `pack_genealogy` -> `pack`) and drop
`--transport sse` from any config. Code that read
`GenealogyKG.stats()["node_counts"]` reads `["nodes"]["by_kind"]` instead.
Keep `living_cutoff_years` in the served repo's `[tool.genealogykg]`: `pack`
reads it there at call time. genealogy-kg now needs kgmodule-utils 0.29.0,
whose `[mcp]` extra brings the MCP SDK.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
