# corpora/entries/

Per-entry GEDCOM test data, one directory per tree: `<genre>/<slug>/<file>.ged`
plus that entry's own `.genealogykg/` build store (gitignored, regenerable
with `genkg build --repo corpora/entries/<genre>/<slug>`).

Source: [D-Jeffrey/gedcom-samples](https://github.com/D-Jeffrey/gedcom-samples),
dual-licensed MIT (`LICENSE`) / CC0 1.0 (`LICENSE-CC0`) by its curator, plus
the Gramps and GEDitCOM 5.5 torture-test samples pulled by
`scripts/fetch_corpora.sh`. Per that repo's own README, the underlying
genealogical data was compiled by other authors and published on the open
internet without separately stated terms -- the curator licenses the
compilation, not a claim over the original authors' work.

This directory previously held only three trees (`bronte`, `washington`,
`tudor`) that had been checked person-by-person for living-person exposure
before this was written -- see `docs/CODEBASE_REVIEW.md` item 1, "Close the
living-person privacy gap": redaction now happens at the query/pack/MCP
boundary (`GedcomExtractor.is_living()`, enforced through `pack()`) rather
than depending on curating which source files are allowed into the repo.
That is the current safety boundary for this directory's broader scope.
