"""Tests for genealogy_kg.snapshots over kg_utils.snapshots."""

from __future__ import annotations

from pathlib import Path

import pytest

from genealogy_kg.module import GenealogyKG
from genealogy_kg.snapshots import SnapshotManager


def _built(corpus_root: Path) -> GenealogyKG:
    kg = GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")])
    kg.build(wipe=True)
    return kg


def test_capture_records_genealogy_metrics(corpus_root: Path) -> None:
    kg = _built(corpus_root)
    mgr = SnapshotManager(corpus_root / ".genealogykg" / "snapshots")
    snap = mgr.capture_genealogy(
        kg.stats(), kg.analysis(), version="0.3.0", branch="main", tree_hash="a" * 40
    )
    assert snap.metrics["people"] == 12
    assert snap.metrics["families"] == 4
    assert snap.metrics["generation_depth"] == 4
    assert snap.metrics["surname_count"] == 5
    assert snap.metrics["total_nodes"] == kg.stats()["total_nodes"]
    assert snap.version == "0.3.0"


def test_save_list_and_diff_report_people_delta(corpus_root: Path) -> None:
    kg = _built(corpus_root)
    mgr = SnapshotManager(corpus_root / ".genealogykg" / "snapshots")
    stats, analysis = kg.stats(), kg.analysis()

    first = mgr.capture_genealogy(
        stats, analysis, version="0.3.0", branch="main", tree_hash="a" * 40
    )
    assert mgr.save_snapshot(first) is not None

    # Pretend two people and one family arrived in the next build.
    stats2 = {**stats, "total_nodes": stats["total_nodes"] + 3}
    analysis2 = {**analysis, "counts": {**analysis["counts"], "person": 14, "family": 5}}
    second = mgr.capture_genealogy(
        stats2, analysis2, version="0.3.1", branch="main", tree_hash="b" * 40
    )
    assert second.vs_previous == {
        "nodes": 3,
        "edges": 0,
        "people": 2,
        "families": 1,
        "events": 0,
        "places": 0,
    }
    mgr.save_snapshot(second)

    listed = mgr.list_snapshots()
    assert [s["key"] for s in listed] == ["b" * 40, "a" * 40]

    diff = mgr.diff_snapshots("a" * 40, "b" * 40)
    assert diff["delta"]["people"] == 2
    assert diff["delta"]["families"] == 1


def test_save_rejects_an_unbuilt_store(corpus_root: Path) -> None:
    mgr = SnapshotManager(corpus_root / ".genealogykg" / "snapshots")
    snap = mgr.capture_genealogy({}, {}, version="0.3.0", branch="main", tree_hash="c" * 40)
    with pytest.raises(ValueError):
        mgr.save_snapshot(snap)
