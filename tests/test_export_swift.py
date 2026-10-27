"""Tests for genealogy_kg.export_swift (``genkg export-swift``).

Uses the fixture GEDCOM for the pack's column mapping and the invented
Vantablack family from ``test_export`` for the privacy gate. Builds embed with
the real model, as the other build tests do.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner
from kg_utils.devicepack import Passage, read_vector_sidecar, search_pack, write_passage_pack

from genealogy_kg.cli import cli
from genealogy_kg.export import ExportError, PrivacySettings, scan_for_names
from genealogy_kg.export_swift import EMBEDDER_FILES, KG_NAME, export_swift
from genealogy_kg.module import GenealogyKG
from tests.test_export import LIVING_GED, LIVING_NAME, _build, _repo_dir

PRIVACY = PrivacySettings(living_cutoff_years=100)


@pytest.fixture
def sample_kg(corpus_root: Path) -> GenealogyKG:
    kg = GenealogyKG(
        repo_root=corpus_root,
        sources=[Path("family.ged")],
        living_cutoff_years=100,
        unknown_birth_policy="redact",
    )
    kg.build(wipe=True)
    return kg


@pytest.fixture
def sample_pack(sample_kg: GenealogyKG, tmp_path: Path) -> Path:
    export_swift(sample_kg, tmp_path / "out", PRIVACY)
    return tmp_path / "out"


def _rows(pack: Path) -> dict[str, dict]:
    con = sqlite3.connect(pack / "family.pack")
    con.row_factory = sqlite3.Row
    rows = {r["id"]: dict(r) for r in con.execute("SELECT * FROM passages")}
    con.close()
    return rows


def _fake_embedder(directory: Path, model: str = "BAAI/bge-small-en-v1.5") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "BGEEmbedder.mlpackage").mkdir()
    (directory / "BGEEmbedder.mlpackage" / "Manifest.json").write_text("{}")
    (directory / "vocab.txt").write_text("[PAD]\n")
    (directory / "embedder.json").write_text(json.dumps({"model": model}))


# ---------------------------------------------------------------------------
# The pack
# ---------------------------------------------------------------------------


def test_every_node_is_a_passage_with_a_vector(sample_pack: Path) -> None:
    rows = _rows(sample_pack)
    kinds = {r["kind"] for r in rows.values()}
    assert {"person", "family", "event", "place"} <= kinds
    assert sum(r["kind"] == "person" for r in rows.values()) == 12
    matrix, dtype = read_vector_sidecar(sample_pack / "family.vectors")
    assert dtype == "int8" and matrix.shape == (len(rows), 384)


def test_columns_carry_the_family(sample_pack: Path) -> None:
    rows = _rows(sample_pack)
    john = rows[f"{KG_NAME}:person:I1"]
    assert (john["genre"], john["author"], john["title"]) == (
        "hartwell-I1",
        "Hartwell",
        "John Hartwell",
    )
    assert "0 @I1@ INDI" in john["content"]  # the record lines follow the summary
    birth = rows[f"{KG_NAME}:event:I1:BIRT"]
    assert birth["title"] == "John Hartwell" and birth["genre"] == "hartwell-I1"
    assert birth["timestamp"] == "1820"
    # A family belongs to the husband's line, even when the wife is the blood relative.
    assert rows[f"{KG_NAME}:family:F3"]["genre"] == "pryce-I9"
    assert all(r["genre"] is None for r in rows.values() if r["kind"] == "place")


def test_the_pack_answers_a_surname_and_a_line_scope(
    sample_pack: Path, sample_kg: GenealogyKG
) -> None:
    query = "Pryce"
    vector = sample_kg.embedder.embed_query(query)
    hits, _ = search_pack(sample_pack / "family.pack", vector, query, k=5, genre="pryce-I9")
    assert hits and all(h["genre"] == "pryce-I9" for h in hits)
    assert any("Pryce" in (h["author"] or "") for h in hits)


def test_manifest_and_golden_describe_the_pack(sample_pack: Path) -> None:
    manifest = json.loads((sample_pack / "manifest.json").read_text())
    assert manifest["embedder"]["model"] == "BAAI/bge-small-en-v1.5"
    assert manifest["packs"][0]["name"] == "family.pack"
    assert manifest["packs"][0]["sidecar"]["name"] == "family.vectors"
    assert manifest["privacy"]["living_cutoff_years"] == 100
    golden = json.loads((sample_pack / "golden.json").read_text())
    assert golden["queries"] and set(golden["queries"][0]["packs"]) == {"family"}


# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------


def test_living_people_are_left_out_of_the_pack(tmp_path: Path) -> None:
    kg = _build(_repo_dir(tmp_path), LIVING_GED, cutoff=100)
    result = export_swift(kg, tmp_path / "out", PRIVACY)
    assert result.redacted == 2
    rows = _rows(tmp_path / "out")
    assert f"{KG_NAME}:person:D" not in rows
    blob = (tmp_path / "out" / "family.pack").read_bytes()
    assert LIVING_NAME.encode() not in blob and b"Zephyrine" not in blob


def test_a_name_split_across_a_page_boundary_is_still_caught(tmp_path: Path) -> None:
    """SQLite splits a long cell across overflow pages, each led by a page pointer.

    At this position in a 9,000-character cell the name straddles a page
    boundary, so it is not in the file's raw bytes at all; the scan reads the
    pack through SQL and must still find it.
    """
    content = "x" * 819 + f" {LIVING_NAME} " + "z" * (9000 - 819)
    pack = tmp_path / "family.pack"
    write_passage_pack(
        pack,
        [Passage(id="a", kg_name="g", kg_kind="g", kind="person", content=content)],
        dim=4,
        embed_model="m",
    )
    assert LIVING_NAME.encode() not in pack.read_bytes()
    assert scan_for_names(tmp_path, {LIVING_NAME: "D"}) == [("family.pack", "D")]


def test_export_swift_refuses_an_unredacted_store(tmp_path: Path) -> None:
    kg = _build(_repo_dir(tmp_path), LIVING_GED, cutoff=0)
    with pytest.raises(ExportError, match="not redacted"):
        export_swift(kg, tmp_path / "out", PRIVACY)
    assert not (tmp_path / "out").exists()


# ---------------------------------------------------------------------------
# The embedder files
# ---------------------------------------------------------------------------


def test_embedder_is_copied_in_and_survives_a_forced_rerun(
    sample_kg: GenealogyKG, tmp_path: Path
) -> None:
    _fake_embedder(tmp_path / "embedder")
    out = tmp_path / "out"
    result = export_swift(
        sample_kg, out, PRIVACY, golden=False, embedder_from=tmp_path / "embedder"
    )
    assert result.embedder
    with pytest.raises(ExportError, match="--force"):
        export_swift(sample_kg, out, PRIVACY, golden=False)
    assert all((out / name).exists() for name in EMBEDDER_FILES)  # a refusal loses nothing
    export_swift(sample_kg, out, PRIVACY, golden=False, force=True)
    assert all((out / name).exists() for name in EMBEDDER_FILES)


def test_an_embedder_for_another_model_is_refused(sample_kg: GenealogyKG, tmp_path: Path) -> None:
    _fake_embedder(tmp_path / "embedder", model="some/other-model")
    with pytest.raises(ExportError, match="these vectors need"):
        export_swift(sample_kg, tmp_path / "out", PRIVACY, embedder_from=tmp_path / "embedder")


def test_a_lexical_only_pack_has_no_sidecar_or_golden(
    sample_kg: GenealogyKG, tmp_path: Path
) -> None:
    result = export_swift(sample_kg, tmp_path / "out", PRIVACY, vectors=False)
    assert result.vectors == 0
    assert not (tmp_path / "out" / "family.vectors").exists()
    assert not (tmp_path / "out" / "golden.json").exists()


def test_cli_export_swift(sample_kg: GenealogyKG, tmp_path: Path) -> None:
    result = CliRunner().invoke(
        cli,
        [
            "export-swift",
            "--repo",
            str(sample_kg.repo_root),
            "--out",
            str(tmp_path / "out"),
            "--living-cutoff",
            "100",
            "--no-golden",
            "--verify",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "recall@10" in result.output
    assert "No Core ML embedder" in result.output
