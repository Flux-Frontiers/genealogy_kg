"""``genealogykg status`` -- store location, sources and counts.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, repo_option


@cli.command("status")
@repo_option
@db_option
def status(repo: str, db: str | None) -> None:
    """Show whether the store is built, its sources, and node/edge counts."""
    raise NotImplementedError("Phase 1")
