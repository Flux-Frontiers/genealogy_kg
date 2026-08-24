"""``genealogykg query`` and ``genealogykg pack``.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, k_option, repo_option, vectors_option
from genealogy_kg.module import GenealogyKG


def _kg(repo: str, db: str | None, vectors: str | None) -> GenealogyKG:
    return GenealogyKG(
        repo_root=Path(repo).resolve(),
        db_path=Path(db) if db else None,
        vectors_path=Path(vectors) if vectors else None,
    )


@cli.command("query")
@click.argument("q")
@repo_option
@db_option
@vectors_option
@k_option
@click.option("--hop", default=1, show_default=True, help="Graph expansion hops.")
def query(q: str, repo: str, db: str | None, vectors: str | None, k: int, hop: int) -> None:
    """Search the graph and print ranked nodes as JSON."""
    result = _kg(repo, db, vectors).query(q, k=k, hop=hop)
    click.echo(result.to_json())


@cli.command("pack")
@click.argument("q")
@repo_option
@db_option
@vectors_option
@k_option
@click.option("--output", "-o", type=click.Path(), default=None, help="Write Markdown here.")
def pack(
    q: str, repo: str, db: str | None, vectors: str | None, k: int, output: str | None
) -> None:
    """Print the GEDCOM records behind a query as a Markdown snippet pack."""
    md = _kg(repo, db, vectors).pack(q, k=k).to_markdown()
    if output:
        Path(output).write_text(md, encoding="utf-8")
        click.echo(f"Wrote {output}")
    else:
        click.echo(md)
