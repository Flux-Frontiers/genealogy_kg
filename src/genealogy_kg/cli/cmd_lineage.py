"""``genkg ancestors`` and ``genkg descendants``.

Both print an ASCII family tree (see ``genealogy_kg.lineage.ascii_tree``);
the difference is only which direction they walk.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, generations_option, open_kg, repo_option


@cli.command("ancestors")
@click.argument("xref")
@repo_option
@db_option
@generations_option
def ancestors(xref: str, repo: str, db: str | None, generations: int) -> None:
    """Print an ASCII tree of a person's ancestors (xref such as I7)."""
    try:
        with open_kg(repo, db) as kg:
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
    try:
        with open_kg(repo, db) as kg:
            tree = kg.tree(xref, direction="descendants", generations=generations)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    click.echo(str(tree))
