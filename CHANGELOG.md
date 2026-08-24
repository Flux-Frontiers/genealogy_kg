# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repository skeleton per fleet conventions: Poetry/PEP 621 packaging with
  `dev` and `kg` groups, ruff/ty/pytest/detect-secrets pre-commit chain, CI
  with a wheel smoke test, tag-driven release workflow with PyPI trusted
  publishing.
- `docs/DESIGN.md`: graph model, temporal mapping, package layout and the
  phased plan.
- `tests/fixtures/sample.ged`: a fictional three-generation GEDCOM 5.5.1
  family exercising `ABT`, `BEF`, `AFT` and `BET ... AND` dates, `CONT`/`CONC`
  notes, hierarchical places and source citations.
- Source modules with their public signatures; bodies raise
  `NotImplementedError` until Phase 1.
- `scripts/fetch_corpora.sh` and `docs/CORPORA.md`: public GEDCOM test
  corpora (D-Jeffrey/gedcom-samples, the GEDitCOM torture test, the Gramps
  sample) fetched into the gitignored `corpora/`, with provenance, licence
  and a parse survey (105 of 108 files read by ged4py 0.5.2).
