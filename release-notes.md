# Release Notes -- v0.3.0

> Released: 2026-10-23

This release changes how GenealogyKG draws a family in 3-D, and adds two
exports that hand a family to The Knowledge Press: The Family, the edition of
the Knowledge Press apps that reads a GenealogyKG store. Both exports enforce
the living-person filter rather than trust it.

## What changed

**The hourglass family tree.** `genkg quilt` and `genkg viz3d` now draw a
person's whole kinship line by default. The person and their spouse(s) are the
trunk at ground level. Ancestors are the roots below the ground, doubling each
generation, and descendants are the canopy above. Every limb is a kinship edge:
a child's wood branches from its parent and a parent's root from its child, so
the wood is the family rather than decoration grown near it. `--ancestors` and
`--descendants` cap the generations drawn (5 and 4 by default), because a file
that traces one line back to legendary kings otherwise draws a long
single-file chain. `--shape canopy` keeps the previous descent-only tree.

**`genkg export-web`.** Writes the web orchard's data: a catalog of every
family line, person, family, cross-line marriage and place, and one page per
person with their events, relatives and GEDCOM record lines. A line is a
surname by birth, joined by descent, so every person belongs to exactly one,
and a marriage between two lines becomes a link between their trees.

**`genkg export-swift`.** Writes the family app's on-device search pack: one
passage per person, family, event, place and source, the store's own vectors
re-encoded for the device, a manifest and golden reference rankings. The format
comes from the new `kg_utils.devicepack` in kgmodule-utils 0.28.0, shared with
gutenberg_kg's book packs.

**Privacy that does not trust the store.** Each export re-reads the GEDCOM
under its own living-person cutoff and refuses a store that was not redacted to
match. After writing, it scans its own output for living people's names and
refuses again on a hit, naming the record to fix, so a note in a dead
relative's record that names a living child stops the export instead of
shipping. Nothing is written when an export refuses.

## Upgrading

Install 0.3.0; it requires kgmodule-utils 0.28.0. No rebuild is needed for
search or lineage. To use the exports, set `living_cutoff_years` (and
preferably `unknown_birth_policy = "redact"`) and rebuild, or pass
`--include-living` for a private copy. Scripts that relied on the descent-only
3-D tree should pass `--shape canopy`; the library's
`build_family_tree_scene` still defaults to it.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
