"""Tests for genealogy_kg.hourglass and the hourglass scene shape.

Against the fixture GEDCOM, rooted at I7 (Robert Hartwell): parents I3 and
I6, grandparents I1 and I2 through I3 (I6 has no recorded parents), spouse
I11, child I12. I8 is Robert's sibling; I4 and I5 are his aunts; I9 and I10
are an aunt's husband and child. None of those five is an ancestor or a
descendant, so none may appear.

Pedigree collapse uses a small invented GEDCOM written per test: two first
cousins marry, so their child reaches the shared grandparents by two paths.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from kg_utils.store import GraphStore

from genealogy_kg import scene
from genealogy_kg.hourglass import EDGE_SUBDIVISIONS, curved_wood, hourglass_positions
from genealogy_kg.module import GenealogyKG

COUSINS_GED = """\
0 HEAD
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
0 @A@ INDI
1 NAME Amos /Root/
1 SEX M
0 @B@ INDI
1 NAME Bea /Stem/
1 SEX F
0 @C@ INDI
1 NAME Carl /Root/
1 SEX M
0 @D@ INDI
1 NAME Dora /Root/
1 SEX F
0 @X@ INDI
1 NAME Xena /Out/
1 SEX F
0 @Y@ INDI
1 NAME Yuri /Away/
1 SEX M
0 @E@ INDI
1 NAME Ezra /Root/
1 SEX M
0 @F@ INDI
1 NAME Faye /Away/
1 SEX F
0 @G@ INDI
1 NAME Gail /Root/
1 SEX F
0 @F1@ FAM
1 HUSB @A@
1 WIFE @B@
1 CHIL @C@
1 CHIL @D@
0 @F2@ FAM
1 HUSB @C@
1 WIFE @X@
1 CHIL @E@
0 @F3@ FAM
1 HUSB @Y@
1 WIFE @D@
1 CHIL @F@
0 @F4@ FAM
1 HUSB @E@
1 WIFE @F@
1 CHIL @G@
0 TRLR
"""


@pytest.fixture
def built_kg(corpus_root: Path) -> GenealogyKG:
    kg = GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")])
    kg.build(wipe=True)
    return kg


@pytest.fixture
def cousins_kg(tmp_path: Path) -> GenealogyKG:
    (tmp_path / "cousins.ged").write_text(COUSINS_GED, encoding="utf-8")
    kg = GenealogyKG(repo_root=tmp_path, sources=[Path("cousins.ged")])
    kg.build(wipe=True)
    return kg


def _kin(store: GraphStore, a: str, b: str) -> bool:
    """True if ``a`` and ``b`` are parent and child, or spouses, either way."""
    a_births = {e["dst"] for e in store.edges_from(a, rel="CHILD_IN")}
    b_births = {e["dst"] for e in store.edges_from(b, rel="CHILD_IN")}
    a_marriages = {e["dst"] for e in store.edges_from(a, rel="SPOUSE_IN")}
    b_marriages = {e["dst"] for e in store.edges_from(b, rel="SPOUSE_IN")}
    return bool(a_births & b_marriages or b_births & a_marriages or a_marriages & b_marriages)


# ---------------------------------------------------------------------------
# Pure layout -- no PyVista
# ---------------------------------------------------------------------------


def test_hourglass_population_is_exactly_ancestors_and_descendants(
    built_kg: GenealogyKG,
) -> None:
    hp = hourglass_positions(built_kg.store, "I7")
    ancestors = {pid for pid, g in hp.generation.items() if g < 0}
    canopy = {pid for pid, g in hp.generation.items() if g >= 0}
    assert ancestors == {"person:I3", "person:I6", "person:I1", "person:I2"}
    assert canopy == {"person:I7", "person:I11", "person:I12"}
    assert (hp.n_ancestors, hp.n_descendants) == (4, 2)


def test_hourglass_roots_never_pull_in_collateral_relatives(built_kg: GenealogyKG) -> None:
    """The backward walk never steps down: no siblings, aunts or cousins."""
    hp = hourglass_positions(built_kg.store, "I7")
    for collateral in ("I8", "I4", "I5", "I9", "I10"):
        assert f"person:{collateral}" not in hp.person_positions


def test_hourglass_generations_are_signed_by_kinship(built_kg: GenealogyKG) -> None:
    hp = hourglass_positions(built_kg.store, "I7")
    assert hp.generation["person:I3"] == -1
    assert hp.generation["person:I1"] == -2
    assert hp.generation["person:I11"] == 0  # a spouse shares the partner's generation
    assert hp.generation["person:I12"] == 1


def test_hourglass_roots_below_ground_canopy_above(built_kg: GenealogyKG) -> None:
    hp = hourglass_positions(built_kg.store, "I7")
    for pid, gen in hp.generation.items():
        z = hp.person_positions[pid][2]
        if gen < 0:
            assert z < 0.0, pid
        else:
            assert z >= hp.trunk_height, pid
    # Older generations sit deeper, newer ones higher.
    assert hp.person_positions["person:I1"][2] < hp.person_positions["person:I3"][2]
    assert hp.person_positions["person:I12"][2] > hp.person_positions["person:I7"][2]


def test_hourglass_every_wood_edge_is_a_kinship_edge(built_kg: GenealogyKG) -> None:
    """One limb per kinship edge: a person's wood grows from a parent, child or spouse.

    The only exception is the focal person's parents, whose roots hang from
    the ground point at the base of the trunk.
    """
    hp = hourglass_positions(built_kg.store, "I7")
    for i, person in enumerate(hp.wood_person):
        parent = int(hp.wood_parents[i])
        if person is None or parent < 0:
            continue
        parent_person = hp.wood_person[parent]
        if parent_person is None:
            assert person in {"person:I7", "person:I3", "person:I6"}
            continue
        assert _kin(built_kg.store, person, parent_person), (person, parent_person)


def test_hourglass_every_placed_parent_child_pair_is_joined_by_wood(
    built_kg: GenealogyKG,
) -> None:
    """Each recorded parent-to-child edge between blood relatives is a direct limb."""
    store = built_kg.store
    hp = hourglass_positions(store, "I7")
    node_of = {p: i for i, p in enumerate(hp.wood_person) if p is not None}
    blood = {pid for pid, g in hp.generation.items() if g != 0} | {"person:I7"}
    for child in blood:
        for birth in store.edges_from(child, rel="CHILD_IN"):
            for parent in store.callers_of(birth["dst"], rel="SPOUSE_IN"):
                pid = parent["id"]
                if pid not in blood:
                    continue
                c, p = node_of[child], node_of[pid]
                if hp.generation[pid] < 0:
                    # Roots: the parent's root grows from the child's.
                    assert int(hp.wood_parents[p]) == c or child == "person:I7"
                else:
                    # Canopy: the child's limb grows from the parent's.
                    assert int(hp.wood_parents[c]) == p


def test_hourglass_wood_is_parent_before_child(built_kg: GenealogyKG) -> None:
    hp = hourglass_positions(built_kg.store, "I7")
    assert hp.wood_parents[0] == -1
    assert all(hp.wood_parents[i] < i for i in range(1, len(hp.wood_parents)))
    points, parents = curved_wood(hp, key="I7")
    assert parents[0] == -1
    assert all(parents[i] < i for i in range(1, len(parents)))
    n = len(hp.wood_points)
    assert points.shape[0] == n + (n - 1) * EDGE_SUBDIVISIONS


def test_hourglass_is_deterministic(built_kg: GenealogyKG) -> None:
    a = hourglass_positions(built_kg.store, "I7")
    b = hourglass_positions(built_kg.store, "I7")
    assert np.array_equal(a.wood_points, b.wood_points)
    assert np.array_equal(curved_wood(a, key="I7")[0], curved_wood(b, key="I7")[0])


def test_hourglass_of_a_leaf_person_is_all_roots(built_kg: GenealogyKG) -> None:
    """I12 has no spouse or child, which the canopy shape rejects; the hourglass grows roots."""
    hp = hourglass_positions(built_kg.store, "I12")
    assert hp.n_descendants == 0
    assert hp.n_ancestors == 6  # I7, I11, I3, I6, I1, I2


def test_hourglass_ancestor_cap_stops_the_roots(built_kg: GenealogyKG) -> None:
    hp = hourglass_positions(built_kg.store, "I7", max_ancestors=1)
    assert {p for p, g in hp.generation.items() if g < 0} == {"person:I3", "person:I6"}
    hp = hourglass_positions(built_kg.store, "I7", max_ancestors=0)
    assert hp.n_ancestors == 0
    assert hp.n_descendants == 2  # the canopy is untouched


def test_hourglass_descendant_cap_keeps_spouses_drops_children(built_kg: GenealogyKG) -> None:
    hp = hourglass_positions(built_kg.store, "I7", max_descendants=0)
    assert "person:I11" in hp.person_positions  # spouse at the capped generation
    assert "person:I12" not in hp.person_positions
    assert hp.n_ancestors == 4


def test_hourglass_uncapped_reaches_every_generation(built_kg: GenealogyKG) -> None:
    capped = hourglass_positions(built_kg.store, "I12", max_ancestors=2)
    uncapped = hourglass_positions(built_kg.store, "I12", max_ancestors=None)
    assert capped.n_ancestors == 4  # I7, I11, I3, I6
    assert uncapped.n_ancestors == 6  # plus I1, I2


def test_hourglass_negative_cap_raises(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="max_ancestors"):
        hourglass_positions(built_kg.store, "I7", max_ancestors=-1)


def test_hourglass_unknown_person_raises(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="no such person"):
        hourglass_positions(built_kg.store, "does-not-exist")


def test_hourglass_pedigree_collapse_places_each_ancestor_once(
    cousins_kg: GenealogyKG,
) -> None:
    """G's parents are first cousins: A and B are reached through both."""
    hp = hourglass_positions(cousins_kg.store, "G")
    people = [p for p in hp.wood_person if p is not None]
    assert len(people) == len(set(people))
    assert {"person:A", "person:B"} <= set(hp.person_positions)
    assert hp.skipped_edges == 2
    assert hp.n_ancestors == 8  # E, F, C, X, D, Y, A, B


# ---------------------------------------------------------------------------
# Scene composition -- needs PyVista
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("organic", [True, False])
def test_build_hourglass_scene_composes_wood_leaves_and_ground(
    built_kg: GenealogyKG, organic: bool
) -> None:
    pv = pytest.importorskip("pyvista")
    plotter = pv.Plotter(off_screen=True)
    tree = scene.build_family_tree_scene(
        built_kg.store, plotter, "I7", shape="hourglass", organic=organic
    )
    assert {"wood", "leaves", "ground"} <= set(plotter.actors)
    assert tree.counts == {"person": 7, "ancestor": 4, "descendant": 2}
    assert tree.leaf_tint.shape[0] == 7
    assert "hourglass" in tree.title
    assert (tree.skeleton is not None) == organic
    plotter.close()


def test_build_hourglass_scene_frame_points_span_both_halves(built_kg: GenealogyKG) -> None:
    pv = pytest.importorskip("pyvista")
    tree = scene.build_family_tree_scene(
        built_kg.store, pv.Plotter(off_screen=True), "I7", shape="hourglass"
    )
    assert tree.points[:, 2].min() < 0.0 < tree.points[:, 2].max()


def test_build_family_tree_scene_rejects_bad_shape(built_kg: GenealogyKG) -> None:
    pv = pytest.importorskip("pyvista")
    plotter = pv.Plotter(off_screen=True)
    with pytest.raises(ValueError, match="shape"):
        scene.build_family_tree_scene(built_kg.store, plotter, "I7", shape="hanging")
    plotter.close()
