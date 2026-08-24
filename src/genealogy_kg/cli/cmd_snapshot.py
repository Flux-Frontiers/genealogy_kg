"""``genkg snapshot`` -- save, list, show and diff metric snapshots.

Snapshots live in ``.genealogykg/snapshots/`` (tracked in git) and are keyed
by git tree hash, like every other KG in the fleet.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from genealogy_kg.cli.group import cli
from genealogy_kg.cli.options import db_option, repo_option
from genealogy_kg.module import GenealogyKG
from genealogy_kg.snapshots import GENEALOGY_METRICS, SnapshotManager

_LIST_COLUMNS = ("total_nodes", "total_edges", *GENEALOGY_METRICS, "generation_depth")


def _snapshots_dir(repo: str) -> Path:
    return Path(repo).resolve() / ".genealogykg" / "snapshots"


@cli.group("snapshot")
def snapshot() -> None:
    """Manage point-in-time metric snapshots of the graph."""


@snapshot.command("save")
@click.argument("version", metavar="[VERSION]", default="", required=False)
@repo_option
@db_option
@click.option("--branch", default=None, help="Branch name; auto-detected if not given.")
@click.option("--tree-hash", default="", help="Git tree hash; auto-detected if not given.")
@click.option("--force", is_flag=True, help="Write a new entry even if metrics are unchanged.")
def save(
    version: str, repo: str, db: str | None, branch: str | None, tree_hash: str, force: bool
) -> None:
    """Capture the current graph metrics as a snapshot.

    VERSION defaults to the installed genealogy-kg version.
    """
    repo_root = Path(repo).resolve()
    kg = GenealogyKG(repo_root=repo_root, db_path=Path(db) if db else None)
    if not kg.db_path.exists():
        raise click.ClickException(f"No store at {kg.db_path}. Run 'genkg build' first.")
    try:
        stats = kg.stats()
        analysis = kg.analysis()
    finally:
        kg.close()

    mgr = SnapshotManager(_snapshots_dir(repo))
    snap = mgr.capture_genealogy(
        stats, analysis, version=version or None, branch=branch, tree_hash=tree_hash
    )
    try:
        path = mgr.save_snapshot(snap, force=force)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Snapshot saved: {path or '(unchanged, entry refreshed)'}")
    click.echo(f"  Key:      {snap.key}")
    click.echo(f"  Version:  {snap.version}")
    for key in _LIST_COLUMNS:
        click.echo(f"  {key + ':':<18}{snap.metrics.get(key, 0)}")


@snapshot.command("list")
@repo_option
@click.option("--limit", type=int, default=None, help="Maximum snapshots to show.")
@click.option("--branch", default=None, help="Filter by branch name.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def list_(repo: str, limit: int | None, branch: str | None, as_json: bool) -> None:
    """List snapshots, newest first."""
    snaps = SnapshotManager(_snapshots_dir(repo)).list_snapshots(limit=limit, branch=branch)
    if as_json:
        click.echo(json.dumps(snaps, indent=2))
        return
    if not snaps:
        click.echo("No snapshots yet. Run 'genkg snapshot save'.")
        return

    header = f"{'Key':<12} {'Timestamp':<17} {'Version':<8} {'Nodes':>6} {'Edges':>6} "
    header += " ".join(f"{k.title():>8}" for k in GENEALOGY_METRICS) + f" {'Depth':>5}"
    click.echo(header)
    click.echo("-" * len(header))
    for s in snaps:
        m = s["metrics"]
        ts = s.get("timestamp", "")[:16].replace("T", " ")
        row = (
            f"{s['key'][:12]:<12} {ts:<17} {s.get('version', '')[:8]:<8} "
            f"{m.get('total_nodes', 0):>6} {m.get('total_edges', 0):>6} "
        )
        row += " ".join(f"{m.get(k, 0):>8}" for k in GENEALOGY_METRICS)
        row += f" {m.get('generation_depth', 0):>5}"
        click.echo(row)


@snapshot.command("show")
@click.argument("key", metavar="KEY")
@repo_option
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def show(key: str, repo: str, as_json: bool) -> None:
    """Show one snapshot by key (tree hash, or a unique prefix)."""
    snap = SnapshotManager(_snapshots_dir(repo)).load_snapshot(key)
    if snap is None:
        raise click.ClickException(f"Snapshot not found: {key}")
    if as_json:
        click.echo(json.dumps(snap.to_dict(), indent=2))
        return

    click.echo(f"Key:       {snap.key}")
    click.echo(f"Branch:    {snap.branch}")
    click.echo(f"Timestamp: {snap.timestamp}")
    click.echo(f"Version:   {snap.version}")
    click.echo()
    click.echo("Metrics:")
    for k, v in snap.metrics.items():
        if isinstance(v, dict):
            click.echo(f"  {k}:")
            for kk, vv in sorted(v.items()):
                click.echo(f"    {kk}: {vv}")
        else:
            click.echo(f"  {k}: {v}")
    for title, delta in (("previous", snap.vs_previous), ("baseline", snap.vs_baseline)):
        if delta:
            click.echo()
            click.echo(f"Delta vs {title}:")
            for k, v in delta.items():
                click.echo(f"  {k}: {v:+d}")


@snapshot.command("diff")
@click.argument("key_a", metavar="KEY_A")
@click.argument("key_b", metavar="KEY_B")
@repo_option
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def diff(key_a: str, key_b: str, repo: str, as_json: bool) -> None:
    """Compare two snapshots (B minus A)."""
    result = SnapshotManager(_snapshots_dir(repo)).diff_snapshots(key_a, key_b)
    if "error" in result:
        raise click.ClickException(result["error"])
    if as_json:
        click.echo(json.dumps(result, indent=2))
        return

    a, b = result["a"], result["b"]
    click.echo(f"Comparing {a['key'][:12]} -> {b['key'][:12]}")
    click.echo()
    click.echo(f"{'Metric':<18} {'A':>8} {'B':>8} {'Delta':>8}")
    click.echo("-" * 45)
    for key in _LIST_COLUMNS:
        va, vb = a["metrics"].get(key, 0), b["metrics"].get(key, 0)
        click.echo(f"{key:<18} {va:>8} {vb:>8} {vb - va:>+8}")
    changed = {k: v for k, v in result.get("node_counts_delta", {}).items() if v}
    if changed:
        click.echo()
        click.echo("Changed node kinds:")
        for kind, delta in sorted(changed.items()):
            click.echo(f"  {kind}: {delta:+d}")
