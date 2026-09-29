# Release Notes -- v0.2.2

> Released: 2026-09-29

This release moves input validation into the shared SDK and raises the fleet dependency floors to the latest releases. Query and pack inputs are checked more strictly than before; nothing else changes for users.

## What changed

**Validation comes from kgmodule-utils.** `bounded_int` and `require_query` were this package's own reference implementations, and kgmodule-utils has taken both over. `query()` and `pack()` no longer validate themselves. The base class does, against limits this package sets as class attributes. The overrides that remain exist only for the genealogy edge defaults and living-person redaction. The SDK's integer check is stricter: a bool, a non-integral float or a string for `k`, `hop` or `max_nodes` now raises `ValueError`, where the old copy let `True` and `2.5` through and failed on `"5"` with a raw `TypeError`.

**Redundant workarounds removed.** The `__enter__` override existed only to keep the `GenealogyKG` type across a `with` block. kgmodule-utils 0.23.0 returns `Self`, so it is gone and `ty` stays clean.

**Dependency floors.** `kgmodule-utils` is now `>=0.26.0`, `quiltwright` `>=0.16.0` and `kg-rag` `>=0.17.0`, with the lock refreshed. The `mcp` floor is `>=1.3.0`, the first release whose `FastMCP` accepts the `instructions=` and `lifespan=` arguments `genkg-mcp` passes. The repo-tooling `kg` Poetry group is retired, since `doc-kg` and `pycode-kg` are installed as global tools.

## Upgrading

`pip install -U genealogy-kg`. If your code passes non-integer values for `k`, `hop` or `max_nodes`, expect a `ValueError`. No config or graph rebuild is needed.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
