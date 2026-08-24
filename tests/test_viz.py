"""Tests for genealogy_kg.viz and ``genkg viz`` against the fixture GEDCOM.

The fixture is three generations of Hartwells: I1 (John) at the top, I12
(a great-granddaughter) at the bottom.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from genealogy_kg import viz
from genealogy_kg.cli import cli
from genealogy_kg.lineage import tree_data
from genealogy_kg.module import GenealogyKG


@pytest.fixture
def built_kg(corpus_root: Path) -> GenealogyKG:
    kg = GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")])
    kg.build(wipe=True)
    return kg


# ---------------------------------------------------------------------------
# The shared walk
# ---------------------------------------------------------------------------


def test_tree_data_carries_the_node_beside_the_label(built_kg: GenealogyKG) -> None:
    tree = tree_data(built_kg.store, "person:I1", generations=4)
    assert tree is not None
    assert tree["node"]["id"] == "person:I1"
    assert tree["label"].startswith("John Hartwell")
    assert all("node" in child for child in tree["children"])


def test_tree_data_unknown_person_is_none(built_kg: GenealogyKG) -> None:
    assert tree_data(built_kg.store, "person:does-not-exist") is None


def test_tree_data_rejects_bad_direction(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="direction"):
        tree_data(built_kg.store, "person:I1", direction="sideways")


# ---------------------------------------------------------------------------
# Generation depth
# ---------------------------------------------------------------------------


def test_generation_depths_count_down_the_descent_line(built_kg: GenealogyKG) -> None:
    depths = viz.generation_depths(built_kg.store, "person:I1")
    assert depths["person:I1"] == 0
    assert depths["person:I3"] == 1  # son
    assert depths["person:I7"] == 2  # grandson
    assert depths["person:I12"] == 3  # great-granddaughter


def test_generation_depths_put_spouses_in_the_same_generation(
    built_kg: GenealogyKG,
) -> None:
    depths = viz.generation_depths(built_kg.store, "person:I1")
    assert depths["person:I2"] == depths["person:I1"]  # wife of the root
    assert depths["person:I11"] == depths["person:I7"]  # wife of the grandson


def test_generation_depths_are_negative_looking_up(built_kg: GenealogyKG) -> None:
    depths = viz.generation_depths(built_kg.store, "person:I12")
    assert depths["person:I7"] == -1
    assert depths["person:I3"] == -2
    assert depths["person:I1"] == -3


# ---------------------------------------------------------------------------
# Sex colouring
# ---------------------------------------------------------------------------


def test_sex_kind_maps_people_and_passes_other_kinds_through(
    built_kg: GenealogyKG,
) -> None:
    assert viz.sex_kind(built_kg.store.node("person:I1")) == "person_male"
    assert viz.sex_kind(built_kg.store.node("person:I2")) == "person_female"
    assert viz.sex_kind({"kind": "family"}) == "family"
    assert viz.sex_kind({"kind": "person"}) == "person_unknown"


# ---------------------------------------------------------------------------
# Pedigree chart
# ---------------------------------------------------------------------------


def test_pedigree_draws_one_marker_per_person_in_the_walk(
    built_kg: GenealogyKG,
) -> None:
    tree = tree_data(built_kg.store, "person:I1", generations=4)
    assert tree is not None

    def count(subtree: dict) -> int:
        return 1 + sum(count(child) for child in subtree["children"])

    figure = viz.pedigree_figure(built_kg.store, "person:I1", generations=4)
    people = figure.data[1]
    assert len(people.x) == count(tree)


def test_pedigree_places_each_generation_on_its_own_row(built_kg: GenealogyKG) -> None:
    figure = viz.pedigree_figure(built_kg.store, "person:I1", generations=4)
    rows = sorted({y for y in figure.data[1].y})
    assert rows == [-3.0, -2.0, -1.0, 0.0]
    assert figure.data[1].y[0] == 0  # the root sits on the top row


def test_pedigree_labels_carry_the_lifespan(built_kg: GenealogyKG) -> None:
    figure = viz.pedigree_figure(built_kg.store, "person:I1", generations=4)
    assert figure.data[1].text[0] == "John Hartwell<br>1820-1891"


def test_pedigree_colours_by_sex(built_kg: GenealogyKG) -> None:
    figure = viz.pedigree_figure(built_kg.store, "person:I1", generations=4)
    assert figure.data[1].marker.color[0] == viz.SEX_COLOR["person_male"]


def test_pedigree_shapes_carry_sex_even_when_colour_carries_generation(
    built_kg: GenealogyKG,
) -> None:
    """Shape is the cue that survives any colour-vision deficiency."""
    for color_by in ("sex", "generation"):
        figure = viz.pedigree_figure(built_kg.store, "person:I1", generations=4, color_by=color_by)
        symbols = list(figure.data[1].marker.symbol)
        assert symbols[0] == viz.SEX_SYMBOL["person_male"]
        assert viz.SEX_SYMBOL["person_female"] in symbols


def test_pedigree_colours_by_generation(built_kg: GenealogyKG) -> None:
    figure = viz.pedigree_figure(built_kg.store, "person:I1", generations=4, color_by="generation")
    colors = list(figure.data[1].marker.color)
    assert colors[0] == viz.GENERATION_COLOR[0]
    assert viz.GENERATION_COLOR[1] in colors


def test_pedigree_ancestors_walk_the_other_way(built_kg: GenealogyKG) -> None:
    figure = viz.pedigree_figure(built_kg.store, "person:I12", direction="ancestors", generations=4)
    assert "Ancestors of" in figure.layout.title.text
    assert len(figure.data[1].x) > 1


def test_pedigree_unknown_person_raises(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="no such person"):
        viz.pedigree_figure(built_kg.store, "person:does-not-exist")


def test_pedigree_rejects_bad_color_by(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="color_by"):
        viz.pedigree_figure(built_kg.store, "person:I1", color_by="mood")


# ---------------------------------------------------------------------------
# Network view
# ---------------------------------------------------------------------------


def test_network_html_is_self_contained(built_kg: GenealogyKG) -> None:
    html = viz.network_html(built_kg.store, root_id="person:I1", hops=3)
    assert "vis-network" in html
    assert "cdn.jsdelivr.net" not in html
    assert "<script" in html


def test_network_html_rooting_keeps_the_family_and_drops_the_rest(
    built_kg: GenealogyKG,
) -> None:
    near = viz.network_html(built_kg.store, root_id="person:I1", hops=1)
    far = viz.network_html(built_kg.store, root_id="person:I1", hops=4)
    assert "person:I12" not in near  # great-granddaughter is four hops out
    assert "person:I12" in far


def test_network_html_colours_by_generation(built_kg: GenealogyKG) -> None:
    html = viz.network_html(built_kg.store, root_id="person:I1", hops=4, color_by="generation")
    assert viz.GENERATION_COLOR[0] in html
    assert viz.GENERATION_COLOR[1] in html


def test_network_html_generation_without_a_root_raises(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="root_id"):
        viz.network_html(built_kg.store, color_by="generation")


def test_network_html_unknown_root_raises(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="no such node"):
        viz.network_html(built_kg.store, root_id="person:does-not-exist")


def test_network_theme_rejects_bad_color_by() -> None:
    with pytest.raises(ValueError, match="color_by"):
        viz.network_theme(color_by="mood")


# ---------------------------------------------------------------------------
# Colour-vision deficiency
# ---------------------------------------------------------------------------
#
# The first palette shipped here paired blue with rose, which measures fine on
# a normal-vision monitor and collapses to dE 7 -- indistinguishable -- for a
# protanope. Reviewing colours by eye cannot catch that, so these tests
# measure it: simulate each dichromacy (Machado 2009) and require a floor on
# the CIELAB distance between any two swatches a reader must tell apart.

#: Dichromacy simulation matrices, applied to linear RGB.
_CVD = {
    "protanopia": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deuteranopia": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritanopia": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}


def _linear(hex_color: str) -> list[float]:
    raw = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(raw[i : i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


def _simulate(hex_color: str, kind: str) -> list[float]:
    lin, m = _linear(hex_color), _CVD[kind]
    return [max(0.0, min(1.0, sum(m[r][i] * lin[i] for i in range(3)))) for r in range(3)]


def _lab(rgb: list[float]) -> tuple[float, float, float]:
    x = 0.4124 * rgb[0] + 0.3576 * rgb[1] + 0.1805 * rgb[2]
    y = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    z = 0.0193 * rgb[0] + 0.1192 * rgb[1] + 0.9505 * rgb[2]

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _distance(a: str, b: str, kind: str) -> float:
    la, lb = _lab(_simulate(a, kind)), _lab(_simulate(b, kind))
    return sum((p - q) ** 2 for p, q in zip(la, lb)) ** 0.5


#: Below roughly dE 10 two swatches read as the same colour.
MIN_SEPARATION = 20.0


@pytest.mark.parametrize("kind", sorted(_CVD))
def test_sex_colours_stay_distinct_under_colour_blindness(kind: str) -> None:
    swatches = list(viz.SEX_COLOR.items())
    for i, (name_a, color_a) in enumerate(swatches):
        for name_b, color_b in swatches[i + 1 :]:
            separation = _distance(color_a, color_b, kind)
            assert separation >= MIN_SEPARATION, (
                f"{name_a} vs {name_b} is only dE {separation:.1f} apart under "
                f"{kind}; needs {MIN_SEPARATION}"
            )


@pytest.mark.parametrize("kind", sorted(_CVD))
def test_adjacent_generations_stay_distinct_under_colour_blindness(kind: str) -> None:
    """Neighbouring generations are the pair a reader actually compares."""
    offsets = sorted(viz.GENERATION_COLOR)
    for lower, upper in zip(offsets, offsets[1:]):
        separation = _distance(viz.GENERATION_COLOR[lower], viz.GENERATION_COLOR[upper], kind)
        assert separation >= 12.0, (
            f"generation {lower:+d} vs {upper:+d} is only dE {separation:.1f} apart under {kind}"
        )


def test_every_person_shape_is_distinct_and_avoids_the_other_kinds() -> None:
    """Shape is the cue that does not depend on colour at all."""
    assert len(set(viz.SEX_SHAPE.values())) == len(viz.SEX_SHAPE)
    assert len(set(viz.SEX_SYMBOL.values())) == len(viz.SEX_SYMBOL)
    others = {shape for kind, shape in viz.KIND_SHAPE.items() if kind != "person"}
    assert others.isdisjoint(set(viz.SEX_SHAPE.values()))


# ---------------------------------------------------------------------------
# The extra stays optional
# ---------------------------------------------------------------------------


def test_importing_the_package_and_cli_pulls_neither_plotly_nor_pyvis() -> None:
    """A bare install must not need the viz extra to import or run --help.

    Phase 4's contract is that ``viz.py`` is reached only from inside
    ``cmd_viz``'s callback and ``adapter.display()``. A module-scope import
    anywhere on the startup path would break a bare install, and would do it
    silently here because this environment has the extra installed -- hence
    the subprocess and the explicit ``sys.modules`` check.
    """
    program = (
        "import sys;"
        "import genealogy_kg;"
        "from genealogy_kg.cli import cli;"
        "leaked = [m for m in ('plotly', 'pyvis') if m in sys.modules];"
        "print(','.join(leaked))"
    )
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_viz_writes_a_pedigree_file(corpus_root: Path) -> None:
    runner = CliRunner()
    source = str(corpus_root / "family.ged")
    build = runner.invoke(cli, ["build", "--repo", str(corpus_root), "--source", source])
    assert build.exit_code == 0, build.output

    out = corpus_root / "tree.html"
    result = runner.invoke(cli, ["viz", "I1", "--repo", str(corpus_root), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.is_file()
    assert "John Hartwell" in out.read_text(encoding="utf-8")


def test_viz_network_view_writes_a_graph_file(corpus_root: Path) -> None:
    runner = CliRunner()
    source = str(corpus_root / "family.ged")
    build = runner.invoke(cli, ["build", "--repo", str(corpus_root), "--source", source])
    assert build.exit_code == 0, build.output

    out = corpus_root / "graph.html"
    result = runner.invoke(
        cli,
        ["viz", "I1", "--view", "network", "--repo", str(corpus_root), "-o", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert "vis-network" in out.read_text(encoding="utf-8")


def test_viz_unknown_person_fails_with_a_usage_error(corpus_root: Path) -> None:
    runner = CliRunner()
    source = str(corpus_root / "family.ged")
    runner.invoke(cli, ["build", "--repo", str(corpus_root), "--source", source])

    result = runner.invoke(cli, ["viz", "NOPE", "--repo", str(corpus_root)])
    assert result.exit_code != 0
    assert "no such person" in result.output
