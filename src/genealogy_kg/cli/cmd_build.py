"""``genealogykg build`` -- GEDCOM file(s) -> SQLite graph + sqlite-vec index.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, model_option, repo_option, vectors_option


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
    raise NotImplementedError("Phase 1")
