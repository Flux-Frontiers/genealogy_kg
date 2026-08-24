"""``genkg viz`` -- write a family tree to a self-contained HTML file.

Two views of the same graph, per docs/DESIGN.md: ``pedigree`` is the drawn
counterpart of ``genkg descendants``, and ``network`` is the person/family
topology around someone.

``genealogy_kg.viz`` is imported inside the command rather than at module
scope: this module is imported whenever the CLI starts, and the rendering
libraries only arrive with the ``viz`` extra.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, generations_option, repo_option
from genealogy_kg.module import GenealogyKG

_VIZ_EXTRA = 'pip install "genealogy-kg[viz]"'


@cli.command("viz")
@click.argument("xref")
@repo_option
@db_option
@click.option(
    "-o",
    "--output",
    default="tree.html",
    show_default=True,
    type=click.Path(dir_okay=False, writable=True),
    help="Where to write the HTML file.",
)
@click.option(
    "--view",
    type=click.Choice(["pedigree", "network"]),
    default="pedigree",
    show_default=True,
    help="'pedigree' draws the descent chart; 'network' draws the person/family graph.",
)
@click.option(
    "--direction",
    type=click.Choice(["descendants", "ancestors"]),
    default="descendants",
    show_default=True,
    help="Which way the pedigree walks. Ignored by --view network.",
)
@generations_option
@click.option(
    "--color-by",
    type=click.Choice(["sex", "generation"]),
    default="sex",
    show_default=True,
    help="Colour people by sex, or by generation distance from this person.",
)
@click.option(
    "--max-nodes",
    default=250,
    show_default=True,
    type=click.IntRange(2, 5000),
    help="Node budget for --view network. The graph is unreadable well below the maximum.",
)
def viz(
    xref: str,
    repo: str,
    db: str | None,
    output: str,
    view: str,
    direction: str,
    generations: int,
    color_by: str,
    max_nodes: int,
) -> None:
    """Write a family tree to a self-contained HTML file (xref such as I1).

    The output has its rendering library inlined, so it opens straight from
    the filesystem and can be sent to someone who has neither the GEDCOM nor
    Python installed.
    """
    missing = "plotly" if view == "pedigree" else "pyvis"
    if importlib.util.find_spec(missing) is None:
        raise click.UsageError(
            f"{missing} is not installed. Install viz dependencies with:\n  {_VIZ_EXTRA}"
        )

    from genealogy_kg import viz as render

    kg = GenealogyKG(repo_root=Path(repo).resolve(), db_path=Path(db) if db else None)
    person_id = f"person:{xref}"

    try:
        if view == "pedigree":
            figure = render.pedigree_figure(
                kg.store,
                person_id,
                direction=direction,
                generations=generations,
                color_by=color_by,
            )
            figure.write_html(output, include_plotlyjs=True)
            drawn = f"{direction} of {xref}, {generations} generations"
        else:
            html = render.network_html(
                kg.store,
                root_id=person_id,
                hops=generations,
                max_nodes=max_nodes,
                color_by=color_by,
            )
            Path(output).write_text(html, encoding="utf-8")
            drawn = f"network around {xref}, {generations} hops"
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    click.echo(f"Wrote {output} -- {drawn}, coloured by {color_by}.")
