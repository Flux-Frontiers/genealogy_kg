"""Unit tests for genealogy_kg.corpus -- the corpora/entries/ scan, build and
registration helpers.

Filesystem-only tests (scan_corpus, build_entry, survey) run unconditionally.
Tests that touch the KGRAG registry require the ``adapter`` extra and are
skipped automatically when ``kg_rag`` is not installed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from genealogy_kg.corpus import (
    EntryMeta,
    IngestOptions,
    build_entry,
    run_ingest,
    scan_corpus,
    survey,
)

FIXTURE_GED = Path(__file__).resolve().parent / "fixtures" / "sample.ged"


def _make_corpus(root: Path, layout: dict[str, list[str]]) -> None:
    """Create a corpora/entries-style tree: ``{genre: [slug, ...]}``, each
    slug directory getting a copy of the fixture GEDCOM."""
    for genre, slugs in layout.items():
        for slug in slugs:
            entry_dir = root / genre / slug
            entry_dir.mkdir(parents=True)
            shutil.copy(FIXTURE_GED, entry_dir / f"{slug}.ged")


# ---------------------------------------------------------------------------
# scan_corpus
# ---------------------------------------------------------------------------


def test_scan_corpus_empty_root(tmp_path: Path) -> None:
    assert scan_corpus(tmp_path / "does-not-exist") == {}


def test_scan_corpus_finds_entries_by_genre(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"royalty": ["tudor", "habsburg"], "samples": ["bach"]})

    result = scan_corpus(tmp_path)

    assert set(result) == {"royalty", "samples"}
    assert [m.slug for m in result["royalty"]] == ["habsburg", "tudor"]
    assert [m.slug for m in result["samples"]] == ["bach"]


def test_scan_corpus_skips_entry_without_ged(tmp_path: Path) -> None:
    empty_dir = tmp_path / "misc" / "no-source"
    empty_dir.mkdir(parents=True)
    (empty_dir / ".genealogykg").mkdir()

    result = scan_corpus(tmp_path)

    assert result == {}


def test_scan_corpus_skips_hidden_dirs(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"royalty": ["tudor"]})
    (tmp_path / ".hidden-genre").mkdir()
    (tmp_path / "royalty" / ".hidden-entry").mkdir()

    result = scan_corpus(tmp_path)

    assert [m.slug for m in result["royalty"]] == ["tudor"]


# ---------------------------------------------------------------------------
# EntryMeta
# ---------------------------------------------------------------------------


def test_entry_meta_name() -> None:
    meta = EntryMeta(
        genre="royalty", slug="tudor", entry_dir=Path("/x"), ged_path=Path("/x/tudor.ged")
    )
    assert meta.name == "genealogy-royalty-tudor"


def test_entry_meta_has_kg_false_before_build(tmp_path: Path) -> None:
    meta = EntryMeta(genre="g", slug="s", entry_dir=tmp_path, ged_path=tmp_path / "s.ged")
    assert meta.has_kg is False


# ---------------------------------------------------------------------------
# build_entry
# ---------------------------------------------------------------------------


def test_build_entry_builds_store(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"samples": ["bach"]})
    meta = scan_corpus(tmp_path)["samples"][0]

    status = build_entry(meta)

    assert status == "built"
    assert meta.has_kg is True


def test_build_entry_skips_when_already_built(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"samples": ["bach"]})
    meta = scan_corpus(tmp_path)["samples"][0]
    build_entry(meta)

    status = build_entry(meta)

    assert status == "skipped"


def test_build_entry_force_rebuilds(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"samples": ["bach"]})
    meta = scan_corpus(tmp_path)["samples"][0]
    build_entry(meta)

    status = build_entry(meta, force=True)

    assert status == "built"


def test_build_entry_dry_run_does_not_touch_disk(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"samples": ["bach"]})
    meta = scan_corpus(tmp_path)["samples"][0]

    status = build_entry(meta, dry_run=True)

    assert status == "built"
    assert meta.has_kg is False


# ---------------------------------------------------------------------------
# survey
# ---------------------------------------------------------------------------


def test_survey_reports_unbuilt_and_built(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"samples": ["bach", "basic"]})
    build_entry(scan_corpus(tmp_path)["samples"][0])  # builds "bach"

    report = survey(tmp_path)

    assert "samples (2 entries)" in report
    assert "bach" in report and "kg=OK" in report
    assert "Totals -- entries: 2  built: 1" in report


def test_survey_genre_filter(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"samples": ["bach"], "royalty": ["tudor"]})

    report = survey(tmp_path, genre="royalty")

    assert "royalty" in report
    assert "samples" not in report


# ---------------------------------------------------------------------------
# run_ingest -- build only (no registry)
# ---------------------------------------------------------------------------


def test_run_ingest_no_register_builds_everything(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"samples": ["bach", "basic"]})

    results = run_ingest(tmp_path, None, IngestOptions(register=False))

    assert {r.status for r in results} == {"built"}
    assert all(not r.registered for r in results)
    assert all(r.meta.has_kg for r in results)


def test_run_ingest_genre_filter(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"samples": ["bach"], "royalty": ["tudor"]})

    results = run_ingest(tmp_path, ["royalty"], IngestOptions(register=False))

    assert [r.meta.genre for r in results] == ["royalty"]


# ---------------------------------------------------------------------------
# run_ingest -- with registration (requires kg_rag)
# ---------------------------------------------------------------------------

kg_rag = pytest.importorskip("kg_rag", reason="kg_rag not installed -- registration test skipped")


def test_run_ingest_registers_and_is_idempotent(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"samples": ["bach"]})
    registry_path = tmp_path / "registry.sqlite"

    first = run_ingest(tmp_path, None, IngestOptions(), registry=registry_path)
    assert first[0].status == "built"
    assert first[0].registered is True

    from kg_rag.corpus_registry import CorpusRegistry
    from kg_rag.registry import KGRegistry

    with KGRegistry(db_path=registry_path) as kg_reg:
        entry = kg_reg.get("genealogy-samples-bach")
        assert entry is not None
        assert entry.kind.value == "genealogy"

    with CorpusRegistry(db_path=registry_path) as corp_reg:
        samples_corpus = corp_reg.get("genealogy-samples")
        all_corpus = corp_reg.get("genealogy-all")
        assert samples_corpus is not None
        assert all_corpus is not None
        assert samples_corpus.size == 1
        assert all_corpus.size == 1

    # Re-running is a no-op: already built, already registered.
    second = run_ingest(tmp_path, None, IngestOptions(), registry=registry_path)
    assert second[0].status == "skipped"
    assert second[0].registered is True

    with CorpusRegistry(db_path=registry_path) as corp_reg:
        # add_kg dedups, so re-running does not duplicate membership.
        all_corpus = corp_reg.get("genealogy-all")
        assert all_corpus is not None
        assert all_corpus.size == 1


def test_run_ingest_dry_run_registers_nothing(tmp_path: Path) -> None:
    _make_corpus(tmp_path, {"samples": ["bach"]})
    registry_path = tmp_path / "registry.sqlite"

    results = run_ingest(tmp_path, None, IngestOptions(dry_run=True), registry=registry_path)

    assert results[0].registered is False

    from kg_rag.registry import KGRegistry

    with KGRegistry(db_path=registry_path) as kg_reg:
        assert kg_reg.get("genealogy-samples-bach") is None
