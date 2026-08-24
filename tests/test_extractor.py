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
        "WITHIN",
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


def test_within_edges_build_the_place_hierarchy(corpus_root: Path) -> None:
    items = _extract(corpus_root)
    nodes = {n.node_id: n for n in items if isinstance(n, NodeSpec)}
    within = {
        (e.source_id, e.target_id)
        for e in items
        if isinstance(e, EdgeSpec) and e.relation == "WITHIN"
    }

    # Every level of "Cincinnati, Hamilton, Ohio, USA" is a place node ...
    for pid in ("place:hamilton-ohio-usa", "place:ohio-usa", "place:usa"):
        assert pid in nodes and nodes[pid].kind == "place"
    assert nodes["place:ohio-usa"].name == "Ohio, USA"
    # ... chained by WITHIN, one edge per level.
    assert ("place:cincinnati-hamilton-ohio-usa", "place:hamilton-ohio-usa") in within
    assert ("place:hamilton-ohio-usa", "place:ohio-usa") in within
    assert ("place:ohio-usa", "place:usa") in within
    # Dayton shares the Ohio/USA levels rather than duplicating them.
    assert ("place:montgomery-ohio-usa", "place:ohio-usa") in within
    assert sum(1 for n in nodes.values() if n.node_id == "place:usa") == 1
    # A single-token place has no hierarchy at all.
    assert "place:wales" in nodes
    assert not any("place:wales" in pair for pair in within)
    # Emitted exactly once each.
    assert len(within) == len(
        [e for e in items if isinstance(e, EdgeSpec) and e.relation == "WITHIN"]
    )


def test_surname_is_stored_in_metadata(corpus_root: Path) -> None:
    nodes = [n for n in _extract(corpus_root) if isinstance(n, NodeSpec)]
    i1 = next(n for n in nodes if n.node_id == "person:I1")
    assert i1.metadata["surname"] == "Hartwell"


def _extract_living(corpus_root: Path, cutoff: int) -> list[NodeSpec | EdgeSpec]:
    extractor = GedcomExtractor(
        corpus_root, sources=[Path("family.ged")], living_cutoff_years=cutoff
    )
    return list(extractor.extract())


def test_living_filter_is_off_by_default(corpus_root: Path) -> None:
    nodes = [n for n in _extract(corpus_root) if isinstance(n, NodeSpec)]
    assert not any(n.name == "Living" for n in nodes)


def test_living_filter_redacts_undead_people_born_after_the_cutoff(corpus_root: Path) -> None:
    # A 200-year cutoff (from today, 2026+) catches everyone born after 1826
    # with no DEAT/BURI: Eliza (1851), Clara (1879), Samuel (1847), Edith
    # (1874), Louise (1880). Anna (1852) died AFT 1930 and Robert (1876) in
    # 1949, so they stay; so does everyone born before 1826.
    items = _extract_living(corpus_root, 200)
    nodes = {n.node_id: n for n in items if isinstance(n, NodeSpec)}
    living = {n.metadata["gedcom_xref"] for n in nodes.values() if n.metadata.get("living")}
    assert living == {"I4", "I8", "I9", "I10", "I11"}

    eliza = nodes["person:I4"]
    assert eliza.name == "Living" and eliza.qualname == "Living"
    assert "Hartwell" not in eliza.docstring
    assert "occurred_start" not in eliza.metadata and "surname" not in eliza.metadata
    assert eliza.metadata["sex"] == "F"  # structure kept, identity withheld
    # No event nodes for a living person: their dates and places would leak.
    assert not any(nid.startswith("event:I4:") for nid in nodes)
    # Lineage edges are kept, so ancestors/descendants still walk through her.
    edges = [e for e in items if isinstance(e, EdgeSpec)]
    assert any(e.relation == "CHILD_IN" and e.source_id == "person:I4" for e in edges)
    # Not-living people keep their full record.
    assert nodes["person:I1"].name == "John Hartwell"
    assert nodes["person:I7"].name == "Robert Hartwell"


def test_living_filter_withholds_the_name_from_other_nodes(corpus_root: Path) -> None:
    nodes = {n.node_id: n for n in _extract_living(corpus_root, 200) if isinstance(n, NodeSpec)}
    # Family F3 is Samuel Pryce (living) & Eliza Hartwell (living), child Edith (living).
    f3 = nodes["family:F3"]
    assert f3.name == "Living & Living"
    assert (
        "Pryce" not in f3.docstring and "Eliza" not in f3.docstring and "Edith" not in f3.docstring
    )
    assert "Married" not in f3.docstring and "occurred_start" not in f3.metadata
    assert "event:F3:MARR" not in nodes
    # John Hartwell's prose lists Eliza among nothing -- children are not
    # listed on the person -- but William's spouse phrase is intact and
    # Edith's parents would have named two living people.
    william = nodes["person:I3"]
    assert "Anna Kessler" in william.docstring
    # Family F2 (William & Anna, both dead) still lists Clara as Living.
    f2 = nodes["family:F2"]
    assert "Robert Hartwell" in f2.docstring and "Clara" not in f2.docstring
    assert "Living" in f2.docstring
