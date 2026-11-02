# Release Notes -- v0.6.0

> Released: 2026-11-02

GenealogyKG can now plant a family that has no surnames. `export-web` used
to put everyone without a surname on one line called `unknown`, so a
biblical genealogy, which records given names only, came out as a single
grove-less heap. It now cuts that remainder into houses, each named for its
head, and the orchard has groves again. GenealogyKG also has a
documentation site, and is now marked Beta.

## What changed

**Houses for the surname-less.** A house is named for its head: the father,
or with no father recorded the mother, of at least three children. It holds
their descent, father first, down to the next head. Families with surnames
export exactly as before, so an existing orchard does not move.

**A documentation site.** The guides under `docs/` are published at
https://flux-frontiers.github.io/genealogy_kg/, built with mkdocs-material.
Pull requests build it with `--strict`, and main deploys it to GitHub Pages.
`make docs-serve` previews it locally.

**Beta.** The PyPI classifier is now `4 - Beta`, and the README's status note
says only what works today.

**Security.** The `viz3d` extra floors quiltwright at 0.17.0, the first
quiltwright that floors Pillow at 13.0.0, so the extra cannot pull in the
vulnerable 12.x line. The lock moves Pillow, Streamlit, certifi, filelock,
setuptools and virtualenv to patched releases.

## Upgrading

`pip install -U genealogy-kg`. Re-run `genkg export-web` on a surname-less
file to get its houses; files with surnames need nothing.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
