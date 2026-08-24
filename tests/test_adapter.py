"""Tests for genealogy_kg.adapter.GenealogyKGAdapter.

Requires the ``adapter`` extra (kg-rag); skipped automatically when it isn't
installed, matching the convention used elsewhere in the fleet for this
optional dependency.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("kg_rag", reason="kg_rag not installed -- adapter test skipped")

from kg_rag.primitives import KGEntry, KGKind  # noqa: E402

from genealogy_kg.adapter import GenealogyKGAdapter  # noqa: E402
from genealogy_kg.module import GenealogyKG  # noqa: E402


def _entry(repo_root: Path) -> KGEntry:
    kg = GenealogyKG(repo_root=repo_root, sources=[Path("family.ged")])
    kg.build(wipe=True)
    return KGEntry(
        name="genealogy-test",
        kind=KGKind.GENEALOGY,
        repo_path=repo_root,
        venv_path=repo_root / ".venv",
        sqlite_path=kg.db_path,
        vectors_path=kg.vectors_path if kg.vectors_path.exists() else None,
        builder_version="1.2.3",
    )


def test_stats_matches_the_kg_rag_field_set(corpus_root: Path) -> None:
    adapter = GenealogyKGAdapter(_entry(corpus_root))
    stats = adapter.stats()

    # Same field set as kg_rag.adapters.genealogy_adapter.GenealogyKGAdapter's
    # stats() -- kg-rag's orchestrator/UI code expects this shape uniformly
    # across every federated adapter.
    assert stats["kind"] == "genealogy"
    assert stats["kg_name"] == "genealogy-test"
    assert stats["builder_version"] == "1.2.3"
    assert stats["available"] is True
    assert stats["db_size_mb"] >= 0.0
    assert stats["node_count"] > 0
    assert stats["edge_count"] > 0
    assert stats["person_count"] == 12
    assert stats["family_count"] == 4


def test_stats_error_path_keeps_the_kg_rag_field_set(corpus_root: Path) -> None:
    adapter = GenealogyKGAdapter(_entry(corpus_root))
    adapter._load()
    adapter._kg.stats = lambda: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[method-assign]

    stats = adapter.stats()

    assert stats["kind"] == "genealogy"
    assert stats["kg_name"] == "genealogy-test"
    assert stats["available"] is True
    assert stats["db_size_mb"] >= 0.0
    assert stats["error"] == "boom"


def test_is_available_reflects_entry_is_built(corpus_root: Path) -> None:
    adapter = GenealogyKGAdapter(_entry(corpus_root))
    assert adapter.is_available() is True
