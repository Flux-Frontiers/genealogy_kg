# GenealogyKG

GenealogyKG reads a GEDCOM 5.5 or 5.5.1 family-history file and builds a
knowledge graph from it: people, families, events, places and sources as
nodes, lineage and marriage as edges, and a sqlite-vec index for
natural-language search. It is a `genkg` command-line tool, an MCP server, and
a Python package, and it federates with the other KGRAG knowledge graphs as
kind `genealogy`.

```bash
pip install genealogy-kg
genkg build --source family.ged
genkg query "emigrated from Yorkshire"
genkg descendants I1
```

## The Family orchard

[The Knowledge Press: The Family](https://flux-frontiers.github.io/kpress_family/)
is a web app that draws a family as an orchard you drive through in the
browser. Each family line is a tree, and the home tree holds one person's
descendants as its crown and ancestors as its roots. It reads the files
`genkg export-web` writes; the public site shows the Kennedys, the Tudors and
George Washington's family, built from this repository's curated corpus with
living people redacted. Its [user guide](https://flux-frontiers.github.io/kpress_family/docs/)
covers driving, the groves and the record reader.

## Where to start

| You want to | Read |
| --- | --- |
| Install it and build a first store | [Usage guide](USAGE.md#installation) |
| Know how living people are protected | [Usage guide](USAGE.md#living-person-privacy) |
| Try it on a public tree | [Usage guide](USAGE.md#the-curated-corpus) |
| Connect Claude or another MCP client | [Usage guide](USAGE.md#mcp-server) |
| See the graph model and the build history | [Design](DESIGN.md) |
| Find out what each test corpus exercises | [Corpora](CORPORA.md) |

## Source and citation

The source is on [GitHub](https://github.com/Flux-Frontiers/genealogy_kg), the
package is on [PyPI](https://pypi.org/project/genealogy-kg/), and every release
is archived on Zenodo under
[10.5281/zenodo.22182369](https://doi.org/10.5281/zenodo.22182369).
GenealogyKG is licensed under the
[Elastic License 2.0](https://www.elastic.co/licensing/elastic-license).
