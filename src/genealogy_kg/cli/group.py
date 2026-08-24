"""Root Click group for the GenealogyKG CLI.

All command modules import ``cli`` from here to avoid circular imports;
``main.py`` imports the group and every command module to register them.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

import importlib.metadata

import click


@click.group()
@click.version_option(version=importlib.metadata.version("genealogy-kg"))
def cli() -> None:
    """GenealogyKG -- knowledge graph tools for GEDCOM family-history files."""
