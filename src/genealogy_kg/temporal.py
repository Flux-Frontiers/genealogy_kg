"""genealogy_kg/temporal.py

The one derivation of the fleet temporal contract from GEDCOM dates.

:func:`temporal_keys` maps a ged4py ``DateValue`` onto
``kg_utils.temporal.temporal_metadata`` and is the only writer of
``occurred_start``, ``occurred_end`` and ``recorded_at`` in this package.
Malformed or unsupported dates return ``{}``; they never raise. The mapping
table is in docs/DESIGN.md under "Temporal contract".

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from typing import Any


def temporal_keys(date_value: Any, *, recorded_at: str | None = None) -> dict[str, str]:
    """Derive the temporal contract keys from a GEDCOM date.

    :param date_value: A ged4py ``DateValue`` (any subclass), or ``None``.
    :param recorded_at: Optional ``HEAD.DATE`` string for the file.
    :return: Subset of ``{"occurred_start", "occurred_end", "recorded_at"}``
        as ISO-8601 strings at the precision the source supports; ``{}`` when
        nothing can be placed on the calendar.
    """
    raise NotImplementedError("Phase 1")


def date_qualifier(date_value: Any) -> str | None:
    """Return the GEDCOM qualifier of a date (``ABT``, ``BEF``, ``BET``, ...).

    :param date_value: A ged4py ``DateValue``.
    :return: The qualifier keyword, or ``None`` for a plain date.
    """
    raise NotImplementedError("Phase 1")
