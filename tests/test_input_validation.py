"""Boundary validation on GenealogyKG's query/pack/person/tree/ancestors/
descendants, and on the CLI commands that front them -- see
docs/CODEBASE_REVIEW.md item 3, "Bound MCP and CLI inputs".
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from genealogy_kg.cli import cli
from genealogy_kg.module import GenealogyKG


@pytest.fixture
def built_kg(corpus_root: Path) -> GenealogyKG:
    kg = GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")])
    kg.build(wipe=True)
    return kg


# ---------------------------------------------------------------------------
# GenealogyKG.query / .pack
# ---------------------------------------------------------------------------


def test_query_rejects_empty_q(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        built_kg.query("")


def test_query_rejects_k_out_of_range(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="k must be between 1 and 100"):
        built_kg.query("chemist", k=0)


def test_query_rejects_hop_out_of_range(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="hop must be between 0 and 5"):
        built_kg.query("chemist", hop=6)


def test_query_accepts_hop_zero(built_kg: GenealogyKG) -> None:
    built_kg.query("chemist", hop=0)  # must not raise


def test_pack_rejects_max_nodes_out_of_range(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="max_nodes must be between 1 and 500"):
        built_kg.pack("chemist", max_nodes=501)


def test_pack_max_nodes_none_uses_sdk_default(built_kg: GenealogyKG) -> None:
    built_kg.pack("chemist")  # must not raise


# ---------------------------------------------------------------------------
# GenealogyKG.person / .tree / .ancestors / .descendants -- xref normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("xref", ["I1", "@I1@", "person:I1"])
def test_person_accepts_every_xref_form(built_kg: GenealogyKG, xref: str) -> None:
    person = built_kg.person(xref)
    assert person is not None
    assert person["id"] == "person:I1"


def test_person_rejects_malformed_xref(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="invalid xref"):
        built_kg.person("I 1")


def test_tree_rejects_malformed_xref(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="invalid xref"):
        built_kg.tree("@I1")


def test_tree_rejects_generations_out_of_range(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="generations must be between 1 and 50"):
        built_kg.tree("I1", generations=0)


def test_ancestors_accepts_every_xref_form(built_kg: GenealogyKG) -> None:
    for xref in ("I12", "@I12@", "person:I12"):
        result = built_kg.ancestors(xref, generations=1)
        assert {n["id"] for n in result} == {"person:I7", "person:I11"}


def test_descendants_accepts_every_xref_form(built_kg: GenealogyKG) -> None:
    for xref in ("I1", "@I1@", "person:I1"):
        result = built_kg.descendants(xref, generations=1)
        assert {n["id"] for n in result} == {"person:I3", "person:I4", "person:I5"}


def test_ancestors_rejects_generations_out_of_range(built_kg: GenealogyKG) -> None:
    with pytest.raises(ValueError, match="generations must be between 1 and 50"):
        built_kg.ancestors("I12", generations=51)


# ---------------------------------------------------------------------------
# CLI -- bad input surfaces as a click usage error, not a traceback
# ---------------------------------------------------------------------------


def test_cli_query_rejects_k_out_of_range(corpus_root: Path) -> None:
    result = CliRunner().invoke(cli, ["query", "chemist", "--repo", str(corpus_root), "--k", "0"])
    assert result.exit_code != 0
    assert "k" in result.output.lower()


def test_cli_query_rejects_hop_out_of_range(corpus_root: Path) -> None:
    result = CliRunner().invoke(
        cli, ["query", "chemist", "--repo", str(corpus_root), "--hop", "999"]
    )
    assert result.exit_code != 0


def test_cli_ancestors_rejects_bad_xref(corpus_root: Path) -> None:
    result = CliRunner().invoke(cli, ["ancestors", "I 1", "--repo", str(corpus_root)])
    assert result.exit_code != 0
    assert "invalid xref" in result.output


def test_cli_ancestors_rejects_generations_out_of_range(corpus_root: Path) -> None:
    result = CliRunner().invoke(
        cli, ["ancestors", "I1", "--repo", str(corpus_root), "--generations", "0"]
    )
    assert result.exit_code != 0


def test_cli_descendants_accepts_gedcom_pointer_form(corpus_root: Path) -> None:
    runner = CliRunner()
    build = runner.invoke(
        cli,
        ["build", "--repo", str(corpus_root), "--source", str(corpus_root / "family.ged")],
    )
    assert build.exit_code == 0, build.output

    result = runner.invoke(cli, ["descendants", "@I1@", "--repo", str(corpus_root)])
    assert result.exit_code == 0
    assert "John Hartwell" in result.output
