"""MCP tool behavioral tests -- codebase review item 6: "Invoke every MCP
tool against a small built fixture," malformed inputs, empty stores, and
living-person privacy through the MCP endpoints specifically (graph-level
redaction and pack()'s own source-grounding are already covered elsewhere;
this file covers the MCP surface on top of them).

The server is built on kg_utils.mcp (step 2 of kgrag_priv's MCP
centralization plan): the five canonical tools under the names every fleet
server shares, then GenealogyKG's own. Each session opens its own
GenealogyKG on the repo, so these tests build a store and serve the repo.

Drives the real server through mcp.shared.memory's in-process transport,
same harness as test_mcp_lifespan.py -- an actual tool call over the MCP
protocol, not a call into the underlying GenealogyKG method.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import pytest
from click.testing import CliRunner
from kg_utils.mcp import CANONICAL_TOOLS, manifest
from kg_utils.stats import stats_problems
from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult

import genealogy_kg
from genealogy_kg.cli import cli
from genealogy_kg.mcp_server import EXTRA_TOOLS, build_server
from genealogy_kg.module import GenealogyKG

_SRC = str(Path(genealogy_kg.__file__).resolve().parents[1])

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@asynccontextmanager
async def _session(kg: GenealogyKG) -> AsyncIterator[ClientSession]:
    """Serve *kg*'s repo; the server opens its own GenealogyKG there."""
    async with create_connected_server_and_client_session(
        build_server(kg.repo_root, kg.db_path)
    ) as session:
        yield session


def _text(result: CallToolResult) -> str:
    return "".join(c.text for c in result.content if hasattr(c, "text"))


@pytest.fixture
def built_kg(corpus_root: Path) -> GenealogyKG:
    GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")]).build(wipe=True)
    return GenealogyKG(repo_root=corpus_root)


# ---------------------------------------------------------------------------
# One happy-path call per tool
# ---------------------------------------------------------------------------


async def test_query(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("query", {"q": "Hartwell chemist", "k": 5})
        assert not result.isError
        assert json.loads(_text(result))["nodes"]


async def test_pack(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("pack", {"q": "Hartwell ironmonger", "k": 3})
        assert not result.isError
        assert "Ironmonger" in _text(result)


@pytest.mark.parametrize("xref", ["I1", "@I1@", "person:I1"])
async def test_get_person_every_xref_form(built_kg: GenealogyKG, xref: str) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("get_person", {"xref": xref})
        assert not result.isError
        assert json.loads(_text(result))["id"] == "person:I1"


async def test_get_person_unknown_xref_returns_null(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("get_person", {"xref": "I999"})
        assert not result.isError
        assert _text(result).strip() == "null"


async def test_ancestors(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("ancestors", {"xref": "I12", "generations": 1})
        assert not result.isError
        assert {n["id"] for n in json.loads(_text(result))} == {"person:I7", "person:I11"}


async def test_descendants(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("descendants", {"xref": "I1", "generations": 1})
        assert not result.isError
        assert {n["id"] for n in json.loads(_text(result))} == {
            "person:I3",
            "person:I4",
            "person:I5",
        }


async def test_family_tree(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("family_tree", {"xref": "I1", "generations": 2})
        assert not result.isError
        assert "John Hartwell" in _text(result)


async def test_stats(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("stats", {})
        assert not result.isError
        stats = result.structuredContent
        assert stats_problems(stats) == []
        assert stats["kind"] == "genealogy"
        assert stats["nodes"]["by_kind"]["person"] == 12


async def test_get_node_and_neighbors(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        node = await session.call_tool("get_node", {"node_id": "person:I1"})
        near = await session.call_tool("neighbors", {"node_id": "family:F1", "direction": "in"})
        missing = await session.call_tool("get_node", {"node_id": "person:I999"})
    assert node.structuredContent["name"] == "John Hartwell"
    assert "person:I1" in {n["id"] for n in near.structuredContent["nodes"]}
    assert missing.isError and "no node with id" in _text(missing)


async def test_analyze_genealogy(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("analyze_genealogy", {})
        assert not result.isError
        assert "People: 12" in _text(result)


# ---------------------------------------------------------------------------
# Malformed input is a tool error, not a crash
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("get_person", {"xref": "I 1"}),
        ("ancestors", {"xref": "@I1"}),
        ("descendants", {"xref": "person:@I1@:extra"}),
        ("family_tree", {"xref": "I1", "generations": 0}),
        ("family_tree", {"xref": "I1", "generations": 51}),
        ("query", {"q": "", "k": 5}),
        ("query", {"q": "chemist", "k": 0}),
        ("query", {"q": "chemist", "k": 101}),
        ("pack", {"q": "chemist", "max_nodes": 9999}),
        ("neighbors", {"node_id": "person:I1", "limit": 0}),
    ],
)
async def test_malformed_input_is_a_tool_error_not_a_crash(
    built_kg: GenealogyKG, tool: str, args: dict[str, object]
) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool(tool, args)
        assert result.isError
        assert "Error executing tool" in _text(result)


# ---------------------------------------------------------------------------
# Empty store: built, but no GEDCOM records
# ---------------------------------------------------------------------------


async def test_query_and_stats_against_an_empty_store(tmp_path: Path) -> None:
    empty_ged = tmp_path / "empty.ged"
    empty_ged.write_text("0 HEAD\n1 GEDC\n2 VERS 5.5.1\n1 CHAR UTF-8\n0 TRLR\n")
    GenealogyKG(repo_root=tmp_path, sources=[Path("empty.ged")]).build(wipe=True)
    kg = GenealogyKG(repo_root=tmp_path)

    async with _session(kg) as session:
        query_result = await session.call_tool("query", {"q": "anyone", "k": 5})
        assert not query_result.isError
        assert json.loads(_text(query_result))["nodes"] == []

        stats_result = await session.call_tool("stats", {})
        assert not stats_result.isError
        assert json.loads(_text(stats_result))["nodes"]["total"] == 0


# ---------------------------------------------------------------------------
# Living-person privacy through the MCP path specifically
# ---------------------------------------------------------------------------


@pytest.fixture
def redacted_kg(corpus_root: Path) -> GenealogyKG:
    # The server opens GenealogyKG(repo_root) with no arguments, so the cutoff
    # lives where a real repo keeps it: [tool.genealogykg] in pyproject.toml.
    (corpus_root / "pyproject.toml").write_text("[tool.genealogykg]\nliving_cutoff_years = 200\n")
    GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")]).build(wipe=True)
    return GenealogyKG(repo_root=corpus_root)


async def test_get_person_redacts_a_living_person(redacted_kg: GenealogyKG) -> None:
    async with _session(redacted_kg) as session:
        result = await session.call_tool("get_person", {"xref": "I4"})
        assert not result.isError
        assert json.loads(_text(result))["name"] == "Living"


async def test_pack_does_not_leak_a_redacted_persons_name(
    redacted_kg: GenealogyKG,
) -> None:
    # Eliza (I4) is redacted under a 200-year cutoff. A query unrelated to
    # her own name still sweeps her in via hop expansion (pack's default
    # hop=1), so this proves pack()'s source-grounding redaction holds over
    # the MCP path too, not just when GenealogyKG.pack() is called directly.
    async with _session(redacted_kg) as session:
        result = await session.call_tool(
            "pack", {"q": "John Hartwell ironmonger", "k": 5, "max_nodes": 20}
        )
        assert not result.isError
        md = _text(result)
        assert "Eliza" not in md
        assert "Living" in md


async def test_ancestors_and_descendants_do_not_leak_a_redacted_persons_name(
    redacted_kg: GenealogyKG,
) -> None:
    async with _session(redacted_kg) as session:
        result = await session.call_tool("descendants", {"xref": "I1", "generations": 1})
        assert not result.isError
        names = {n.get("name") for n in json.loads(_text(result))}
        assert "Eliza Hartwell" not in names
        assert "Living" in names


async def test_no_canonical_tool_leaks_a_redacted_person(redacted_kg: GenealogyKG) -> None:
    """query, pack, get_node and neighbors, aimed straight at Eliza (I4).

    The query describes her without naming her, since both tools echo it.
    """
    q = "Hartwell daughter born 1851 in Cincinnati"
    async with _session(redacted_kg) as session:
        results = [
            await session.call_tool("query", {"q": q, "k": 10, "hop": 2}),
            await session.call_tool("pack", {"q": q, "k": 10, "hop": 2, "max_nodes": 50}),
            await session.call_tool("get_node", {"node_id": "person:I4"}),
            await session.call_tool("neighbors", {"node_id": "person:I4", "limit": 500}),
            await session.call_tool("neighbors", {"node_id": "family:F3", "limit": 500}),
            await session.call_tool("neighbors", {"node_id": "family:F1", "limit": 500}),
        ]
    for result in results:
        assert not result.isError, _text(result)
        assert "Eliza" not in _text(result)
    node = results[2].structuredContent
    assert node["name"] == "Living"
    assert "1851" not in json.dumps(node)
    # Her own node has no events: nothing at the far end of her edges is one.
    assert all(n["kind"] != "event" for n in results[3].structuredContent["nodes"])


# ---------------------------------------------------------------------------
# The tool surface and the command
# ---------------------------------------------------------------------------


def test_canonical_tools_then_the_extras(tmp_path: Path) -> None:
    names = [t["name"] for t in manifest(build_server(tmp_path))["tools"]]
    assert names == [*CANONICAL_TOOLS, *(fn.__name__ for fn in EXTRA_TOOLS)]
    assert not {"query_genealogy", "pack_genealogy", "graph_stats"} & set(names)


def test_an_unbuilt_repo_is_refused_not_served_empty(tmp_path: Path) -> None:
    async def run() -> None:
        async with create_connected_server_and_client_session(build_server(tmp_path)):
            pass

    with pytest.raises(BaseException) as info:
        anyio.run(run)
    assert "no graph at" in repr(info.value) or any(
        "no graph at" in str(e) for e in getattr(info.value, "exceptions", ())
    )
    assert not (tmp_path / ".genealogykg" / "graph.sqlite").exists()


def test_manifest_answers_without_a_graph_and_creates_nothing(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["mcp", "--repo", str(tmp_path), "--manifest"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["canonical"] == list(CANONICAL_TOOLS)
    assert json.loads(result.output)["kind"] == "genealogy"
    assert not (tmp_path / ".genealogykg").exists()


def test_both_entry_points_are_the_same_command(tmp_path: Path) -> None:
    via_cli = CliRunner().invoke(cli, ["mcp", "--repo", str(tmp_path), "--manifest"]).output
    via_script = subprocess.run(
        [
            sys.executable,
            "-c",
            "from genealogy_kg.mcp_server import main; main()",
            "--repo",
            str(tmp_path),
            "--manifest",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert json.loads(via_cli) == json.loads(via_script)


def test_sse_is_gone(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        cli, ["mcp", "--repo", str(tmp_path), "--transport", "sse", "--manifest"]
    )
    assert result.exit_code == 2


def test_other_commands_do_not_import_mcp() -> None:
    out = subprocess.run(
        [sys.executable, "-c", "import sys, genealogy_kg.cli; print('mcp' in sys.modules)"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert out == "False"


def test_stdio_subprocess_serves(built_kg: GenealogyKG) -> None:
    repo = built_kg.repo_root
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from genealogy_kg.mcp_server import main; main()", "--repo", str(repo)],
        env={**os.environ, "PYTHONPATH": _SRC},
    )

    async def run():
        with open(repo / "stderr.log", "w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as client:
                    init = await client.initialize()
                    tools = await client.list_tools()
                    stats = await client.call_tool("stats", {})
                    return init, tools, stats

    init, tools, stats = anyio.run(run)
    assert (init.serverInfo.name, init.serverInfo.version) == ("genkg", genealogy_kg.__version__)
    assert [t.name for t in tools.tools][: len(CANONICAL_TOOLS)] == list(CANONICAL_TOOLS)
    assert stats.structuredContent["nodes"]["by_kind"]["person"] == 12
