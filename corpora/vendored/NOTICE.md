# Vendored demo GEDCOMs

Three public-domain-era GEDCOM files, tracked in this repo (unlike the rest
of `corpora/`, which `scripts/fetch_corpora.sh` pulls at dev time and never
commits -- see `docs/CORPORA.md`). Used by `make famous-bronte`;
`washington/` and `tudor/` are here as data, without a dedicated Makefile
target yet. `famous-royal` stays fetch-only -- see below.

| File | People | Root xref for `genkg viz3d`/`quilt` |
|---|---|---|
| `bronte/bronte.ged` | 14 | `I0001` (Patrick Bronte) |
| `washington/washington.ged` | 529 | `I3` (Augustine Washington) |
| `tudor/EnglishTudorRoyalFamily.ged` | 347 | `I1` (Henry VII Tudor) |

## Why these three and not the rest of `corpora/`

All three were checked person-by-person for anyone born after 1920 with no
recorded death -- the same test that ruled out `sample-kennedy/kennedy.ged`
(108 of its 208 people, including recognizably living people such as
Caroline Kennedy Schlossberg, b. 1957). Zero hits in all three.

`gedcom-samples/royal/royal92.ged` was vendored here and then removed on
the same check: it is a 1992 snapshot of European royalty and contains
hundreds of people born after 1920 with no death recorded, several of whom
are still alive as of this writing. Its own root person looked safe
(William the Conqueror, d. 1087), but growing his descent line is exactly
what walks down into his living descendants -- the modern British and
European royal families. `famous-royal` (`Makefile`) stays fetch-only via
`scripts/fetch_corpora.sh`, same as `famous-kennedy`.

## Licensing

Source: [D-Jeffrey/gedcom-samples](https://github.com/D-Jeffrey/gedcom-samples),
dual-licensed MIT (`LICENSE`) / CC0 1.0 (`LICENSE-CC0`) by its curator. Per
that repo's own README, the underlying genealogical data was compiled by
other authors and published on the open internet without separately stated
terms -- the curator licenses the compilation, not a claim over the
original authors' work. Vendored here on that basis, same as
`fetch_corpora.sh` already reasons for the files it fetches instead of
vendoring.
