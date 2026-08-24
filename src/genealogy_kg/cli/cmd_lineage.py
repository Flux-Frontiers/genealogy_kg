"""``genkg ancestors`` and ``genkg descendants``.

Both print an ASCII family tree (see ``genealogy_kg.lineage.ascii_tree``);
the difference is only which direction they walk.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, generations_option, repo_option
from genealogy_kg.module import GenealogyKG


@cli.command("ancestors")
@click.argument("xref")
@repo_option
@db_option
@generations_option
def ancestors(xref: str, repo: str, db: str | None, generations: int) -> None:
    """Print an ASCII tree of a person's ancestors (xref such as I7)."""
    kg = GenealogyKG(repo_root=Path(repo).resolve(), db_path=Path(db) if db else None)
    try:
        tree = kg.tree(xref, direction="ancestors", generations=generations)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    click.echo(str(tree))


@cli.command("descendants")
@click.argument("xref")
@repo_option
@db_option
@generations_option
def descendants(xref: str, repo: str, db: str | None, generations: int) -> None:
    """Print an ASCII tree of a person's descendants (xref such as I1)."""
    kg = GenealogyKG(repo_root=Path(repo).resolve(), db_path=Path(db) if db else None)
    try:
        tree = kg.tree(xref, direction="descendants", generations=generations)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    click.echo(str(tree))
