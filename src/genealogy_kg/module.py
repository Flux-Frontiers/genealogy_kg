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

from genealogy_kg.extractor import EDGE_KINDS, GedcomExtractor

#: Relations followed by default during query/pack expansion. ``CITES`` is
#: excluded so a hit on a person does not drag every census page in with it.
DEFAULT_GENEALOGY_RELS: tuple[str, ...] = tuple(r for r in EDGE_KINDS if r != "CITES")


class GenealogyKG(KGModule):
    """Knowledge graph over one or more GEDCOM files.

    :param repo_root: Repository root; ``.genealogykg/`` is created under it.
    :param db_path: SQLite graph path (default ``.genealogykg/graph.sqlite``).
    :param vectors_path: sqlite-vec path (default ``.genealogykg/vectors.sqlite``).
    :param sources: GEDCOM files to index; defaults to the configured sources.
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

        :return: A :class:`GedcomExtractor`.
        """
        raise NotImplementedError("Phase 1")

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

    def analyze(self) -> str:
        """Return a Markdown analysis report. Must not raise.

        :return: Markdown text.
        """
        raise NotImplementedError("Phase 1")

    def person(self, xref: str) -> dict[str, Any] | None:
        """Return the person node for a GEDCOM xref such as ``I7``.

        :param xref: Individual xref without ``@``.
        :return: Node dict, or ``None`` when absent.
        """
        raise NotImplementedError("Phase 2")
