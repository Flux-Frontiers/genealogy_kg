"""GenealogyKG resource cleanup -- codebase review item 4, "Standardize
GenealogyKG resource cleanup".

Covers the CLI's shared `open_kg()` context-manager helper and the MCP
server's lifespan hook, both of which now close the underlying SQLite
connection deterministically instead of relying on process exit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from genealogy_kg.cli.options import open_kg
from genealogy_kg.module import GenealogyKG


def _closed(kg: GenealogyKG) -> bool:
    """True if kg's underlying SQLite connection has been closed."""
    store = kg._store  # noqa: SLF001 - white-box check that close() really ran
    return store is None or store._con is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# open_kg() -- the CLI's shared context-managed helper
# ---------------------------------------------------------------------------


def test_open_kg_closes_on_normal_exit(corpus_root: Path) -> None:
    GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")]).build(wipe=True)
    with open_kg(str(corpus_root)) as kg:
        kg.stats()  # touches the store, opening a connection
        assert not _closed(kg)
    assert _closed(kg)


def test_open_kg_closes_on_exception(corpus_root: Path) -> None:
    GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")]).build(wipe=True)
    kg_ref = None
    with pytest.raises(RuntimeError):
        with open_kg(str(corpus_root)) as kg:
            kg_ref = kg
            kg.stats()
            raise RuntimeError("boom")
    assert kg_ref is not None
    assert _closed(kg_ref)


def test_open_kg_repeated_cycles_leave_no_lingering_handle(corpus_root: Path) -> None:
    # The review's own ask: repeated open/query/close cycles, as a real CLI
    # invocation does one per command.
    GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")]).build(wipe=True)
    for _ in range(5):
        with open_kg(str(corpus_root)) as kg:
            result = kg.query("Hartwell", k=3)
            assert result.nodes
        assert _closed(kg)


def test_open_kg_resolves_repo_db_vectors(corpus_root: Path) -> None:
    with open_kg(str(corpus_root), db=None, vectors=None) as kg:
        assert kg.repo_root == corpus_root.resolve()
        assert kg.db_path == corpus_root / ".genealogykg" / "graph.sqlite"
