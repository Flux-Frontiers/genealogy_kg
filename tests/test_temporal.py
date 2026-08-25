"""Table-driven tests for genealogy_kg.temporal, covering every qualifier
in the mapping table from docs/DESIGN.md."""

from __future__ import annotations

import pytest
from ged4py.date import DateValue

from genealogy_kg.temporal import date_qualifier, person_temporal_keys, temporal_keys

CASES = [
    ("12 MAR 1901", {"occurred_start": "1901-03-12"}, None),
    ("MAR 1901", {"occurred_start": "1901-03"}, None),
    ("1901", {"occurred_start": "1901"}, None),
    ("ABT 1850", {"occurred_start": "1850"}, "ABT"),
    ("CAL 1850", {"occurred_start": "1850"}, "CAL"),
    ("EST 1850", {"occurred_start": "1850"}, "EST"),
    ("BEF 1857", {"occurred_end": "1857"}, "BEF"),
    ("AFT 1930", {"occurred_start": "1930"}, "AFT"),
    ("BET 1899 AND 1901", {"occurred_start": "1899", "occurred_end": "1901"}, "BET"),
    ("FROM 1846 TO 1850", {"occurred_start": "1846", "occurred_end": "1850"}, "FROM"),
    ("FROM 1846", {"occurred_start": "1846"}, "FROM"),
    ("TO 1850", {"occurred_end": "1850"}, "TO"),
    ("(before the war)", {}, None),
    # Julian dates convert to Gregorian at day precision (1700: +11 days) ...
    ("@#DJULIAN@ 1 MAR 1700", {"occurred_start": "1700-03-12"}, None),
    ("@#DJULIAN@ 29 FEB 1700", {"occurred_start": "1700-03-11"}, None),  # a real Julian leap day
    ("BEF @#DJULIAN@ 25 DEC 1600", {"occurred_end": "1601-01-04"}, "BEF"),
    # ... and pass through unchanged at month and year precision.
    ("@#DJULIAN@ MAR 1700", {"occurred_start": "1700-03"}, None),
    ("@#DJULIAN@ 1700", {"occurred_start": "1700"}, None),
    # Hebrew and French Republican are still not placed; BC has no ISO form.
    ("@#DHEBREW@ 1 TSH 5785", {}, None),
    ("@#DFRENCH R@ 1 VEND 8", {}, None),
    ("100 BC", {}, None),
    # A day/month combination the Gregorian calendar does not have (a
    # mistyped source record) resolves to nothing rather than raising.
    ("30 FEB 1901", {}, None),
    ("31 APR 1901", {}, None),
]


@pytest.mark.parametrize("raw,expected,qualifier", CASES)
def test_temporal_keys_table(raw: str, expected: dict, qualifier: str | None) -> None:
    dv = DateValue.parse(raw)
    assert temporal_keys(dv) == expected
    assert date_qualifier(dv) == qualifier


def test_temporal_keys_none() -> None:
    assert temporal_keys(None) == {}
    assert date_qualifier(None) is None


def test_temporal_keys_recorded_at_passthrough() -> None:
    dv = DateValue.parse("1901")
    result = temporal_keys(dv, recorded_at="2026-08-23")
    assert result["recorded_at"] == "2026-08-23"


def test_person_temporal_keys_combines_birth_and_death() -> None:
    birth = DateValue.parse("ABT 1820")
    death = DateValue.parse("7 NOV 1891")
    result = person_temporal_keys(birth, death)
    assert result == {"occurred_start": "1820", "occurred_end": "1891-11-07"}


def test_person_temporal_keys_before_qualified_death_still_ends() -> None:
    birth = DateValue.parse("1855")
    death = DateValue.parse("BEF 1857")
    result = person_temporal_keys(birth, death)
    assert result == {"occurred_start": "1855", "occurred_end": "1857"}


def test_person_temporal_keys_missing_dates() -> None:
    assert person_temporal_keys(None, None) == {}
    assert person_temporal_keys(DateValue.parse("1900"), None) == {"occurred_start": "1900"}
