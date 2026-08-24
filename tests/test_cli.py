"""CLI acceptance tests via click.testing.CliRunner."""

from __future__ import annotations

import json
import os
import subprocess
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


def test_ancestors_and_descendants_print_ascii_trees(corpus_root: Path) -> None:
    runner = CliRunner()
    source = str(corpus_root / "family.ged")
    build = runner.invoke(cli, ["build", "--repo", str(corpus_root), "--source", source])
    assert build.exit_code == 0, build.output

    desc = runner.invoke(cli, ["descendants", "I1", "--repo", str(corpus_root)])
    assert desc.exit_code == 0, desc.output
    assert "John Hartwell" in desc.output
    assert "William Hartwell" in desc.output

    anc = runner.invoke(cli, ["ancestors", "I12", "--repo", str(corpus_root)])
    assert anc.exit_code == 0, anc.output
    assert "Margaret Hartwell" in anc.output
    assert "John Hartwell" in anc.output


def test_build_without_source_or_config_fails_clearly(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["build", "--repo", str(tmp_path)])
    assert result.exit_code != 0
    assert "No GEDCOM sources configured" in result.output


def test_snapshot_save_list_show_diff(corpus_root: Path) -> None:
    runner = CliRunner()
    repo = str(corpus_root)
    build = runner.invoke(
        cli, ["build", "--repo", repo, "--source", str(corpus_root / "family.ged")]
    )
    assert build.exit_code == 0, build.output

    save = runner.invoke(
        cli,
        ["snapshot", "save", "0.3.0", "--repo", repo, "--tree-hash", "a" * 40, "--branch", "main"],
    )
    assert save.exit_code == 0, save.output
    assert "people:" in save.output and "12" in save.output
    assert (corpus_root / ".genealogykg" / "snapshots" / "manifest.json").exists()

    listed = runner.invoke(cli, ["snapshot", "list", "--repo", repo])
    assert listed.exit_code == 0, listed.output
    assert "a" * 12 in listed.output and "0.3.0" in listed.output

    shown = runner.invoke(cli, ["snapshot", "show", "a" * 40, "--repo", repo])
    assert shown.exit_code == 0, shown.output
    assert "generation_depth: 4" in shown.output

    second = runner.invoke(
        cli,
        [
            "snapshot",
            "save",
            "0.3.1",
            "--repo",
            repo,
            "--tree-hash",
            "b" * 40,
            "--branch",
            "main",
            "--force",
        ],
    )
    assert second.exit_code == 0, second.output
    diff = runner.invoke(cli, ["snapshot", "diff", "a" * 40, "b" * 40, "--repo", repo])
    assert diff.exit_code == 0, diff.output
    assert "people" in diff.output and "+0" in diff.output

    missing = runner.invoke(cli, ["snapshot", "show", "nope", "--repo", repo])
    assert missing.exit_code != 0


def test_snapshot_save_without_a_store_fails_clearly(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["snapshot", "save", "--repo", str(tmp_path)])
    assert result.exit_code != 0
    assert "genkg build" in result.output


def test_build_honours_living_cutoff_from_pyproject(corpus_root: Path) -> None:
    (corpus_root / "pyproject.toml").write_text(
        '[tool.genealogykg]\nsources = ["family.ged"]\nliving_cutoff_years = 200\n'
    )
    runner = CliRunner()
    build = runner.invoke(cli, ["build", "--repo", str(corpus_root)])
    assert build.exit_code == 0, build.output
    analyze = runner.invoke(cli, ["analyze", "--repo", str(corpus_root)])
    assert "Living people redacted: 5" in analyze.output


def test_install_hooks(tmp_path: Path) -> None:
    # Strip any inherited GIT_DIR/GIT_WORK_TREE/etc: when this test itself runs
    # inside a git hook (e.g. the pre-commit hook invoking pytest), git has
    # already set these for the current process, and `git init` in a fresh
    # directory honours them over the path argument -- pointing the new repo
    # at the *outer* .git instead of tmp_path/.git.
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, env=clean_env)
    runner = CliRunner()
    result = runner.invoke(cli, ["install-hooks", "--repo", str(tmp_path)])
    assert result.exit_code == 0, result.output
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook.exists() and hook.stat().st_mode & 0o111
    assert "GENKG_SNAPSHOT" in hook.read_text()

    again = runner.invoke(cli, ["install-hooks", "--repo", str(tmp_path)])
    assert again.exit_code != 0 and "--force" in again.output
    forced = runner.invoke(cli, ["install-hooks", "--repo", str(tmp_path), "--force"])
    assert forced.exit_code == 0, forced.output


def test_install_hooks_outside_git_fails(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["install-hooks", "--repo", str(tmp_path)])
    assert result.exit_code != 0
    assert "not a git repository" in result.output
