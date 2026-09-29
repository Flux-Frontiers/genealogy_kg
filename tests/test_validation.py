"""Unit tests for genealogy_kg.validation -- pure boundary-checking helpers."""

from __future__ import annotations

import pytest

from genealogy_kg.validation import normalize_xref

# ---------------------------------------------------------------------------
# normalize_xref
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    ["I7", "@I7@", "person:I7", "  I7  ", "  @I7@  "],
)
def test_normalize_xref_accepts_every_known_form(raw: str) -> None:
    assert normalize_xref(raw) == "I7"


def test_normalize_xref_rejects_empty() -> None:
    with pytest.raises(ValueError, match="invalid xref"):
        normalize_xref("")


def test_normalize_xref_rejects_bare_at() -> None:
    with pytest.raises(ValueError, match="invalid xref"):
        normalize_xref("@")


def test_normalize_xref_rejects_unbalanced_at() -> None:
    with pytest.raises(ValueError, match="invalid xref"):
        normalize_xref("@I7")


def test_normalize_xref_rejects_embedded_whitespace() -> None:
    with pytest.raises(ValueError, match="invalid xref"):
        normalize_xref("I 7")


def test_normalize_xref_strips_prefix_then_pointer_wrapper() -> None:
    # "person:" is stripped first, then the @...@ pointer wrapper -- an agent
    # that prefixes a raw GEDCOM pointer it copied verbatim still resolves.
    assert normalize_xref("person:@I7@") == "I7"
