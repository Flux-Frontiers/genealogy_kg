"""genealogy_kg/corpus.py

Corpus-wide operations over ``corpora/entries/<genre>/<slug>/`` -- scanning
for what's built, building what isn't, and registering every entry with the
KGRAG registry so federated queries and ``kgrag`` tooling can find them.

Mirrors the pattern gutenberg_kg uses for its own ``corpus/<genre>/<book>/``
layout (``bookgraph.scan_corpus`` + ``ingest.register_book``/``add_to_corpus``),
scaled down to genealogy_kg's much smaller corpus and single-file-per-entry
layout.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from genealogy_kg.module import GenealogyKG

if TYPE_CHECKING:
    from kg_rag.corpus_registry import CorpusRegistry
    from kg_rag.primitives import KGEntry
    from kg_rag.registry import KGRegistry

#: Name of the corpus grouping every registered entry, regardless of genre.
TOP_CORPUS = "genealogy-all"


@dataclass
class EntryMeta:
    """One tree under ``corpora/entries/<genre>/<slug>/``.

    :param genre: The genre subdirectory name, e.g. ``royalty``.
    :param slug: The entry subdirectory name.
    :param entry_dir: Absolute path to the entry directory.
    :param ged_path: Absolute path to the entry's GEDCOM file.
    """

    genre: str
    slug: str
    entry_dir: Path
    ged_path: Path

    @property
    def name(self) -> str:
        """Registry name for this entry, e.g. ``genealogy-royalty-tudor``."""
        return f"genealogy-{self.genre}-{self.slug}"

    @property
    def store_dir(self) -> Path:
        """Path to this entry's ``.genealogykg/`` build store."""
        return self.entry_dir / ".genealogykg"

    @property
    def has_kg(self) -> bool:
        """Whether this entry's graph has been built."""
        return (self.store_dir / "graph.sqlite").exists()


@dataclass
class EntryResult:
    """Outcome of processing one entry during ``run_ingest``.

    :param meta: The entry that was processed.
    :param status: ``"built"``, ``"skipped"``, or ``"failed"``.
    :param registered: Whether it was added to the KGRAG registry.
    """

    meta: EntryMeta
    status: str
    registered: bool = False


@dataclass
class GenreStatus:
    """Aggregate build/registration/count status for one genre.

    :param genre: Genre directory name.
    :param entries: Total entries under this genre.
    :param built: Entries with a local ``.genealogykg/`` store.
    :param registered: Entries registered under this genre's corpus in the
        KGRAG registry, or ``None`` if the registry could not be checked.
    :param people: Total ``person`` node count across the genre's built stores.
    :param families: Total ``family`` node count across the genre's built stores.
    :param nodes: Total node count (every kind) across the genre's built stores.
    :param edges: Total edge count across the genre's built stores.
    """

    genre: str
    entries: int
    built: int
    registered: int | None
    people: int
    families: int
    nodes: int
    edges: int


_EMPTY_ENTRY_COUNTS: dict[str, int] = {"people": 0, "families": 0, "nodes": 0, "edges": 0}


def _entry_counts(path: Path) -> dict[str, int]:
    """Return people/family/node/edge counts from a built entry's ``graph.sqlite``.

    :param path: Path to a ``graph.sqlite`` file.
    :return: ``{"people", "families", "nodes", "edges"}``, all zero if the
        store is missing or unreadable.
    """
    if not path.exists():
        return dict(_EMPTY_ENTRY_COUNTS)
    try:
        with sqlite3.connect(str(path)) as con:
            kind_counts = dict(con.execute("SELECT kind, COUNT(*) FROM nodes GROUP BY kind"))
            edges = con.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        return {
            "people": kind_counts.get("person", 0),
            "families": kind_counts.get("family", 0),
            "nodes": sum(kind_counts.values()),
            "edges": edges,
        }
    except sqlite3.Error:
        return dict(_EMPTY_ENTRY_COUNTS)


def _registered_counts(genres: list[str], registry: str | Path | None) -> dict[str, int] | None:
    """Return ``{genre: registered_count}`` from the KGRAG registry.

    :param genres: Genre names to look up (each mapped to its
        ``genealogy-<genre>`` corpus).
    :param registry: Override path to the KGRAG registry database, or
        ``None`` for the default location.
    :return: Counts per genre, or ``None`` if kg-rag isn't installed or the
        registry can't be opened.
    """
    try:
        from kg_rag.corpus_registry import CorpusRegistry
        from kg_rag.registry import default_registry_path
    except ImportError:
        return None

    registry_path = Path(registry).resolve() if registry else default_registry_path()
    if not registry_path.exists():
        return None
    try:
        with CorpusRegistry(db_path=registry_path) as corp_reg:
            counts = {}
            for genre in genres:
                entry = corp_reg.get(f"genealogy-{genre}")
                counts[genre] = len(entry.kg_ids) if entry else 0
            return counts
    except Exception:  # noqa: BLE001
        return None


def collect_corpus_status(corpus_root: Path, registry: str | Path | None = None) -> dict[str, Any]:
    """Return a live, per-genre status summary for ``corpora/entries/``.

    Node/edge counts are read directly from each entry's own
    ``.genealogykg/graph.sqlite``, so this works without kg-rag installed;
    registration counts come from the KGRAG registry when available.

    :param corpus_root: Root of the per-entry corpus tree.
    :param registry: Override path to the KGRAG registry database.
    :return: Dict with ``genres`` (per-genre stat dicts), ``totals``, and
        ``registry_available``.
    """
    by_genre = scan_corpus(corpus_root)
    registered = _registered_counts(sorted(by_genre), registry)

    genre_stats: list[GenreStatus] = []
    for genre, entries in sorted(by_genre.items()):
        built = people = families = nodes = edges = 0
        for meta in entries:
            if meta.has_kg:
                built += 1
                counts = _entry_counts(meta.store_dir / "graph.sqlite")
                people += counts["people"]
                families += counts["families"]
                nodes += counts["nodes"]
                edges += counts["edges"]
        genre_stats.append(
            GenreStatus(
                genre=genre,
                entries=len(entries),
                built=built,
                registered=(registered.get(genre) if registered is not None else None),
                people=people,
                families=families,
                nodes=nodes,
                edges=edges,
            )
        )

    return {
        "genres": [asdict(g) for g in genre_stats],
        "totals": {
            "entries": sum(g.entries for g in genre_stats),
            "built": sum(g.built for g in genre_stats),
            "registered": sum(registered.values()) if registered is not None else None,
            "people": sum(g.people for g in genre_stats),
            "families": sum(g.families for g in genre_stats),
            "nodes": sum(g.nodes for g in genre_stats),
            "edges": sum(g.edges for g in genre_stats),
        },
        "registry_available": registered is not None,
    }


@dataclass
class IngestOptions:
    """Flags controlling :func:`run_ingest`.

    :param force_build: Rebuild even if ``.genealogykg/`` already exists.
    :param force_register: Re-register even if already present in the registry.
    :param register: Register built entries with the KGRAG registry.
    :param dry_run: Print actions without executing anything.
    """

    force_build: bool = False
    force_register: bool = False
    register: bool = True
    dry_run: bool = False


def scan_corpus(corpus_root: Path) -> dict[str, list[EntryMeta]]:
    """Walk ``corpus_root`` and return ``{genre: [EntryMeta, ...]}``.

    An entry directory with no ``*.ged`` file (e.g. a stray build cache left
    behind after its source was removed) is skipped.

    :param corpus_root: Root of the per-entry corpus tree, e.g.
        ``corpora/entries``.
    :return: Dict mapping genre name to its entries, sorted by slug.
    """
    result: dict[str, list[EntryMeta]] = {}
    if not corpus_root.is_dir():
        return result
    for genre_dir in sorted(corpus_root.iterdir()):
        if not genre_dir.is_dir() or genre_dir.name.startswith("."):
            continue
        entries: list[EntryMeta] = []
        for entry_dir in sorted(genre_dir.iterdir()):
            if not entry_dir.is_dir() or entry_dir.name.startswith("."):
                continue
            ged_files = sorted(entry_dir.glob("*.ged"))
            if not ged_files:
                continue
            entries.append(
                EntryMeta(
                    genre=genre_dir.name,
                    slug=entry_dir.name,
                    entry_dir=entry_dir,
                    ged_path=ged_files[0],
                )
            )
        if entries:
            result[genre_dir.name] = entries
    return result


def build_entry(meta: EntryMeta, *, force: bool = False, dry_run: bool = False) -> str:
    """Build (or skip) one entry's ``.genealogykg/`` store.

    :param meta: The entry to build.
    :param force: Rebuild even if a store already exists.
    :param dry_run: Print what would happen instead of building.
    :return: ``"built"``, ``"skipped"``, or ``"failed"``.
    """
    if meta.has_kg and not force:
        return "skipped"
    if dry_run:
        print(f"    [dry] genkg build --repo {meta.entry_dir} --source {meta.ged_path.name}")
        return "built"
    kg = GenealogyKG(repo_root=meta.entry_dir, sources=[meta.ged_path.relative_to(meta.entry_dir)])
    try:
        kg.build(wipe=True)
    except Exception as exc:  # noqa: BLE001
        print(f"    [x] build failed: {exc}")
        return "failed"
    finally:
        kg.close()
    return "built"


def ensure_corpus(
    corp_reg: CorpusRegistry,
    name: str,
    description: str = "",
    dry_run: bool = False,
) -> None:
    """Create a corpus grouping if it doesn't exist yet (idempotent).

    :param corp_reg: Open registry connection.
    :param name: Corpus name.
    :param description: Description to set if creating.
    :param dry_run: Print what would happen instead of creating.
    """
    from kg_rag.primitives import CorpusEntry

    if corp_reg.get(name) is not None:
        return
    if dry_run:
        print(f"  [dry] corpus create {name!r}")
        return
    corp_reg.create(CorpusEntry(name=name, description=description))
    print(f"  [+] corpus: {name}")


def register_entry(
    kg_reg: KGRegistry,
    meta: EntryMeta,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> KGEntry | None:
    """Register one entry's GenealogyKG store in the KGRAG registry.

    :param kg_reg: Open registry connection.
    :param meta: The entry to register.
    :param force: Re-register even if already present under this name.
    :param dry_run: Print what would happen instead of registering.
    :return: The KGEntry (new or existing), or ``None`` on dry-run.
    """
    from kg_rag.primitives import KGEntry, KGKind

    existing = kg_reg.get(meta.name)
    if existing is not None and not force:
        return existing
    if dry_run:
        print(f"    [dry] register {meta.name!r} -> {meta.entry_dir}")
        return None

    sqlite = meta.store_dir / "graph.sqlite"
    vectors = meta.store_dir / "vectors.sqlite"
    entry = KGEntry(
        name=meta.name,
        kind=KGKind.GENEALOGY,
        repo_path=meta.entry_dir,
        venv_path=meta.entry_dir / ".venv",
        sqlite_path=sqlite if sqlite.exists() else None,
        vectors_path=vectors if vectors.exists() else None,
        tags=[meta.genre, date.today().isoformat()],
    )
    kg_reg.register(entry)
    return entry


def add_to_corpus(
    corp_reg: CorpusRegistry,
    corpus_name: str,
    kg_entry: KGEntry,
    dry_run: bool = False,
) -> bool:
    """Add ``kg_entry`` to ``corpus_name`` (idempotent via ``add_kg``'s dedup).

    :param corp_reg: Open registry connection.
    :param corpus_name: Name of the corpus to add to.
    :param kg_entry: The registered entry to add.
    :param dry_run: Print what would happen instead of adding.
    :return: True on success (or dry-run).
    """
    if dry_run:
        print(f"    [dry] corpus add {corpus_name!r} {kg_entry.name!r}")
        return True
    result = corp_reg.add_kg(corpus_name, kg_entry.id)
    if result is None:
        print(f"    [!] corpus not found: {corpus_name!r}")
        return False
    return True


def run_ingest(
    corpus_root: Path,
    genres: list[str] | None,
    opts: IngestOptions,
    registry: str | Path | None = None,
) -> list[EntryResult]:
    """Build and register every entry under ``corpus_root``.

    :param corpus_root: Root of the per-entry corpus tree.
    :param genres: Genre names to process, or ``None`` for all present.
    :param opts: Ingest option flags.
    :param registry: Override path to the KGRAG registry database; ``None``
        uses the default location returned by ``default_registry_path()``.
    :return: One :class:`EntryResult` per processed entry.
    """
    by_genre = scan_corpus(corpus_root)
    if genres:
        missing = [g for g in genres if g not in by_genre]
        for g in missing:
            print(f"[!] Genre not found under {corpus_root}: {g}")
        by_genre = {g: v for g, v in by_genre.items() if g in genres}

    results: list[EntryResult] = []

    if not opts.register:
        for genre, entries in by_genre.items():
            print(f"=== {genre} ({len(entries)} entries) ===")
            for meta in entries:
                results.append(_process_entry(meta, None, None, opts))
        return results

    from kg_rag.corpus_registry import CorpusRegistry
    from kg_rag.registry import KGRegistry, default_registry_path

    registry_path = Path(registry).resolve() if registry else default_registry_path()
    with (
        KGRegistry(db_path=registry_path) as kg_reg,
        CorpusRegistry(db_path=registry_path) as corp_reg,
    ):
        print("--- Ensuring corpora ---")
        for genre in by_genre:
            ensure_corpus(
                corp_reg,
                f"genealogy-{genre}",
                description=f"GenealogyKG -- {genre}",
                dry_run=opts.dry_run,
            )
        ensure_corpus(
            corp_reg,
            TOP_CORPUS,
            description="GenealogyKG -- every corpora/entries tree",
            dry_run=opts.dry_run,
        )
        print()

        for genre, entries in by_genre.items():
            print(f"=== {genre} ({len(entries)} entries) ===")
            genre_corpus = f"genealogy-{genre}"
            for meta in entries:
                results.append(_process_entry(meta, kg_reg, corp_reg, opts, genre_corpus))

    return results


def _process_entry(
    meta: EntryMeta,
    kg_reg: KGRegistry | None,
    corp_reg: CorpusRegistry | None,
    opts: IngestOptions,
    genre_corpus: str | None = None,
) -> EntryResult:
    """Build, then (if requested) register, one entry. Prints progress."""
    print(f"  [{meta.slug}]")
    status = build_entry(meta, force=opts.force_build, dry_run=opts.dry_run)
    if status == "failed" or kg_reg is None:
        return EntryResult(meta=meta, status=status)

    existing = kg_reg.get(meta.name)
    verb = "re-registering" if existing and opts.force_register else "registering"
    if existing is not None and not opts.force_register:
        print(f"    [=] already registered: {meta.name}")
    else:
        print(f"    [.] {verb}: {meta.name}")
    entry = register_entry(kg_reg, meta, force=opts.force_register, dry_run=opts.dry_run)

    registered = False
    if entry is not None and corp_reg is not None:
        assert genre_corpus is not None
        add_to_corpus(corp_reg, genre_corpus, entry, dry_run=opts.dry_run)
        add_to_corpus(corp_reg, TOP_CORPUS, entry, dry_run=opts.dry_run)
        registered = True

    return EntryResult(meta=meta, status=status, registered=registered)


def print_ingest_summary(results: list[EntryResult]) -> None:
    """Print a totals line for a completed :func:`run_ingest` run.

    :param results: The results returned by :func:`run_ingest`.
    """
    built = sum(1 for r in results if r.status == "built")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")
    registered = sum(1 for r in results if r.registered)
    print()
    print(
        f"Done. {len(results)} entries -- built={built} skipped={skipped} "
        f"failed={failed} registered={registered}"
    )
    if failed:
        for r in results:
            if r.status == "failed":
                print(f"  [x] {r.meta.name}")


def survey(corpus_root: Path, genre: str | None = None) -> str:
    """Return a plain-text table of build status per entry, grouped by genre.

    :param corpus_root: Root of the per-entry corpus tree.
    :param genre: Optional genre filter; default surveys every genre.
    :return: Multi-line report, ready to print.
    """
    by_genre = scan_corpus(corpus_root)
    if genre:
        by_genre = {genre: by_genre.get(genre, [])}

    lines: list[str] = []
    total = built = 0
    for g, entries in by_genre.items():
        lines.append(f"\n=== {g} ({len(entries)} entries) ===")
        for meta in entries:
            total += 1
            built += int(meta.has_kg)
            lines.append(f"  {meta.slug:<55} kg={'OK' if meta.has_kg else '--'}")

    lines.append(f"\nTotals -- entries: {total}  built: {built}")
    return "\n".join(lines)
