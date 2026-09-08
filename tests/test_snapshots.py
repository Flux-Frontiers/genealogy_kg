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
        stats, analysis, version="0.3.0", branch="main", tree_hash="a" * 40, key="v0.3.0"
    )
    assert mgr.save_snapshot(first) is not None

    # Pretend two people and one family arrived in the next build.
    stats2 = {**stats, "total_nodes": stats["total_nodes"] + 3}
    analysis2 = {**analysis, "counts": {**analysis["counts"], "person": 14, "family": 5}}
    second = mgr.capture_genealogy(
        stats2, analysis2, version="0.3.1", branch="main", tree_hash="b" * 40, key="v0.3.1"
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
    assert [s["key"] for s in listed] == ["v0.3.1", "v0.3.0"]

    diff = mgr.diff_snapshots("v0.3.0", "v0.3.1")
    assert diff["delta"]["people"] == 2
    assert diff["delta"]["families"] == 1


def test_save_rejects_an_unbuilt_store(corpus_root: Path) -> None:
    mgr = SnapshotManager(corpus_root / ".genealogykg" / "snapshots")
    snap = mgr.capture_genealogy({}, {}, version="0.3.0", branch="main", tree_hash="c" * 40)
    with pytest.raises(ValueError):
        mgr.save_snapshot(snap)


def test_save_and_reload_persists_key_subject_and_tool(corpus_root: Path) -> None:
    """The round trip this repo had no test for at all.

    Until 0.2.0 ``capture_genealogy`` took neither ``key`` nor ``subject`` and
    passed neither to the base, so a release tag could not become the key and
    the subject was always empty. On the old ``kgmodule-utils>=0.18.1`` floor
    the key fell back to the git tree hash, which names a tree that is never
    committed because it is read before ``git add`` stages the snapshot.
    """
    import json

    kg = _built(corpus_root)
    mgr = SnapshotManager(corpus_root / ".genealogykg" / "snapshots")
    snap = mgr.capture_genealogy(
        kg.stats(),
        kg.analysis(),
        version="9.9.9",
        branch="main",
        tree_hash="e" * 40,
        key="v9.9.9",
        subject="tree:family",
    )
    saved = mgr.save_snapshot(snap)
    assert saved is not None and saved.name == "v9.9.9.json"

    on_disk = json.loads(saved.read_text(encoding="utf-8"))
    assert on_disk["key"] == "v9.9.9"
    assert on_disk["subject"] == "tree:family"
    assert on_disk["tree_hash"] == "e" * 40
    assert on_disk["tool"] == "genealogy-kg"
    assert on_disk["tool_version"]

    reloaded = mgr.load_snapshot("v9.9.9")
    assert reloaded is not None
    assert reloaded.key == "v9.9.9"
    assert reloaded.subject == "tree:family"
    assert reloaded.tool == "genealogy-kg"


def test_capture_without_a_key_does_not_use_the_tree_hash(corpus_root: Path) -> None:
    """An omitted key is a UTC timestamp, never the tree hash.

    The hash is read before ``git add`` stages the snapshot, so it names a tree
    that never gets committed and cannot be resolved afterwards.
    """
    kg = _built(corpus_root)
    mgr = SnapshotManager(corpus_root / ".genealogykg" / "snapshots")
    snap = mgr.capture_genealogy(kg.stats(), kg.analysis(), version="0.3.0", tree_hash="a" * 40)
    assert snap.key != "a" * 40
    assert snap.key.startswith("20")
    assert snap.tree_hash == "a" * 40


def test_package_name_comes_from_the_class_attribute(corpus_root: Path) -> None:
    """Replaces the deleted __init__, whose only job was this string.

    Against kgmodule-utils < 0.20.0 the base has no package_name class
    attribute, so every snapshot's tool field would read "kg-utils".
    """
    mgr = SnapshotManager(corpus_root / ".genealogykg" / "snapshots")
    assert SnapshotManager.package_name == "genealogy-kg"
    assert mgr.package_name == "genealogy-kg"
