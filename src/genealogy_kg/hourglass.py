"""genealogy_kg/hourglass.py

The hourglass family tree: one person's whole kinship line as a literal
tree. The focal person and their spouse(s) are the trunk at ground level.
Ancestors are the roots: parents one tier down, grandparents two, doubling
each generation, the oldest deepest. Descendants are the canopy: children
one tier up, grandchildren two, spread by fecundity. Every limb is a
kinship edge: a child's wood branches from its parent, a parent's root from
its child, so the wood *is* the family and not a decoration grown near it.

This is the layout half, pure NumPy, no PyVista import. The result is a
wood graph -- points and a parent index per point -- that
:func:`genealogy_kg.scene.build_family_tree_scene` sweeps into a mesh
(organic) or draws as straight tubes (schematic).

Layout rules:

* **Tiers.** Generation ``g`` from the focal person sits at height
  ``g * TIER_UP`` above the trunk top for descendants and ``-g * TIER_DOWN``
  below ground for ancestors.
* **Rings.** Each tier is a ring whose radius grows with generation, floored
  so the people on it stay at least :data:`MIN_LEAF_ARC` apart: a fecund
  generation spreads wider on its own.
* **Wedges.** The canopy is a radial tidy tree: a person's angular wedge is
  split among their families, and a family's among its children, in
  proportion to how many descendants each carries. The roots are a fan
  chart: a person's wedge is halved between their two parents.
* **Spouses share the fork.** A married-in spouse hangs as a short twig off
  the blood relative's node; the children branch from the same node.

Both halves are depth-capped: :data:`DEFAULT_ANCESTOR_GENERATIONS` below
ground and :data:`DEFAULT_DESCENDANT_GENERATIONS` above, unless the caller
passes other caps or ``None`` for no cap.

Pedigree collapse (an ancestor reachable by two paths, as when cousins
marry) places the person once, on the first path found; the second edge is
counted in ``skipped_edges`` and not drawn, since a skeleton node has one
parent.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Final

import numpy as np
from kg_utils.store import GraphStore
from kg_utils.viz3d import seed_from_key

#: Height of the trunk, from the ground plane to the focal couple's fork.
TRUNK_HEIGHT: Final[float] = 3.0

#: Vertical rise per descendant generation, world units.
TIER_UP: Final[float] = 2.0

#: Vertical drop per ancestor generation. Roots are shallower than the
#: canopy is tall, as real roots are.
TIER_DOWN: Final[float] = 1.5

#: Radial reach per generation before the crowding floor below.
RING: Final[float] = 2.0

#: Minimum arc between two people on the same ring. A tier with many people
#: widens until they fit.
MIN_LEAF_ARC: Final[float] = 0.9

#: How far a married-in spouse's twig reaches from the fork.
SPOUSE_REACH: Final[float] = 0.55

#: Intermediate wood nodes inserted per kinship edge in organic mode, so a
#: limb curves instead of running straight.
EDGE_SUBDIVISIONS: Final[int] = 3

#: Sideways jitter on those intermediate nodes, as a fraction of edge length.
EDGE_JITTER: Final[float] = 0.08

#: Default generation caps, as the pedigree and ASCII views cap theirs. A
#: file that traces one line back to legendary kings (royal92 runs 70
#: generations above Victoria) otherwise draws a long single-file chain
#: that dwarfs everything else.
DEFAULT_ANCESTOR_GENERATIONS: Final[int] = 5
DEFAULT_DESCENDANT_GENERATIONS: Final[int] = 4

#: Population at which the ring and tier spacing are exactly the defaults;
#: see :func:`genealogy_kg.scene._population_size_scale` for the idea.
SIZE_REFERENCE_POPULATION: Final[int] = 200
MIN_SIZE_SCALE: Final[float] = 0.6
MAX_SIZE_SCALE: Final[float] = 2.0


@dataclass
class HourglassPositions:
    """Pure-geometry result of :func:`hourglass_positions`.

    :param person_positions: Every placed person's position.
    :param generation: Each placed person's signed generation offset from
        the focal person: ancestors negative, descendants positive, spouses
        their partner's.
    :param wood_points: ``(N, 3)`` wood graph nodes. Index 0 is the ground
        point at the trunk base; index 1 is the focal person at the trunk
        top. Every parent index is lower than its child's, as
        ``kg_utils.viz3d.pipe_radii`` requires.
    :param wood_parents: ``(N,)`` parent index per wood node, ``-1`` for the
        ground point.
    :param wood_person: Person node id per wood node, or ``None`` for the
        ground point.
    :param root_id: The focal person's node id.
    :param trunk_height: Height of the trunk, world units.
    :param size_scale: Population-based spacing multiplier applied.
    :param skipped_edges: Kinship edges not drawn because their target was
        already placed by another path (pedigree collapse).
    :param n_ancestors: Ancestors placed (not counting the focal person).
    :param n_descendants: Descendants and married-in spouses placed.
    """

    person_positions: dict[str, np.ndarray]
    generation: dict[str, int]
    wood_points: np.ndarray
    wood_parents: np.ndarray
    wood_person: list[str | None]
    root_id: str
    trunk_height: float
    size_scale: float = 1.0
    skipped_edges: int = 0
    n_ancestors: int = 0
    n_descendants: int = 0
    # Kept for parity with FamilyTreePositions: scene.py's schematic and
    # framing code reads a family-tip dict. The hourglass has no separate
    # family tips, so this is empty.
    family_positions: dict[str, np.ndarray] = field(default_factory=dict)


def _size_scale(population: int) -> float:
    """Spacing multiplier: wider for small families, tighter for huge ones.

    :param population: Number of people placed.
    :return: Multiplier clamped to ``[MIN_SIZE_SCALE, MAX_SIZE_SCALE]``.
    """
    raw = math.sqrt(SIZE_REFERENCE_POPULATION / max(population, 1))
    return min(max(raw, MIN_SIZE_SCALE), MAX_SIZE_SCALE)


def _spouses(store: GraphStore, family_id: str) -> list[str]:
    return [s["id"] for s in store.callers_of(family_id, rel="SPOUSE_IN")]


def _children(store: GraphStore, family_id: str) -> list[str]:
    return [c["id"] for c in store.callers_of(family_id, rel="CHILD_IN")]


def _families_of(store: GraphStore, person_id: str) -> list[str]:
    return [e["dst"] for e in store.edges_from(person_id, rel="SPOUSE_IN")]


def _birth_families_of(store: GraphStore, person_id: str) -> list[str]:
    return [e["dst"] for e in store.edges_from(person_id, rel="CHILD_IN")]


def _sort_key(store: GraphStore, node_id: str) -> tuple[str, str]:
    """Order siblings by birth year and families by marriage year, then id."""
    node = store.node(node_id) or {}
    return (str((node.get("metadata") or {}).get("occurred_start") or ""), node_id)


class _Builder:
    """Accumulates the wood graph in parent-before-child order."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store
        self.points: list[np.ndarray] = []
        self.parents: list[int] = []
        self.person: list[str | None] = []
        self.positions: dict[str, np.ndarray] = {}
        self.generation: dict[str, int] = {}
        self.skipped = 0

    def add(self, point: np.ndarray, parent: int, person_id: str | None) -> int:
        index = len(self.points)
        self.points.append(np.asarray(point, dtype=float))
        self.parents.append(parent)
        self.person.append(person_id)
        if person_id is not None:
            self.positions[person_id] = self.points[-1]
        return index


def _descendant_weight(
    store: GraphStore,
    person_id: str,
    seen: set[str],
    cache: dict[tuple[str, float], int],
    depth: float,
) -> int:
    """Number of people drawn in ``person_id``'s descent, counting themselves.

    :param store: The graph store.
    :param person_id: Person node id.
    :param seen: Persons already on the current path, to cut cycles.
    :param cache: Memo of finished weights, keyed by person and depth.
    :param depth: Generations still drawn below ``person_id``.
    :return: Weight for wedge allocation, at least 1.
    """
    key = (person_id, depth)
    if key in cache:
        return cache[key]
    if person_id in seen:
        return 1
    seen.add(person_id)
    total = 1
    for family_id in _families_of(store, person_id):
        total += 1  # the spouse's twig takes a little room too
        if depth >= 1:
            for child_id in _children(store, family_id):
                total += _descendant_weight(store, child_id, seen, cache, depth - 1)
    seen.discard(person_id)
    cache[key] = total
    return total


def _tier_counts_canopy(store: GraphStore, root_id: str, max_gen: float) -> dict[int, int]:
    """People per descendant generation, including married-in spouses."""
    counts: dict[int, int] = {}
    seen = {root_id}
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])
    while queue:
        pid, gen = queue.popleft()
        counts[gen] = counts.get(gen, 0) + 1
        for family_id in _families_of(store, pid):
            for spouse in _spouses(store, family_id):
                if spouse not in seen:
                    seen.add(spouse)
                    counts[gen] = counts.get(gen, 0) + 1
            if gen + 1 > max_gen:
                continue
            for child in _children(store, family_id):
                if child not in seen:
                    seen.add(child)
                    queue.append((child, gen + 1))
    return counts


def _tier_counts_roots(store: GraphStore, root_id: str, max_gen: float) -> dict[int, int]:
    """People per ancestor generation (positive keys: 1 = parents)."""
    counts: dict[int, int] = {}
    seen = {root_id}
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])
    while queue:
        pid, gen = queue.popleft()
        if gen + 1 > max_gen:
            continue
        for family_id in _birth_families_of(store, pid):
            for parent in _spouses(store, family_id):
                if parent not in seen:
                    seen.add(parent)
                    counts[gen + 1] = counts.get(gen + 1, 0) + 1
                    queue.append((parent, gen + 1))
    return counts


def _ring_radius(tier: int, count: int, scale: float) -> float:
    """Radius of a tier's ring: by generation, floored by crowding."""
    by_generation = tier * RING * scale
    by_crowding = count * MIN_LEAF_ARC * scale / (2.0 * math.pi)
    return max(by_generation, by_crowding)


def _polar(radius: float, angle: float, z: float) -> np.ndarray:
    return np.array([radius * math.cos(angle), radius * math.sin(angle), z])


def hourglass_positions(
    store: GraphStore,
    xref: str,
    *,
    max_ancestors: int | None = DEFAULT_ANCESTOR_GENERATIONS,
    max_descendants: int | None = DEFAULT_DESCENDANT_GENERATIONS,
) -> HourglassPositions:
    """Place the focal person's ancestors as roots and descendants as canopy.

    :param store: The graph store.
    :param xref: Individual xref without ``@``, such as ``I1``. The focal
        person: trunk top, ground plane at their generation.
    :param max_ancestors: Ancestor generations drawn below ground (1 is
        parents only), or ``None`` for every recorded generation.
    :param max_descendants: Descendant generations drawn above the trunk (1
        is children only), or ``None`` for all. Spouses of the last drawn
        generation are still drawn; their children are not.
    :return: Positions and the wood graph.
    :raises ValueError: If ``xref`` is not a known person, a cap is
        negative, or there is no relative within the caps to grow toward.
    """
    root_id = f"person:{xref}"
    if store.node(root_id) is None:
        raise ValueError(f"no such person: {root_id}")
    for name, cap in (("max_ancestors", max_ancestors), ("max_descendants", max_descendants)):
        if cap is not None and cap < 0:
            raise ValueError(f"{name} must be >= 0 or None, got {cap}")
    up: float = math.inf if max_ancestors is None else max_ancestors
    down: float = math.inf if max_descendants is None else max_descendants

    canopy_counts = _tier_counts_canopy(store, root_id, down)
    root_counts = _tier_counts_roots(store, root_id, up)
    population = sum(canopy_counts.values()) + sum(root_counts.values())
    if population <= 1:
        raise ValueError(f"{root_id} has no parents, spouses or children to grow toward")
    scale = _size_scale(population)
    trunk_height = TRUNK_HEIGHT * scale
    tier_up = TIER_UP * scale
    tier_down = TIER_DOWN * scale

    b = _Builder(store)
    ground = b.add(np.zeros(3), -1, None)
    focal = b.add(np.array([0.0, 0.0, trunk_height]), ground, root_id)
    b.generation[root_id] = 0
    weights: dict[tuple[str, float], int] = {}

    # --- canopy: radial tidy tree, wedges by descendant weight ---------------
    def place_canopy(person_id: str, node: int, gen: int, a: float, span: float) -> None:
        families = sorted(_families_of(store, person_id), key=lambda f: _sort_key(store, f))
        if not families:
            return
        below = down - gen - 1  # generations still drawn below a child
        fam_weights = []
        for family_id in families:
            w = 1
            if below >= 0:
                for child in _children(store, family_id):
                    w += _descendant_weight(store, child, set(), weights, below)
            fam_weights.append(w)
        total = sum(fam_weights)
        cursor = a
        here = b.points[node]
        for family_id, w in zip(families, fam_weights, strict=True):
            fam_span = span * w / total
            mid = cursor + fam_span / 2.0
            for spouse in _spouses(store, family_id):
                if spouse == person_id or spouse in b.positions:
                    if spouse != person_id:
                        b.skipped += 1
                    continue
                twig = (
                    here
                    + _polar(SPOUSE_REACH * scale, mid, 0.0)
                    + np.array([0.0, 0.0, 0.25 * scale])
                )
                b.add(twig, node, spouse)
                b.generation[spouse] = gen
            if below < 0:
                cursor += fam_span
                continue
            children = sorted(
                (c for c in _children(store, family_id)),
                key=lambda c: _sort_key(store, c),
            )
            child_weights = [_descendant_weight(store, c, set(), weights, below) for c in children]
            child_total = sum(child_weights) or 1
            child_cursor = cursor
            radius = _ring_radius(gen + 1, canopy_counts.get(gen + 1, 1), scale)
            z = trunk_height + (gen + 1) * tier_up
            for child, cw in zip(children, child_weights, strict=True):
                child_span = fam_span * cw / child_total
                angle = child_cursor + child_span / 2.0
                child_cursor += child_span
                if child in b.positions:
                    b.skipped += 1
                    continue
                child_node = b.add(_polar(radius, angle, z), node, child)
                b.generation[child] = gen + 1
                place_canopy(child, child_node, gen + 1, angle - child_span / 2.0, child_span)
            cursor += fam_span

    place_canopy(root_id, focal, 0, 0.0, 2.0 * math.pi)
    n_descendants = len(b.positions) - 1

    # --- roots: fan chart, wedge halved between the two parents --------------
    def place_roots(person_id: str, node: int, depth: int, a: float, span: float) -> None:
        if depth + 1 > up:
            return
        parents: list[str] = []
        for family_id in _birth_families_of(store, person_id):
            for parent in _spouses(store, family_id):
                if parent not in parents:
                    parents.append(parent)
        if not parents:
            return
        radius = _ring_radius(depth + 1, root_counts.get(depth + 1, 1), scale)
        z = -(depth + 1) * tier_down
        part = span / len(parents)
        for i, parent in enumerate(parents):
            angle = a + part * (i + 0.5)
            if parent in b.positions:
                b.skipped += 1
                continue
            parent_node = b.add(_polar(radius, angle, z), node, parent)
            b.generation[parent] = -(depth + 1)
            place_roots(parent, parent_node, depth + 1, a + part * i, part)

    # Roots hang from the ground point, not the focal node: the trunk runs
    # between them, and the two halves meet at the ground plane.
    place_roots(root_id, ground, 0, 0.0, 2.0 * math.pi)
    n_ancestors = len(b.positions) - 1 - n_descendants

    return HourglassPositions(
        person_positions=b.positions,
        generation=b.generation,
        wood_points=np.vstack(b.points),
        wood_parents=np.asarray(b.parents, dtype=int),
        wood_person=b.person,
        root_id=root_id,
        trunk_height=trunk_height,
        size_scale=scale,
        skipped_edges=b.skipped,
        n_ancestors=n_ancestors,
        n_descendants=n_descendants,
    )


def curved_wood(
    positions: HourglassPositions,
    *,
    key: str = "",
    subdivisions: int = EDGE_SUBDIVISIONS,
    jitter: float = EDGE_JITTER,
) -> tuple[np.ndarray, np.ndarray]:
    """Insert curved intermediate nodes on every kinship edge.

    Each edge from parent ``P`` to child ``C`` becomes a quadratic curve whose
    control point is above (canopy) or below (roots) ``P`` at ``C``'s height:
    the limb leaves its parent along the trunk's direction and then reaches
    out, which is how wood looks. A little seeded sideways jitter keeps two
    siblings' limbs from being mirror images.

    Parent-before-child order is preserved, so the result goes straight to
    ``kg_utils.viz3d.pipe_radii``.

    :param positions: Layout from :func:`hourglass_positions`.
    :param key: Seed key for the jitter.
    :param subdivisions: Intermediate nodes per edge.
    :param jitter: Sideways offset as a fraction of the edge length.
    :return: ``(points (N, 3), parents (N,))``.
    """
    rng = np.random.default_rng(seed_from_key(f"{key}:wood"))
    src_points = positions.wood_points
    src_parents = positions.wood_parents
    out_points: list[np.ndarray] = []
    out_parents: list[int] = []
    index_map: dict[int, int] = {}

    for i in range(src_points.shape[0]):
        p = int(src_parents[i])
        if p < 0:
            index_map[i] = len(out_points)
            out_points.append(src_points[i])
            out_parents.append(-1)
            continue
        start = src_points[p]
        end = src_points[i]
        control = np.array([start[0], start[1], end[2]])
        delta = end - start
        length = float(np.linalg.norm(delta))
        side = np.cross(delta, [0.0, 0.0, 1.0])
        side_norm = float(np.linalg.norm(side))
        side = side / side_norm if side_norm > 1e-9 else np.zeros(3)
        last = index_map[p]
        for k in range(1, subdivisions + 1):
            t = k / (subdivisions + 1)
            point = (1 - t) ** 2 * start + 2 * (1 - t) * t * control + t**2 * end
            point = point + side * (rng.normal() * jitter * length * math.sin(math.pi * t))
            out_parents.append(last)
            last = len(out_points)
            out_points.append(point)
        index_map[i] = len(out_points)
        out_points.append(end)
        out_parents.append(last)

    return np.vstack(out_points), np.asarray(out_parents, dtype=int)


__all__ = ["HourglassPositions", "curved_wood", "hourglass_positions"]
