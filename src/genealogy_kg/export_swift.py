"""genealogy_kg/export_swift.py

``genkg export-swift``: the on-device search pack the family app opens with no
server, in the format :mod:`kg_utils.devicepack` writes and the Knowledge Press
Swift kit reads.

Layout produced::

    <out>/
      manifest.json      pack version, the embedder, the pack, privacy settings
      family.pack        passages + FTS5
      family.vectors     their embeddings, int8 by default
      golden.json        reference top-k per query: the app's parity gate
      BGEEmbedder.mlpackage, vocab.txt, embedder.json   with --embedder-from

Every person, family, event, place and source becomes one passage, except a
redacted living person, whose placeholder says nothing worth finding. The
pack's columns carry the family the way they carry a book:

* ``kind``: the node kind (``person``, ``family``, ``event``, ...).
* ``genre``: the family line (see :func:`genealogy_kg.export.assign_lines`),
  so the app's scope picker becomes a line picker. Places and sources belong
  to no line.
* ``title``: the person's or family's name; an event's owner.
* ``node_title``: the event itself, or the node kind.
* ``author``: the surname, so author search becomes surname search.
* ``timestamp``: an event's date, for the date browse.
* ``content``: the prose summary the vectors were embedded from, followed for
  a person or family by their GEDCOM record lines.

The vectors need no re-embedding: the store was embedded with the
``kgmodule-utils`` default, ``BAAI/bge-small-en-v1.5``, the model the app's
Core ML embedder was converted from.

The same privacy gate as ``export-web`` runs first and last; see
:mod:`genealogy_kg.export`.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from genealogy_kg import __version__
from genealogy_kg.export import (
    UNKNOWN_LINE,
    ExportError,
    FamilyGraph,
    PrivacySettings,
    _is_living,
    _meta,
    _RecordReader,
    _replace_dir,
    assign_lines,
    check_replaceable,
    load_graph,
    refuse_on_hits,
    scan_for_names,
    verify_redaction,
)

if TYPE_CHECKING:
    from kg_utils.devicepack import Passage

    from genealogy_kg.module import GenealogyKG

#: The pack's file name, and the stem of its sidecar.
PACK_NAME: Final[str] = "family.pack"

#: ``kg_name`` and ``kg_kind`` on every passage.
KG_NAME: Final[str] = "genealogy"

#: Kinds exported, in the order written.
EXPORTED_KINDS: Final[tuple[str, ...]] = ("person", "family", "event", "place", "source")

#: The Core ML embedder and its tokenizer, as ``gutenkg export-embedder``
#: writes them. Copied in with ``--embedder-from``, carried over on ``--force``.
EMBEDDER_FILES: Final[tuple[str, ...]] = ("BGEEmbedder.mlpackage", "vocab.txt", "embedder.json")

#: Default golden queries: the kinds of question a family app is asked.
GOLDEN_QUERIES: Final[tuple[str, ...]] = (
    "who was born in Boston",
    "who emigrated from Ireland",
    "married in a church",
    "died in the war",
    "buried in the family cemetery",
    "occupation farmer",
    "the children of the first marriage",
    "a family that moved west",
)

#: Hits recorded per golden query.
GOLDEN_K: Final[int] = 10


@dataclass(frozen=True)
class SwiftExport:
    """What :func:`export_swift` wrote.

    :param out: The output directory.
    :param passages: Passages in the pack.
    :param vectors: Vectors in the sidecar.
    :param redacted: People treated as living.
    :param bytes: Pack plus sidecar.
    :param recall_at_10: Dense recall of the quantised vectors against the
        source store, when verified.
    :param embedder: Whether the Core ML embedder is in the directory.
    """

    out: Path
    passages: int
    vectors: int
    redacted: int
    bytes: int
    recall_at_10: float | None
    embedder: bool


def _owners(graph: FamilyGraph) -> dict[str, str]:
    """Event id -> the person or family it belongs to."""
    return {event: owner for owner, events in graph.events_of.items() for event in events}


def _family_line(graph: FamilyGraph, family_id: str, assignment: dict[str, str]) -> str:
    """A family's line: its husband's, else its wife's, else ``unknown``."""
    spouses = sorted(
        graph.spouses_of.get(family_id, []),
        key=lambda s: (str(_meta(graph.nodes[s]).get("sex", "")).upper() != "M", s),
    )
    for spouse in spouses:
        if assignment.get(spouse, UNKNOWN_LINE) != UNKNOWN_LINE:
            return assignment[spouse]
    return UNKNOWN_LINE


def family_passages(
    graph: FamilyGraph, assignment: dict[str, str], reader: _RecordReader
) -> list[Passage]:
    """Turn the graph into pack rows.

    :param graph: The loaded graph.
    :param assignment: Person id -> line id.
    :param reader: GEDCOM line reader, for record lines.
    :return: One :class:`~kg_utils.devicepack.Passage` per exported node.
    """
    from kg_utils.devicepack import Passage  # noqa: PLC0415 - NumPy-free, but keep it local

    owners = _owners(graph)
    passages: list[Passage] = []
    for kind in EXPORTED_KINDS:
        for node in graph.of_kind(kind):
            node_id = node["id"]
            meta = _meta(node)
            if kind == "person" and _is_living(node):
                continue
            owner = graph.nodes.get(owners.get(node_id, ""))
            if kind == "event" and (owner is None or _is_living(owner)):
                continue

            content = node.get("docstring") or node["name"]
            if kind in {"person", "family"} and node.get("lineno") and node.get("end_lineno"):
                record = reader.lines(node["module_path"], node["lineno"], node["end_lineno"])
                content = f"{content}\n\n" + "\n".join(record)

            if kind == "person":
                genre, title, surname = assignment[node_id], node["name"], meta.get("surname")
            elif kind == "family":
                genre = _family_line(graph, node_id, assignment)
                title, surname = node["name"], None
            elif kind == "event" and owner is not None:
                genre = (
                    assignment.get(owner["id"])
                    if owner["kind"] == "person"
                    else _family_line(graph, owner["id"], assignment)
                )
                title, surname = owner["name"], _meta(owner).get("surname")
            else:
                genre, title, surname = None, node["name"], None

            passages.append(
                Passage(
                    id=f"{KG_NAME}:{node_id}",
                    kg_name=KG_NAME,
                    kg_kind=KG_NAME,
                    kind=kind,
                    content=content,
                    name=node["name"],
                    title=title,
                    node_title=node["name"] if kind == "event" else kind.capitalize(),
                    author=surname,
                    genre=genre,
                    file_path=Path(node["module_path"]).name if node.get("module_path") else None,
                    char_start=node.get("lineno"),
                    timestamp=meta.get("occurred_start") if kind == "event" else None,
                )
            )
    return passages


def _source_vectors(kg: GenealogyKG) -> dict[str, Any]:
    """Read every stored vector, keyed by pack id."""
    from kg_utils.vector_backend import SqliteVecBackend  # noqa: PLC0415

    if not kg.vectors_path.exists():
        raise ExportError(
            f"no vector store at {kg.vectors_path}; run 'genkg build' first, "
            "or pass --no-vectors for a lexical-only pack"
        )
    backend = SqliteVecBackend(kg.vectors_path)
    try:
        return {f"{KG_NAME}:{node_id}": vec for node_id, vec in backend.iter_vectors()}
    finally:
        backend.close()


def _recall_at_10(pack: Path, vectors: dict[str, Any], query_vectors: list[Any]) -> float:
    """Dense recall@10 of the packed vectors against the source vectors.

    Ground truth is exact cosine over the float source vectors of the
    passages in the pack; the pack side is its own dense channel. This is what
    quantisation cost, and nothing else.
    """
    import numpy as np  # noqa: PLC0415
    from kg_utils.devicepack import search_pack  # noqa: PLC0415

    con = sqlite3.connect(f"file:{pack}?mode=ro", uri=True)
    try:
        ids = [r[0] for r in con.execute("SELECT id FROM passages WHERE vector_index IS NOT NULL")]
    finally:
        con.close()
    matrix = np.stack([np.asarray(vectors[i], dtype=np.float32) for i in ids])
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True).clip(min=1e-12)
    found = total = 0
    for query in query_vectors:
        q = np.asarray(query, dtype=np.float32)
        truth = {ids[i] for i in np.argsort(-(matrix @ (q / np.linalg.norm(q))))[:10]}
        hits, _ = search_pack(pack, q, "", k=10, lexical=False)
        found += len(truth & {h["node_id"] for h in hits})
        total += len(truth)
    return found / total if total else 1.0


def _copy_embedder(source: Path, dest: Path, model: str) -> None:
    """Copy the Core ML embedder in, refusing one converted from another model."""
    spec = source / "embedder.json"
    if not spec.exists():
        raise ExportError(f"{source} holds no embedder.json; run 'gutenkg export-embedder'")
    converted = json.loads(spec.read_text(encoding="utf-8")).get("model")
    if converted != model:
        raise ExportError(f"the embedder in {source} is {converted}; these vectors need {model}")
    for name in EMBEDDER_FILES:
        item = source / name
        if not item.exists():
            raise ExportError(f"{source} is missing {name}")
        if item.is_dir():
            shutil.copytree(item, dest / name)
        else:
            shutil.copy2(item, dest / name)


def export_swift(
    kg: GenealogyKG,
    out: Path,
    privacy: PrivacySettings,
    *,
    dtype: str = "int8",
    vectors: bool = True,
    golden: bool = True,
    verify: bool = False,
    queries: tuple[str, ...] = GOLDEN_QUERIES,
    embedder_from: Path | None = None,
    force: bool = False,
) -> SwiftExport:
    """Write the family app's search pack.

    :param kg: An open GenealogyKG.
    :param out: Output directory.
    :param privacy: Living-person settings.
    :param dtype: Sidecar dtype, ``"int8"`` or ``"float"``.
    :param vectors: Include the vector sidecar; ``False`` gives a lexical-only
        pack and no golden file.
    :param golden: Write ``golden.json``.
    :param verify: Measure the sidecar's dense recall@10 against the source
        vectors over the golden queries.
    :param queries: Golden queries.
    :param embedder_from: A directory holding the Core ML embedder files to
        copy in. Without it, embedder files already in *out* are kept.
    :param force: Replace an earlier export in *out*.
    :return: A :class:`SwiftExport` summary.
    :raises ExportError: If the privacy gate refuses, the store has no
        vectors, or *out* is not ours to replace.
    """
    from kg_utils.devicepack import (  # noqa: PLC0415 - NumPy is needed from here on
        build_golden,
        build_manifest,
        write_passage_pack,
    )

    out = out.resolve()
    check_replaceable(out, force=force, marker="manifest.json")
    names = verify_redaction(kg, privacy)
    graph = load_graph(kg.store)
    assignment, _lines = assign_lines(graph)
    passages = family_passages(graph, assignment, _RecordReader(kg.repo_root))
    source_vectors = _source_vectors(kg) if vectors else {}
    model = kg.model_name
    dim = len(next(iter(source_vectors.values()))) if source_vectors else 384

    tmp = out.parent / f".{out.name}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    recall: float | None = None
    try:
        stats = write_passage_pack(
            tmp / PACK_NAME,
            passages,
            source_vectors or None,
            dim=dim,
            embed_model=model,
            dtype=dtype,
            meta={"generator": f"genealogy_kg {__version__}"},
        )
        query_vectors: list[Any] = []
        if source_vectors and (golden or verify):
            query_vectors = kg.embedder.embed_texts(list(queries))
        if source_vectors and golden:
            document = build_golden(
                {stats.path.stem: stats.path},
                queries,
                query_vectors,
                k=GOLDEN_K,
                embed_model=model,
                dim=dim,
                dtype=dtype,
            )
            (tmp / "golden.json").write_text(json.dumps(document, indent=1) + "\n")
        if source_vectors and verify:
            recall = _recall_at_10(stats.path, source_vectors, query_vectors)

        manifest = build_manifest(
            [stats],
            embed_model=model,
            dim=dim,
            dtype=dtype,
            golden="golden.json" if (tmp / "golden.json").exists() else None,
            extra={
                "generator": f"genealogy_kg {__version__}",
                "sources": [Path(s).name for s in kg.make_extractor().sources],
                "privacy": privacy.as_dict(),
                "verification": None if recall is None else {"recall_at_10": round(recall, 4)},
            },
        )
        (tmp / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")

        refuse_on_hits(scan_for_names(tmp, names))

        if embedder_from is not None:
            _copy_embedder(embedder_from, tmp, model)
        elif out.exists():
            for name in EMBEDDER_FILES:
                if (out / name).exists():
                    shutil.move(str(out / name), str(tmp / name))
        _replace_dir(tmp, out, force=force, marker="manifest.json")
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)

    return SwiftExport(
        out=out,
        passages=stats.passages,
        vectors=stats.vectors,
        redacted=sum(_is_living(n) for n in graph.of_kind("person")),
        bytes=stats.total_bytes,
        recall_at_10=recall,
        embedder=(out / "embedder.json").exists(),
    )


__all__ = [
    "EMBEDDER_FILES",
    "GOLDEN_QUERIES",
    "KG_NAME",
    "PACK_NAME",
    "SwiftExport",
    "export_swift",
    "family_passages",
]
