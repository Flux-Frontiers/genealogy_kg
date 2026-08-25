# Test corpora

No real family export exists for this project, and one would be personal
data anyway. Development and testing run against public GEDCOM files fetched
by `scripts/fetch_corpora.sh` into `corpora/`, which is gitignored except for
`corpora/entries/`. The only GEDCOMs tracked in this repo are the fictional
`tests/fixtures/sample.ged` and the 97 public-domain-era trees under
`corpora/entries/` (below) -- everything else in `corpora/` is fetched,
never committed.

Surveyed 2026-08-23 with ged4py 0.5.2: 108 files fetched, 105 parse.

## The development set

Use these, in this order, as Phase 1 grows:

| File | People | Families | GEDCOM | Charset | Exercises |
|---|---|---|---|---|---|
| `tests/fixtures/sample.ged` | 12 | 4 | 5.5.1 | UTF-8 | unit tests; every date qualifier; tracked |
| `corpora/gedcom-samples/bronte.ged` | 14 | 4 | 5.5 | UTF-8 | smallest real file; a recognisable family |
| `corpora/gedcom-samples/shakespeare.ged` | 31 | 11 | 5.5.1 | UTF-8 | |
| `corpora/gramps/sample.ged` | 42 | 15 | 5.5 | UTF-8 | Gramps export dialect; 4 sources |
| `corpora/torture/TGC551LF.ged` | 15 | 7 | 5.5 | ANSEL | every tag 5.5 allows; RESN privacy flags; multimedia links; accented ANSEL; CR+LF |
| `corpora/torture/TGC551.ged` | 15 | 7 | 5.5 | ANSEL | same, CR-only line endings |
| `corpora/gedcom-samples/sample-kennedy/kennedy.ged` | 208 | 75 | 5.5.1 | UTF-8 | Ancestris export; 20th-century dates |
| `corpora/gedcom-samples/royal/royal92.ged` | 3,010 | 1,422 | none declared | ANSEL | the classic 1992 PAF file; no `GEDC` header; deep ancestry to 534 |
| `corpora/gedcom-samples/pres/pres2020.ged` | 2,322 | 1,115 | 5.5.1 | UTF-8 + BOM | Family Tree Maker export; 91 sources; the federation demo corpus |
| `corpora/gedcom-samples/queen/Queen.ged` | 4,683 | 2,863 | 5.5.1 | UTF-8 | RootsMagic; dates back to "4004 BC", a temporal edge case |

## The scale ladder

For build-time and query benchmarks once Phase 1 works:

| File | People | Size | ged4py read |
|---|---|---|---|
| `gedcom-samples/washington/washington.ged` | 529 | 140 KB | 0.1 s |
| `gedcom-samples/ivar/IvarKingOfDublin.ged` | 1,288 | 270 KB | 0.1 s |
| `gedcom-samples/pres/pres2020.ged` | 2,322 | 1.1 MB | 0.3 s |
| `gedcom-samples/habs/Habsburg.ged` | 34,020 | 9.9 MB | 3.8 s |
| `gedcom-samples/longsword/WilliamLongsword.ged` | 203,154 | 48 MB | 17.8 s |

Longsword is the Phase 3 target: 200k person nodes plus events and places
is roughly a million nodes, which is where the embedding pass, not the
parse, sets the build time.

## What else is in `gedcom-samples/`

The `famous family trees/` directory mirrors the SourceForge "Famous Family
Trees" collection: 88 small files covering dynasties (Tudor, Habsburg, Han,
Ming, Ptolemaic), religious lineages, fictional families (Harry Potter,
Tolkien, the Simpsons) and some that are not genealogy at all (corporate
histories, language families, Windows versions, DNA haplogroups). The
non-genealogical ones are a cheap way to check that nothing in the extractor
assumes people are human.

Three files in the collection did not originally parse:

- `fictional characters/Lord+of+the+Rings+Family+Tree.ged`: a stray blank
  line after `0 TRLR` at 1108, which ged4py's strict grammar rejected as
  invalid syntax. Fixed: `GedcomFile` now trims trailing blank lines from
  the copy it hands ged4py (`gedcom._trim_trailing_blank_lines`), without
  shifting any real record's byte offset, so `spans()`'s line numbers (read
  from the untouched file on disk) are unaffected. Committed at
  `corpora/entries/fictional-characters/lord-of-the-rings-family-tree/`.
- `US presidents/GeorgeWashington+Family+Small.ged`: not a truncated
  header -- the file is, byte for byte, a saved HTML error page (a Google
  Groups page, not a GEDCOM export), and upstream `D-Jeffrey/gedcom-samples`
  carries the identical broken content, confirmed by diff against its
  `main` branch. Not fixable by re-fetching from the documented source;
  dropped from `corpora/entries/us-presidents/`.
- `religious figures and systems/Wikipedia+Gods+not+Yet+Connected.ged`:
  byte `0x85` under a charset that cannot hold it. Not committed to
  `corpora/entries/`; still unresolved.

Many files declare `CHAR ANSI`, `IBMPC` or `IBM WINDOWS`, none of which the
standard allows. ged4py warns once per file and reads them as cp1252 or
cp437. The extractor should surface that warning in `build` output rather
than hide it.

## The curated corpus: `corpora/entries/`

`corpora/entries/<genre>/<slug>/` is tracked, not fetched -- see
[corpora/entries/NOTICE.md](../corpora/entries/NOTICE.md). It supersedes
what used to be a hand-picked `corpora/vendored/` of three trees
(`bronte`, `washington`, `tudor`), each checked person-by-person for
living-person exposure before being let in. That approach hit its limit at
`royal92.ged`: its own root (William the Conqueror, d. 1087) looks
historical, but his descent line walks straight into the living modern
European royal families -- vendored, then removed on that same check.

The safety boundary is now the living-person filter itself, enforced at
the query/pack/MCP boundary (`GedcomExtractor.is_living()`, through
`pack()`) rather than which files are let into the repo. That's what let
the corpus grow to its current 97 trees across 10 genres -- `royal92.ged`
included, per the table below -- without re-doing a person-by-person audit
of each one. `genkg corpus survey`/`ingest` (see the main
[README](../README.md#the-curated-corpus)) build and register them; the
three originally-vendored trees are still in here, at new paths:

| File | People | Root xref |
|---|---|---|
| `corpora/entries/samples/bronte/bronte.ged` | 14 | `I0001` |
| `corpora/entries/us-presidents/washington/washington.ged` | 529 | `I3` |
| `corpora/entries/royalty/tudor/EnglishTudorRoyalFamily.ged` | 347 | `I1` |
| `corpora/entries/royalty/royal92-famous-european-royalty-gedcom/*.ged` | 3,010 | -- |

## Licensing

- **D-Jeffrey/gedcom-samples** is dual-licensed MIT / CC0 1.0 by its
  curator. The files' original authors (Denis R. Reid for royal92, Paul E.
  Stobbe for pres2020, and others) published them on the open internet
  without stated terms.
- **The torture test** (H. Eichmann 1997, modified by J. A. Nairn
  1999-2001): "Feel free to copy and use this GEDCOM file for any
  non-commercial purpose." Now committed under `corpora/entries/torture/`
  (its four variants exercise every 5.5 tag, ANSEL, and both line-ending
  conventions -- see the development-set table above).
- **Gramps `sample.ged`** lives in a GPL-2.0 repository. It is data, not
  code, and is used here as test input only, and is not committed.

Only the D-Jeffrey/gedcom-samples-derived and torture-test files under
`corpora/entries/` (above) are committed to the repository -- royal92
included, under the query/pack/MCP-boundary safety model, not a
person-by-person exclusion list.
`*.ged` is gitignored outside `tests/fixtures/` and `corpora/entries/`, and
the rest of `corpora/` is gitignored whole.

## Refreshing

```bash
./scripts/fetch_corpora.sh     # idempotent; pulls the clone, skips existing downloads
```
