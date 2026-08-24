"""genealogy_kg/adapter.py

GenealogyKGAdapter -- KGRAG adapter for :class:`genealogy_kg.GenealogyKG`.
Requires the ``adapter`` extra (``kg-rag``). kg-rag ships its own lazy
adapter as well once ``KGKind.GENEALOGY`` exists there (Phase 2).

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from typing import Any

from kg_rag.adapters.base import KGAdapter
from kg_rag.primitives import CrossHit, CrossSnippet, KGEntry, QueryScope


class GenealogyKGAdapter(KGAdapter):
    """Adapter wrapping :class:`genealogy_kg.GenealogyKG`.

    :param entry: KGEntry with ``kind="genealogy"``.
    """

    def __init__(self, entry: KGEntry, embedder=None) -> None:
        super().__init__(entry, embedder=embedder)
        self._kg: Any = None

    def is_available(self) -> bool:
        """Return True when the store is built."""
        return self.entry.is_built

    def query(
        self,
        q: str,
        k: int = 8,
        min_score: float = 0.0,
        semantic_floor: float = 0.0,
        scope: QueryScope | None = None,
    ) -> list[CrossHit]:
        """Query the genealogy graph and return ranked hits."""
        raise NotImplementedError("Phase 2")

    def pack(
        self,
        q: str,
        k: int = 8,
        context: int = 5,
        semantic_floor: float = 0.0,
        scope: QueryScope | None = None,
    ) -> list[CrossSnippet]:
        """Return GEDCOM record snippets for matching nodes."""
        raise NotImplementedError("Phase 2")

    def stats(self) -> dict[str, Any]:
        """Return live statistics for this instance."""
        raise NotImplementedError("Phase 2")

    def analyze(self) -> str:
        """Return the Markdown analysis report."""
        raise NotImplementedError("Phase 2")
