"""genealogy_kg/extractor.py

GedcomExtractor -- KGExtractor that turns a GEDCOM file into the graph model
described in docs/DESIGN.md: ``person``, ``family``, ``event``, ``place`` and
``source`` nodes; ``CHILD_IN``, ``SPOUSE_IN``, ``PARENT_OF``, ``MARRIED_TO``,
``HAS_EVENT``, ``OCCURRED_AT`` and ``CITES`` edges.

Extraction is deterministic: node ids derive from GEDCOM xrefs and tags, and
records are emitted in file order.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from kg_utils.extractor import KGExtractor
from kg_utils.specs import EdgeSpec, NodeSpec

NODE_KINDS: tuple[str, ...] = ("person", "family", "event", "place", "source")
EDGE_KINDS: tuple[str, ...] = (
    "CHILD_IN",
    "SPOUSE_IN",
    "PARENT_OF",
    "MARRIED_TO",
    "HAS_EVENT",
    "OCCURRED_AT",
    "CITES",
)


class GedcomExtractor(KGExtractor):
    """Extract nodes and edges from one or more GEDCOM files.

    :param repo_path: Repository root; source paths are stored relative to it.
    :param config: Optional configuration dict. Recognised key: ``sources``,
        a list of repo-relative ``.ged`` paths.
    """

    def __init__(
        self,
        repo_path: Path,
        config: dict[str, Any] | None = None,
        sources: list[Path] | None = None,
    ) -> None:
        super().__init__(repo_path, config)
        self.sources = sources or []

    def node_kinds(self) -> list[str]:
        """Return the node kinds this extractor emits.

        :return: ``["person", "family", "event", "place", "source"]``.
        """
        return list(NODE_KINDS)

    def edge_kinds(self) -> list[str]:
        """Return the edge relations this extractor emits.

        :return: The relations listed in :data:`EDGE_KINDS`.
        """
        return list(EDGE_KINDS)

    def extract(self) -> Iterator[NodeSpec | EdgeSpec]:
        """Yield the graph for every configured source file.

        :return: Iterator of :class:`NodeSpec` and :class:`EdgeSpec` objects.
        """
        raise NotImplementedError("Phase 1")
