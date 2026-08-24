"""genealogy_kg/scene.py

Grows a family's descent line as a real 3-D tree via the fleet's shared
space-colonization engine (``kg_utils.viz3d.organic``): the root person plus
their spouse(s) at the base, each family they or their descendants founded as
a limb, each descendant a leaf clustered around their birth family's limb tip.

Split the way ``pycode_kg.scene3d`` splits its own layout from composition,
so most of this is testable without PyVista installed:

* :func:`family_tree_positions` is pure NumPy -- the attractor points a tree
  grows toward, and where each person ends up. No PyVista import.
* :func:`build_family_tree_scene` composes those attractors through
  ``grow_tree`` / ``tree_mesh`` / ``leaf_glyphs`` into a caller-supplied
  ``pv.Plotter``. This half needs the ``viz3d`` extra.

Colours come from :mod:`genealogy_kg.theme`, never from :mod:`genealogy_kg.viz`
-- ``viz.py`` imports ``plotly`` at module scope, and this module must stay
importable with only the ``viz3d`` extra installed, no ``viz``.

The root is always an explicit person, not an auto-detected progenitor: a
GEDCOM can hold several unrelated lines, and a person can have two ancestor
chains (through each parent), so there is no single well-defined "the"
progenitor to find. ``<xref>`` founds the tree; it never sits inside someone
else's.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from kg_utils.store import GraphStore
from kg_utils.viz3d import (
    Skeleton,
    fibonacci_annulus,
    grow_tree,
    leaf_facing,
    oriented_cluster,
    seed_from_key,
)

from genealogy_kg.theme import GENERATION_COLOR, SEX_COLOR, generation_depths, sex_kind

if TYPE_CHECKING:
    import pyvista as pv

#: Golden angle, in radians -- the same even angular spacing
#: ``pycode_kg.scene3d.CodeTreeLayout`` uses to spread limbs with no natural
#: order of their own around a trunk.
GOLDEN_ANGLE: Final[float] = math.pi * (3.0 - math.sqrt(5.0))

#: Trunk height grows with how many generations there are to reach, in world
#: units per generation, floored so a one-generation family still gets a
#: real trunk to branch from.
TRUNK_HEIGHT_PER_GENERATION: Final[float] = 2.4
MIN_TRUNK_HEIGHT: Final[float] = 3.0

#: Fraction of trunk height below which no limb branches -- climbing room,
#: so the leader grows a trunk before it forks. Mirrors
#: ``CodeTreeLayout.limb_start``.
LIMB_START: Final[float] = 0.15

#: Base radial reach of a family's limb tip from the trunk axis, before the
#: fecundity scaling below.
BRANCH_REACH: Final[float] = 2.2

#: How steeply limb reach grows with a family's child count -- "canopy
#: density by branch fecundity" from docs/DESIGN.md. Reused from
#: ``CodeTreeLayout``'s own biggest-module-reaches-furthest formula.
REACH_FLOOR: Final[float] = 0.4

#: Trunk growth-target guide points, so colonization climbs before it
#: branches instead of bridging straight to the nearest limb at an angle.
#: Never rendered as foliage -- see ``CodeTreeLayout.trunk_guides``.
N_TRUNK_GUIDES: Final[int] = 8

#: Height of the root/spouse ring, as a fraction of trunk height. Below
#: LIMB_START (families' own floor) so the founding generation still reads
#: as "older" than every family it started, but well off z=0 -- a founding
#: couple flush with the trunk's very base looks buried, not planted.
ROOT_RING_HEIGHT_FRACTION: Final[float] = 0.12

#: Population at which tip_radius/leaf_size/branch_reach are exactly the
#: caller-supplied defaults. Below it, geometry scales up -- a 9-person
#: family drawn at Habsburg-scale radii is a scatter of unconnected dust,
#: not a tree. Above it, geometry scales down so wood and foliage do not
#: drown a large tree. See docs/DESIGN.md.
SIZE_REFERENCE_POPULATION: Final[int] = 200
MIN_SIZE_SCALE: Final[float] = 0.6
MAX_SIZE_SCALE: Final[float] = 3.0


def _population_size_scale(population: int) -> float:
    """Geometry scale factor: bigger for small families, smaller for huge ones.

    :param population: Number of people in the grown tree.
    :return: Multiplier for radii/reach, clamped to
        ``[MIN_SIZE_SCALE, MAX_SIZE_SCALE]``.
    """
    raw = math.sqrt(SIZE_REFERENCE_POPULATION / max(population, 1))
    return min(max(raw, MIN_SIZE_SCALE), MAX_SIZE_SCALE)


@dataclass
class FamilyTreePositions:
    """Pure-geometry result of :func:`family_tree_positions`.

    :param person_positions: Every population member's leaf position.
    :param family_positions: Every limb tip, keyed by family node id.
    :param trunk_guides: Growth-target-only points along the trunk axis,
        never rendered as foliage.
    :param trunk_height: Trunk height used, in world units.
    :param root_id: The tree's root person node id.
    :param person_family: Each person's birth family id, or ``None`` for the
        root and their spouse(s) -- who ring the trunk base instead. The
        schematic renderer draws this as a twig line; the organic renderer
        does not need it, since ``grow_tree`` finds its own connections.
    :param size_scale: Population-based geometry multiplier from
        :func:`_population_size_scale`; the caller applies it to
        tip_radius/leaf_size so a small family doesn't render as dust.
    """

    person_positions: dict[str, np.ndarray]
    family_positions: dict[str, np.ndarray]
    trunk_guides: np.ndarray
    trunk_height: float
    root_id: str
    person_family: dict[str, str | None]
    size_scale: float = 1.0


def _family_spouses(store: GraphStore, family_id: str) -> list[str]:
    return [s["id"] for s in store.callers_of(family_id, rel="SPOUSE_IN")]


def _family_children(store: GraphStore, family_id: str) -> list[str]:
    return [c["id"] for c in store.callers_of(family_id, rel="CHILD_IN")]


def _birth_year(store: GraphStore, person_id: str) -> str:
    node = store.node(person_id)
    if node is None:
        return ""
    return str((node.get("metadata") or {}).get("occurred_start") or "")


def _descendant_population(store: GraphStore, root_id: str) -> dict[str, int]:
    """Return ``root_id`` and everyone descended from them, generation-tagged.

    Forward-only: children (``PARENT_OF``) and spouses (``MARRIED_TO``, same
    generation), *never* a step to a parent. This is deliberately not
    :func:`~genealogy_kg.theme.generation_depths` filtered to non-negative --
    that walk is bidirectional, so on a person with recorded parents it climbs
    to them and back down through every sibling's own line, pulling in
    collateral relatives who are not descendants of ``root_id`` at all.
    Right for Phase 4's "generation distance from whoever I clicked on";
    wrong for "grow this person's own descent line."

    :param store: The graph store.
    :param root_id: Node id to grow from, such as ``person:I1``.
    :return: Node id to generation offset (``root_id`` at ``0``), including
        every descendant and every spouse who married in.
    """
    depths: dict[str, int] = {root_id: 0}
    queue: deque[str] = deque([root_id])
    while queue:
        cur = queue.popleft()
        here = depths[cur]
        steps: list[tuple[str, int]] = []
        for edge in store.edges_from(cur, rel="PARENT_OF"):
            steps.append((edge["dst"], here + 1))
        for edge in store.edges_from(cur, rel="MARRIED_TO"):
            steps.append((edge["dst"], here))
        for spouse in store.callers_of(cur, rel="MARRIED_TO"):
            steps.append((spouse["id"], here))
        for node_id, offset in steps:
            if node_id not in depths:
                depths[node_id] = offset
                queue.append(node_id)
    return depths


def family_tree_positions(
    store: GraphStore,
    xref: str,
    *,
    trunk_height_per_generation: float = TRUNK_HEIGHT_PER_GENERATION,
    branch_reach: float = BRANCH_REACH,
) -> FamilyTreePositions:
    """Place the root, every family they founded or descend into, and every person.

    The population is ``xref``'s descent line -- ``xref`` plus every
    descendant plus every spouse who married in -- from
    :func:`_descendant_population`. Not :func:`~genealogy_kg.theme.generation_depths`:
    that walk is bidirectional (built for Phase 4's "generation distance from
    whoever I clicked on"), so on a person with recorded parents it climbs to
    them and back down through every sibling's own line -- confirmed against
    the Kennedy corpus, where reusing it pulled in 86 collateral relatives for
    a person with no descendants of their own.

    Each family founded by a population member becomes a limb, height set by
    generation depth (older generations low, like a real trunk's old growth;
    newer generations toward the canopy, like new tips), angle spread by the
    golden angle since -- unlike generation -- families have no natural order
    of their own. Each person clusters around their birth family's limb tip,
    ordered within the cluster by birth year (falling back to the existing
    deterministic cluster order when undated). ``xref`` and their spouse(s)
    have no birth family in this population -- by construction, since their
    own parents sit at a negative offset and were excluded -- and ring the
    trunk base instead, the same fallback
    ``pycode_kg.scene3d.CodeTreeLayout`` uses for nodes no limb claims.

    :param store: The graph store.
    :param xref: Individual xref without ``@``, such as ``I1``. Founds the
        tree; their ancestors are not grown.
    :param trunk_height_per_generation: World units of trunk height per
        generation reached.
    :param branch_reach: Base radial reach of a limb tip before fecundity
        scaling.
    :return: Attractor points and per-node positions.
    :raises ValueError: If ``xref`` is not a known person, or has no
        descendants or spouses to grow toward.
    """
    root_id = f"person:{xref}"
    if store.node(root_id) is None:
        raise ValueError(f"no such person: {root_id}")

    population = _descendant_population(store, root_id)
    max_depth = max(population.values(), default=0)

    family_ids: set[str] = set()
    for pid in population:
        for edge in store.edges_from(pid, rel="SPOUSE_IN"):
            family_ids.add(edge["dst"])
    if not family_ids:
        raise ValueError(f"{root_id} has no descendants or spouses to grow toward")

    def family_sort_key(family_id: str) -> tuple[int, str, str]:
        spouses = _family_spouses(store, family_id)
        depth = min((population.get(s, 0) for s in spouses), default=0)
        node = store.node(family_id) or {}
        married = str((node.get("metadata") or {}).get("occurred_start") or "")
        return (depth, married, family_id)

    ordered_families = sorted(family_ids, key=family_sort_key)

    size_scale = _population_size_scale(len(population))
    branch_reach = branch_reach * size_scale

    trunk_height = max(trunk_height_per_generation * max_depth, MIN_TRUNK_HEIGHT)
    max_children = max((len(_family_children(store, fid)) for fid in ordered_families), default=1)
    max_children = max(max_children, 1)

    family_positions: dict[str, np.ndarray] = {}
    family_children: dict[str, list[str]] = {}
    for i, family_id in enumerate(ordered_families):
        spouses = _family_spouses(store, family_id)
        depth = min((population.get(s, 0) for s in spouses), default=0)
        z = trunk_height * (LIMB_START + (1.0 - LIMB_START) * (depth / max(max_depth, 1)))
        angle = i * GOLDEN_ANGLE
        n_children = len(_family_children(store, family_id))
        reach = branch_reach * (
            REACH_FLOOR + (1.0 - REACH_FLOOR) * math.sqrt(n_children / max_children)
        )
        family_positions[family_id] = np.array(
            [reach * math.cos(angle), reach * math.sin(angle), z]
        )
        family_children[family_id] = _family_children(store, family_id)

    person_positions: dict[str, np.ndarray] = {}
    person_family: dict[str, str | None] = {}
    for family_id in ordered_families:
        tip = family_positions[family_id]
        axis = np.array([0.0, 0.0, tip[2]])
        facing = leaf_facing(tip - axis)
        siblings = sorted(
            (pid for pid in family_children[family_id] if pid in population),
            key=lambda pid: _birth_year(store, pid),
        )
        if not siblings:
            continue
        cluster_radius = (0.9 + math.sqrt(len(siblings)) * 0.6) * size_scale
        cluster = oriented_cluster(len(siblings), tip, facing, cluster_radius)
        for sib_id, pos in zip(siblings, cluster, strict=True):
            person_positions[sib_id] = pos
            person_family[sib_id] = family_id

    orphans = [pid for pid in population if pid not in person_positions]
    for person_id in orphans:
        person_family[person_id] = None

    if orphans:
        # A flat ring, not a sphere: the founding couple is "the roots", and
        # a sphere's lower hemisphere would dip below the trunk's own base
        # -- a couple with no known parents is not literally underground.
        # Raised to ROOT_RING_HEIGHT_FRACTION rather than sitting at the
        # trunk's literal base -- flush with z=0 reads as buried, not planted.
        base_radius = max(branch_reach * 0.4, 1.0)
        ring_center = np.array([0.0, 0.0, trunk_height * ROOT_RING_HEIGHT_FRACTION])
        ring = fibonacci_annulus(
            len(orphans),
            inner_radius=base_radius * 0.3,
            outer_radius=base_radius,
            center=ring_center,
            z_thickness=trunk_height * 0.02,
        )
        for person_id, pos in zip(orphans, ring, strict=True):
            person_positions[person_id] = pos

    guide_z = np.linspace(trunk_height * 0.06, trunk_height * LIMB_START * 0.85, N_TRUNK_GUIDES)
    trunk_guides = np.column_stack([np.zeros_like(guide_z), np.zeros_like(guide_z), guide_z])

    return FamilyTreePositions(
        person_positions=person_positions,
        family_positions=family_positions,
        trunk_guides=trunk_guides,
        trunk_height=trunk_height,
        root_id=root_id,
        person_family=person_family,
        size_scale=size_scale,
    )


@dataclass
class TreeGeometry:
    """What a composed family-tree scene contains.

    :param skeleton: The grown skeleton; ``None`` in schematic mode, which
        never grows one. Its radii report limb load when present.
    :param positions: :class:`FamilyTreePositions` this scene was grown from.
    :param leaf_tint: Per-person scalar array carried onto the foliage/point
        glyphs.
    :param title: Human-readable summary for a window title or CLI echo.
    :param points: Every drawn point, for camera framing via
        :func:`~kg_utils.viz3d.frame_tree` regardless of mode -- the grown
        wood's points in organic mode, person and family positions in
        schematic mode.
    :param counts: ``{"person": n, "family": n}``.
    """

    skeleton: Skeleton | None
    positions: FamilyTreePositions
    leaf_tint: np.ndarray
    title: str
    points: np.ndarray
    counts: dict[str, int] = field(default_factory=dict)


def _leaf_tint(
    store: GraphStore, person_ids: list[str], *, color_by: str, depths: dict[str, int]
) -> tuple[np.ndarray, list[str]]:
    """Return a per-leaf tint array plus the ordered palette it indexes into.

    :param store: The graph store.
    :param person_ids: Leaf order; must match the positions array's order.
    :param color_by: ``"sex"`` or ``"generation"``.
    :param depths: Signed generation offsets, for ``color_by="generation"``.
    :return: ``(tint, palette)`` -- integer codes and the hex colour each
        code maps to, ready for a ``ListedColormap``.
    """
    if color_by == "sex":
        keys = ["person_male", "person_female", "person_unknown"]
        palette = [SEX_COLOR[k] for k in keys]
        index = {k: i for i, k in enumerate(keys)}
        codes = [index[sex_kind(store.node(pid) or {})] for pid in person_ids]
    elif color_by == "generation":
        keys = sorted(GENERATION_COLOR)
        palette = [GENERATION_COLOR[k] for k in keys]
        index = {k: i for i, k in enumerate(keys)}
        offsets = [max(min(depths.get(pid, 0), keys[-1]), keys[0]) for pid in person_ids]
        codes = [index[o] for o in offsets]
    else:
        raise ValueError(f"color_by must be 'sex' or 'generation', got {color_by!r}")
    return np.asarray(codes, dtype=float), palette


def _line_mesh(segments: list[tuple[np.ndarray, np.ndarray]]) -> pv.PolyData:
    """Build one flat-numpy line mesh from ``(start, end)`` segment pairs.

    One draw call regardless of segment count -- the same technique
    ``gutenberg_kg.scene.build_forest_scene`` uses for its branch lines,
    rather than one actor per segment.

    :param segments: Endpoint pairs.
    :return: A ``pv.PolyData`` with a ``lines`` cell array; empty if
        *segments* is empty.
    """
    import pyvista as pv  # noqa: PLC0415 - the viz3d-only import boundary

    n = len(segments)
    if n == 0:
        return pv.PolyData()
    points = np.empty((n * 2, 3), dtype=float)
    points[0::2] = [s[0] for s in segments]
    points[1::2] = [s[1] for s in segments]
    cells = np.empty(n * 3, dtype=np.intp)
    cells[0::3] = 2
    cells[1::3] = np.arange(0, n * 2, 2)
    cells[2::3] = np.arange(1, n * 2 + 1, 2)
    mesh = pv.PolyData()
    mesh.points = points
    mesh.lines = cells
    return mesh


def build_family_tree_scene(
    store: GraphStore,
    plotter: pv.Plotter,
    xref: str,
    *,
    color_by: str = "generation",
    tip_radius: float = 0.06,
    leaf_size: float = 0.35,
    tropism: tuple[float, float, float] | None = None,
    organic: bool = True,
) -> TreeGeometry:
    """Compose ``xref``'s descent line into *plotter* as a single tree.

    :param store: The graph store.
    :param plotter: PyVista plotter to compose into; cleared first.
    :param xref: Individual xref without ``@``. Founds the tree.
    :param color_by: ``"sex"`` or ``"generation"`` (default) -- see
        docs/DESIGN.md's "leaf colour by generation".
    :param tip_radius: Radius of leaf-bearing twigs (organic mode) or the
        trunk cylinder's radius (schematic mode), in world units.
    :param leaf_size: Leaf/point glyph radius before density scaling.
    :param tropism: Growth bias; :func:`~kg_utils.viz3d.grow_tree`'s own
        default if omitted. Ignored in schematic mode.
    :param organic: ``True`` (default) grows real wood via space
        colonization -- see docs/DESIGN.md's "the family tree, literally".
        ``False`` skips growth entirely and draws :func:`family_tree_positions`'s
        own schematic layout directly: a straight trunk, straight branch and
        twig lines, and a sphere glyph per person. Cheap regardless of family
        size, and useful as a fast diagram or a sanity check on the layout
        that :func:`build_family_tree_scene` (organic) then grows wood toward
        -- the same relationship ``gutenberg_kg``'s ``--schematic`` flag has
        to its own organic render.
    :return: The composed :class:`TreeGeometry`.
    """
    import pyvista as pv  # noqa: PLC0415 - the viz3d-only import boundary
    from matplotlib.colors import ListedColormap  # noqa: PLC0415 - arrives with pyvista

    positions = family_tree_positions(store, xref)
    depths = generation_depths(store, positions.root_id)

    # A 9-person family drawn at radii tuned for a 1700-person one is dust,
    # not a tree -- see FamilyTreePositions.size_scale.
    tip_radius = tip_radius * positions.size_scale
    leaf_size = leaf_size * positions.size_scale

    person_ids = list(positions.person_positions)
    leaf_points = np.array([positions.person_positions[pid] for pid in person_ids])
    tint, palette = _leaf_tint(store, person_ids, color_by=color_by, depths=depths)
    cmap = ListedColormap(palette)
    clim = [-0.5, len(palette) - 0.5]

    plotter.clear_actors()
    plotter.enable_anti_aliasing("msaa")

    skeleton: Skeleton | None = None
    if organic:
        attractors = np.vstack([positions.trunk_guides, leaf_points])
        root = np.zeros(3)
        kwargs: dict[str, Any] = {"key": xref, "tip_radius": tip_radius}
        if tropism is not None:
            kwargs["tropism"] = tropism
        skeleton = grow_tree(attractors, root, **kwargs)

        from kg_utils.viz3d import tree_mesh  # noqa: PLC0415

        wood = tree_mesh(skeleton)
        if wood.n_points:
            plotter.add_mesh(wood, color="#5A3A22", smooth_shading=True, name="wood")

        if leaf_points.size:
            from kg_utils.viz3d import leaf_glyphs  # noqa: PLC0415

            leaves = leaf_glyphs(
                leaf_points,
                skeleton,
                size=leaf_size,
                tint=tint,
                seed=seed_from_key(f"{xref}:leaves"),
            )
            if leaves.n_points:
                plotter.add_mesh(
                    leaves,
                    scalars="tint",
                    cmap=cmap,
                    clim=clim,
                    show_scalar_bar=False,
                    name="leaves",
                )
        points = skeleton.points
    else:
        trunk = pv.Cylinder(
            center=(0.0, 0.0, positions.trunk_height / 2.0),
            direction=(0.0, 0.0, 1.0),
            radius=max(tip_radius * 4.0, 0.02),
            height=positions.trunk_height,
            resolution=12,
        )
        plotter.add_mesh(trunk, color="#5A3A22", smooth_shading=True, name="wood")

        segments: list[tuple[np.ndarray, np.ndarray]] = []
        for tip in positions.family_positions.values():
            segments.append((np.array([0.0, 0.0, tip[2]]), tip))
        trunk_base = np.array([0.0, 0.0, 0.0])
        for pid in person_ids:
            family_id = positions.person_family.get(pid)
            anchor = positions.family_positions[family_id] if family_id else trunk_base
            segments.append((anchor, positions.person_positions[pid]))
        branches = _line_mesh(segments)
        if branches.n_points:
            # A real tube, not a screen-space line width: line_width is
            # pixels, not world units, so it shrinks to invisible on zoom-out
            # and never reads as a solid connector the way the trunk does.
            tubes = branches.tube(radius=max(tip_radius * 0.6, 0.01), n_sides=8)
            plotter.add_mesh(tubes, color="#8A6A4A", smooth_shading=True, name="branches")

        if leaf_points.size:
            people = pv.PolyData(leaf_points)
            people.point_data["tint"] = tint
            sphere = pv.Sphere(radius=leaf_size, theta_resolution=16, phi_resolution=16)
            glyphs = people.glyph(geom=sphere, orient=False, scale=False)
            plotter.add_mesh(
                glyphs,
                scalars="tint",
                cmap=cmap,
                clim=clim,
                show_scalar_bar=False,
                smooth_shading=True,
                name="leaves",
            )
        family_points = np.array(list(positions.family_positions.values()))
        points = np.vstack([leaf_points, family_points]) if leaf_points.size else family_points

    root_node = store.node(positions.root_id) or {}
    root_name = root_node.get("name") or xref
    n_families = len(positions.family_positions)
    mode = "organic" if organic else "schematic"
    title = (
        f"{root_name}'s descent ({mode}) | people={len(person_ids)}  "
        f"families={n_families}  generations={max(depths.values(), default=0)}"
    )

    return TreeGeometry(
        skeleton=skeleton,
        positions=positions,
        leaf_tint=tint,
        title=title,
        points=points,
        counts={"person": len(person_ids), "family": n_families},
    )


__all__ = [
    "FamilyTreePositions",
    "TreeGeometry",
    "build_family_tree_scene",
    "family_tree_positions",
]
