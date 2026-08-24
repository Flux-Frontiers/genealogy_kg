"""``genealogykg build`` -- GEDCOM file(s) -> SQLite graph + sqlite-vec index.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, model_option, repo_option, vectors_option
from genealogy_kg.config import load_sources, save_sources
from genealogy_kg.module import GenealogyKG


@cli.command("build")
@repo_option
@db_option
@vectors_option
@model_option
@click.option(
    "--source",
    "sources",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False),
    help="GEDCOM file to index. Repeatable. Recorded in .genealogykg/config.json.",
)
@click.option("--no-wipe", is_flag=True, default=False, help="Keep the existing graph.")
def build(
    repo: str,
    db: str | None,
    vectors: str | None,
    model: str,
    sources: tuple[str, ...],
    no_wipe: bool,
) -> None:
    """Extract a genealogy knowledge graph from GEDCOM and build its indices."""
    repo_root = Path(repo).resolve()

    if sources:
        rel_sources = [Path(s).resolve().relative_to(repo_root) for s in sources]
        save_sources(repo_root, rel_sources)
    else:
        rel_sources = load_sources(repo_root)

    if not rel_sources:
        raise click.ClickException(
            "No GEDCOM sources configured. Pass --source, or set "
            "[tool.genealogykg] sources in pyproject.toml."
        )

    click.echo(f"Building GenealogyKG for {repo_root}")
    click.echo("  Sources: " + ", ".join(str(s) for s in rel_sources))

    kg = GenealogyKG(
        repo_root=repo_root,
        db_path=Path(db) if db else None,
        vectors_path=Path(vectors) if vectors else None,
        sources=rel_sources,
        model=model,
    )
    stats = kg.build(wipe=not no_wipe)

    click.echo("Build complete")
    click.echo(f"  Nodes: {stats.total_nodes}")
    click.echo(f"  Edges: {stats.total_edges}")
    for kind, count in sorted(stats.node_counts.items()):
        click.echo(f"    {kind}: {count}")
