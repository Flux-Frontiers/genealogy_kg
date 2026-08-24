"""genealogy_kg/config.py

Where the GEDCOM sources come from, in precedence order:

1. ``--source`` on the command line
2. ``.genealogykg/config.json`` written by the last build
3. ``[tool.genealogykg] sources`` in ``pyproject.toml``

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path


def load_sources(repo_root: Path) -> list[Path]:
    """Return the configured GEDCOM sources for a repo.

    :param repo_root: Repository root.
    :return: Absolute paths, possibly empty.
    """
    raise NotImplementedError("Phase 1")


def save_sources(repo_root: Path, sources: list[Path]) -> None:
    """Record the sources used by a build in ``.genealogykg/config.json``.

    :param repo_root: Repository root.
    :param sources: Paths to record, stored relative to ``repo_root``.
    """
    raise NotImplementedError("Phase 1")
