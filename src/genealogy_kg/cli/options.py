"""Shared Click option decorators for GenealogyKG commands.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click
from kg_utils.semantic import DEFAULT_MODEL

from genealogy_kg.module import GenealogyKG
from genealogy_kg.validation import MAX_GENERATIONS, MAX_HOP, MAX_K, normalize_xref

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
    type=click.IntRange(1, MAX_K),
    show_default=True,
    help="Number of top results to return.",
)

generations_option = click.option(
    "--generations",
    default=4,
    type=click.IntRange(1, MAX_GENERATIONS),
    show_default=True,
    help="Maximum generations to walk.",
)

hop_option = click.option(
    "--hop",
    default=1,
    type=click.IntRange(0, MAX_HOP),
    show_default=True,
    help="Graph expansion hops.",
)


def cli_normalize_xref(xref: str) -> str:
    """Normalize an XREF argument, raising a Click usage error if invalid.

    :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
    :return: The bare pointer, e.g. ``"I7"``.
    :raises click.UsageError: If ``xref`` is not a plausible GEDCOM pointer.
    """
    try:
        return normalize_xref(xref)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc


def open_kg(repo: str, db: str | None = None, vectors: str | None = None) -> GenealogyKG:
    """Construct a GenealogyKG for the standard ``--repo``/``--db``/``--vectors``
    options, for use as ``with open_kg(...) as kg:`` so ``close()`` always
    runs -- ``GenealogyKG`` is a context manager via its ``KGModule`` base.

    :param repo: Repository root, matching :data:`repo_option`.
    :param db: SQLite graph path override, or ``None`` for the default.
    :param vectors: sqlite-vec store path override, or ``None`` for the default.
    :return: A new, unopened ``GenealogyKG`` instance.
    """
    return GenealogyKG(
        repo_root=Path(repo).resolve(),
        db_path=Path(db) if db else None,
        vectors_path=Path(vectors) if vectors else None,
    )
