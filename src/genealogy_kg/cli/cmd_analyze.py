"""``genkg analyze`` -- Markdown analysis report.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, open_kg, repo_option


@cli.command("analyze")
@repo_option
@db_option
@click.option("--output", "-o", type=click.Path(), default=None, help="Write the report here.")
def analyze(repo: str, db: str | None, output: str | None) -> None:
    """Print a Markdown analysis of the graph."""
    with open_kg(repo, db) as kg:
        report = kg.analyze()
    if output:
        Path(output).write_text(report, encoding="utf-8")
        click.echo(f"Wrote {output}")
    else:
        click.echo(report)
