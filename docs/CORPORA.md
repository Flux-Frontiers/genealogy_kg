# Test corpora

No real family export exists for this project, and one would be personal
data anyway. Development and testing run against public GEDCOM files fetched
by `scripts/fetch_corpora.sh` into `corpora/`, which is gitignored. The only
GEDCOMs tracked in this repo are the fictional `tests/fixtures/sample.ged`
and the three public-domain-era historical trees under `corpora/vendored/`
(below) -- everything else in `corpora/` is fetched, never committed.

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

Three files in the collection do not parse, and none is worth fixing:

- `US presidents/GeorgeWashington+Family+Small.ged`: truncated header
- `fictional characters/Lord+of+the+Rings+Family+Tree.ged`: stray blank
  line at 1108
- `religious figures and systems/Wikipedia+Gods+not+Yet+Connected.ged`:
  byte `0x85` under a charset that cannot hold it

Many files declare `CHAR ANSI`, `IBMPC` or `IBM WINDOWS`, none of which the
standard allows. ged4py warns once per file and reads them as cp1252 or
cp437. The extractor should surface that warning in `build` output rather
than hide it.

## Vendored famous-tree demos

`corpora/vendored/` is tracked, not fetched -- see
`corpora/vendored/NOTICE.md` for the licensing basis, the person-by-person
living-check every file here passed, and why `royal92.ged` was vendored and
then removed on that same check (its own root looks historical, but growing
his descent line walks straight into the living modern royal families).
Used by `make famous-bronte`; `washington/` and `tudor/` have no dedicated
target yet. `make famous-royal` stays fetch-only.

| File | People | Root xref |
|---|---|---|
| `corpora/vendored/bronte/bronte.ged` | 14 | `I0001` |
| `corpora/vendored/washington/washington.ged` | 529 | `I3` |
| `corpora/vendored/tudor/EnglishTudorRoyalFamily.ged` | 347 | `I1` |

## Licensing

- **D-Jeffrey/gedcom-samples** is dual-licensed MIT / CC0 1.0 by its
  curator. The files' original authors (Denis R. Reid for royal92, Paul E.
  Stobbe for pres2020, and others) published them on the open internet
  without stated terms.
- **The torture test** (H. Eichmann 1997, modified by J. A. Nairn
  1999-2001): "Feel free to copy and use this GEDCOM file for any
  non-commercial purpose." Fetched, never vendored, never shipped in a
  wheel or a test fixture.
- **Gramps `sample.ged`** lives in a GPL-2.0 repository. It is data, not
  code, and is used here as test input only.

None of these files may be added to the repository, with the sole exception
of the three vendored under `corpora/vendored/` (above), each checked
person-by-person for anyone born after 1920 with no recorded death.
`*.ged` is gitignored outside `tests/fixtures/` and `corpora/vendored/`, and
the rest of `corpora/` is gitignored whole.

## Refreshing

```bash
./scripts/fetch_corpora.sh     # idempotent; pulls the clone, skips existing downloads
```
