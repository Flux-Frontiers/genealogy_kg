# Release Notes -- v0.5.0

> Released: 2026-10-27

GenealogyKG now protects living people without being asked to. A build with
nothing configured redacts anyone with no death or burial record born in the
last 100 years, and treats people with no usable birth date the same way.
`pack()` also stops returning the submitter's name, address, phone and email,
which it leaked before even with redaction on. This changes default behavior,
hence the minor version.

## What changed

**Redaction is the default.** An unset `living_cutoff_years` now means 100
years, and `unknown_birth_policy` defaults to `"redact"`. Before, the filter
was off unless configured, and even a configured cutoff kept undated people,
who are about half the people in the curated corpus. Set
`living_cutoff_years = 0` to turn redaction off for a private store.
`export-web` and `export-swift` pick up the same default.

**Submitter records stay out of `pack()`.** Most GEDCOM files carry a `SUBM`
record naming whoever compiled them, often with a home address and email. It
sits just above the first person in the file, inside that person's snippet
padding, so `pack()` returned it. `pack()` now clips it whether or not
redaction is on.

**The committed corpus is scrubbed.** The 97 public trees in
`corpora/entries/` came with their compilers' contact details. The new
`scripts/scrub_submitters.py` cuts each submitter record to
`1 NAME Withheld`; 88 trees are committed scrubbed, `fetch_corpora.sh` scrubs
everything it fetches, and a test fails if a committed tree is not scrubbed.

**Two exposures, documented apart.** The living-person filter governs what
the tool returns. It does nothing for the GEDCOM files in the repository,
which anyone can read. The README's new "What this repository holds" section
and the design docs now say so.

## Upgrading

Rebuild every store. A store built before 0.5.0 keeps its unredacted nodes
until rebuilt, and stores over `corpora/entries/` also return misaligned
`pack()` snippets, because the scrub shifted line numbers:

```bash
genkg corpus ingest --force-build --no-register
```

If you relied on redaction being off, add `living_cutoff_years = 0` under
`[tool.genealogykg]` in `pyproject.toml`. `GedcomExtractor` used directly is
unchanged: it redacts nobody unless given a cutoff.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
