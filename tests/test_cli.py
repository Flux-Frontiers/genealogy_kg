"""CLI acceptance tests via click.testing.CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from genealogy_kg.cli import cli


def test_build_query_pack_status_analyze_round_trip(corpus_root: Path) -> None:
    runner = CliRunner()

    source = str(corpus_root / "family.ged")
    result = runner.invoke(cli, ["build", "--repo", str(corpus_root), "--source", source])
    assert result.exit_code == 0, result.output
    assert "Nodes:" in result.output
    assert (corpus_root / ".genealogykg" / "config.json").exists()

    status = runner.invoke(cli, ["status", "--repo", str(corpus_root)])
    assert status.exit_code == 0, status.output
    assert "family.ged" in status.output

    query = runner.invoke(cli, ["query", "Cincinnati ironmonger", "--repo", str(corpus_root)])
    assert query.exit_code == 0, query.output
    payload = json.loads(query.output)
    assert payload["nodes"]

    pack = runner.invoke(cli, ["pack", "Hartwell marriage", "--repo", str(corpus_root)])
    assert pack.exit_code == 0, pack.output
    assert "family.ged" in pack.output

    analyze = runner.invoke(cli, ["analyze", "--repo", str(corpus_root)])
    assert analyze.exit_code == 0, analyze.output
    assert "People: 12" in analyze.output


def test_build_without_source_or_config_fails_clearly(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["build", "--repo", str(tmp_path)])
    assert result.exit_code != 0
    assert "No GEDCOM sources configured" in result.output
