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

from genealogy_kg.analysis import analyze_graph, render_report
from genealogy_kg.config import load_living_cutoff, load_sources, load_unknown_birth_policy
from genealogy_kg.extractor import EDGE_KINDS, GedcomExtractor
from genealogy_kg.lineage import FamilyTree, ascii_tree
from genealogy_kg.lineage import ancestors as _walk_ancestors
from genealogy_kg.lineage import descendants as _walk_descendants
from genealogy_kg.validation import (
    MAX_GENERATIONS,
    MAX_HOP,
    MAX_K,
    MAX_MAX_NODES,
    bounded_int,
    normalize_xref,
    require_query,
)

#: Relations followed by default during query/pack expansion. ``CITES`` is
#: excluded so a hit on a person does not drag every census page in with it,
#: and ``WITHIN`` so a hit on a country does not drag in every place inside it.
DEFAULT_GENEALOGY_RELS: tuple[str, ...] = tuple(
    r for r in EDGE_KINDS if r not in ("CITES", "WITHIN")
)


def _redact_snippet_overlaps(
    pack: SnippetPack, living_spans: dict[str, dict[str, tuple[int, int]]]
) -> SnippetPack:
    """Strip any line inside a living person's real record from every snippet.

    A snippet's own node is never the redacted person -- ``_living_person``
    already omits their span, so ``pack()`` cannot ground one for them
    directly. This closes the other path: a legitimate neighbor's
    context-padded window can run past its own record into the next one in
    the file, which may belong to a living person redacted everywhere else.

    :param pack: The result from ``super().pack()``.
    :param living_spans: From :meth:`~genealogy_kg.extractor.GedcomExtractor.living_spans`.
    :return: *pack*, mutated in place and returned for convenience.
    """
    for node in pack.nodes:
        snippet = node.get("snippet")
        if not snippet:
            continue
        file_spans = living_spans.get(snippet.get("path"))
        if not file_spans:
            continue
        start = snippet["start"]
        lines = snippet["text"].split("\n")
        kept = [
            line
            for offset, line in enumerate(lines)
            if not any(lo <= start + offset <= hi for lo, hi in file_spans.values())
        ]
        if len(kept) != len(lines):
            snippet["text"] = "\n".join(kept)
    return pack


class GenealogyKG(KGModule):
    """Knowledge graph over one or more GEDCOM files.

    :param repo_root: Repository root; ``.genealogykg/`` is created under it.
    :param db_path: SQLite graph path (default ``.genealogykg/graph.sqlite``).
    :param vectors_path: sqlite-vec path (default ``.genealogykg/vectors.sqlite``).
    :param sources: GEDCOM files to index, relative to ``repo_root``. When
        ``None``, resolved from ``.genealogykg/config.json`` or
        ``[tool.genealogykg] sources`` at build/status time.
    :param model: Sentence-transformer model name.
    :param living_cutoff_years: Redact people without a death record born
        within this many years of today. When ``None``, resolved from
        ``[tool.genealogykg] living_cutoff_years`` at build time; unset there
        too means no redaction.
    :param unknown_birth_policy: How to handle people without a usable birth
        date or death/burial evidence: ``"keep"`` or ``"redact"``. When
        ``None``, resolved from ``[tool.genealogykg] unknown_birth_policy``;
        unset there preserves the person.
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
        living_cutoff_years: int | None = None,
        unknown_birth_policy: str | None = None,
    ) -> None:
        super().__init__(repo_root, db_path, vectors_path, model=model)
        self.sources = sources
        self.living_cutoff_years = living_cutoff_years
        self.unknown_birth_policy = unknown_birth_policy

    def __enter__(self) -> GenealogyKG:
        """Return ``self`` for ``with GenealogyKG(...) as kg:``.

        Overrides :meth:`KGModule.__enter__`, which is typed to return the
        base class -- without this, ``with GenealogyKG(...) as kg:`` narrows
        ``kg`` to ``KGModule`` and every ``genealogy_kg``-specific attribute
        access (``.tree()``, ``.sources``, ...) fails type checking.

        :return: This instance.
        """
        return self

    def make_extractor(self) -> GedcomExtractor:
        """Return the GEDCOM extractor for the configured sources.

        :return: A :class:`~genealogy_kg.extractor.GedcomExtractor`.
        """
        sources = self.sources if self.sources is not None else load_sources(self.repo_root)
        cutoff = self.living_cutoff_years
        if cutoff is None:
            cutoff = load_living_cutoff(self.repo_root)
        policy = self.unknown_birth_policy
        if policy is None:
            policy = load_unknown_birth_policy(self.repo_root)
        return GedcomExtractor(
            self.repo_root,
            sources=sources,
            living_cutoff_years=cutoff,
            unknown_birth_policy=policy,
        )

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

        :param q: Natural-language query. Must be non-empty and at most
            :data:`~genealogy_kg.validation.MAX_QUERY_LEN` characters.
        :param k: Top-K semantic hits, ``1``-:data:`~genealogy_kg.validation.MAX_K`.
        :param hop: Graph expansion hops, ``0``-:data:`~genealogy_kg.validation.MAX_HOP`.
        :param rels: Edge types to follow; defaults to every relation except
            ``CITES``.
        :return: :class:`~kg_utils.specs.QueryResult`.
        :raises ValueError: If ``q``, ``k``, or ``hop`` is out of bounds.
        """
        q = require_query(q)
        bounded_int("k", k, 1, MAX_K)
        bounded_int("hop", hop, 0, MAX_HOP)
        return super().query(q, k=k, hop=hop, rels=rels, **kwargs)

    def pack(
        self,
        q: str,
        *,
        k: int = 8,
        hop: int = 1,
        rels: tuple[str, ...] = DEFAULT_GENEALOGY_RELS,
        max_nodes: int | None = None,
        **kwargs: Any,
    ) -> SnippetPack:
        """Hybrid query + source-grounded GEDCOM snippet extraction.

        :param q: Natural-language query. Must be non-empty and at most
            :data:`~genealogy_kg.validation.MAX_QUERY_LEN` characters.
        :param k: Top-K semantic hits, ``1``-:data:`~genealogy_kg.validation.MAX_K`.
        :param hop: Graph expansion hops, ``0``-:data:`~genealogy_kg.validation.MAX_HOP`.
        :param rels: Edge types to follow; defaults to every relation except
            ``CITES``.
        :param max_nodes: Maximum nodes in the pack, ``1``-
            :data:`~genealogy_kg.validation.MAX_MAX_NODES`. ``None`` uses the
            SDK default.
        :return: :class:`~kg_utils.specs.SnippetPack`. When living-person
            redaction is on, no returned snippet contains a line from a
            redacted person's real GEDCOM record -- see
            :func:`_redact_snippet_overlaps`.
        :raises ValueError: If ``q``, ``k``, ``hop``, or ``max_nodes`` is out
            of bounds.
        """
        q = require_query(q)
        bounded_int("k", k, 1, MAX_K)
        bounded_int("hop", hop, 0, MAX_HOP)
        if max_nodes is not None:
            bounded_int("max_nodes", max_nodes, 1, MAX_MAX_NODES)
            kwargs["max_nodes"] = max_nodes
        result = super().pack(q, k=k, hop=hop, rels=rels, **kwargs)
        extractor = self.make_extractor()
        if extractor.living_cutoff_years is None:
            return result
        living_spans = extractor.living_spans()
        if not living_spans:
            return result
        return _redact_snippet_overlaps(result, living_spans)

    def analysis(self) -> dict[str, Any]:
        """Return the analysis data: counts, generation depth, surnames, hygiene lists.

        :return: See :func:`genealogy_kg.analysis.analyze_graph`.
        """
        return analyze_graph(self.store)

    def analyze(self) -> str:
        """Return a Markdown analysis report. Must not raise.

        :return: Markdown text.
        """
        try:
            return render_report(self.analysis(), self.stats())
        except Exception as exc:  # noqa: BLE001 - analyze() must not raise
            return f"# GenealogyKG Analysis\n\nAnalysis failed: {exc}\n"

    def person(self, xref: str) -> dict[str, Any] | None:
        """Return the person node for a GEDCOM xref such as ``I7``.

        :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
        :return: Node dict, or ``None`` when absent.
        :raises ValueError: If ``xref`` is not a plausible GEDCOM pointer.
        """
        return self.node(f"person:{normalize_xref(xref)}")

    def tree(
        self, xref: str, *, direction: str = "descendants", generations: int = 4
    ) -> FamilyTree:
        """Render an ASCII family tree rooted at a person.

        :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
        :param direction: ``"descendants"`` (default) or ``"ancestors"``.
        :param generations: Maximum generations to walk, ``1``-
            :data:`~genealogy_kg.validation.MAX_GENERATIONS`.
        :return: A :class:`~genealogy_kg.lineage.FamilyTree`.
        :raises ValueError: If ``xref`` or ``generations`` is invalid.
        """
        xref = normalize_xref(xref)
        bounded_int("generations", generations, 1, MAX_GENERATIONS)
        return ascii_tree(
            self.store, f"person:{xref}", direction=direction, generations=generations
        )

    def ancestors(self, xref: str, *, generations: int = 4) -> list[dict[str, Any]]:
        """Return the ancestors of a person, nearest generation first.

        :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
        :param generations: Maximum generations to climb, ``1``-
            :data:`~genealogy_kg.validation.MAX_GENERATIONS`.
        :return: List of person node dicts, each with a ``generation`` key.
        :raises ValueError: If ``xref`` or ``generations`` is invalid.
        """
        xref = normalize_xref(xref)
        bounded_int("generations", generations, 1, MAX_GENERATIONS)
        return _walk_ancestors(self.store, f"person:{xref}", generations=generations)

    def descendants(self, xref: str, *, generations: int = 4) -> list[dict[str, Any]]:
        """Return the descendants of a person, nearest generation first.

        :param xref: Individual xref -- ``I7``, ``@I7@``, or ``person:I7``.
        :param generations: Maximum generations to descend, ``1``-
            :data:`~genealogy_kg.validation.MAX_GENERATIONS`.
        :return: List of person node dicts, each with a ``generation`` key.
        :raises ValueError: If ``xref`` or ``generations`` is invalid.
        """
        xref = normalize_xref(xref)
        bounded_int("generations", generations, 1, MAX_GENERATIONS)
        return _walk_descendants(self.store, f"person:{xref}", generations=generations)


__all__ = ["GenealogyKG", "DEFAULT_GENEALOGY_RELS"]
