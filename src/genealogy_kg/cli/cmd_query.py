"""``genkg query`` and ``genkg pack``.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import (
    db_option,
    hop_option,
    k_option,
    open_kg,
    repo_option,
    vectors_option,
)


@cli.command("query")
@click.argument("q")
@repo_option
@db_option
@vectors_option
@k_option
@hop_option
def query(q: str, repo: str, db: str | None, vectors: str | None, k: int, hop: int) -> None:
    """Search the graph and print ranked nodes as JSON."""
    try:
        with open_kg(repo, db, vectors) as kg:
            result = kg.query(q, k=k, hop=hop)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
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
    try:
        with open_kg(repo, db, vectors) as kg:
            md = kg.pack(q, k=k).to_markdown()
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    if output:
        Path(output).write_text(md, encoding="utf-8")
        click.echo(f"Wrote {output}")
    else:
        click.echo(md)
