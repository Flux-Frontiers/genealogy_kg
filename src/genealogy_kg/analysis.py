"""genealogy_kg/analysis.py

The data behind ``genkg analyze`` and the genealogy metrics a snapshot
records: generation depth, surname distribution, date coverage per kind,
people with no family links, places with no hierarchy, redacted people.

:func:`analyze_graph` computes it from a ``GraphStore``;
:func:`render_report` turns it into Markdown.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from kg_utils.store import GraphStore

#: Kinds whose nodes are expected to carry the temporal contract.
DATED_KINDS: tuple[str, ...] = ("person", "family", "event")
#: How many entries the Markdown report lists per hygiene section.
REPORT_LIMIT = 20


def _surname(node: dict[str, Any]) -> str:
    meta = node.get("metadata") or {}
    if meta.get("surname"):
        return str(meta["surname"])
    qualname = node.get("qualname") or ""
    return qualname.split(",")[0].strip() if "," in qualname else ""


def generation_depth(store: GraphStore, people: list[dict[str, Any]]) -> int:
    """Return the length of the longest ``PARENT_OF`` chain, in people.

    A single person with no lineage edges is depth 1; an empty graph is 0.
    Cycles (a GEDCOM error, but they happen) are cut at the point of
    re-entry rather than followed.

    :param store: The graph store.
    :param people: Every ``person`` node.
    :return: Number of generations on the longest descent line.
    """
    depth: dict[str, int] = {}

    def walk(pid: str, path: set[str]) -> int:
        if pid in depth:
            return depth[pid]
        path.add(pid)
        best = 0
        for edge in store.edges_from(pid, rel="PARENT_OF"):
            child = edge["dst"]
            if child in path:
                continue
            best = max(best, walk(child, path))
        path.discard(pid)
        depth[pid] = best + 1
        return depth[pid]

    return max((walk(p["id"], set()) for p in people), default=0)


def analyze_graph(store: GraphStore) -> dict[str, Any]:
    """Compute the analysis data for a built graph.

    :param store: The graph store.
    :return: A JSON-serialisable dict; see :func:`render_report` for the keys.
    """
    people = store.query_nodes(kinds=["person"])
    families = store.query_nodes(kinds=["family"])
    events = store.query_nodes(kinds=["event"])
    places = store.query_nodes(kinds=["place"])
    sources = store.query_nodes(kinds=["source"])

    surnames = Counter(_surname(p) for p in people)
    surnames.pop("", None)

    coverage: dict[str, dict[str, int]] = {}
    for kind, nodes in (("person", people), ("family", families), ("event", events)):
        dated = sum(
            1
            for n in nodes
            if (n.get("metadata") or {}).get("occurred_start")
            or (n.get("metadata") or {}).get("occurred_end")
        )
        coverage[kind] = {"dated": dated, "total": len(nodes)}

    linked = {
        row[0]
        for row in store.con.execute(
            "SELECT DISTINCT src FROM edges WHERE rel IN ('CHILD_IN', 'SPOUSE_IN')"
        )
    }
    unlinked = [{"id": p["id"], "name": p["name"]} for p in people if p["id"] not in linked]

    in_hierarchy = {
        row[0]
        for row in store.con.execute(
            "SELECT src FROM edges WHERE rel = 'WITHIN' UNION SELECT dst FROM edges WHERE rel = 'WITHIN'"
        )
    }
    flat_places = [
        {"id": pl["id"], "name": pl["name"]} for pl in places if pl["id"] not in in_hierarchy
    ]

    redacted = sum(1 for p in people if (p.get("metadata") or {}).get("living"))

    return {
        "counts": {
            "person": len(people),
            "family": len(families),
            "event": len(events),
            "place": len(places),
            "source": len(sources),
        },
        "generation_depth": generation_depth(store, people),
        "surnames": dict(surnames.most_common()),
        "date_coverage": coverage,
        "unlinked_people": unlinked,
        "places_without_hierarchy": flat_places,
        "living_redacted": redacted,
    }


def render_report(data: dict[str, Any], stats: dict[str, Any]) -> str:
    """Render :func:`analyze_graph` output as Markdown.

    :param data: The analysis dict.
    :param stats: ``KGModule.stats()`` output, for the node and edge totals.
    :return: Markdown text ending in a newline.
    """
    counts = data["counts"]
    lines = [
        "# GenealogyKG Analysis",
        "",
        f"- People: {counts['person']}",
        f"- Families: {counts['family']}",
        f"- Events: {counts['event']}",
        f"- Places: {counts['place']}",
        f"- Sources: {counts['source']}",
        f"- Total nodes: {stats.get('total_nodes', 0)}",
        f"- Total edges: {stats.get('total_edges', 0)}",
        f"- Generation depth: {data['generation_depth']}",
    ]
    if data["living_redacted"]:
        lines.append(f"- Living people redacted: {data['living_redacted']}")

    lines += ["", "## Surnames", ""]
    surnames = data["surnames"]
    lines.append(f"{len(surnames)} distinct surnames.")
    if surnames:
        lines.append("")
        lines.append("| Surname | People |")
        lines.append("|---|---|")
        for name, n in list(surnames.items())[:REPORT_LIMIT]:
            lines.append(f"| {name} | {n} |")
        if len(surnames) > REPORT_LIMIT:
            lines.append(f"| ... {len(surnames) - REPORT_LIMIT} more | |")

    lines += [
        "",
        "## Date coverage",
        "",
        "| Kind | Dated | Total | Coverage |",
        "|---|---|---|---|",
    ]
    for kind, c in data["date_coverage"].items():
        pct = f"{100 * c['dated'] / c['total']:.0f}%" if c["total"] else "n/a"
        lines.append(f"| {kind} | {c['dated']} | {c['total']} | {pct} |")

    lines += ["", "## Hygiene", ""]
    lines += _hygiene_section("People with no family links", data["unlinked_people"])
    lines += _hygiene_section("Places with no hierarchy", data["places_without_hierarchy"])
    return "\n".join(lines) + "\n"


def _hygiene_section(title: str, items: list[dict[str, Any]]) -> list[str]:
    lines = [f"### {title}: {len(items)}"]
    if items:
        lines.append("")
        for item in items[:REPORT_LIMIT]:
            lines.append(f"- {item['name']} (`{item['id']}`)")
        if len(items) > REPORT_LIMIT:
            lines.append(f"- ... {len(items) - REPORT_LIMIT} more")
    lines.append("")
    return lines


__all__ = ["analyze_graph", "render_report", "generation_depth", "DATED_KINDS"]
