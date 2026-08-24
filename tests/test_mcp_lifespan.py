"""The MCP server's lifespan hook closes the graph's SQLite connection on
shutdown -- codebase review item 4, "Standardize GenealogyKG resource
cleanup", recommended addition: "Close the MCP server's long-lived graph
instance during server shutdown if the framework exposes a lifecycle hook."
It does (FastMCP's ``lifespan=``), and both the stdio and SSE transports
route through the same underlying ``Server.run()``, so this fires either
way.

Drives the real server through ``mcp.shared.memory``'s in-process transport
-- an actual ``Server.run()``/lifespan cycle, not a mock.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from genealogy_kg import mcp_server
from genealogy_kg.module import GenealogyKG

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_lifespan_closes_kg_on_server_shutdown(corpus_root: Path) -> None:
    GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")]).build(wipe=True)
    kg = GenealogyKG(repo_root=corpus_root)
    mcp_server._kg = kg
    try:
        async with create_connected_server_and_client_session(mcp_server.mcp) as session:
            result = await session.call_tool("graph_stats", {})
            assert not result.isError

        # The server task has fully unwound by the time the block above
        # exits, so the lifespan's `finally: kg.close()` has already run.
        assert kg._store is not None  # noqa: SLF001 - the tool call opened it
        assert kg._store._con is None  # noqa: SLF001 - and the lifespan closed it
    finally:
        mcp_server._kg = None


async def test_lifespan_is_a_noop_when_kg_was_never_set() -> None:
    # main() always sets _kg before mcp.run(), but the lifespan itself
    # should not blow up if it somehow runs first.
    assert mcp_server._kg is None
    async with create_connected_server_and_client_session(mcp_server.mcp):
        pass
    assert mcp_server._kg is None
