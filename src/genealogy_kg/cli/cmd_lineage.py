"""``genealogykg ancestors`` and ``genealogykg descendants``.

Both print an ASCII family tree (see ``genealogy_kg.lineage.ascii_tree``);
the difference is only which direction they walk.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, repo_option
from genealogy_kg.module import GenealogyKG

generations_option = click.option(
    "--generations", default=4, show_default=True, help="Maximum generations to walk."
)


@cli.command("ancestors")
@click.argument("xref")
@repo_option
@db_option
@generations_option
def ancestors(xref: str, repo: str, db: str | None, generations: int) -> None:
    """Print an ASCII tree of a person's ancestors (xref such as I7)."""
    kg = GenealogyKG(repo_root=Path(repo).resolve(), db_path=Path(db) if db else None)
    click.echo(str(kg.tree(xref, direction="ancestors", generations=generations)))


@cli.command("descendants")
@click.argument("xref")
@repo_option
@db_option
@generations_option
def descendants(xref: str, repo: str, db: str | None, generations: int) -> None:
    """Print an ASCII tree of a person's descendants (xref such as I1)."""
    kg = GenealogyKG(repo_root=Path(repo).resolve(), db_path=Path(db) if db else None)
    click.echo(str(kg.tree(xref, direction="descendants", generations=generations)))
