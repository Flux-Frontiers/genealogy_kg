"""The server opens the graph per session and closes it after -- codebase
review item 4, "Standardize GenealogyKG resource cleanup", recommended
addition: "Close the MCP server's long-lived graph instance during server
shutdown if the framework exposes a lifecycle hook."

kg_utils.mcp's lifespan does this for every fleet server, replacing the
module-level ``_kg`` this file used to patch.

Drives the real server through ``mcp.shared.memory``'s in-process transport
-- an actual ``Server.run()``/lifespan cycle, not a mock.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from genealogy_kg.mcp_server import build_server
from genealogy_kg.module import GenealogyKG

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_the_session_opens_the_graph_and_closes_it(
    corpus_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")]).build(wipe=True)

    closed: list[GenealogyKG] = []
    real_close = GenealogyKG.close

    def counting_close(self: GenealogyKG) -> None:
        closed.append(self)
        real_close(self)

    monkeypatch.setattr(GenealogyKG, "close", counting_close)
    async with create_connected_server_and_client_session(build_server(corpus_root)) as session:
        result = await session.call_tool("stats", {})
        assert not result.isError
        assert closed == [], "the graph stays open for the whole session"

    # The server task has fully unwound by the time the block above exits.
    assert len(closed) == 1
    assert closed[0]._store is not None  # noqa: SLF001 - the tool call opened it
    assert closed[0]._store._con is None  # noqa: SLF001 - and the lifespan closed it
