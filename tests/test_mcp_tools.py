"""MCP tool behavioral tests -- codebase review item 6: "Invoke every MCP
tool against a small built fixture," malformed inputs, empty stores, and
living-person privacy through the MCP endpoints specifically (graph-level
redaction and pack()'s own source-grounding are already covered elsewhere;
this file covers the MCP surface on top of them).

Drives the real server through mcp.shared.memory's in-process transport,
same harness as test_mcp_lifespan.py -- an actual tool call over the MCP
protocol, not a call into the underlying GenealogyKG method.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult

from genealogy_kg import mcp_server
from genealogy_kg.module import GenealogyKG

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@asynccontextmanager
async def _session(kg: GenealogyKG) -> AsyncIterator[ClientSession]:
    mcp_server._kg = kg
    try:
        async with create_connected_server_and_client_session(mcp_server.mcp) as session:
            yield session
    finally:
        mcp_server._kg = None


def _text(result: CallToolResult) -> str:
    return "".join(c.text for c in result.content if hasattr(c, "text"))


@pytest.fixture
def built_kg(corpus_root: Path) -> GenealogyKG:
    GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")]).build(wipe=True)
    return GenealogyKG(repo_root=corpus_root)


# ---------------------------------------------------------------------------
# One happy-path call per tool
# ---------------------------------------------------------------------------


async def test_query_genealogy(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("query_genealogy", {"q": "Hartwell chemist", "k": 5})
        assert not result.isError
        assert json.loads(_text(result))["nodes"]


async def test_pack_genealogy(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("pack_genealogy", {"q": "Hartwell ironmonger", "k": 3})
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


async def test_graph_stats(built_kg: GenealogyKG) -> None:
    async with _session(built_kg) as session:
        result = await session.call_tool("graph_stats", {})
        assert not result.isError
        assert json.loads(_text(result))["total_nodes"] > 0


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
        ("query_genealogy", {"q": "", "k": 5}),
        ("query_genealogy", {"q": "chemist", "k": 0}),
        ("query_genealogy", {"q": "chemist", "k": 101}),
        ("pack_genealogy", {"q": "chemist", "max_nodes": 9999}),
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
        query_result = await session.call_tool("query_genealogy", {"q": "anyone", "k": 5})
        assert not query_result.isError
        assert json.loads(_text(query_result))["nodes"] == []

        stats_result = await session.call_tool("graph_stats", {})
        assert not stats_result.isError
        assert json.loads(_text(stats_result))["total_nodes"] == 0


# ---------------------------------------------------------------------------
# Living-person privacy through the MCP path specifically
# ---------------------------------------------------------------------------


@pytest.fixture
def redacted_kg(corpus_root: Path) -> GenealogyKG:
    GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")], living_cutoff_years=200).build(
        wipe=True
    )
    return GenealogyKG(repo_root=corpus_root, living_cutoff_years=200)


async def test_get_person_redacts_a_living_person(redacted_kg: GenealogyKG) -> None:
    async with _session(redacted_kg) as session:
        result = await session.call_tool("get_person", {"xref": "I4"})
        assert not result.isError
        assert json.loads(_text(result))["name"] == "Living"


async def test_pack_genealogy_does_not_leak_a_redacted_persons_name(
    redacted_kg: GenealogyKG,
) -> None:
    # Eliza (I4) is redacted under a 200-year cutoff. A query unrelated to
    # her own name still sweeps her in via hop expansion (pack_genealogy's
    # default hop=1, since the tool doesn't expose --hop), so this proves
    # pack()'s source-grounding redaction holds over the MCP path too, not
    # just when GenealogyKG.pack() is called directly.
    async with _session(redacted_kg) as session:
        result = await session.call_tool(
            "pack_genealogy", {"q": "John Hartwell ironmonger", "k": 5, "max_nodes": 20}
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
