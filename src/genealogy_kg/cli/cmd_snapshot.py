"""``genealogykg snapshot`` -- save, list, show and diff metric snapshots.

Phase 3 work.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from genealogy_kg.cli.group import cli


@cli.group("snapshot")
def snapshot() -> None:
    """Manage point-in-time metric snapshots of the graph."""
