"""Tests for genealogy_kg.analysis: the data behind ``analyze`` and snapshots."""

from __future__ import annotations

from pathlib import Path

from genealogy_kg.module import GenealogyKG


def _build(corpus_root: Path, **kwargs: object) -> GenealogyKG:
    kg = GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")], **kwargs)  # type: ignore[arg-type]
    kg.build(wipe=True)
    return kg


def test_analysis_data_on_the_fixture(corpus_root: Path) -> None:
    data = _build(corpus_root).analysis()
    assert data["counts"]["person"] == 12
    assert data["counts"]["family"] == 4
    # John -> William -> Robert -> Margaret
    assert data["generation_depth"] == 4
    assert data["surnames"]["Hartwell"] == 7
    assert list(data["surnames"])[0] == "Hartwell"  # most common first
    assert data["date_coverage"]["person"] == {"dated": 12, "total": 12}
    assert data["date_coverage"]["family"] == {"dated": 4, "total": 4}
    # Every person in the fixture is in a family.
    assert data["unlinked_people"] == []
    # "Wales" and "Bavaria, Germany"'s parent "Germany" ... no: "Germany" is
    # WITHIN-linked from Bavaria. Only comma-less strings are flat.
    assert [p["name"] for p in data["places_without_hierarchy"]] == ["Wales"]
    assert data["living_redacted"] == 0


def test_analysis_counts_redacted_people(corpus_root: Path) -> None:
    data = _build(corpus_root, living_cutoff_years=200).analysis()
    assert data["living_redacted"] == 5
    assert "Hartwell" in data["surnames"]
    assert data["surnames"].get("Pryce") is None  # both Pryces are redacted


def test_analyze_report_sections(corpus_root: Path) -> None:
    report = _build(corpus_root).analyze()
    assert "- Generation depth: 4" in report
    assert "## Surnames" in report and "| Hartwell | 7 |" in report
    assert "## Date coverage" in report and "| person | 12 | 12 | 100% |" in report
    assert "### People with no family links: 0" in report
    assert "### Places with no hierarchy: 1" in report and "Wales" in report


def test_analyze_never_raises_without_a_store(tmp_path: Path) -> None:
    report = GenealogyKG(repo_root=tmp_path).analyze()
    assert report.startswith("# GenealogyKG Analysis")
