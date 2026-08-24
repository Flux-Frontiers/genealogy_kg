"""Tests for genealogy_kg.gedcom."""

from __future__ import annotations

from pathlib import Path

from genealogy_kg.gedcom import GedcomFile, place_slug


def test_place_slug() -> None:
    assert place_slug("Leeds, Yorkshire, England") == "leeds-yorkshire-england"
    assert place_slug("  Dayton, Montgomery, Ohio, USA  ") == "dayton-montgomery-ohio-usa"
    assert place_slug("") == "unknown-place"


def test_spans_cover_every_level0_record(sample_ged: Path) -> None:
    with GedcomFile(sample_ged) as gedcom:
        spans = gedcom.spans()
    xrefs = {s.xref for s in spans.values()}
    assert xrefs == {f"I{i}" for i in range(1, 13)} | {f"F{i}" for i in range(1, 5)} | {
        "S1",
        "S2",
        "SUB1",
    }
    for span in spans.values():
        assert span.lineno <= span.end_lineno


def test_span_includes_multiline_note(sample_ged: Path) -> None:
    # I1's NOTE has a CONT continuation line; the span must reach past it,
    # up to (not including) I2's own first line.
    with GedcomFile(sample_ged) as gedcom:
        spans = gedcom.spans()
        i1, i2 = spans["I1"], spans["I2"]
    assert i1.end_lineno >= i1.lineno + 5  # BIRT/DEAT/BURI/OCCU/RESI/NOTE/CONT lines
    assert i1.end_lineno < i2.lineno


def test_line_of_matches_a_known_tag_line(sample_ged: Path, corpus_root: Path) -> None:
    ged_path = corpus_root / "family.ged"
    lines = ged_path.read_text().splitlines()
    birt_line = next(i for i, line in enumerate(lines, start=1) if line == "1 BIRT")
    with GedcomFile(ged_path) as gedcom:
        ind = next(gedcom.records("INDI"))
        birt = ind.sub_tag("BIRT")
        assert gedcom.line_of(birt.offset) == birt_line
