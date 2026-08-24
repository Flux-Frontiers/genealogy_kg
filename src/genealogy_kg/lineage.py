"""genealogy_kg/lineage.py

Ancestor, descendant and kinship walks over ``GraphStore``, plus a basic
ASCII family-tree renderer.

Ancestors follow ``PARENT_OF`` inbound (``GraphStore.callers_of``),
descendants follow it outbound (``GraphStore.edges_from``); no second edge
kind is stored for either direction. ``kinship_path`` additionally walks
``MARRIED_TO`` in both directions, since it is stored husband -> wife only
but is conceptually symmetric.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from kg_utils.store import GraphStore


def ancestors(store: GraphStore, person_id: str, *, generations: int = 4) -> list[dict[str, Any]]:
    """Return ancestors of a person, nearest generation first.

    :param store: The graph store.
    :param person_id: Node id such as ``person:I7``.
    :param generations: Maximum generations to climb.
    :return: Node dicts, each with a ``generation`` key (1 = parents).
    """
    result: list[dict[str, Any]] = []
    seen = {person_id}
    frontier = [person_id]
    for gen in range(1, generations + 1):
        next_frontier: list[str] = []
        for pid in frontier:
            for parent in store.callers_of(pid, rel="PARENT_OF"):
                if parent["id"] in seen:
                    continue
                seen.add(parent["id"])
                result.append({**parent, "generation": gen})
                next_frontier.append(parent["id"])
        if not next_frontier:
            break
        frontier = next_frontier
    return result


def descendants(store: GraphStore, person_id: str, *, generations: int = 4) -> list[dict[str, Any]]:
    """Return descendants of a person, nearest generation first.

    :param store: The graph store.
    :param person_id: Node id such as ``person:I1``.
    :param generations: Maximum generations to descend.
    :return: Node dicts, each with a ``generation`` key (1 = children).
    """
    result: list[dict[str, Any]] = []
    seen = {person_id}
    frontier = [person_id]
    for gen in range(1, generations + 1):
        next_frontier: list[str] = []
        for pid in frontier:
            for edge in store.edges_from(pid, rel="PARENT_OF"):
                child_id = edge["dst"]
                if child_id in seen:
                    continue
                node = store.node(child_id)
                if node is None:
                    continue
                seen.add(child_id)
                result.append({**node, "generation": gen})
                next_frontier.append(child_id)
        if not next_frontier:
            break
        frontier = next_frontier
    return result


def _neighbors(store: GraphStore, node_id: str) -> list[tuple[str, str]]:
    """Return ``(neighbor_id, relation_label)`` pairs in every direction."""
    out: list[tuple[str, str]] = []
    for edge in store.edges_from(node_id, rel="PARENT_OF"):
        out.append((edge["dst"], "parent of"))
    for parent in store.callers_of(node_id, rel="PARENT_OF"):
        out.append((parent["id"], "child of"))
    for edge in store.edges_from(node_id, rel="MARRIED_TO"):
        out.append((edge["dst"], "married to"))
    for spouse in store.callers_of(node_id, rel="MARRIED_TO"):
        out.append((spouse["id"], "married to"))
    return out


def kinship_path(store: GraphStore, a: str, b: str) -> list[dict[str, Any]]:
    """Return the shortest chain of ``PARENT_OF`` / ``MARRIED_TO`` steps from a to b.

    :param store: The graph store.
    :param a: Starting person node id.
    :param b: Target person node id.
    :return: Alternating node dicts and ``{"relation": ...}`` step dicts;
        empty when ``a`` is unknown or unrelated to ``b``.
    """
    start = store.node(a)
    if start is None:
        return []
    if a == b:
        return [start]

    came_from: dict[str, tuple[str | None, str | None]] = {a: (None, None)}
    queue: deque[str] = deque([a])
    while queue:
        cur = queue.popleft()
        if cur == b:
            break
        for neighbor_id, label in _neighbors(store, cur):
            if neighbor_id in came_from:
                continue
            came_from[neighbor_id] = (cur, label)
            queue.append(neighbor_id)

    if b not in came_from:
        return []

    chain_ids: list[str] = []
    node_id: str | None = b
    while node_id is not None:
        chain_ids.append(node_id)
        node_id = came_from[node_id][0]
    chain_ids.reverse()

    result: list[dict[str, Any]] = []
    for i, nid in enumerate(chain_ids):
        node = store.node(nid)
        if node is None:
            continue
        if i > 0:
            result.append({"relation": came_from[nid][1]})
        result.append(node)
    return result


# ---------------------------------------------------------------------------
# ASCII family tree
# ---------------------------------------------------------------------------


@dataclass
class FamilyTree:
    """A rendered ASCII family tree.

    ``repr()`` and ``str()`` both return the rendered art, so printing an
    instance -- or evaluating it at a REPL prompt -- shows the tree directly.

    :param root_id: The node id the tree is rooted at.
    :param direction: ``"descendants"`` or ``"ancestors"``.
    :param text: The rendered tree.
    """

    root_id: str
    direction: str
    text: str

    def __repr__(self) -> str:
        return self.text

    def __str__(self) -> str:
        return self.text


def _spouse_names(store: GraphStore, person_id: str) -> list[str]:
    """Return a person's spouse names for the ASCII tree's ``m. ...`` suffix.

    ``MARRIED_TO`` is stored husband -> wife only but is conceptually
    symmetric, so both directions are walked (see the module docstring).

    :param store: The graph store to walk.
    :param person_id: The person's node id.
    :return: One name per spouse, in edge order; a redacted spouse's name
        is already ``"Living"`` on the node, so no separate check is needed.
    """
    names: list[str] = []
    for edge in store.edges_from(person_id, rel="MARRIED_TO"):
        n = store.node(edge["dst"])
        if n:
            names.append(n.get("name") or n["id"])
    for n in store.callers_of(person_id, rel="MARRIED_TO"):
        names.append(n.get("name") or n["id"])
    return names


def life_span(node: Mapping[str, Any]) -> str:
    """Return a person's years as ``1801-1875``, ``b. 1801``, ``d. 1875`` or ``""``.

    Reads only the temporal contract keys, so it works for any dated node.

    :param node: Node dict.
    :return: Display text, empty when the node carries no dates.
    """
    metadata = node.get("metadata") or {}
    start = metadata.get("occurred_start")
    end = metadata.get("occurred_end")
    if start and end:
        return f"{start[:4]}-{end[:4]}"
    if start:
        return f"b. {start[:4]}"
    if end:
        return f"d. {end[:4]}"
    return ""


def _label(store: GraphStore, node: dict[str, Any]) -> str:
    """Return one person's tree-row text: name, life span, spouse(s).

    :param store: The graph store, for looking up spouses.
    :param node: The person node to label.
    :return: E.g. ``"John Hartwell (1820-1891) m. Mary Ashcombe"``.
    """
    name = node.get("name") or node["id"]
    span = life_span(node)
    spouses = _spouse_names(store, node["id"])
    marriage = f" m. {', '.join(spouses)}" if spouses else ""
    return f"{name}{f' ({span})' if span else ''}{marriage}"


def _build_children(
    store: GraphStore, person_id: str, *, generations: int, depth: int, visited: set[str]
) -> list[dict[str, Any]]:
    """Recursively build the descendant subtree rooted at ``person_id``.

    :param store: The graph store to walk.
    :param person_id: The person to start from (not included in the result
        -- this returns their children, recursively).
    :param generations: Maximum depth to descend.
    :param depth: Current depth; the initial call passes ``0``.
    :param visited: Node ids already on the current path, to stay cycle-safe.
    :return: One ``{"node", "label", "children"}`` dict per child, each
        ``"children"`` itself built the same way one generation deeper.
    """
    if depth >= generations:
        return []
    out: list[dict[str, Any]] = []
    for edge in store.edges_from(person_id, rel="PARENT_OF"):
        child_id = edge["dst"]
        if child_id in visited:
            continue
        node = store.node(child_id)
        if node is None:
            continue
        out.append(
            {
                "node": node,
                "label": _label(store, node),
                "children": _build_children(
                    store,
                    child_id,
                    generations=generations,
                    depth=depth + 1,
                    visited=visited | {child_id},
                ),
            }
        )
    return out


def _build_parents(
    store: GraphStore, person_id: str, *, generations: int, depth: int, visited: set[str]
) -> list[dict[str, Any]]:
    """Recursively build the ancestor subtree rooted at ``person_id``.

    Mirrors :func:`_build_children`, walking ``PARENT_OF`` edges backward
    (``callers_of``) instead of forward -- same shape, same key name
    (``"children"``) for the ASCII renderer's benefit even though these are
    ancestors, not descendants.

    :param store: The graph store to walk.
    :param person_id: The person to start from (not included in the result).
    :param generations: Maximum depth to climb.
    :param depth: Current depth; the initial call passes ``0``.
    :param visited: Node ids already on the current path, to stay cycle-safe.
    :return: One ``{"node", "label", "children"}`` dict per parent.
    """
    if depth >= generations:
        return []
    out: list[dict[str, Any]] = []
    for node in store.callers_of(person_id, rel="PARENT_OF"):
        pid = node["id"]
        if pid in visited:
            continue
        out.append(
            {
                "node": node,
                "label": _label(store, node),
                "children": _build_parents(
                    store,
                    pid,
                    generations=generations,
                    depth=depth + 1,
                    visited=visited | {pid},
                ),
            }
        )
    return out


def _render(node: dict[str, Any], *, prefix: str, is_last: bool, is_root: bool) -> list[str]:
    """Recursively render one ``_build_children``/``_build_parents`` subtree as ASCII lines.

    :param node: A ``{"node", "label", "children"}`` dict from
        :func:`_build_children`/:func:`_build_parents`.
    :param prefix: The indentation/connector text accumulated so far.
    :param is_last: Whether this is the last sibling at its level (picks
        ``` `-- ``` vs ``+--``).
    :param is_root: Whether this is the tree's root (no connector, no
        indent contribution).
    :return: One line per node in this subtree, in depth-first order.
    """
    # Pure ASCII connectors (`+--`/`` `-- ``/`|`), not Unicode box-drawing --
    # this is genuinely an ASCII tree, not a Unicode one that merely looks
    # like one in most terminals.
    connector = "" if is_root else ("`-- " if is_last else "+-- ")
    lines = [prefix + connector + node["label"]]
    child_prefix = prefix if is_root else prefix + ("    " if is_last else "|   ")
    children = node["children"]
    for i, child in enumerate(children):
        lines.extend(
            _render(child, prefix=child_prefix, is_last=(i == len(children) - 1), is_root=False)
        )
    return lines


def tree_data(
    store: GraphStore,
    person_id: str,
    *,
    direction: str = "descendants",
    generations: int = 4,
) -> dict[str, Any] | None:
    """Return the nested family walk that every family-tree renderer draws.

    :func:`ascii_tree` and ``genealogy_kg.viz.pedigree_figure`` both consume
    this, so the ASCII art and the 2-D chart agree on shape by construction
    rather than by two independent walks kept in step by hand.

    :param store: The graph store.
    :param person_id: Node id such as ``person:I1``.
    :param direction: ``"descendants"`` (default) or ``"ancestors"``.
    :param generations: Maximum generations to walk.
    :return: ``{"node": ..., "label": ..., "children": [...]}`` nested to
        ``generations`` deep, or ``None`` when ``person_id`` is unknown.
    :raises ValueError: If ``direction`` is neither ``"descendants"`` nor ``"ancestors"``.
    """
    if direction not in ("descendants", "ancestors"):
        raise ValueError(f"direction must be 'descendants' or 'ancestors', got {direction!r}")

    root = store.node(person_id)
    if root is None:
        return None

    builder = _build_children if direction == "descendants" else _build_parents
    return {
        "node": root,
        "label": _label(store, root),
        "children": builder(
            store, person_id, generations=generations, depth=0, visited={person_id}
        ),
    }


def ascii_tree(
    store: GraphStore,
    person_id: str,
    *,
    direction: str = "descendants",
    generations: int = 4,
) -> FamilyTree:
    """Render an ASCII family tree rooted at a person.

    :param store: The graph store.
    :param person_id: Node id such as ``person:I1``.
    :param direction: ``"descendants"`` (default) or ``"ancestors"``.
    :param generations: Maximum generations to walk.
    :return: A :class:`FamilyTree`; its text says so when ``person_id`` is unknown.
    :raises ValueError: If ``direction`` is neither ``"descendants"`` nor ``"ancestors"``.
    """
    tree = tree_data(store, person_id, direction=direction, generations=generations)
    if tree is None:
        return FamilyTree(person_id, direction, f"(no such person: {person_id})")
    text = "\n".join(_render(tree, prefix="", is_last=True, is_root=True))
    return FamilyTree(person_id, direction, text)
