"""genealogy_kg/snapshots.py

Thin layer over ``kg_utils.snapshots`` adding genealogy metrics (people,
families, events, places, generation depth, surnames, unlinked people) to
each snapshot, and reporting people/family deltas alongside the shared
node/edge ones.

Usage
-----
>>> from genealogy_kg.snapshots import SnapshotManager
>>> mgr = SnapshotManager(".genealogykg/snapshots")
>>> snap = mgr.capture_genealogy(kg.stats(), kg.analysis())
>>> mgr.save_snapshot(snap)

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kg_utils.snapshots import PruneResult as PruneResult  # noqa: F401 -- re-export
from kg_utils.snapshots import Snapshot
from kg_utils.snapshots import SnapshotManager as _BaseSnapshotManager

#: Metric keys ``snapshot list``/``diff`` show and ``_compute_delta_from_metrics`` reports.
GENEALOGY_METRICS: tuple[str, ...] = ("people", "families", "events", "places")


class GenealogySnapshotManager(_BaseSnapshotManager):
    """Snapshot manager for ``.genealogykg/snapshots``.

    :param snapshots_dir: Snapshot directory.
    """

    def __init__(self, snapshots_dir: Path | str) -> None:
        super().__init__(snapshots_dir, package_name="genealogy-kg")

    def capture_genealogy(
        self,
        stats: dict[str, Any],
        analysis: dict[str, Any],
        *,
        version: str | None = None,
        branch: str | None = None,
        tree_hash: str = "",
    ) -> Snapshot:
        """Capture a snapshot from ``stats()`` and ``analysis()`` output.

        :param stats: ``GenealogyKG.stats()``.
        :param analysis: ``GenealogyKG.analysis()``.
        :param version: Version string; the installed package version if ``None``.
        :param branch: Git branch; auto-detected if ``None``.
        :param tree_hash: Git tree hash; auto-detected if empty.
        :return: A :class:`~kg_utils.snapshots.Snapshot`, not yet saved.
        """
        counts = analysis.get("counts", {})
        metrics: dict[str, Any] = {
            "total_nodes": stats.get("total_nodes", 0),
            "total_edges": stats.get("total_edges", 0),
            "node_counts": stats.get("node_counts", {}),
            "edge_counts": stats.get("edge_counts", {}),
            "people": counts.get("person", 0),
            "families": counts.get("family", 0),
            "events": counts.get("event", 0),
            "places": counts.get("place", 0),
            "sources": counts.get("source", 0),
            "generation_depth": analysis.get("generation_depth", 0),
            "surname_count": len(analysis.get("surnames", {})),
            "unlinked_people": len(analysis.get("unlinked_people", [])),
            "living_redacted": analysis.get("living_redacted", 0),
        }
        return super().capture(
            version=version, branch=branch, graph_stats_dict=metrics, tree_hash=tree_hash
        )

    def get_previous(self, key: str) -> Snapshot | None:
        """Return the snapshot before ``key`` by timestamp.

        The base class knows only saved keys, so a freshly captured (unsaved)
        snapshot would get no ``vs_previous``; for an unknown key this falls
        back to the most recently saved snapshot instead, as ``diary_kg``
        does.

        :param key: Tree hash of the snapshot being placed.
        :return: The previous snapshot, or ``None`` when there is none.
        """
        manifest = self.load_manifest()
        if not any(s.get("key") == key for s in manifest.snapshots):
            if not manifest.snapshots:
                return None
            latest = max(manifest.snapshots, key=lambda s: s.get("timestamp", ""))
            return self.load_snapshot(latest["key"])
        return super().get_previous(key)

    def _compute_delta_from_metrics(
        self, new_m: dict[str, Any], old_m: dict[str, Any]
    ) -> dict[str, Any]:
        delta = super()._compute_delta_from_metrics(new_m, old_m)
        for key in GENEALOGY_METRICS:
            delta[key] = new_m.get(key, 0) - old_m.get(key, 0)
        return delta


SnapshotManager = GenealogySnapshotManager

__all__ = ["GenealogySnapshotManager", "SnapshotManager", "Snapshot", "GENEALOGY_METRICS"]
