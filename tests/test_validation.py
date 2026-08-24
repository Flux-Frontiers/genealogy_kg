"""Unit tests for genealogy_kg.validation -- pure boundary-checking helpers."""

from __future__ import annotations

import pytest

from genealogy_kg.validation import bounded_int, normalize_xref, require_query

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


# ---------------------------------------------------------------------------
# bounded_int
# ---------------------------------------------------------------------------


def test_bounded_int_accepts_edges_of_the_range() -> None:
    assert bounded_int("k", 1, 1, 100) == 1
    assert bounded_int("k", 100, 1, 100) == 100


def test_bounded_int_rejects_below_minimum() -> None:
    with pytest.raises(ValueError, match="k must be between 1 and 100, got 0"):
        bounded_int("k", 0, 1, 100)


def test_bounded_int_rejects_above_maximum() -> None:
    with pytest.raises(ValueError, match="k must be between 1 and 100, got 101"):
        bounded_int("k", 101, 1, 100)


# ---------------------------------------------------------------------------
# require_query
# ---------------------------------------------------------------------------


def test_require_query_strips_whitespace() -> None:
    assert require_query("  chemist  ") == "chemist"


def test_require_query_rejects_empty() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        require_query("")


def test_require_query_rejects_whitespace_only() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        require_query("   ")


def test_require_query_rejects_too_long() -> None:
    with pytest.raises(ValueError, match="at most 500 characters"):
        require_query("x" * 501)


def test_require_query_accepts_exactly_the_limit() -> None:
    assert require_query("x" * 500) == "x" * 500
