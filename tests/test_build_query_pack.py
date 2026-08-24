"""Phase 1 acceptance test: build the fixture, query it, and confirm pack()
returns the original GEDCOM record with correct line numbers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from genealogy_kg.config import load_sources
from genealogy_kg.gedcom import GedcomFile
from genealogy_kg.module import GenealogyKG


def _build(corpus_root: Path, living_cutoff_years: int | None = None) -> GenealogyKG:
    kg = GenealogyKG(
        repo_root=corpus_root,
        sources=[Path("family.ged")],
        living_cutoff_years=living_cutoff_years,
    )
    kg.build(wipe=True)
    return kg


def test_build_produces_the_expected_counts(corpus_root: Path) -> None:
    kg = _build(corpus_root)
    stats = kg.stats()
    assert stats["node_counts"]["person"] == 12
    assert stats["node_counts"]["family"] == 4
    assert stats["node_counts"]["source"] == 2
    assert stats["total_edges"] > 0


def test_query_finds_hartwell_by_occupation(corpus_root: Path) -> None:
    kg = _build(corpus_root)
    result = kg.query("chemist", k=5)
    node_ids = {n["id"] for n in result.nodes}
    assert any(nid.startswith("person:I7") or nid.startswith("event:I7:OCCU") for nid in node_ids)


def test_pack_returns_the_original_gedcom_record(corpus_root: Path) -> None:
    kg = _build(corpus_root)
    ged_path = corpus_root / "family.ged"
    ged_lines = ged_path.read_text().splitlines()

    with GedcomFile(ged_path) as gedcom:
        i1_span = gedcom.spans()["I1"]

    pack = kg.pack("John Hartwell ironmonger", k=5, hop=0)
    person_nodes = [n for n in pack.nodes if n.get("id") == "person:I1"]
    assert person_nodes, "expected person:I1 among the packed nodes"

    # kg_utils pads the record's own span with a few lines of context on
    # either side, so the window need not start exactly on "0 @I1@ INDI" --
    # it must still cover that line.
    snippet = person_nodes[0]["snippet"]
    start, end = snippet["start"], snippet["end"]
    assert start <= i1_span.lineno <= end
    assert ged_lines[i1_span.lineno - 1] == "0 @I1@ INDI"
    assert any("Hartwell" in line for line in ged_lines[start - 1 : end])
    assert "1 NOTE Emigrated" in "\n".join(ged_lines[start - 1 : end])


def test_pack_does_not_leak_a_redacted_living_person(corpus_root: Path) -> None:
    # Eliza (I4) is redacted under a 200-year cutoff (born 1851, no DEAT/BURI
    # -- see test_extractor.py's test_living_filter_redacts_undead_people_...).
    # She is I1's daughter via family F1, two hops from a query seeded on I1:
    # I1 -SPOUSE_IN-> F1 -CHILD_IN-> I4. hop=2 is enough to sweep her into
    # the pack the same way the acceptance test above sweeps in I1 at hop=0.
    kg = _build(corpus_root, living_cutoff_years=200)
    pack = kg.pack("John Hartwell ironmonger", k=5, hop=2)

    eliza_nodes = [n for n in pack.nodes if n.get("id") == "person:I4"]
    assert eliza_nodes, "expected the redacted person:I4 among the packed nodes"
    eliza = eliza_nodes[0]

    # The graph-level redaction (name/qualname) is already covered by
    # test_extractor.py; what this test guards is pack()'s own source
    # grounding, which reads a node's lineno/end_lineno straight off the
    # GEDCOM file regardless of what its name/docstring say. Without a real
    # span there, pack() cannot attach a snippet at all.
    assert "snippet" not in eliza
    assert not any("Eliza" in str(n.get("snippet", "")) for n in pack.nodes)


def test_build_persists_sources_so_a_fresh_instance_can_find_them(corpus_root: Path) -> None:
    # Every CLI command and the MCP server construct a *new* GenealogyKG per
    # invocation and rely on load_sources() to resolve what .build() used --
    # config.json is the only thing connecting them, and only build() itself
    # can be trusted to have written it (the CLI's own save_sources() call
    # is a belt-and-suspenders duplicate, not the only writer).
    assert load_sources(corpus_root) == []
    _build(corpus_root)
    assert load_sources(corpus_root) == [Path("family.ged")]


def test_pack_redacts_correctly_from_a_fresh_instance_after_build(corpus_root: Path) -> None:
    # Regression test: a GenealogyKG built directly (not through `genkg
    # build`, which used to be the only thing persisting sources) and then
    # queried through a *separate*, freshly constructed instance -- exactly
    # what every CLI command and the MCP server do -- must still redact.
    # Before build() persisted sources, the fresh instance resolved
    # sources=[], living_spans() came back trivially empty, and pack()
    # silently served Eliza's real GEDCOM record.
    _build(corpus_root, living_cutoff_years=200)
    fresh = GenealogyKG(repo_root=corpus_root, living_cutoff_years=200)

    pack = fresh.pack("John Hartwell ironmonger", k=5, hop=1)

    md = pack.to_markdown()
    assert "Eliza" not in md
    assert "Living" in md


def test_pack_refuses_to_serve_unredacted_content_when_sources_are_unresolved(
    corpus_root: Path,
) -> None:
    # Backstop for the same gap, for whatever config.json can't cover --
    # a deleted config file, a repo built by something other than this
    # module. living_cutoff_years is configured but no sources resolve at
    # all, so redaction cannot be verified: pack() must fail loud rather
    # than silently return whatever the SDK's own pack() found.
    _build(corpus_root, living_cutoff_years=200)
    (corpus_root / ".genealogykg" / "config.json").unlink()
    fresh = GenealogyKG(repo_root=corpus_root, living_cutoff_years=200)
    assert load_sources(corpus_root) == []

    with pytest.raises(RuntimeError, match="no GEDCOM sources"):
        fresh.pack("John Hartwell ironmonger", k=5, hop=1)


def test_analyze_reports_counts(corpus_root: Path) -> None:
    kg = _build(corpus_root)
    report = kg.analyze()
    assert "People: 12" in report
    assert "Families: 4" in report


def test_status_before_build_reports_no_store(corpus_root: Path) -> None:
    kg = GenealogyKG(repo_root=corpus_root, sources=[Path("family.ged")])
    assert not kg.db_path.exists()
