"""Integration tests against the public GEDCOM corpora from docs/CORPORA.md.

Skipped whole when corpora/ has not been fetched (./scripts/fetch_corpora.sh).
These exercise what the fixture cannot: ANSEL encoding, a file with no GEDC
header at all, and a file over a megabyte -- while staying well short of the
203k-person scale-ladder file, which is a Phase 3 benchmark, not a test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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
