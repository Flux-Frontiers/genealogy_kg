"""Integration tests against the public GEDCOM corpora from docs/CORPORA.md.

Skipped whole when corpora/ has not been fetched (./scripts/fetch_corpora.sh).
These exercise what the fixture cannot: ANSEL encoding, a file with no GEDC
header at all, and a file over a megabyte -- while staying well short of the
203k-person scale-ladder file, which is a Phase 3 benchmark, not a test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kg_utils.specs import NodeSpec

from genealogy_kg.module import GenealogyKG

CORPORA = Path(__file__).resolve().parents[1] / "corpora"

pytestmark = pytest.mark.integration

CASES = [
    pytest.param(CORPORA / "torture" / "TGC551LF.ged", 15, 7, id="torture-ansel-every-tag"),
    pytest.param(
        CORPORA / "gedcom-samples" / "royal" / "royal92.ged",
        3010,
        1422,
        id="royal92-no-gedc-header",
    ),
    pytest.param(
        CORPORA / "gedcom-samples" / "pres" / "pres2020.ged", 2322, 1115, id="pres2020-bom"
    ),
]


@pytest.mark.skipif(
    not CORPORA.exists(), reason="corpora/ not fetched; run scripts/fetch_corpora.sh"
)
@pytest.mark.parametrize("ged_path,n_person,n_family", CASES)
def test_public_corpus_builds_with_expected_counts(
    tmp_path: Path, ged_path: Path, n_person: int, n_family: int
) -> None:
    if not ged_path.exists():
        pytest.skip(f"{ged_path.name} not present under corpora/")
    dest = tmp_path / ged_path.name
    dest.write_bytes(ged_path.read_bytes())

    kg = GenealogyKG(repo_root=tmp_path, sources=[Path(ged_path.name)])
    stats = kg.build(wipe=True)

    assert stats.node_counts["person"] == n_person
    assert stats.node_counts["family"] == n_family


def test_kennedy_conservative_policy_redacts_unknown_births() -> None:
    kennedy_root = CORPORA / "gedcom-samples" / "sample-kennedy"
    ged_path = kennedy_root / "kennedy.ged"
    if not ged_path.exists():
        pytest.skip("Kennedy sample not present; run scripts/fetch_corpora.sh")

    default_nodes = {
        node.node_id: node
        for node in GenealogyKG(
            repo_root=kennedy_root,
            sources=[Path("kennedy.ged")],
            living_cutoff_years=100,
        )
        .make_extractor()
        .extract()
        if isinstance(node, NodeSpec)
    }
    conservative_nodes = {
        node.node_id: node
        for node in GenealogyKG(
            repo_root=kennedy_root,
            sources=[Path("kennedy.ged")],
            living_cutoff_years=100,
            unknown_birth_policy="redact",
        )
        .make_extractor()
        .extract()
        if isinstance(node, NodeSpec)
    }

    # Doris Kearns Goodwin (I70) has neither a usable birth date nor a
    # DEAT/BURI record in this sample. Preserve the legacy default, but redact
    # her when the conservative policy is explicitly selected.
    assert default_nodes["person:I70"].name == "Doris Kearns Goodwin"
    assert conservative_nodes["person:I70"].name == "Living"

    # Patrick Kennedy (I120) also has no usable birth date, but a DEAT record
    # is affirmative evidence that he is not living.
    assert conservative_nodes["person:I120"].name == "Patrick Kennedy"

    # Qualified and partial dates remain usable: ABOUT 1955 and 1933 are both
    # within the cutoff and are redacted under either policy.
    assert default_nodes["person:I182"].name == "Living"
    assert default_nodes["person:I18"].name == "Living"
