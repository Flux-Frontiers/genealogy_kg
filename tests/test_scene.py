"""Tests for genealogy_kg.scene against the fixture GEDCOM.

The fixture is three generations of Hartwells: I1 (John) and I2 (his wife)
found the tree; I3 -> I7 -> I12 is the deepest descent line.

Split like the module itself: pure-layout tests need no PyVista; the scene
composition tests do, and are the only ones that would need to skip without
the ``viz3d`` extra (this environment has it, so nothing here skips).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from genealogy_kg import scene
from genealogy_kg.module import GenealogyKG


@pytest.fixture
def built_kg(corpus_root: Path) -> GenealogyKG:
    kg = GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")])
    kg.build(wipe=True)
    return kg


# ---------------------------------------------------------------------------
# Pure layout -- no PyVista
# ---------------------------------------------------------------------------


def test_family_tree_positions_places_every_descendant(built_kg: GenealogyKG) -> None:
    fp = scene.family_tree_positions(built_kg.store, "I1")
    # Every descendant of I1 plus I1 and every spouse who married in.
    assert "person:I1" in fp.person_positions
    assert "person:I3" in fp.person_positions
    assert "person:I7" in fp.person_positions
    assert "person:I12" in fp.person_positions


def test_family_tree_positions_excludes_collateral_relatives(
    built_kg: GenealogyKG,
) -> None:
    """A person's siblings are not descendants of that person.

    Regression: an earlier version reused the bidirectional
    ``theme.generation_depths`` (built for "generation distance from whoever
    I clicked on") and filtered to non-negative offsets. On a person with
    recorded parents, that walk climbs to the parents and back down through
    every sibling's own line -- confirmed against a real corpus, where it
    pulled in 86 collateral relatives for a person with no descendants of
    their own.

    The fixture reproduces the same shape: I3, I4 and I5 are siblings
    (children of I1 and I2). Rooted at I4, the tree must be exactly I4,
    I4's spouse I9, and I4's own child I10 -- never I3's or I5's lines.
    """
    fp = scene.family_tree_positions(built_kg.store, "I4")
    assert set(fp.person_positions) == {"person:I4", "person:I9", "person:I10"}


def test_family_tree_positions_unknown_person_raises(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="no such person"):
        scene.family_tree_positions(built_kg.store, "does-not-exist")


def test_family_tree_positions_leaf_person_raises(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="no descendants or spouses"):
        scene.family_tree_positions(built_kg.store, "I12")


def test_family_tree_positions_root_and_spouse_ring_the_base(
    built_kg: GenealogyKG,
) -> None:
    """I1 and I2 have no birth family in this population -- they founded it."""
    fp = scene.family_tree_positions(built_kg.store, "I1")
    root_z = fp.person_positions["person:I1"][2]
    spouse_z = fp.person_positions["person:I2"][2]
    # The ring sits near the base, not dipped below it (a full sphere would
    # place roughly half its points at negative z).
    assert root_z >= 0
    assert spouse_z >= 0
    assert root_z < fp.trunk_height * 0.1
    assert spouse_z < fp.trunk_height * 0.1


def test_family_tree_positions_person_family_tracks_birth_family(
    built_kg: GenealogyKG,
) -> None:
    """The schematic renderer's twig lines read this: family id, or None."""
    fp = scene.family_tree_positions(built_kg.store, "I1")
    assert fp.person_family["person:I1"] is None  # root: no birth family here
    assert fp.person_family["person:I2"] is None  # spouse: likewise
    i3_family = fp.person_family["person:I3"]
    assert i3_family is not None
    assert i3_family in fp.family_positions


def test_family_tree_positions_deeper_generations_sit_higher(
    built_kg: GenealogyKG,
) -> None:
    """Old growth low, new growth toward the canopy, like a real tree."""
    fp = scene.family_tree_positions(built_kg.store, "I1")
    z_gen1 = fp.person_positions["person:I3"][2]  # I1's child
    z_gen2 = fp.person_positions["person:I7"][2]  # I1's grandchild
    z_gen3 = fp.person_positions["person:I12"][2]  # I1's great-grandchild
    assert z_gen1 < z_gen2 < z_gen3


def test_family_tree_positions_is_deterministic(built_kg: GenealogyKG) -> None:
    a = scene.family_tree_positions(built_kg.store, "I1")
    b = scene.family_tree_positions(built_kg.store, "I1")
    for pid in a.person_positions:
        assert np.allclose(a.person_positions[pid], b.person_positions[pid])


def test_family_tree_positions_trunk_guides_are_never_leaves(
    built_kg: GenealogyKG,
) -> None:
    fp = scene.family_tree_positions(built_kg.store, "I1")
    guide_positions = {tuple(p) for p in fp.trunk_guides}
    leaf_positions = {tuple(p) for p in fp.person_positions.values()}
    assert guide_positions.isdisjoint(leaf_positions)


# ---------------------------------------------------------------------------
# Scene composition -- needs the viz3d extra
# ---------------------------------------------------------------------------


def test_build_family_tree_scene_composes_wood_and_leaves(
    built_kg: GenealogyKG,
) -> None:
    pv = pytest.importorskip("pyvista")
    plotter = pv.Plotter(off_screen=True)
    tree = scene.build_family_tree_scene(built_kg.store, plotter, "I1")
    assert "wood" in plotter.actors
    assert "leaves" in plotter.actors
    assert tree.counts["person"] == len(tree.positions.person_positions)
    assert "John Hartwell" in tree.title
    plotter.close()


def test_build_family_tree_scene_colors_by_sex_and_generation(
    built_kg: GenealogyKG,
) -> None:
    pv = pytest.importorskip("pyvista")
    for color_by in ("sex", "generation"):
        plotter = pv.Plotter(off_screen=True)
        tree = scene.build_family_tree_scene(built_kg.store, plotter, "I1", color_by=color_by)
        assert tree.leaf_tint.shape[0] == len(tree.positions.person_positions)
        plotter.close()


def test_build_family_tree_scene_rejects_bad_color_by(built_kg: GenealogyKG) -> None:
    pv = pytest.importorskip("pyvista")
    plotter = pv.Plotter(off_screen=True)
    with pytest.raises(ValueError, match="color_by"):
        scene.build_family_tree_scene(built_kg.store, plotter, "I1", color_by="mood")
    plotter.close()


def test_build_family_tree_scene_schematic_skips_growth(built_kg: GenealogyKG) -> None:
    """--schematic is the cheap straight-line diagram: no Skeleton grown."""
    pv = pytest.importorskip("pyvista")
    plotter = pv.Plotter(off_screen=True)
    tree = scene.build_family_tree_scene(built_kg.store, plotter, "I1", organic=False)
    assert tree.skeleton is None
    assert "wood" in plotter.actors  # the straight trunk cylinder
    assert "branches" in plotter.actors  # organic mode has no such actor
    assert "leaves" in plotter.actors  # sphere glyphs, not leaf_glyphs foliage
    assert "(schematic)" in tree.title
    plotter.close()


def test_build_family_tree_scene_schematic_and_organic_agree_on_population(
    built_kg: GenealogyKG,
) -> None:
    """Both modes draw the same people -- they differ only in connective tissue."""
    pv = pytest.importorskip("pyvista")
    organic_tree = scene.build_family_tree_scene(
        built_kg.store, pv.Plotter(off_screen=True), "I1", organic=True
    )
    schematic_tree = scene.build_family_tree_scene(
        built_kg.store, pv.Plotter(off_screen=True), "I1", organic=False
    )
    assert set(organic_tree.positions.person_positions) == set(
        schematic_tree.positions.person_positions
    )
    assert organic_tree.counts == schematic_tree.counts


def test_build_family_tree_scene_schematic_frame_points_cover_everyone(
    built_kg: GenealogyKG,
) -> None:
    """frame_tree needs every drawn point, not just the people."""
    pv = pytest.importorskip("pyvista")
    plotter = pv.Plotter(off_screen=True)
    tree = scene.build_family_tree_scene(built_kg.store, plotter, "I1", organic=False)
    n_people = len(tree.positions.person_positions)
    n_families = len(tree.positions.family_positions)
    assert tree.points.shape[0] == n_people + n_families
    plotter.close()


# ---------------------------------------------------------------------------
# The extra stays optional
# ---------------------------------------------------------------------------


def test_importing_theme_pulls_no_heavy_dependency() -> None:
    """theme.py backs both viz.py (plotly) and scene.py (pyvista) -- it must
    need neither, or a viz3d-only install would fail importing scene.py.
    """
    program = (
        "import sys;"
        "import genealogy_kg.theme;"
        "leaked = [m for m in ('plotly', 'pyvis', 'pyvista', 'PyQt5') if m in sys.modules];"
        "print(','.join(leaked))"
    )
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == ""


def test_importing_scene_pulls_no_plotly_or_pyvis() -> None:
    """scene.py needs pyvista (the viz3d extra) but never plotly/pyvis (viz).

    A viz3d-only install (no [viz]) must be able to import scene.py; it
    would fail here if scene.py reached into genealogy_kg.viz for anything,
    even a colour constant.
    """
    program = (
        "import sys;"
        "import genealogy_kg.scene;"
        "leaked = [m for m in ('plotly', 'pyvis') if m in sys.modules];"
        "print(','.join(leaked))"
    )
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == ""


def test_importing_the_package_and_cli_pulls_no_viz3d_dependency() -> None:
    """A bare install must not need the viz3d extra to import or run --help."""
    program = (
        "import sys;"
        "from genealogy_kg.cli import cli;"
        "leaked = [m for m in ('pyvista', 'PyQt5', 'pyvistaqt', 'quiltwright') if m in sys.modules];"
        "print(','.join(leaked))"
    )
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == ""
