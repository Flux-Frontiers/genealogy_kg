"""``genkg corpus`` -- survey and register the ``corpora/entries/`` tree.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.corpus import IngestOptions, print_ingest_summary, run_ingest, survey

_root_option = click.option(
    "--root",
    default=None,
    type=click.Path(),
    help="Per-entry corpus root (default: <repo>/corpora/entries).",
)
_repo_option = click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    show_default=True,
    help="Repository root; used to resolve --root when it isn't given.",
)
_genre_option = click.option(
    "--genre", "genres", multiple=True, help="Limit to this genre. Repeatable."
)


def _corpus_root(repo: str, root: str | None) -> Path:
    return Path(root).resolve() if root else Path(repo).resolve() / "corpora" / "entries"


@cli.group("corpus")
def corpus() -> None:
    """Manage the ``corpora/entries/`` tree of GEDCOM entries."""


@corpus.command("survey")
@_repo_option
@_root_option
@_genre_option
def corpus_survey(repo: str, root: str | None, genres: tuple[str, ...]) -> None:
    """Show which entries under corpora/entries/ are built."""
    click.echo(survey(_corpus_root(repo, root), genre=genres[0] if genres else None))


@corpus.command("ingest")
@_repo_option
@_root_option
@_genre_option
@click.option("--force-build", is_flag=True, help="Rebuild even if .genealogykg already exists.")
@click.option(
    "--force-register", is_flag=True, help="Re-register even if already in the KGRAG registry."
)
@click.option(
    "--no-register", is_flag=True, help="Build only; skip KGRAG registry/corpus membership."
)
@click.option("--dry-run", is_flag=True, help="Print actions without executing anything.")
@click.option("--registry", default=None, help="Override KGRAG registry path.")
def corpus_ingest(
    repo: str,
    root: str | None,
    genres: tuple[str, ...],
    force_build: bool,
    force_register: bool,
    no_register: bool,
    dry_run: bool,
    registry: str | None,
) -> None:
    """Build every unbuilt entry and register it with the KGRAG registry.

    Registration requires the ``adapter`` extra (``pip install -e ".[adapter]"``).
    """
    opts = IngestOptions(
        force_build=force_build,
        force_register=force_register,
        register=not no_register,
        dry_run=dry_run,
    )
    try:
        results = run_ingest(
            _corpus_root(repo, root), list(genres) or None, opts, registry=registry
        )
    except ImportError as exc:
        raise click.ClickException(
            f"kg-rag not installed (needed for registration): {exc}\n"
            'Install with: pip install -e ".[adapter]", or pass --no-register.'
        ) from exc
    print_ingest_summary(results)
