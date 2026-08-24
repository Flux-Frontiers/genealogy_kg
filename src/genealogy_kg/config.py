"""genealogy_kg/config.py

Where the GEDCOM sources come from, in precedence order:

1. ``--source`` on the command line, or an explicit ``sources=`` argument
2. ``.genealogykg/config.json`` written by the last build
3. ``[tool.genealogykg] sources`` in ``pyproject.toml``

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

_CONFIG_PATH = ".genealogykg/config.json"


def _pyproject_table(repo_root: Path) -> dict[str, Any]:
    """Return the ``[tool.genealogykg]`` table of ``pyproject.toml``, or ``{}``."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return {}
    data = tomllib.loads(pyproject.read_text())
    return data.get("tool", {}).get("genealogykg", {})


def load_sources(repo_root: Path) -> list[Path]:
    """Return the configured GEDCOM sources for a repo.

    :param repo_root: Repository root.
    :return: Paths relative to ``repo_root``, possibly empty.
    """
    cfg_file = repo_root / _CONFIG_PATH
    if cfg_file.exists():
        data = json.loads(cfg_file.read_text())
        return [Path(p) for p in data.get("sources", [])]

    return [Path(p) for p in _pyproject_table(repo_root).get("sources", [])]


def load_living_cutoff(repo_root: Path) -> int | None:
    """Return ``[tool.genealogykg] living_cutoff_years``, or ``None`` when unset.

    Unset means no living-person redaction. See docs/DESIGN.md, "Source
    files are private by default".

    :param repo_root: Repository root.
    :return: Number of years, or ``None``.
    """
    value = _pyproject_table(repo_root).get("living_cutoff_years")
    return int(value) if value is not None else None


def load_unknown_birth_policy(repo_root: Path) -> str:
    """Return the living-person policy for records without a usable birth date.

    :param repo_root: Repository root.
    :return: ``"keep"`` (the default) or the configured value.
    """
    return str(_pyproject_table(repo_root).get("unknown_birth_policy", "keep"))


def load_default_xref(repo_root: Path) -> str | None:
    """Return ``[tool.genealogykg] default_xref``, or ``None`` when unset.

    Used by ``genkg quilt``/``genkg viz3d`` when XREF is omitted from the
    command line.

    :param repo_root: Repository root.
    :return: Xref without ``@``, or ``None``.
    """
    value = _pyproject_table(repo_root).get("default_xref")
    return str(value) if value is not None else None


def save_sources(repo_root: Path, sources: list[Path]) -> None:
    """Record the sources used by a build in ``.genealogykg/config.json``.

    :param repo_root: Repository root.
    :param sources: Paths to record, stored relative to ``repo_root``.
    """
    cfg_file = repo_root / _CONFIG_PATH
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    rel: list[str] = []
    for source in sources:
        p = Path(source)
        rel.append(str(p.relative_to(repo_root)) if p.is_absolute() else str(p))
    cfg_file.write_text(json.dumps({"sources": rel}, indent=2, ensure_ascii=False) + "\n")
