#!/usr/bin/env python3
"""genealogy_kg/mcp_server.py

GenealogyKG MCP server -- exposes the genealogy graph as Model Context
Protocol tools.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from genealogy_kg.module import GenealogyKG

_kg: GenealogyKG | None = None


def _get_kg() -> GenealogyKG:
    """Return the server's GenealogyKG instance.

    :return: The instance built by :func:`main`.
    :raises RuntimeError: If the server was imported without going through main().
    """
    if _kg is None:
        raise RuntimeError("GenealogyKG not initialised. Run via 'genkg-mcp --repo PATH'")
    return _kg


mcp = FastMCP(
    "genkg",
    instructions=(
        "GenealogyKG is a knowledge graph over a GEDCOM family-history file. "
        "People, families, events, places and sources are nodes; lineage and "
        "marriage are edges. Use query_genealogy for natural-language search, "
        "pack_genealogy for the original GEDCOM records behind a query, and "
        "ancestors/descendants to walk lineage from a person id such as I7."
    ),
)


@mcp.tool()
def query_genealogy(q: str, k: int = 8) -> str:
    """Search the genealogy graph and return ranked nodes as JSON.

    :param q: Natural-language query. Must be non-empty, at most 500 characters.
    :param k: Maximum number of seed hits, 1-100.
    :return: JSON-encoded QueryResult.
    """
    return _get_kg().query(q, k=k).to_json()


@mcp.tool()
def pack_genealogy(q: str, k: int = 8, max_nodes: int = 15) -> str:
    """Return the GEDCOM records behind the nodes matching a query.

    :param q: Natural-language query. Must be non-empty, at most 500 characters.
    :param k: Number of seed hits, 1-100.
    :param max_nodes: Maximum nodes in the pack, 1-500.
    :return: Markdown snippet pack with line-numbered GEDCOM records.
    """
    return _get_kg().pack(q, k=k, max_nodes=max_nodes).to_markdown()


@mcp.tool()
def get_person(xref: str) -> str:
    """Return one person node by GEDCOM xref.

    :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
    :return: JSON node dict, or ``null``.
    """
    return json.dumps(_get_kg().person(xref), indent=2, ensure_ascii=False)


@mcp.tool()
def ancestors(xref: str, generations: int = 4) -> str:
    """Return the ancestors of a person, nearest generation first.

    :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
    :param generations: Maximum generations to climb, 1-50.
    :return: JSON list of person nodes with a ``generation`` key.
    """
    return json.dumps(
        _get_kg().ancestors(xref, generations=generations),
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def descendants(xref: str, generations: int = 4) -> str:
    """Return the descendants of a person, nearest generation first.

    :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
    :param generations: Maximum generations to descend, 1-50.
    :return: JSON list of person nodes with a ``generation`` key.
    """
    return json.dumps(
        _get_kg().descendants(xref, generations=generations),
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def family_tree(xref: str, direction: str = "descendants", generations: int = 4) -> str:
    """Render an ASCII family tree rooted at a person.

    :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
    :param direction: ``"descendants"`` (default) or ``"ancestors"``.
    :param generations: Maximum generations to walk, 1-50.
    :return: The rendered tree as plain text.
    """
    return str(_get_kg().tree(xref, direction=direction, generations=generations))


@mcp.tool()
def graph_stats() -> str:
    """Return node and edge counts for the current store.

    :return: JSON with total_nodes, total_edges, node_counts, edge_counts.
    """
    return json.dumps(_get_kg().stats(), indent=2, ensure_ascii=False)


@mcp.tool()
def analyze_genealogy() -> str:
    """Return the Markdown analysis report for the graph.

    :return: Markdown text.
    """
    return _get_kg().analyze()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    :param argv: Argument vector; defaults to ``sys.argv[1:]``.
    :return: Parsed namespace.
    """
    p = argparse.ArgumentParser(
        prog="genkg-mcp",
        description="GenealogyKG MCP server -- exposes genealogy graph tools to AI agents.",
    )
    p.add_argument("--repo", default=".", help="Repository root containing .genealogykg/")
    p.add_argument(
        "--db", default=None, help="SQLite graph path (default: .genealogykg/graph.sqlite)"
    )
    p.add_argument("--vectors", default=None, help="sqlite-vec path (default: beside the graph)")
    p.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Start the MCP server.

    :param argv: Argument vector; defaults to ``sys.argv[1:]``.
    """
    global _kg

    args = _parse_args(argv)
    repo = Path(args.repo).resolve()
    _kg = GenealogyKG(repo_root=repo, db_path=args.db, vectors_path=args.vectors)
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
