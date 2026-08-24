"""genealogy_kg/lineage.py

Ancestor, descendant and kinship walks over ``GraphStore``. Ancestors follow
``PARENT_OF`` inbound (``callers_of``), descendants follow it outbound
(``edges_from``); no second edge kind is stored.

Phase 2 work. See docs/DESIGN.md.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from typing import Any

from kg_utils.store import GraphStore


def ancestors(store: GraphStore, person_id: str, *, generations: int = 4) -> list[dict[str, Any]]:
    """Return ancestors of a person, nearest generation first.

    :param store: The graph store.
    :param person_id: Node id such as ``person:I7``.
    :param generations: Maximum generations to climb.
    :return: Node dicts, each with a ``generation`` key (1 = parents).
    """
    raise NotImplementedError("Phase 2")


def descendants(store: GraphStore, person_id: str, *, generations: int = 4) -> list[dict[str, Any]]:
    """Return descendants of a person, nearest generation first.

    :param store: The graph store.
    :param person_id: Node id such as ``person:I1``.
    :param generations: Maximum generations to descend.
    :return: Node dicts, each with a ``generation`` key (1 = children).
    """
    raise NotImplementedError("Phase 2")


def kinship_path(store: GraphStore, a: str, b: str) -> list[dict[str, Any]]:
    """Return the shortest chain of ``PARENT_OF`` / ``MARRIED_TO`` steps from a to b.

    :param store: The graph store.
    :param a: Starting person node id.
    :param b: Target person node id.
    :return: Alternating node and edge dicts; empty when unrelated.
    """
    raise NotImplementedError("Phase 2")
