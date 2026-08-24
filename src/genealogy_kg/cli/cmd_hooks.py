"""``genkg install-hooks`` -- a pre-commit hook for corpus repos.

The hook runs the repo's ``pre-commit`` checks if it has any, then, only when
``GENKG_SNAPSHOT=1``, rebuilds the store and saves a snapshot. Snapshots
are off by default for the reason every fleet hook gives: a snapshot staged
into the commit it describes can never match that commit's tree
(kgrag_priv/docs/SNAPSHOT_STRATEGY.md).

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import stat
from pathlib import Path

import click

from genealogy_kg.cli.group import cli

_PRE_COMMIT_HOOK = """\
#!/usr/bin/env bash
# GenealogyKG pre-commit hook. Installed by: genkg install-hooks
#
#   GENKG_SNAPSHOT=1 git commit ...        opt in to a per-commit snapshot
#   GENKG_SKIP_SNAPSHOT=1 git commit ...   force snapshots off (wins)
#
# Snapshots are off by default: a snapshot staged into the commit it
# describes records a tree hash that commit can never have. Snapshot at
# release instead (kgrag_priv/docs/SNAPSHOT_STRATEGY.md).
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Quality checks first, when the repo has them.
if [ -x "$REPO_ROOT/.venv/bin/pre-commit" ] && [ -f .pre-commit-config.yaml ]; then
    "$REPO_ROOT/.venv/bin/pre-commit" run || exit 1
elif command -v pre-commit >/dev/null 2>&1 && [ -f .pre-commit-config.yaml ]; then
    pre-commit run || exit 1
fi

[ "${GENKG_SNAPSHOT:-0}" = "1" ] || exit 0
[ "${GENKG_SKIP_SNAPSHOT:-0}" = "1" ] && exit 0

if [ -x "$REPO_ROOT/.venv/bin/genkg" ]; then
    GENEALOGYKG="$REPO_ROOT/.venv/bin/genkg"
else
    GENEALOGYKG="$(command -v genkg)"
fi

TREE_HASH=$(git write-tree)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

"$GENEALOGYKG" build --repo "$REPO_ROOT" || exit 1
"$GENEALOGYKG" snapshot save --repo "$REPO_ROOT" --tree-hash "$TREE_HASH" --branch "$BRANCH" \\
    || echo "[genkg] snapshot skipped" >&2
git add .genealogykg/snapshots/ 2>/dev/null || true

exit 0
"""


@cli.command("install-hooks")
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    show_default=True,
    help="Repository root.",
)
@click.option("--force", is_flag=True, help="Overwrite an existing pre-commit hook.")
def install_hooks(repo: str, force: bool) -> None:
    """Install the GenealogyKG pre-commit hook into .git/hooks/."""
    repo_root = Path(repo).resolve()
    git_dir = repo_root / ".git"
    if not git_dir.is_dir():
        raise click.ClickException(f"{repo_root} is not a git repository.")

    hook_path = git_dir / "hooks" / "pre-commit"
    if hook_path.exists() and not force:
        raise click.ClickException(f"Hook already exists: {hook_path} (use --force to overwrite)")

    hook_path.parent.mkdir(exist_ok=True)
    hook_path.write_text(_PRE_COMMIT_HOOK)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    click.echo(f"Installed pre-commit hook: {hook_path}")
    click.echo("  Snapshots are off by default. Opt in with GENKG_SNAPSHOT=1 git commit ...")
