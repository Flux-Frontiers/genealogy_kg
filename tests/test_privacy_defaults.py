"""Privacy is on by default: a 100-year living cutoff, undated people
redacted, and submitter contact records never shown by ``pack()``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from genealogy_kg.config import (
    DEFAULT_LIVING_CUTOFF_YEARS,
    load_living_cutoff,
    load_unknown_birth_policy,
)
from genealogy_kg.module import GenealogyKG

SUBMITTER_EMAIL = "submitter@example.invalid"

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "scrub_submitters", REPO_ROOT / "scripts" / "scrub_submitters.py"
)
assert _spec and _spec.loader
scrub_submitters = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scrub_submitters)

UNDATED_GED = """\
0 HEAD
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Wren /Undated/
1 SEX F
0 TRLR
"""


def _with_submitter_contact(corpus_root: Path) -> None:
    """Give the fixture's submitter record a postal address, phone and email."""
    ged = corpus_root / "family.ged"
    text = ged.read_text()
    contact = (
        "1 NAME GenealogyKG fixture\n"
        "1 ADDR 1 Example Street\n"
        "2 CONT Nowhere\n"
        "1 PHON 555-0100\n"
        f"1 EMAIL {SUBMITTER_EMAIL}\n"
    )
    ged.write_text(text.replace("1 NAME GenealogyKG fixture\n", contact, 1))


def test_defaults_redact_living_and_undated_people(tmp_path: Path) -> None:
    assert DEFAULT_LIVING_CUTOFF_YEARS == 100
    assert load_living_cutoff(tmp_path) == 100
    assert load_unknown_birth_policy(tmp_path) == "redact"


def test_a_zero_cutoff_turns_redaction_off(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.genealogykg]\nliving_cutoff_years = 0\n")
    assert load_living_cutoff(tmp_path) is None
    assert GenealogyKG(repo_root=tmp_path).make_extractor().living_cutoff_years is None
    explicit = GenealogyKG(repo_root=tmp_path / "x", living_cutoff_years=0)
    assert explicit.make_extractor().living_cutoff_years is None


def test_a_default_build_redacts_an_undated_person(tmp_path: Path) -> None:
    (tmp_path / "family.ged").write_text(UNDATED_GED)
    kg = GenealogyKG(repo_root=tmp_path, sources=[Path("family.ged")])
    kg.build(wipe=True)

    assert (kg.person("I1") or {}).get("name") == "Living"
    assert "Wren" not in kg.pack("Wren Undated", k=5, hop=0).to_markdown().replace(
        "Wren Undated", ""
    )


@pytest.mark.parametrize("cutoff", [0, 200])
def test_pack_never_shows_the_submitter_record(corpus_root: Path, cutoff: int) -> None:
    _with_submitter_contact(corpus_root)
    kg = GenealogyKG(
        repo_root=corpus_root, sources=[Path("family.ged")], living_cutoff_years=cutoff
    )
    kg.build(wipe=True)

    # I1 is the first INDI, directly below the SUBM record, so its padded
    # snippet window reaches up into the submitter's contact lines.
    pack = kg.pack("John Hartwell ironmonger", k=5, hop=0)
    assert any(n.get("id") == "person:I1" and n.get("snippet") for n in pack.nodes)
    snippets = "\n".join(str(n.get("snippet", "")) for n in pack.nodes)
    assert SUBMITTER_EMAIL not in snippets
    assert "555-0100" not in snippets
    assert "Example Street" not in snippets


def test_scrub_withholds_the_submitter_and_keeps_everything_else() -> None:
    raw = (
        b"0 HEAD\r\n1 SUBM @U1@\r\n0 @U1@ SUBM\r\n1 NAME Ann /Doe/\r\n"
        b"1 ADDR 1 Main St\r\n2 CONT Town\r\n1 EMAIL ann@example.invalid\r\n"
        b"0 @I1@ INDI\r\n1 NAME Bo /Doe/\r\n0 TRLR\r\n"
    )
    scrubbed = scrub_submitters.scrub(raw)
    assert scrubbed == (
        b"0 HEAD\r\n1 SUBM @U1@\r\n0 @U1@ SUBM\r\n1 NAME Withheld\r\n"
        b"0 @I1@ INDI\r\n1 NAME Bo /Doe/\r\n0 TRLR\r\n"
    )
    assert scrub_submitters.scrub(scrubbed) == scrubbed


def test_every_committed_corpus_file_is_scrubbed() -> None:
    entries = REPO_ROOT / "corpora" / "entries"
    unscrubbed = [
        str(path.relative_to(entries))
        for path in sorted(entries.rglob("*.ged"))
        if scrub_submitters.scrub(data := path.read_bytes()) != data
    ]
    assert not unscrubbed, f"run scripts/scrub_submitters.py on: {unscrubbed}"
