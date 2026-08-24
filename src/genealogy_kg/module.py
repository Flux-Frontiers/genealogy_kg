"""genealogy_kg/module.py

GenealogyKG -- KGModule over GEDCOM files. Storage, indexing, ``query()``
and ``pack()`` come from ``kg_utils.pipeline.KGModule``; this class supplies
the extractor, the kind, the genealogy edge set as the default expansion
relations, the extra ``text`` index column, and lineage helpers.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kg_utils.pipeline import KGModule
from kg_utils.semantic import DEFAULT_MODEL
from kg_utils.specs import QueryResult, SnippetPack

from genealogy_kg.config import load_sources
from genealogy_kg.extractor import EDGE_KINDS, GedcomExtractor

#: Relations followed by default during query/pack expansion. ``CITES`` is
#: excluded so a hit on a person does not drag every census page in with it.
DEFAULT_GENEALOGY_RELS: tuple[str, ...] = tuple(r for r in EDGE_KINDS if r != "CITES")


class GenealogyKG(KGModule):
    """Knowledge graph over one or more GEDCOM files.

    :param repo_root: Repository root; ``.genealogykg/`` is created under it.
    :param db_path: SQLite graph path (default ``.genealogykg/graph.sqlite``).
    :param vectors_path: sqlite-vec path (default ``.genealogykg/vectors.sqlite``).
    :param sources: GEDCOM files to index, relative to ``repo_root``. When
        ``None``, resolved from ``.genealogykg/config.json`` or
        ``[tool.genealogykg] sources`` at build/status time.
    :param model: Sentence-transformer model name.
    """

    _default_dir = ".genealogykg"

    def __init__(
        self,
        repo_root: str | Path,
        db_path: str | Path | None = None,
        vectors_path: str | Path | None = None,
        *,
        sources: list[Path] | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        super().__init__(repo_root, db_path, vectors_path, model=model)
        self.sources = sources

    def make_extractor(self) -> GedcomExtractor:
        """Return the GEDCOM extractor for the configured sources.

        :return: A :class:`~genealogy_kg.extractor.GedcomExtractor`.
        """
        sources = self.sources if self.sources is not None else load_sources(self.repo_root)
        return GedcomExtractor(self.repo_root, sources=sources)

    def kind(self) -> str:
        """Return the KG kind string.

        :return: ``"genealogy"``.
        """
        return "genealogy"

    def index_meta_columns(self) -> tuple[str, ...]:
        """Vector metadata columns; adds ``text`` so hits surface their summary.

        :return: Column names.
        """
        return ("kind", "name", "qualname", "module_path", "text")

    def query(
        self,
        q: str,
        *,
        k: int = 8,
        hop: int = 1,
        rels: tuple[str, ...] = DEFAULT_GENEALOGY_RELS,
        **kwargs: Any,
    ) -> QueryResult:
        """Hybrid query, defaulting expansion to the genealogy edge set.

        :param q: Natural-language query.
        :param k: Top-K semantic hits.
        :param hop: Graph expansion hops.
        :param rels: Edge types to follow; defaults to every relation except
            ``CITES``.
        :return: :class:`~kg_utils.specs.QueryResult`.
        """
        return super().query(q, k=k, hop=hop, rels=rels, **kwargs)

    def pack(
        self,
        q: str,
        *,
        k: int = 8,
        hop: int = 1,
        rels: tuple[str, ...] = DEFAULT_GENEALOGY_RELS,
        **kwargs: Any,
    ) -> SnippetPack:
        """Hybrid query + source-grounded GEDCOM snippet extraction.

        :param q: Natural-language query.
        :param k: Top-K semantic hits.
        :param hop: Graph expansion hops.
        :param rels: Edge types to follow; defaults to every relation except
            ``CITES``.
        :return: :class:`~kg_utils.specs.SnippetPack`.
        """
        return super().pack(q, k=k, hop=hop, rels=rels, **kwargs)

    def analyze(self) -> str:
        """Return a Markdown analysis report. Must not raise.

        :return: Markdown text.
        """
        try:
            stats = self.stats()
        except Exception as exc:  # noqa: BLE001 - analyze() must not raise
            return f"# GenealogyKG Analysis\n\nAnalysis failed: {exc}\n"
        counts = stats.get("node_counts", {})
        lines = [
            "# GenealogyKG Analysis",
            "",
            f"- People: {counts.get('person', 0)}",
            f"- Families: {counts.get('family', 0)}",
            f"- Events: {counts.get('event', 0)}",
            f"- Places: {counts.get('place', 0)}",
            f"- Sources: {counts.get('source', 0)}",
            f"- Total nodes: {stats.get('total_nodes', 0)}",
            f"- Total edges: {stats.get('total_edges', 0)}",
        ]
        return "\n".join(lines) + "\n"

    def person(self, xref: str) -> dict[str, Any] | None:
        """Return the person node for a GEDCOM xref such as ``I7``.

        :param xref: Individual xref without ``@``.
        :return: Node dict, or ``None`` when absent.
        """
        return self.node(f"person:{xref}")


__all__ = ["GenealogyKG", "DEFAULT_GENEALOGY_RELS"]
