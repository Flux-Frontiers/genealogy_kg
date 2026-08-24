"""Tests for genealogy_kg.extractor against the fixture GEDCOM."""

from __future__ import annotations

from pathlib import Path

from kg_utils.specs import EdgeSpec, NodeSpec

from genealogy_kg.extractor import GedcomExtractor


def _extract(corpus_root: Path) -> list[NodeSpec | EdgeSpec]:
    extractor = GedcomExtractor(corpus_root, sources=[Path("family.ged")])
    return list(extractor.extract())


def test_node_kinds_and_edge_kinds() -> None:
    extractor = GedcomExtractor(Path("."), sources=[])
    assert extractor.node_kinds() == ["person", "family", "event", "place", "source"]
    assert set(extractor.edge_kinds()) == {
        "CHILD_IN",
        "SPOUSE_IN",
        "PARENT_OF",
        "MARRIED_TO",
        "HAS_EVENT",
        "OCCURRED_AT",
        "CITES",
    }


def test_counts_match_fixture(corpus_root: Path) -> None:
    items = _extract(corpus_root)
    nodes = [n for n in items if isinstance(n, NodeSpec)]
    edges = [e for e in items if isinstance(e, EdgeSpec)]

    by_kind: dict[str, int] = {}
    for n in nodes:
        by_kind[n.kind] = by_kind.get(n.kind, 0) + 1
    assert by_kind["person"] == 12
    assert by_kind["family"] == 4
    assert by_kind["source"] == 2

    by_rel: dict[str, int] = {}
    for e in edges:
        by_rel[e.relation] = by_rel.get(e.relation, 0) + 1
    assert by_rel["MARRIED_TO"] == 4
    assert by_rel["CHILD_IN"] == 7  # 3 + 2 + 1 + 1 children across the 4 families


def test_ids_are_stable_across_two_extractions(corpus_root: Path) -> None:
    first = {n.node_id for n in _extract(corpus_root) if isinstance(n, NodeSpec)}
    second = {n.node_id for n in _extract(corpus_root) if isinstance(n, NodeSpec)}
    assert first == second
    assert "person:I1" in first
    assert "family:F1" in first
    assert "source:S1" in first


def test_every_dated_node_carries_the_temporal_contract(corpus_root: Path) -> None:
    nodes = [n for n in _extract(corpus_root) if isinstance(n, NodeSpec)]
    i1 = next(n for n in nodes if n.node_id == "person:I1")
    assert i1.metadata["occurred_start"] == "1820"  # ABT 1820
    assert i1.metadata["occurred_end"] == "1891-11-07"  # 7 NOV 1891

    i2 = next(n for n in nodes if n.node_id == "person:I2")
    assert i2.metadata["occurred_start"] == "1824-03-12"
    assert i2.metadata["occurred_end"] == "1901"  # BET 1899 AND 1901 -> the later bound

    marr_f1 = next(n for n in nodes if n.node_id == "event:F1:MARR")
    assert marr_f1.metadata["occurred_start"] == "1846-06-03"


def test_parent_of_edges_come_only_from_the_family_record(corpus_root: Path) -> None:
    edges = [e for e in _extract(corpus_root) if isinstance(e, EdgeSpec)]
    parent_of = [(e.source_id, e.target_id) for e in edges if e.relation == "PARENT_OF"]
    assert ("person:I1", "person:I3") in parent_of
    assert ("person:I2", "person:I3") in parent_of
    # No duplicates: exactly husband+wife per child, never re-derived from FAMC.
    assert len(parent_of) == len(set(parent_of))


def test_event_ids_disambiguate_repeats(corpus_root: Path) -> None:
    nodes = [n for n in _extract(corpus_root) if isinstance(n, NodeSpec)]
    event_ids = {n.node_id for n in nodes if n.kind == "event"}
    assert "event:I1:BIRT" in event_ids
    assert "event:I1:RESI" in event_ids  # only one RESI in the fixture, no ":2" suffix


def test_place_nodes_deduplicate_across_records(corpus_root: Path) -> None:
    nodes = [n for n in _extract(corpus_root) if isinstance(n, NodeSpec)]
    cincinnati_nodes = [
        n for n in nodes if n.kind == "place" and n.node_id == "place:cincinnati-hamilton-ohio-usa"
    ]
    assert len(cincinnati_nodes) == 1
    edges = [e for e in _extract(corpus_root) if isinstance(e, EdgeSpec)]
    occurred_at = [
        e
        for e in edges
        if e.relation == "OCCURRED_AT" and e.target_id == "place:cincinnati-hamilton-ohio-usa"
    ]
    assert len(occurred_at) > 1  # multiple events happened there


def test_cites_edges_reference_sources(corpus_root: Path) -> None:
    edges = [e for e in _extract(corpus_root) if isinstance(e, EdgeSpec)]
    cites = [(e.source_id, e.target_id) for e in edges if e.relation == "CITES"]
    assert ("event:I1:DEAT", "source:S1") in cites
    assert ("event:I1:RESI", "source:S2") in cites
    assert ("event:F1:MARR", "source:S1") in cites
    # Attributed once, to the event -- not duplicated onto the family node.
    assert ("family:F1", "source:S1") not in cites
