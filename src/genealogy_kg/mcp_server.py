#!/usr/bin/env python3
"""genealogy_kg/mcp_server.py

GenealogyKG MCP server -- serves the genealogy graph to any MCP-compatible
agent over the fleet's shared server base, :mod:`kg_utils.mcp`.

The server answers the fleet's canonical tools -- ``stats``, ``query``,
``pack``, ``get_node``, ``neighbors`` -- under the same names as every other
KG server, then GenealogyKG's own: ``get_person``, ``ancestors``,
``descendants``, ``family_tree`` and ``analyze_genealogy``.

Living-person privacy holds on every path. A living person is redacted when
the graph is built (a bare ``Living`` node with no name, dates, events or
source span), so ``query``, ``get_node``, ``neighbors`` and the lineage tools
read only the redacted graph; ``pack`` goes through
:meth:`~genealogy_kg.module.GenealogyKG.pack`, which also strips every line of
a living person's real GEDCOM record from the snippets it returns.

The tool list is not kept by hand anywhere: each tool's docstring is its
description, the server's instructions are generated from them, and::

    genkg mcp --manifest

prints the whole list as JSON without opening the graph.

Usage
-----
::

    genkg mcp --repo /path/to/repo

``genkg-mcp`` is the same command under its older name.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kg_utils.mcp import Context, KGServer, kg_from, make_server

from genealogy_kg import __version__
from genealogy_kg.module import GenealogyKG

PREAMBLE = (
    "GenealogyKG is a knowledge graph over a GEDCOM family-history file. "
    "People, families, events, places and sources are nodes; lineage and "
    "marriage are edges. Person ids look like 'person:I7'. Living people are "
    "redacted: their node is named 'Living' and carries no dates or events.\n\n"
    "## Recommended workflows\n\n"
    "- **Orientation**: stats, then analyze_genealogy\n"
    "- **Find people**: query -> get_person or get_node\n"
    "- **Read the records**: pack, the original GEDCOM records behind a query\n"
    "- **Walk lineage**: ancestors / descendants / family_tree from a person id "
    "such as I7; neighbors(node_id) for one node's families, events and places"
)


def get_person(xref: str, ctx: Context) -> str:
    """Return one person node by GEDCOM xref.

    :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
    :return: JSON node dict, or ``null``.
    """
    return json.dumps(kg_from(ctx).person(xref), indent=2, ensure_ascii=False)


def ancestors(xref: str, ctx: Context, generations: int = 4) -> str:
    """Return the ancestors of a person, nearest generation first.

    :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
    :param generations: Maximum generations to climb, 1-50.
    :return: JSON list of person nodes with a ``generation`` key.
    """
    return json.dumps(
        kg_from(ctx).ancestors(xref, generations=generations),
        indent=2,
        ensure_ascii=False,
    )


def descendants(xref: str, ctx: Context, generations: int = 4) -> str:
    """Return the descendants of a person, nearest generation first.

    :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
    :param generations: Maximum generations to descend, 1-50.
    :return: JSON list of person nodes with a ``generation`` key.
    """
    return json.dumps(
        kg_from(ctx).descendants(xref, generations=generations),
        indent=2,
        ensure_ascii=False,
    )


def family_tree(
    xref: str, ctx: Context, direction: str = "descendants", generations: int = 4
) -> str:
    """Render an ASCII family tree rooted at a person.

    :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
    :param direction: ``"descendants"`` (default) or ``"ancestors"``.
    :param generations: Maximum generations to walk, 1-50.
    :return: The rendered tree as plain text.
    """
    return str(kg_from(ctx).tree(xref, direction=direction, generations=generations))


def analyze_genealogy(ctx: Context) -> str:
    """Return the Markdown analysis report for the graph.

    :return: Markdown text.
    """
    return kg_from(ctx).analyze()


#: Domain tools, registered after the canonical five in this order.
EXTRA_TOOLS = (get_person, ancestors, descendants, family_tree, analyze_genealogy)


def build_server(
    repo: str | Path,
    db: str | Path | None = None,
    vectors: str | Path | None = None,
    model: str | None = None,
) -> KGServer:
    """Build the GenealogyKG MCP server for one repo, without opening its graph.

    :param repo: Repository root containing ``.genealogykg/``.
    :param db: Graph database; ``None`` for ``<repo>/.genealogykg/graph.sqlite``.
    :param vectors: Vector store; ``None`` for the store beside the graph.
    :param model: Embedding model; ``None`` for GenealogyKG's default.
    :return: The server; serve it with :func:`kg_utils.mcp.run`.
    """
    root = Path(repo).resolve()
    kwargs: dict[str, Any] = {"model": model} if model else {}

    def open_kg() -> GenealogyKG:
        return GenealogyKG(root, db, vectors, **kwargs)

    server = make_server(
        open_kg, name="genkg", kind="genealogy", version=__version__, instructions=PREAMBLE
    )
    for fn in EXTRA_TOOLS:
        server.tool()(fn)
    return server


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``genkg-mcp``: the same command as ``genkg mcp``.

    :param argv: Arguments; ``None`` for ``sys.argv[1:]``.
    """
    from genealogy_kg.cli.cmd_mcp import mcp_command  # noqa: PLC0415 - cli imports this lazily

    mcp_command.main(args=argv, prog_name="genkg-mcp")


if __name__ == "__main__":
    main()
