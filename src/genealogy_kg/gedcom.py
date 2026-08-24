"""genealogy_kg/gedcom.py

Thin reader over ged4py. Everything the extractor needs from a GEDCOM file
comes through here: level-0 records, the line span of each record (derived
once from ged4py's byte offsets, so ``pack()`` can return the original
text), and formatting helpers for names and places.

Phase 1 work. See docs/DESIGN.md.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: GEDCOM sub-record tags that become ``event`` nodes.
EVENT_TAGS: tuple[str, ...] = (
    "BIRT",
    "DEAT",
    "BURI",
    "BAPM",
    "CHR",
    "MARR",
    "DIV",
    "RESI",
    "OCCU",
    "IMMI",
    "EMIG",
    "CENS",
)


@dataclass(frozen=True)
class RecordSpan:
    """Line span of one level-0 record in the source file.

    :param xref: The record's cross-reference id without ``@`` (``I1``, ``F1``).
    :param tag: The record tag (``INDI``, ``FAM``, ``SOUR``).
    :param lineno: 1-based first line.
    :param end_lineno: 1-based last line, inclusive.
    """

    xref: str
    tag: str
    lineno: int
    end_lineno: int


class GedcomFile:
    """One GEDCOM file, opened for extraction.

    :param path: Path to the ``.ged`` file.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def __enter__(self) -> GedcomFile:
        raise NotImplementedError("Phase 1")

    def __exit__(self, *_: object) -> None:
        raise NotImplementedError("Phase 1")

    def records(self, tag: str) -> Iterator[Any]:
        """Yield level-0 records with the given tag, in file order.

        :param tag: ``INDI``, ``FAM`` or ``SOUR``.
        :return: Iterator of ged4py ``Record`` objects.
        """
        raise NotImplementedError("Phase 1")

    def spans(self) -> dict[str, RecordSpan]:
        """Return the line span of every level-0 record, keyed by xref.

        Computed once per file by mapping ged4py byte offsets onto newline
        positions.

        :return: ``{xref: RecordSpan}``.
        """
        raise NotImplementedError("Phase 1")

    def header_date(self) -> str | None:
        """Return the ``HEAD.DATE`` value, used as ``recorded_at``.

        :return: The raw date string, or ``None`` when the header has none.
        """
        raise NotImplementedError("Phase 1")


def place_slug(place: str) -> str:
    """Return the deterministic node-id slug for a ``PLAC`` string.

    :param place: The place as written, for example ``"Leeds, Yorkshire, England"``.
    :return: Lower-case, hyphen-joined slug: ``"leeds-yorkshire-england"``.
    """
    raise NotImplementedError("Phase 1")
