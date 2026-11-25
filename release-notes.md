# Release Notes -- v0.7.0

> Released: 2026-11-24

A store now notices when its GEDCOM file changes after the build. `pack()`
cuts each snippet from the live file by the line numbers recorded at build, so
an edit that shifts lines, like the submitter scrub in 0.5.0, used to make an
older store quote the wrong records under the right names. With
kgmodule-utils 0.32.0 the build records a hash of each GEDCOM, `pack()` leaves
out the snippets of a file that no longer matches, and `genkg status` says
which files those are.

## What changed

**`genkg status` reports source drift.** A single store's status adds one
line: the GEDCOM files are unchanged since the build, or these files changed
or went missing and the store needs a rebuild, or the store predates the
hashes and a rebuild turns the check on. Redaction is unchanged: it still
scans the current file, in the same line coordinates `pack()` serves.

**Dependencies.** The kgmodule-utils floor is 0.32.0. The lock carries
kgmodule-utils 0.32.0 and kg-rag 0.19.2 for the `adapter` extra, written with
Poetry 2.4.3, and a new test fails if a lock would install two versions of a
package on any platform.

**A new logo.** The Art Techno hourglass: the root person at the center,
ancestors above in copper and descendants below in gold, on the README, PyPI
and the docs site.

## Upgrading

Rebuild your stores with `genkg build` after upgrading. A store built earlier
has no hashes: it packs exactly as before, and `genkg status` says no hashes
are recorded. After a rebuild, editing a GEDCOM without rebuilding leaves its
records out of `pack()` until you do.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
