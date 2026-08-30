# Release Notes -- v0.1.0

> Released: 2026-08-30

The first published release of GenealogyKG, a knowledge-graph module over
GEDCOM family-history files. It reads a GEDCOM, builds a semantic graph of
people, families, events, places and sources, and lets you search it in
natural language, walk lineage in either direction, render the result as
ASCII, as a 2-D chart, or as a literal 3-D tree you can cast to a Looking
Glass display. Everything is reachable from one CLI (`genkg`) and from an
MCP server (`genkg-mcp`), so an AI agent gets the same surface a person does.

A note on the version number, because two schemes collide: `docs/DESIGN.md`
labels its plan phases 0.1.0 through 0.5.0. Those are milestones in that
plan, not published versions -- none of them was ever released. This 0.1.0
is the first version of the package to exist, and all five phases are in it.

## What changed

**A graph you can trust to be the same twice.** Node identity is derived
from the GEDCOM's own cross-reference ids -- `person:I1`, `family:F1`,
`event:I1:BIRT`, `place:<slug>`, `source:S1` -- so two builds of the same
file produce the same graph. Every date qualifier the standard allows
(`ABT`, `CAL`, `EST`, `BEF`, `AFT`, `BET`, `FROM`, `TO`) maps onto the
fleet's temporal contract, Julian dates convert at day precision, and every
comma-separated level of a `PLAC` becomes its own node so "Ohio, USA"
answers questions about places in Ohio.

**Lineage as a first-class operation.** Ancestor, descendant and kinship
walks run over the graph store rather than re-parsing the file, and the
ASCII renderer and the 2-D pedigree chart draw from one shared walk -- so
the picture and the text agree by construction instead of by maintenance.

**Living people are redacted at the boundary that matters.** Set
`living_cutoff_years` and anyone without a death record born inside that
window collapses to a bare `Living` node, their name withheld from every
other node's prose. Crucially this is enforced through `pack()`, not just
in the graph: an earlier design redacted nodes while leaving the original
GEDCOM record reachable, which meant a query could return a redacted person
and then hand back their source record anyway. That gap is closed, and it
is what allows the 97-tree test corpus to include trees whose descent lines
reach living families.

**Three-dimensional family trees.** `genkg viz3d` grows a literal tree --
root and spouses as the trunk, each family a limb, each descendant a leaf
clustered around their birth family -- using space colonization, so the
canopy's shape is the data rather than a decoration applied to it.
`genkg quilt` renders the same scene as a light-field quilt for Looking
Glass hardware.

**Colour chosen for the reader, not the author.** Sex uses Okabe-Ito
blue/orange rather than the obvious blue/rose, which measures fine on a
normal-vision monitor and collapses to a single colour for a protanope.
Generations use a diverging ramp that separates by luminance as well as
hue. Shape carries sex independently of colour, always. The tests simulate
each dichromacy and assert a perceptual-distance floor, so this is checked
rather than asserted.

**A hardening pass, and CI that runs what it claims to.** The living-person
bug above was found by that pass; it also bounded and normalized CLI and
MCP inputs, made resource cleanup deterministic, and set an 80% coverage
floor. CI now installs the 3-D extra and runs under `xvfb`, which turned
six scene tests from silently skipping on every run into tests that
actually execute.

## Upgrading

Nothing to upgrade from -- this is the first release.

```
pip install genealogy-kg
```

The core install stays light. Visualisation is opt-in through extras, and
they are genuinely optional: `[viz]` for the 2-D charts, `[viz3d]` for the
PyVista/Qt viewer and Looking Glass output, `[adapter]` to register the
graph with kg-rag for federated queries. A bare install never imports
plotly, pyvis, pyvista or PyQt5, and a test asserts that rather than
trusting it. Python 3.12 and 3.13.

Start with `genkg build --source <file>.ged`, then `genkg query`,
`genkg ancestors`/`descendants`, or point an MCP client at `genkg-mcp`.
`docs/USAGE.md` has the full command surface and `docs/DESIGN.md` the graph
model.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
