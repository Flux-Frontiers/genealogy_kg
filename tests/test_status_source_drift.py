"""``genkg status`` reports source files edited since the build (fleet sweep item 97).

kgmodule-utils 0.32.0 records a hash of each GEDCOM at build, and ``pack()``
omits the snippets of a file whose bytes changed since. ``status`` is where a
user sees why: it names the files that no longer match the store.
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from genealogy_kg.cli import cli


def _build(corpus_root: Path) -> CliRunner:
    runner = CliRunner()
    source = str(corpus_root / "family.ged")
    result = runner.invoke(cli, ["build", "--repo", str(corpus_root), "--source", source])
    assert result.exit_code == 0, result.output
    return runner


def test_status_says_the_sources_match_after_a_build(corpus_root: Path) -> None:
    runner = _build(corpus_root)
    status = runner.invoke(cli, ["status", "--repo", str(corpus_root)])
    assert status.exit_code == 0, status.output
    assert "Source files: unchanged since the build" in status.output


def test_status_and_pack_after_the_gedcom_is_edited(corpus_root: Path) -> None:
    runner = _build(corpus_root)
    ged = corpus_root / "family.ged"
    ged.write_bytes(ged.read_bytes().replace(b"\n", b"\n0 NOTE inserted line\n", 1))

    status = runner.invoke(cli, ["status", "--repo", str(corpus_root)])
    assert status.exit_code == 0, status.output
    assert "Source files: 1 changed since the build" in status.output
    assert "family.ged" in status.output
    assert "rebuild" in status.output

    pack = runner.invoke(cli, ["pack", "Hartwell marriage", "--repo", str(corpus_root)])
    assert pack.exit_code == 0, pack.output
    assert "changed since the graph was built; its snippets are omitted" in pack.output


def test_status_on_a_store_without_hashes(corpus_root: Path) -> None:
    runner = _build(corpus_root)
    from genealogy_kg.module import GenealogyKG

    kg = GenealogyKG(corpus_root, sources=[corpus_root / "family.ged"])
    kg.store.write([], [], wipe=False)  # a write without record_sources(), as old stores have
    kg.close()
    status = runner.invoke(cli, ["status", "--repo", str(corpus_root)])
    assert status.exit_code == 0, status.output
    assert "Source files: no hashes recorded; rebuild to check them" in status.output
