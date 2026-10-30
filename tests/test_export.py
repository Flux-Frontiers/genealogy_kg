"""Tests for genealogy_kg.export (``genkg export-web``).

Line tests use the fixture GEDCOM: John Hartwell (I1) and Mary Ashcombe (I2)
found the Hartwell line; Anna Kessler (I6), Samuel Pryce (I9) and Louise
Brandt (I11) married into it, so each founds a line of their own, and Edith
Pryce (I10) is in her father's.

Privacy tests use an invented family written per test: Orrin and Hester
Vantablack (dead), their son Bartholomew (dead), and his children Zephyrine
(born 2000, living) and a second Orrin (born 1995, living), who shares his
grandfather's name.

The house test uses a surname-less family: Terah's three children make him a
head, so his descent is the house of Terah; his wife Amathlai has no parents
and no house; and Zimri, living, cannot head one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from genealogy_kg.cli import cli
from genealogy_kg.export import (
    UNKNOWN_LINE,
    ExportError,
    PrivacySettings,
    assign_lines,
    export_web,
    load_graph,
    scan_for_names,
)
from genealogy_kg.module import GenealogyKG

LIVING_GED = """\
0 HEAD
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
0 @A@ INDI
1 NAME Orrin /Vantablack/
1 SEX M
1 BIRT
2 DATE 1890
1 DEAT
2 DATE 1960
0 @B@ INDI
1 NAME Hester /Moss/
1 SEX F
1 BIRT
2 DATE 1895
1 DEAT
2 DATE 1970
0 @C@ INDI
1 NAME Bartholomew /Vantablack/
1 SEX M
1 BIRT
2 DATE 1925
1 DEAT
2 DATE 1999
1 NOTE A quiet man.
0 @E@ INDI
1 NAME Ione /Brightwater/
1 SEX F
1 BIRT
2 DATE 1930
1 DEAT
2 DATE 2010
0 @D@ INDI
1 NAME Zephyrine /Vantablack/
1 SEX F
1 BIRT
2 DATE 2000
0 @N@ INDI
1 NAME Orrin /Vantablack/
1 SEX M
1 BIRT
2 DATE 1995
0 @F1@ FAM
1 HUSB @A@
1 WIFE @B@
1 CHIL @C@
0 @F2@ FAM
1 HUSB @C@
1 WIFE @E@
1 CHIL @D@
1 CHIL @N@
0 TRLR
"""

HOUSE_GED = """\
0 HEAD
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
0 @T@ INDI
1 NAME Terah //
1 SEX M
1 BIRT
2 DATE 1800
0 @W@ INDI
1 NAME Amathlai //
1 SEX F
1 BIRT
2 DATE 1802
0 @A@ INDI
1 NAME Abram //
1 SEX M
1 BIRT
2 DATE 1825
0 @N@ INDI
1 NAME Nahor //
1 SEX M
1 BIRT
2 DATE 1827
0 @H@ INDI
1 NAME Haran //
1 SEX M
1 BIRT
2 DATE 1829
0 @I@ INDI
1 NAME Isaac //
1 SEX M
1 BIRT
2 DATE 1850
0 @J@ INDI
1 NAME Jacob //
1 SEX M
1 BIRT
2 DATE 1875
0 @Z@ INDI
1 NAME Zimri //
1 SEX M
1 BIRT
2 DATE 1990
0 @Z1@ INDI
1 NAME Zia //
1 SEX F
1 BIRT
2 DATE 2015
0 @Z2@ INDI
1 NAME Zed //
1 SEX M
1 BIRT
2 DATE 2017
0 @Z3@ INDI
1 NAME Zev //
1 SEX M
1 BIRT
2 DATE 2019
0 @F1@ FAM
1 HUSB @T@
1 WIFE @W@
1 CHIL @A@
1 CHIL @N@
1 CHIL @H@
0 @F2@ FAM
1 HUSB @A@
1 CHIL @I@
0 @F3@ FAM
1 HUSB @I@
1 CHIL @J@
0 @F4@ FAM
1 HUSB @Z@
1 CHIL @Z1@
1 CHIL @Z2@
1 CHIL @Z3@
0 TRLR
"""

LIVING_NAME = "Zephyrine Vantablack"
PRIVACY = PrivacySettings(living_cutoff_years=100)


def _build(root: Path, ged: str, *, cutoff: int) -> GenealogyKG:
    (root / "family.ged").write_text(ged, encoding="utf-8")
    kg = GenealogyKG(
        repo_root=root,
        sources=[Path("family.ged")],
        living_cutoff_years=cutoff,
        unknown_birth_policy="redact",
    )
    kg.build(wipe=True)
    return kg


def _repo_dir(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


def _all_text(root: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*") if p.is_file())


@pytest.fixture
def sample_kg(corpus_root: Path) -> GenealogyKG:
    kg = GenealogyKG(
        repo_root=corpus_root,
        sources=[Path("family.ged")],
        living_cutoff_years=100,
        unknown_birth_policy="redact",
    )
    kg.build(wipe=True)
    return kg


# ---------------------------------------------------------------------------
# Privacy settings
# ---------------------------------------------------------------------------


def test_privacy_refuses_no_cutoff_without_include_living() -> None:
    with pytest.raises(ExportError, match="without a living-person cutoff"):
        PrivacySettings(living_cutoff_years=None)


def test_privacy_refuses_cutoff_and_include_living_together() -> None:
    with pytest.raises(ExportError, match="not both"):
        PrivacySettings(living_cutoff_years=100, include_living=True)


def test_privacy_records_its_settings() -> None:
    assert PrivacySettings(living_cutoff_years=90, unknown_birth_policy="keep").as_dict() == {
        "living_cutoff_years": 90,
        "unknown_birth_policy": "keep",
        "include_living": False,
    }


# ---------------------------------------------------------------------------
# The privacy gate, end to end
# ---------------------------------------------------------------------------


def test_export_refuses_a_store_built_without_redaction(tmp_path: Path) -> None:
    kg = _build(_repo_dir(tmp_path), LIVING_GED, cutoff=0)
    with pytest.raises(ExportError, match="not redacted in the store"):
        export_web(kg, tmp_path / "out", PRIVACY)
    assert not (tmp_path / "out").exists()


def test_export_carries_no_living_name(tmp_path: Path) -> None:
    kg = _build(_repo_dir(tmp_path), LIVING_GED, cutoff=100)
    result = export_web(kg, tmp_path / "out", PRIVACY)
    text = _all_text(tmp_path / "out")
    assert LIVING_NAME.casefold() not in text.casefold()
    assert "Zephyrine" not in text
    assert result.redacted == 2  # Zephyrine and the younger Orrin
    catalog = json.loads((tmp_path / "out" / "catalog.json").read_text())
    assert catalog["meta"]["privacy"]["living_cutoff_years"] == 100
    living = [p for p in catalog["people"] if p["living"]]
    assert {p["name"] for p in living} == {"Living"}
    assert all(p["born"] is None and p["surname"] is None for p in living)
    page = json.loads((tmp_path / "out" / "people" / "D.json").read_text())
    assert page["summary"] is None and page["events"] == [] and page["record"] is None


def test_export_refuses_a_note_naming_a_living_person(tmp_path: Path) -> None:
    ged = LIVING_GED.replace("1 NOTE A quiet man.", f"1 NOTE Father of {LIVING_NAME}.")
    kg = _build(_repo_dir(tmp_path), ged, cutoff=100)
    # Named by xref and file, so the record to fix can be found; never by name.
    with pytest.raises(ExportError, match=r"living person D's name appears in people/C\.json"):
        export_web(kg, tmp_path / "out", PRIVACY)
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".out.tmp"))


def test_a_living_namesake_of_an_ancestor_does_not_block_the_export(tmp_path: Path) -> None:
    """The younger Orrin is living; his grandfather's page must still name Orrin."""
    kg = _build(_repo_dir(tmp_path), LIVING_GED, cutoff=100)
    export_web(kg, tmp_path / "out", PRIVACY)
    page = json.loads((tmp_path / "out" / "people" / "A.json").read_text())
    assert page["name"] == "Orrin Vantablack"


def test_include_living_exports_everyone_and_says_so(tmp_path: Path) -> None:
    kg = _build(_repo_dir(tmp_path), LIVING_GED, cutoff=0)
    export_web(kg, tmp_path / "out", PrivacySettings(None, include_living=True))
    catalog = json.loads((tmp_path / "out" / "catalog.json").read_text())
    assert catalog["meta"]["privacy"]["include_living"] is True
    assert LIVING_NAME in {p["name"] for p in catalog["people"]}


# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------


def test_every_person_is_in_exactly_one_line(sample_kg: GenealogyKG) -> None:
    graph = load_graph(sample_kg.store)
    assignment, lines = assign_lines(graph)
    members = [m for line in lines for m in line.members]
    assert len(members) == len(set(members)) == len(assignment) == 12


def test_lines_follow_the_birth_surname(sample_kg: GenealogyKG) -> None:
    assignment, lines = assign_lines(load_graph(sample_kg.store))
    by_id = {line.id: line for line in lines}
    hartwell = by_id["hartwell-I1"]
    assert set(hartwell.members) == {f"person:I{n}" for n in (1, 3, 4, 5, 7, 8, 12)}
    assert hartwell.founder == "person:I1"
    # Married-in spouses found lines of their own; a child takes the father's.
    assert assignment["person:I2"] == "ashcombe-I2"
    assert assignment["person:I10"] == assignment["person:I9"] == "pryce-I9"


def test_a_placeholder_surname_founds_no_line(tmp_path: Path) -> None:
    ged = LIVING_GED.replace("Hester /Moss/", "Hester /(-----)/")
    kg = _build(_repo_dir(tmp_path), ged, cutoff=100)
    assignment, lines = assign_lines(load_graph(kg.store))
    assert assignment["person:B"] == UNKNOWN_LINE
    assert all(line.id[0].isalpha() for line in lines)


def test_surname_less_descent_is_cut_into_houses(tmp_path: Path) -> None:
    kg = _build(_repo_dir(tmp_path), HOUSE_GED, cutoff=100)
    assignment, lines = assign_lines(load_graph(kg.store))
    by_id = {line.id: line for line in lines}
    terah = by_id["terah-T"]
    assert terah.surname == "Terah"
    assert terah.founder == "person:T"
    assert set(terah.members) == {f"person:{x}" for x in "TANHIJ"}
    # A wife with no parents has no house; a living man heads none.
    assert assignment["person:W"] == UNKNOWN_LINE
    assert all(assignment[f"person:{x}"] == UNKNOWN_LINE for x in ("Z", "Z1", "Z2", "Z3"))


def test_cross_line_marriages_are_links(sample_kg: GenealogyKG, tmp_path: Path) -> None:
    export_web(sample_kg, tmp_path / "out", PRIVACY)
    catalog = json.loads((tmp_path / "out" / "catalog.json").read_text())
    links = {link["family"]: link["lines"] for link in catalog["links"]}
    assert links["F1"] == ["ashcombe-I2", "hartwell-I1"]
    assert "pryce-I9" in links["F3"]
    assert all(UNKNOWN_LINE not in lines for lines in links.values())


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def test_person_page_carries_the_record_lines(sample_kg: GenealogyKG, tmp_path: Path) -> None:
    export_web(sample_kg, tmp_path / "out", PRIVACY)
    page = json.loads((tmp_path / "out" / "people" / "I1.json").read_text())
    assert page["record"]["lines"][0] == "0 @I1@ INDI"
    assert page["children"] == ["I3", "I4", "I5"]
    assert page["line"] == "hartwell-I1"
    assert (tmp_path / "out" / "species.json").exists()


def test_export_needs_force_and_never_removes_a_foreign_directory(
    sample_kg: GenealogyKG, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    export_web(sample_kg, out, PRIVACY)
    with pytest.raises(ExportError, match="--force"):
        export_web(sample_kg, out, PRIVACY)
    export_web(sample_kg, out, PRIVACY, force=True)

    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("mine")
    with pytest.raises(ExportError, match="something other than an export"):
        export_web(sample_kg, foreign, PRIVACY, force=True)
    assert (foreign / "keep.txt").read_text() == "mine"


def test_cli_export_web(sample_kg: GenealogyKG, tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "out"
    result = runner.invoke(
        cli,
        [
            "export-web",
            "--repo",
            str(sample_kg.repo_root),
            "--out",
            str(out),
            "--living-cutoff",
            "100",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "12 people" in result.output
    # No flag: the default cutoff applies.
    again = runner.invoke(
        cli, ["export-web", "--repo", str(sample_kg.repo_root), "--out", str(out), "--force"]
    )
    assert again.exit_code == 0, again.output
    # Redaction turned off in pyproject: refused without --include-living.
    (sample_kg.repo_root / "pyproject.toml").write_text(
        "[tool.genealogykg]\nliving_cutoff_years = 0\n"
    )
    refused = runner.invoke(
        cli, ["export-web", "--repo", str(sample_kg.repo_root), "--out", str(out), "--force"]
    )
    assert refused.exit_code != 0
    assert "living-person cutoff" in refused.output


def test_the_scan_matches_whole_names_only(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text('{"name": "Joann Lee", "other": "Mary Ann Leeds"}')
    assert scan_for_names(tmp_path, {"Ann Lee": "X1"}) == []
    (tmp_path / "b.json").write_text('{"note": "visited Ann Lee, a cousin"}')
    assert scan_for_names(tmp_path, {"Ann Lee": "X1"}) == [("b.json", "X1")]
