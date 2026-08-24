"""Phase 0 smoke tests: the package installs, versions agree, the CLI and MCP
entry points import, and the fixture GEDCOM parses.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from click.testing import CliRunner

import genealogy_kg
from genealogy_kg.cli import cli

REPO = Path(__file__).resolve().parents[1]


def test_version_matches_pyproject() -> None:
    data = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert genealogy_kg.__version__ == data["project"]["version"]


def test_cli_version_flag() -> None:
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert genealogy_kg.__version__ in result.output


def test_cli_registers_every_command() -> None:
    expected = {
        "build",
        "query",
        "pack",
        "ancestors",
        "descendants",
        "analyze",
        "status",
        "snapshot",
    }
    assert expected <= set(cli.commands)


def test_mcp_server_imports_and_declares_tools() -> None:
    from genealogy_kg import mcp_server

    names = {t.name for t in mcp_server.mcp._tool_manager.list_tools()}
    assert {
        "query_genealogy",
        "pack_genealogy",
        "get_person",
        "ancestors",
        "descendants",
        "graph_stats",
        "analyze_genealogy",
    } <= names


def test_fixture_gedcom_parses(sample_ged: Path) -> None:
    from ged4py.parser import GedcomReader

    with GedcomReader(str(sample_ged)) as reader:
        individuals = list(reader.records0("INDI"))
        families = list(reader.records0("FAM"))
        sources = list(reader.records0("SOUR"))
    assert len(individuals) == 12
    assert len(families) == 4
    assert len(sources) == 2
    assert individuals[0].name.format() == "John Hartwell"
