# Release Notes -- v0.2.0

> Released: 2026-09-08

This release fixes `genkg snapshot save` so it actually keys a snapshot on
the version you pass it, and removes a class override the SDK no longer
requires.

## What changed

**Snapshots now resolve to the tag you asked for.** `genkg snapshot save
VERSION` accepted a release tag but never forwarded it, so every snapshot
fell back to whatever the SDK chose instead: a UTC timestamp, or, on this
repo's previous `kgmodule-utils` floor, a git tree hash read before `git
add` staged the snapshot -- a hash that named a tree no commit ever
produced, and so could never be resolved again afterward. `capture_genealogy()`
now takes `key` and `subject` and forwards both, and `snapshot save` gains
a `--subject` flag. Leave `VERSION` off and you still get a timestamp,
which remains the right default for a family tree with no release tag of
its own.

**One less override to maintain.** `SnapshotManager.__init__` is gone.
Its entire body existed to set one string that `kgmodule-utils` 0.20.0 now
exposes as a `package_name` class attribute, so the subclass carries no
code of its own anymore.

**Dependency floors moved up to match.** `kgmodule-utils` now floors on
`>=0.20.0` everywhere it's declared, `doc-kg` on `>=0.26.0`, and `pycode-kg`
on `>=0.27.0` -- the releases where each of those packages retired the same
kind of snapshot override this repo just dropped.

## Upgrading

Reinstall to pick up the new `kgmodule-utils`, `doc-kg`, and `pycode-kg`
floors:

```
pip install --upgrade genealogy-kg
```

If you call `capture_genealogy()` directly rather than through the CLI,
pass `key` and `subject` explicitly -- the previous implicit tree-hash
fallback is gone along with the override that produced it.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
