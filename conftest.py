"""Pytest configuration for GenealogyKG tests.

Fixtures:
- ``sample_ged``: path to the fictional three-generation GEDCOM 5.5.1 file
  under ``tests/fixtures/``. Every name in it is invented; it exists so the
  test suite never needs a real family's data.
- ``corpus_root``: a temporary repo root containing a copy of ``sample_ged``,
  for tests that build a ``.genealogykg/`` store.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


@pytest.fixture
def sample_ged() -> Path:
    """Return the path to the fixture GEDCOM file.

    :return: Absolute path to ``tests/fixtures/sample.ged``.
    """
    return (FIXTURES / "sample.ged").resolve()


@pytest.fixture
def corpus_root(tmp_path: Path, sample_ged: Path) -> Path:
    """Copy the fixture GEDCOM into a temporary repo root.

    :param tmp_path: Temporary directory from pytest.
    :param sample_ged: The fixture GEDCOM path.
    :return: Path to the temporary root containing ``family.ged``.
    """
    shutil.copy(sample_ged, tmp_path / "family.ged")
    return tmp_path
