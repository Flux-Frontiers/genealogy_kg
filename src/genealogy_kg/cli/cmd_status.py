"""``genealogykg status`` -- store location, sources and counts.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, repo_option
from genealogy_kg.config import load_sources
from genealogy_kg.module import GenealogyKG


@cli.command("status")
@repo_option
@db_option
def status(repo: str, db: str | None) -> None:
    """Show whether the store is built, its sources, and node/edge counts."""
    repo_root = Path(repo).resolve()
    kg = GenealogyKG(repo_root=repo_root, db_path=Path(db) if db else None)
    sources = kg.sources if kg.sources is not None else load_sources(repo_root)
    source_line = "Sources: " + (", ".join(str(s) for s in sources) or "(none configured)")

    if not kg.db_path.exists():
        click.echo(f"No store built yet at {kg.db_path}")
        click.echo(source_line)
        return

    stats = kg.stats()
    click.echo(f"Store: {kg.db_path}")
    click.echo(source_line)
    click.echo(f"Nodes: {stats['total_nodes']}  Edges: {stats['total_edges']}")
    for kind, count in sorted(stats.get("node_counts", {}).items()):
        click.echo(f"  {kind}: {count}")
