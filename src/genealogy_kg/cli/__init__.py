"""genealogy_kg.cli -- Click entry points.

The root group is importable from either location::

    from genealogy_kg.cli import cli
    from genealogy_kg.cli.main import cli

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from genealogy_kg.cli import (
    cmd_analyze,  # noqa: F401
    cmd_build,  # noqa: F401
    cmd_hooks,  # noqa: F401
    cmd_lineage,  # noqa: F401
    cmd_query,  # noqa: F401
    cmd_snapshot,  # noqa: F401
    cmd_status,  # noqa: F401
    cmd_viz,  # noqa: F401
)
from genealogy_kg.cli.group import cli

__all__ = ["cli"]
