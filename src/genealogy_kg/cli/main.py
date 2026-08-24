"""Registers every command on the root group.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

import genealogy_kg.cli.cmd_analyze  # noqa: F401
import genealogy_kg.cli.cmd_build  # noqa: F401
import genealogy_kg.cli.cmd_lineage  # noqa: F401
import genealogy_kg.cli.cmd_query  # noqa: F401
import genealogy_kg.cli.cmd_snapshot  # noqa: F401
import genealogy_kg.cli.cmd_status  # noqa: F401
import genealogy_kg.cli.cmd_viz  # noqa: F401
from genealogy_kg.cli.group import cli  # noqa: F401

if __name__ == "__main__":
    cli()
