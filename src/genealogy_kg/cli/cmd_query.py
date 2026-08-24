"""``genealogykg query`` and ``genealogykg pack``.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, k_option, repo_option, vectors_option


@cli.command("query")
@click.argument("q")
@repo_option
@db_option
@vectors_option
@k_option
@click.option("--hop", default=1, show_default=True, help="Graph expansion hops.")
def query(q: str, repo: str, db: str | None, vectors: str | None, k: int, hop: int) -> None:
    """Search the graph and print ranked nodes."""
    raise NotImplementedError("Phase 1")


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
    raise NotImplementedError("Phase 1")
