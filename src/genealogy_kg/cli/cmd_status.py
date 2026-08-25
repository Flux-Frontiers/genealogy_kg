"""``genkg status`` -- corpus-wide build/registration status, or a single
store's status when no ``corpora/entries/`` tree is present.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, open_kg, repo_option
from genealogy_kg.config import load_sources
from genealogy_kg.corpus import collect_corpus_status

_root_option = click.option(
    "--root",
    default=None,
    type=click.Path(),
    help="Per-entry corpus root (default: <repo>/corpora/entries).",
)


@cli.command("status")
@repo_option
@_root_option
@db_option
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit machine-readable JSON.")
@click.option("--registry", default=None, help="Override KGRAG registry path.")
def status(
    repo: str, root: str | None, db: str | None, as_json: bool, registry: str | None
) -> None:
    """Show corpus-wide status, or a single store's status if no corpus is present."""
    repo_root = Path(repo).resolve()
    corpus_root = Path(root).resolve() if root else repo_root / "corpora" / "entries"

    if corpus_root.is_dir() and any(corpus_root.iterdir()):
        result = collect_corpus_status(corpus_root, registry=registry)
        if not result["genres"]:
            click.echo(f"No corpus entries found under {corpus_root}")
            return
        if as_json:
            click.echo(json.dumps(result, indent=2))
        else:
            _print_corpus_status(result)
        return

    _print_store_status(repo, db)


def _print_store_status(repo: str, db: str | None) -> None:
    """Show whether a single store is built, its sources, and node/edge counts."""
    repo_root = Path(repo).resolve()
    with open_kg(repo, db) as kg:
        sources = kg.sources if kg.sources is not None else load_sources(repo_root)
        source_line = "Sources: " + (", ".join(str(s) for s in sources) or "(none configured)")

        if not kg.db_path.exists():
            click.echo(f"No store built yet at {kg.db_path}")
            click.echo(source_line)
            return

        stats = kg.stats()
    click.echo(f"Store: {kg.db_path}")
    click.echo(source_line)
    click.echo(f"Nodes: {stats['total_nodes']}  Edges: {stats['total_edges']}")
    for kind, count in sorted(stats.get("node_counts", {}).items()):
        click.echo(f"  {kind}: {count}")


def _print_corpus_status(result: dict[str, Any]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        _print_corpus_status_plain(result)
        return

    totals = result["totals"]
    console = Console()
    table = Table(title="GenealogyKG Corpus Status", show_footer=True)
    table.add_column("Genre", style="cyan", footer="Total")
    table.add_column("Entries", justify="right", footer=str(totals["entries"]))
    table.add_column("Built", justify="right", footer=str(totals["built"]))
    reg_footer = str(totals["registered"]) if result["registry_available"] else "-"
    table.add_column("Registered", justify="right", footer=reg_footer)
    table.add_column("People", justify="right", footer=f"{totals['people']:,}")
    table.add_column("Families", justify="right", footer=f"{totals['families']:,}")
    table.add_column("Nodes", justify="right", footer=f"{totals['nodes']:,}")
    table.add_column("Edges", justify="right", footer=f"{totals['edges']:,}")

    for g in result["genres"]:
        reg = str(g["registered"]) if g["registered"] is not None else "-"
        table.add_row(
            g["genre"],
            str(g["entries"]),
            str(g["built"]),
            reg,
            f"{g['people']:,}",
            f"{g['families']:,}",
            f"{g['nodes']:,}",
            f"{g['edges']:,}",
        )

    console.print(table)
    if not result["registry_available"]:
        console.print(
            "KGRAG registry not available -- registration counts not shown. "
            'Install with: pip install -e ".[adapter]"',
            style="dim",
            markup=False,
        )


def _print_corpus_status_plain(result: dict[str, Any]) -> None:
    totals = result["totals"]
    header = (
        f"{'Genre':<40} {'Entries':>8} {'Built':>6} {'Reg':>6} "
        f"{'People':>8} {'Families':>9} {'Nodes':>10} {'Edges':>12}"
    )
    sep = "-" * len(header)
    click.echo(header)
    click.echo(sep)
    for g in result["genres"]:
        reg = g["registered"] if g["registered"] is not None else "-"
        click.echo(
            f"{g['genre']:<40} {g['entries']:>8} {g['built']:>6} {reg!s:>6} "
            f"{g['people']:>8,} {g['families']:>9,} {g['nodes']:>10,} {g['edges']:>12,}"
        )
    click.echo(sep)
    reg_total = totals["registered"] if totals["registered"] is not None else "-"
    click.echo(
        f"{'Total':<40} {totals['entries']:>8} {totals['built']:>6} {reg_total!s:>6} "
        f"{totals['people']:>8,} {totals['families']:>9,} {totals['nodes']:>10,} "
        f"{totals['edges']:>12,}"
    )
