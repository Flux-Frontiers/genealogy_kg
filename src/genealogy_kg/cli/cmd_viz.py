"""``genkg viz``/``quilt``/``viz3d`` -- render a family tree.

``viz`` writes a self-contained HTML file: ``pedigree`` is the drawn
counterpart of ``genkg descendants``, ``network`` the person/family topology
around someone (both 2-D, the ``viz`` extra). ``quilt`` and ``viz3d`` grow
xref's descent line as a real 3-D tree and either render it to a Looking
Glass quilt or open it in an interactive viewer (both 3-D, the ``viz3d``
extra) -- see ``genealogy_kg.scene`` for the growth/placement logic.

Every renderer is imported inside its command rather than at module scope:
this module loads whenever the CLI starts, and the rendering libraries only
arrive with their respective extras.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import (
    cli_normalize_xref,
    db_option,
    generations_option,
    open_kg,
    repo_option,
)
from genealogy_kg.config import load_default_xref

_VIZ_EXTRA = 'pip install "genealogy-kg[viz]"'


def _resolve_xref(xref: str | None, repo_root: Path) -> str:
    """Fall back to ``[tool.genealogykg] default_xref`` when XREF is omitted.

    :param xref: The XREF argument as passed on the command line, or ``None``.
    :param repo_root: Repository root, for reading ``pyproject.toml``.
    :return: The normalized, bare xref.
    :raises click.UsageError: If XREF was omitted and no default is configured,
        or the resolved value is not a plausible GEDCOM pointer.
    """
    if xref is None:
        xref = load_default_xref(repo_root)
        if xref is None:
            raise click.UsageError(
                "Missing argument XREF -- pass one, or set "
                "[tool.genealogykg] default_xref in pyproject.toml."
            )
    return cli_normalize_xref(xref)


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

    person_id = f"person:{cli_normalize_xref(xref)}"

    try:
        with open_kg(repo, db) as kg:
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


_VIZ3D_EXTRA = 'pip install "genealogy-kg[viz3d]"'

color_by_3d_option = click.option(
    "--color-by",
    type=click.Choice(["sex", "generation"]),
    default="generation",
    show_default=True,
    help="Colour foliage by sex, or by generation distance from the root.",
)

preset_option = click.option(
    "--preset",
    default="16-landscape",
    show_default=True,
    help="Looking Glass quilt preset.",
)


@cli.command("quilt")
@click.argument("xref", required=False)
@repo_option
@db_option
@preset_option
@click.option(
    "-o",
    "--out",
    "out_dir",
    default="renders",
    show_default=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory for the quilt.",
)
@color_by_3d_option
@click.option(
    "--tip-radius",
    default=0.06,
    show_default=True,
    type=float,
    help="Radius of leaf-bearing twigs, in world units.",
)
@click.option(
    "--leaf-size",
    default=0.35,
    show_default=True,
    type=float,
    help="Leaf glyph radius.",
)
@click.option(
    "--zoom",
    default=1.0,
    show_default=True,
    type=float,
    help="Camera dolly after framing. >1 fills more of the tile, driving more depth.",
)
@click.option(
    "--fov",
    default=14.0,
    show_default=True,
    type=float,
    help="Per-view vertical field of view in degrees; Looking Glass recommends ~14.",
)
@click.option("--cast", is_flag=True, help="Send the finished quilt to Looking Glass Bridge.")
@click.option(
    "--schematic",
    is_flag=True,
    help="Draw the straight-line schematic instead of growing organic wood.",
)
def quilt(
    xref: str | None,
    repo: str,
    db: str | None,
    preset: str,
    out_dir: Path,
    color_by: str,
    tip_radius: float,
    leaf_size: float,
    zoom: float,
    fov: float,
    cast: bool,
    schematic: bool,
) -> None:
    """Grow xref's descent line and render it as a Looking Glass quilt.

    xref founds the tree -- their ancestors are not grown, since a GEDCOM can
    hold several unrelated lines with no single well-defined "the"
    progenitor to auto-detect. The tree is xref plus every descendant plus
    every spouse who married in. XREF may be omitted if
    [tool.genealogykg] default_xref is set in pyproject.toml.
    """
    try:
        import pyvista as pv
        from quiltwright import QUILT_PRESETS, depth_report, render_quilt, save_quilt
    except ImportError as exc:
        raise click.UsageError(
            f"quilt requires pyvista and quiltwright.\n"
            f"Install with:  {_VIZ3D_EXTRA}\n"
            f"Details: {exc}"
        ) from exc

    from kg_utils.viz3d import frame_tree

    from genealogy_kg import scene as render3d

    if preset not in QUILT_PRESETS:
        raise click.ClickException(
            f"Unknown quilt preset {preset!r}. Choose from: {', '.join(QUILT_PRESETS)}"
        )
    spec = QUILT_PRESETS[preset]

    repo_root = Path(repo).resolve()
    xref = _resolve_xref(xref, repo_root)

    plotter = pv.Plotter(off_screen=True)
    try:
        with open_kg(repo, db) as kg:
            tree = render3d.build_family_tree_scene(
                kg.store,
                plotter,
                xref,
                color_by=color_by,
                tip_radius=tip_radius,
                leaf_size=leaf_size,
                organic=not schematic,
            )
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    click.echo(f"Scene: {tree.title}")

    frame = frame_tree(tree.points, fov=fov)
    plotter.camera.position = frame.position
    plotter.camera.focal_point = frame.focal_point
    plotter.camera.up = frame.up
    plotter.reset_camera()  # ty: ignore[missing-argument]

    click.echo(
        depth_report(
            plotter,
            spec,
            fov=fov,
            zoom=zoom,
            labels=("nearest foliage", "focal plane (display surface)", "farthest foliage"),
        )
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Rendering {spec.n_views} views at {spec.tile_width}x{spec.tile_height}...")
    path = save_quilt(render_quilt(plotter, spec, fov=fov, zoom=zoom), out_dir / xref, spec)
    plotter.close()
    click.echo(f"Wrote {path}")

    if cast:
        from quiltwright import cast_quilt

        try:
            cast_quilt(path.resolve(), spec)
            click.echo("Cast to Looking Glass Bridge.")
        except Exception as exc:  # noqa: BLE001 - Bridge absence must not fail the render
            click.echo(f"Cast failed (is Looking Glass Bridge running?): {exc}", err=True)


@cli.command("viz3d")
@click.argument("xref", required=False)
@repo_option
@db_option
@color_by_3d_option
@preset_option
@click.option("--width", default=1400, show_default=True, type=int, help="Window width, pixels.")
@click.option("--height", default=900, show_default=True, type=int, help="Window height, pixels.")
@click.option(
    "--schematic",
    is_flag=True,
    help="Draw the straight-line schematic instead of growing organic wood.",
)
def viz3d(
    xref: str | None,
    repo: str,
    db: str | None,
    color_by: str,
    preset: str,
    width: int,
    height: int,
    schematic: bool,
) -> None:
    """Launch an interactive 3-D viewer of xref's grown descent line.

    Orbit/zoom/pan with the mouse. The toolbar's "Cast to Looking Glass"
    button sends the current view to Bridge. XREF may be omitted if
    [tool.genealogykg] default_xref is set in pyproject.toml.
    """
    if importlib.util.find_spec("PyQt5") is None or importlib.util.find_spec("pyvistaqt") is None:
        raise click.UsageError(
            f"viz3d requires PyQt5 and pyvistaqt.\nInstall with:  {_VIZ3D_EXTRA}"
        )

    from genealogy_kg import viz3d as viewer

    repo_root = Path(repo).resolve()
    xref = _resolve_xref(xref, repo_root)
    db_path = Path(db) if db else None
    try:
        viewer.launch(
            repo_root,
            db_path,
            xref,
            color_by=color_by,
            preset=preset,
            organic=not schematic,
            width=width,
            height=height,
        )
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
