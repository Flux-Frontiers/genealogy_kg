"""``genkg export-web`` and ``genkg export-swift``: the files The Family reads.

Every export runs the living-person check; see :mod:`genealogy_kg.export`.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, open_kg, repo_option
from genealogy_kg.config import load_living_cutoff
from genealogy_kg.export import ExportError, PrivacySettings, export_web


def privacy_options(func):
    """Add the living-person options every export takes."""
    func = click.option(
        "--include-living",
        is_flag=True,
        help="Export with no redaction. For a private copy only; recorded in the output.",
    )(func)
    func = click.option(
        "--unknown-birth",
        type=click.Choice(["redact", "keep"]),
        default="redact",
        show_default=True,
        help="Treat people with no usable birth date and no death record as living.",
    )(func)
    func = click.option(
        "--living-cutoff",
        type=click.IntRange(min=0),
        default=None,
        help="Years: anyone born more recently with no death record is living. "
        "Default: [tool.genealogykg] living_cutoff_years.",
    )(func)
    return func


def resolve_privacy(
    repo: str, living_cutoff: int | None, unknown_birth: str, include_living: bool
) -> PrivacySettings:
    """Build the export's privacy settings from the options and pyproject.

    :raises click.UsageError: If the settings are refused.
    """
    cutoff = living_cutoff
    if cutoff is None and not include_living:
        cutoff = load_living_cutoff(Path(repo).resolve())
    try:
        return PrivacySettings(
            living_cutoff_years=cutoff,
            unknown_birth_policy=unknown_birth,
            include_living=include_living,
        )
    except ExportError as exc:
        raise click.UsageError(str(exc)) from exc


@cli.command("export-web")
@click.option(
    "--out",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory for catalog.json, species.json and people/.",
)
@click.option("--force", is_flag=True, help="Replace an earlier export in --out.")
@privacy_options
@repo_option
@db_option
def export_web_cmd(
    out: Path,
    force: bool,
    living_cutoff: int | None,
    unknown_birth: str,
    include_living: bool,
    repo: str,
    db: str | None,
) -> None:
    """Write the web orchard's data for kpress_family.

    catalog.json holds every line, person, family, cross-line marriage and
    place; people/<xref>.json is each person's page for the record reader;
    species.json is the tree-species table. The store must have been built
    with at least the export's living cutoff, or the export refuses.
    """
    privacy = resolve_privacy(repo, living_cutoff, unknown_birth, include_living)
    try:
        with open_kg(repo, db) as kg:
            result = export_web(kg, out, privacy, force=force)
    except ExportError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(
        f"Wrote {result.out}: {result.people} people ({result.redacted} living, redacted), "
        f"{result.lines} lines, {result.links} cross-line marriages."
    )


@cli.command("export-swift")
@click.option(
    "--out",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory for family.pack, family.vectors, manifest.json and golden.json.",
)
@click.option(
    "--dtype",
    type=click.Choice(["int8", "float"]),
    default="int8",
    show_default=True,
    help="Vector sidecar encoding; float is about 4x larger and exact.",
)
@click.option("--no-vectors", is_flag=True, help="Lexical-only pack: no sidecar, no golden file.")
@click.option("--no-golden", is_flag=True, help="Skip golden.json (and loading the embedder).")
@click.option(
    "--verify", is_flag=True, help="Report dense recall@10 of the sidecar against the store."
)
@click.option(
    "--embedder-from",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Copy the Core ML embedder (BGEEmbedder.mlpackage, vocab.txt, embedder.json) "
    "from this directory, e.g. a gutenberg_kg swift bundle.",
)
@click.option("--force", is_flag=True, help="Replace an earlier export in --out.")
@privacy_options
@repo_option
@db_option
def export_swift_cmd(
    out: Path,
    dtype: str,
    no_vectors: bool,
    no_golden: bool,
    verify: bool,
    embedder_from: Path | None,
    force: bool,
    living_cutoff: int | None,
    unknown_birth: str,
    include_living: bool,
    repo: str,
    db: str | None,
) -> None:
    """Write the family app's on-device search pack.

    One passage per person, family, event, place and source, each line a
    scope, with the store's vectors re-encoded for the device. The store must
    have been built with at least the export's living cutoff, or the export
    refuses.
    """
    from genealogy_kg.export_swift import export_swift  # noqa: PLC0415 - needs NumPy

    privacy = resolve_privacy(repo, living_cutoff, unknown_birth, include_living)
    try:
        with open_kg(repo, db) as kg:
            result = export_swift(
                kg,
                out,
                privacy,
                dtype=dtype,
                vectors=not no_vectors,
                golden=not no_golden,
                verify=verify,
                embedder_from=embedder_from,
                force=force,
            )
    except ExportError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(
        f"Wrote {result.out}: {result.passages} passages, {result.vectors} vectors "
        f"({result.bytes / 1e6:.1f} MB), {result.redacted} living people left out."
    )
    if result.recall_at_10 is not None:
        click.echo(f"Dense recall@10 against the store: {result.recall_at_10:.3f}")
    if not result.embedder:
        click.echo(
            "No Core ML embedder in --out yet: pass --embedder-from, or the app cannot open it."
        )
