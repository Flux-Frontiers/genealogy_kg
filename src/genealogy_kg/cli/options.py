"""Shared Click option decorators for GenealogyKG commands.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

import click
from kg_utils.semantic import DEFAULT_MODEL

repo_option = click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    show_default=True,
    help="Repository root; the store lives in <repo>/.genealogykg/.",
)

db_option = click.option(
    "--db",
    default=None,
    type=click.Path(),
    help="SQLite graph path (default: <repo>/.genealogykg/graph.sqlite).",
)

vectors_option = click.option(
    "--vectors",
    default=None,
    type=click.Path(),
    help="sqlite-vec store path (default: <repo>/.genealogykg/vectors.sqlite).",
)

model_option = click.option(
    "--model",
    default=DEFAULT_MODEL,
    show_default=True,
    help="Sentence-transformer model name.",
)

k_option = click.option(
    "-k",
    "--k",
    default=8,
    type=int,
    show_default=True,
    help="Number of top results to return.",
)

generations_option = click.option(
    "--generations", default=4, show_default=True, help="Maximum generations to walk."
)
