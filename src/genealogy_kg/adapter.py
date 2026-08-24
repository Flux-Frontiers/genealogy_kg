"""genealogy_kg/adapter.py

GenealogyKGAdapter -- KGRAG adapter for :class:`genealogy_kg.GenealogyKG`.
Requires the ``adapter`` extra (``kg-rag``).

This mirrors ``kg_rag.adapters.genealogy_adapter.GenealogyKGAdapter`` (the
one actually registered by kg-rag's own adapter factory) so this class is
usable standalone -- constructing a ``KGEntry`` and adapter directly,
without going through kg-rag's registry. The two are independent
implementations against the same ``kg_utils.pipeline.KGModule`` contract,
same as every other sibling KG in the fleet; see docs/DESIGN.md's Phase 2
note on that duplication and the drift it has already caused elsewhere.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from typing import Any

from kg_rag.adapters.base import KGAdapter, node_metadata
from kg_rag.primitives import CrossHit, CrossSnippet, KGEntry, KGKind, QueryScope
from kg_rag.viz import DisplayMode, RenderBackend, Viewport

from genealogy_kg.module import GenealogyKG


class GenealogyKGAdapter(KGAdapter):
    """Adapter wrapping :class:`genealogy_kg.GenealogyKG`.

    :param entry: KGEntry with ``kind=KGKind.GENEALOGY``.
    """

    def __init__(self, entry: KGEntry, embedder: Any = None) -> None:
        super().__init__(entry, embedder=embedder)
        self._kg: GenealogyKG | None = None

    def _load(self) -> None:
        if self._kg is not None:
            return
        entry = self.entry
        self._kg = GenealogyKG(
            repo_root=str(entry.repo_path),
            db_path=str(entry.sqlite_path) if entry.sqlite_path else None,
            vectors_path=str(entry.vectors_path) if entry.vectors_path else None,
        )

    def is_available(self) -> bool:
        """Return True when the store is built.

        :return: True if this adapter can serve queries.
        """
        return bool(self.entry.is_built)

    @staticmethod
    def _score(node: dict[str, Any]) -> float:
        return float(node.get("relevance", {}).get("score", 0.0))

    def query(
        self,
        q: str,
        k: int = 8,
        min_score: float = 0.0,
        semantic_floor: float = 0.0,
        scope: QueryScope | None = None,
    ) -> list[CrossHit]:
        """Query the genealogy graph and return ranked hits.

        :param q: Natural-language query string.
        :param k: Number of results to return.
        :param min_score: Minimum relevance score; hits below this are dropped.
        :param semantic_floor: If the best hit scores below this, the whole
            result set is discarded.
        :param scope: Accepted and ignored -- this adapter cannot push scope
            into its backend, so the orchestrator post-filters.
        :return: List of CrossHit objects.
        """
        self._load()
        assert self._kg is not None
        nodes = list(self._kg.query(q, k=k).nodes)[:k]
        if semantic_floor > 0.0 and nodes and self._score(nodes[0]) < semantic_floor:
            return []
        hits = []
        for n in nodes:
            score = self._score(n)
            if score < min_score:
                continue
            hits.append(
                CrossHit(
                    kg_name=self.entry.name,
                    kg_kind=KGKind.GENEALOGY,
                    node_id=n.get("id", ""),
                    name=n.get("name", ""),
                    kind=n.get("kind", ""),
                    score=score,
                    summary=n.get("docstring", ""),
                    source_path=n.get("module_path", ""),
                    metadata=node_metadata(n),
                )
            )
        return hits

    def pack(
        self,
        q: str,
        k: int = 8,
        context: int = 5,
        semantic_floor: float = 0.0,
        scope: QueryScope | None = None,
    ) -> list[CrossSnippet]:
        """Return GEDCOM record snippets for matching genealogy nodes.

        :param q: Natural-language query string.
        :param k: Number of snippets to return.
        :param context: Lines of context around the matched record.
        :param semantic_floor: If the best snippet scores below this, the
            whole result set is discarded.
        :param scope: Accepted and ignored -- see :meth:`query`.
        :return: List of CrossSnippet objects.
        """
        self._load()
        assert self._kg is not None
        nodes = [n for n in self._kg.pack(q, k=k, context=context).nodes if n.get("snippet")]
        if semantic_floor > 0.0 and nodes and self._score(nodes[0]) < semantic_floor:
            return []
        snippets = []
        for n in nodes:
            snippet = n["snippet"]
            snippets.append(
                CrossSnippet(
                    kg_name=self.entry.name,
                    kg_kind=KGKind.GENEALOGY,
                    node_id=n.get("id", ""),
                    source_path=n.get("module_path", ""),
                    lineno=snippet.get("start"),
                    end_lineno=snippet.get("end"),
                    content=snippet.get("text", ""),
                    score=self._score(n),
                    metadata=node_metadata(n),
                )
            )
        return snippets

    def stats(self) -> dict[str, Any]:
        """Return live statistics for this instance.

        :return: Dict with kind, node/edge counts, and person/family counts.
        """
        self._load()
        assert self._kg is not None
        try:
            s = self._kg.stats()
            counts = s.get("node_counts", {})
            return {
                "kind": "genealogy",
                "node_count": s.get("total_nodes", 0),
                "edge_count": s.get("total_edges", 0),
                "person_count": counts.get("person", 0),
                "family_count": counts.get("family", 0),
            }
        except Exception as exc:  # noqa: BLE001 - stats() must not raise
            return {"kind": "genealogy", "error": str(exc)}

    def analyze(self) -> str:
        """Return the Markdown analysis report.

        :return: Markdown text.
        """
        self._load()
        assert self._kg is not None
        try:
            return self._kg.analyze()
        except Exception as exc:  # noqa: BLE001 - analyze() must not raise
            return f"# GenealogyKG Analysis\n\nAnalysis failed: {exc}\n"

    # ------------------------------------------------------------------
    # Viewport display
    # ------------------------------------------------------------------

    def _display_root(self) -> str | None:
        """Return the person a family tree should be rooted at.

        The first person with no known parents -- a progenitor, which is what
        a descent chart wants at its top. Store order is GEDCOM file order, so
        the choice is deterministic for a given file.

        :return: A ``person:`` node id, or ``None`` when the graph has nobody.
        """
        assert self._kg is not None
        people = self._kg.store.query_nodes(kinds=["person"])
        if not people:
            return None
        for person in people:
            if not self._kg.store.callers_of(person["id"], rel="PARENT_OF"):
                return str(person["id"])
        return str(people[0]["id"])

    def display(self, viewport: Viewport) -> None:
        """Render the genealogy graph into a KGRAG viewport.

        ``SEMANTIC`` draws the descent chart from a progenitor -- for a family
        history the pedigree *is* the natural tree -- and ``ONTOLOGICAL`` draws
        the person/family network. Both need the ``viz`` extra; without it, or
        on a non-Streamlit backend, this falls back to the base placeholder
        card rather than failing the whole visualizer.

        :param viewport: The display region to render into. Never raises; a
            failure renders an error card inside the viewport instead.
        """
        if viewport.backend != RenderBackend.STREAMLIT:
            self._display_stub(viewport)
            return
        try:
            import streamlit as st  # noqa: PLC0415
            import streamlit.components.v1 as components  # noqa: PLC0415

            from genealogy_kg import viz as render  # noqa: PLC0415

            self._load()
            root = viewport.metadata.get("root_id") or self._display_root()
            if root is None:
                with viewport.container:
                    st.info(f"`{self.entry.name}` holds no people to draw.")
                return

            height = viewport.height or 600
            with viewport.container:
                if viewport.mode == DisplayMode.ONTOLOGICAL:
                    assert self._kg is not None
                    components.html(
                        render.network_html(self._kg.store, root_id=root, height=f"{height}px"),
                        height=height,
                    )
                else:
                    assert self._kg is not None
                    st.plotly_chart(
                        render.pedigree_figure(self._kg.store, root),
                        use_container_width=True,
                    )
        except ImportError:
            self._display_stub(viewport)
        except Exception as exc:  # noqa: BLE001 - display() must not raise
            try:
                viewport.container.error(f"GenealogyKG display failed: {exc}")
            except Exception:  # noqa: BLE001 - the viewport itself is unusable
                pass

    def _collect_snapshot_metrics(self) -> dict[str, Any]:
        """Return genealogy-specific metrics for the snapshot."""
        try:
            self._load()
            assert self._kg is not None
            s = self._kg.stats()
            counts = s.get("node_counts", {})
            return {
                "total_nodes": s.get("total_nodes", 0),
                "total_edges": s.get("total_edges", 0),
                "person_count": counts.get("person", 0),
                "family_count": counts.get("family", 0),
            }
        except Exception:  # noqa: BLE001 - snapshot metrics must not raise
            return {}
