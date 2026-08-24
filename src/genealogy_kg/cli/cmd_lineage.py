"""``genealogykg ancestors`` and ``genealogykg descendants``.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, repo_option

generations_option = click.option(
    "--generations", default=4, show_default=True, help="Maximum generations to walk."
)


@cli.command("ancestors")
@click.argument("xref")
@repo_option
@db_option
@generations_option
def ancestors(xref: str, repo: str, db: str | None, generations: int) -> None:
    """List the ancestors of a person (xref such as I7), nearest first."""
    raise NotImplementedError("Phase 2")


@cli.command("descendants")
@click.argument("xref")
@repo_option
@db_option
@generations_option
def descendants(xref: str, repo: str, db: str | None, generations: int) -> None:
    """List the descendants of a person (xref such as I1), nearest first."""
    raise NotImplementedError("Phase 2")
