"""genealogy_kg/snapshots.py

Thin layer over ``kg_utils.snapshots`` adding genealogy metrics (people,
families, generation depth) to each snapshot.

Phase 3 work. See docs/DESIGN.md.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from kg_utils.snapshots import SnapshotManager as _BaseSnapshotManager


class GenealogySnapshotManager(_BaseSnapshotManager):
    """Snapshot manager defaulting ``package_name`` to ``genealogy-kg``."""


SnapshotManager = GenealogySnapshotManager
