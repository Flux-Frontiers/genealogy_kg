"""genealogy_kg/temporal.py

The one derivation of the fleet temporal contract from GEDCOM dates.

:func:`temporal_keys` maps a ged4py ``DateValue`` onto
``kg_utils.temporal.temporal_metadata`` and, together with
:func:`person_temporal_keys`, is the only place in this package that turns a
GEDCOM date into ``occurred_start`` / ``occurred_end`` / ``recorded_at``.
Julian dates are converted to Gregorian with ``convertdate`` (a ged4py
dependency) at day precision; coarser Julian dates pass through unchanged,
since the two calendars differ by at most 13 days in the years GEDCOM files
cover. Malformed or unsupported dates (Hebrew and French Republican
calendars, BC years -- the fleet contract's ISO strings have no
negative-year form, free-text phrases) resolve to nothing rather than
raising.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from typing import Any

from convertdate import julian
from ged4py.calendar import MONTHS_GREG, CalendarType
from ged4py.date import DateValueTypes
from kg_utils.temporal import temporal_metadata

#: Kinds whose own date value is the natural start of the thing.
_START_KINDS = frozenset(
    {
        DateValueTypes.SIMPLE,
        DateValueTypes.ABOUT,
        DateValueTypes.CALCULATED,
        DateValueTypes.ESTIMATED,
        DateValueTypes.INTERPRETED,
        DateValueTypes.AFTER,
        DateValueTypes.FROM,
    }
)
#: Kinds whose own date value is the natural end of the thing.
_END_KINDS = frozenset({DateValueTypes.BEFORE, DateValueTypes.TO})
#: Kinds carrying two dates, mapped straight to start/end.
_RANGE_KINDS = frozenset({DateValueTypes.RANGE, DateValueTypes.PERIOD})

_QUALIFIERS: dict[DateValueTypes, str] = {
    DateValueTypes.ABOUT: "ABT",
    DateValueTypes.CALCULATED: "CAL",
    DateValueTypes.ESTIMATED: "EST",
    DateValueTypes.BEFORE: "BEF",
    DateValueTypes.AFTER: "AFT",
    DateValueTypes.RANGE: "BET",
    DateValueTypes.FROM: "FROM",
    DateValueTypes.TO: "TO",
    DateValueTypes.PERIOD: "FROM",
    DateValueTypes.INTERPRETED: "INT",
}


def iso_date(calendar_date: Any | None) -> str | None:
    """Convert a ged4py ``CalendarDate`` to an ISO-8601 string.

    Gregorian and Julian only, matching what ``kg_utils.temporal.parse_temporal``
    accepts (``YYYY``, ``YYYY-MM`` or ``YYYY-MM-DD``, no BC form). A Julian
    date with a day is converted to the proleptic Gregorian calendar; a
    Julian year or year-month is kept as written, the offset between the
    calendars being smaller than that precision. Hebrew and French
    Republican calendars, and BC years, return ``None``.

    :param calendar_date: A ged4py ``CalendarDate``, or ``None``.
    :return: ISO-8601 string at the precision the source supports, or ``None``.
    """
    if calendar_date is None or calendar_date.bc:
        return None
    if calendar_date.calendar not in (CalendarType.GREGORIAN, CalendarType.JULIAN):
        return None
    year = calendar_date.year
    if not calendar_date.month:
        return f"{year:04d}"
    try:
        month = MONTHS_GREG.index(calendar_date.month) + 1
    except ValueError:
        return f"{year:04d}"
    day = calendar_date.day
    if not day:
        return f"{year:04d}-{month:02d}"
    if calendar_date.calendar == CalendarType.JULIAN:
        try:
            year, month, day = julian.to_gregorian(year, month, day)
        except ValueError:  # a day the Julian calendar does not have
            return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def date_qualifier(date_value: Any | None) -> str | None:
    """Return the GEDCOM qualifier of a date (``ABT``, ``BEF``, ``BET``, ...).

    :param date_value: A ged4py ``DateValue``, or ``None``.
    :return: The qualifier keyword, or ``None`` for a plain date or no date.
    """
    if date_value is None:
        return None
    return _QUALIFIERS.get(date_value.kind)


def temporal_keys(date_value: Any | None, *, recorded_at: str | None = None) -> dict[str, str]:
    """Derive the temporal contract keys from one GEDCOM date value.

    :param date_value: A ged4py ``DateValue`` (any subclass), or ``None``.
    :param recorded_at: Optional ``HEAD.DATE`` string for the file, passed
        through unchanged.
    :return: Subset of ``{"occurred_start", "occurred_end", "recorded_at"}``;
        ``{}`` when nothing can be placed on the calendar.
    """
    start: str | None = None
    end: str | None = None
    if date_value is not None:
        kind = date_value.kind
        if kind in _START_KINDS:
            start = iso_date(date_value.date)
        elif kind in _END_KINDS:
            end = iso_date(date_value.date)
        elif kind in _RANGE_KINDS:
            start = iso_date(date_value.date1)
            end = iso_date(date_value.date2)
        # PHRASE: free text, nothing derivable.
    return temporal_metadata(occurred_start=start, occurred_end=end, recorded_at=recorded_at)


def person_temporal_keys(
    birth: Any | None,
    death: Any | None,
    *,
    recorded_at: str | None = None,
) -> dict[str, str]:
    """Compose a person's lifespan from separate birth and death dates.

    Unlike :func:`temporal_keys`, which reads one date value's own qualifier
    to decide start vs. end, this combines two independently-qualified dates
    into one span: whichever bound the birth date offers becomes
    ``occurred_start`` (an ``AFT`` birth still starts the span), and
    whichever bound the death date offers becomes ``occurred_end`` (a
    ``BEF`` death still ends it).

    :param birth: The person's birth (or baptism/christening) date value.
    :param death: The person's death (or burial) date value.
    :param recorded_at: Optional ``HEAD.DATE`` string for the file.
    :return: Subset of the temporal contract keys.
    """
    start: str | None = None
    end: str | None = None
    if birth is not None:
        b = temporal_keys(birth)
        start = b.get("occurred_start") or b.get("occurred_end")
    if death is not None:
        d = temporal_keys(death)
        end = d.get("occurred_end") or d.get("occurred_start")
    return temporal_metadata(occurred_start=start, occurred_end=end, recorded_at=recorded_at)
