# Release Notes -- v0.2.1

> Released: 2026-09-18

Casting a family tree to the Looking Glass now sweeps a 35-degree view cone instead of the panel's full cone.

## What changed

**Cast to Looking Glass fuses cleanly.** The `kgmodule-utils` floor moves to 0.22.0, which routes Cast to Looking Glass through `quiltwright.quilt.resolve_view_cone`. The 16" landscape preset's native cone is 50 degrees -- wider than reliably fuses -- so a family tree's limbs previously ghosted where a quilt rendered by `genkg quilt` itself held. No code in this repo changed; the fix arrives through the shared `cast_scene_to_looking_glass` helper. The `quiltwright` pin moves to 0.14.1 alongside it, which the extra already required transitively.

## Upgrading

`poetry update kgmodule-utils quiltwright` (or `pip install -U kgmodule-utils quiltwright`). No config or API changes.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
