"""genealogy_kg/gedcom.py

Thin reader over ged4py. Everything the extractor needs from a GEDCOM file
comes through here: level-0 records, the line span of each level-0 record
(derived from byte offsets, diffed against the next level-0 record so
embedded CONT/CONC continuation lines are counted correctly), a single-line
lookup for nested sub-records such as events, and a place-string slugifier.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from ged4py.parser import GedcomReader

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

_LINE_END_RE = re.compile(rb"\r\n|\r|\n")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def place_slug(place: str) -> str:
    """Return the deterministic node-id slug for a ``PLAC`` string.

    :param place: The place as written, for example ``"Leeds, Yorkshire, England"``.
    :return: Lower-case, hyphen-joined slug: ``"leeds-yorkshire-england"``.
    """
    slug = _SLUG_RE.sub("-", place.strip().lower()).strip("-")
    return slug or "unknown-place"


def _line_starts(data: bytes) -> list[int]:
    """Return the 0-based byte offset of the first character of every line."""
    starts = [0]
    for m in _LINE_END_RE.finditer(data):
        starts.append(m.end())
    return starts


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
        self._fh: BinaryIO | None = None
        self._reader: GedcomReader | None = None
        self._line_starts: list[int] | None = None

    def __enter__(self) -> GedcomFile:
        # Open the file ourselves rather than handing GedcomReader a path
        # string: GedcomReader.__exit__ closes whatever file it owns, but its
        # own type stub declares exc_type as non-optional `type` even though
        # a normal (non-exceptional) exit always passes None. Owning the file
        # handle here sidesteps that upstream mismatch instead of fighting it.
        self._fh = open(self.path, "rb")
        self._reader = GedcomReader(self._fh)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fh is not None:
            self._fh.close()
        self._fh = None
        self._reader = None

    @property
    def reader(self) -> GedcomReader:
        """The underlying ged4py reader.

        :raises RuntimeError: If used outside a ``with`` block.
        """
        if self._reader is None:
            raise RuntimeError("GedcomFile must be used as a context manager")
        return self._reader

    def records(self, tag: str) -> Iterator[Any]:
        """Yield level-0 records with the given tag, in file order.

        :param tag: ``INDI``, ``FAM`` or ``SOUR``.
        :return: Iterator of ged4py ``Record`` objects.
        """
        return self.reader.records0(tag)

    def _ensure_line_starts(self) -> None:
        if self._line_starts is None:
            self._line_starts = _line_starts(self.path.read_bytes())

    def line_of(self, offset: int) -> int:
        """Return the 1-based line number containing a byte offset.

        Works for any record's ``.offset``, level-0 or nested; use it for
        single-line lookups such as an event sub-record's own line.

        :param offset: Byte offset into the file.
        :return: 1-based line number.
        """
        self._ensure_line_starts()
        assert self._line_starts is not None
        return bisect.bisect_right(self._line_starts, offset)

    def spans(self) -> dict[str, RecordSpan]:
        """Return the line span of every level-0 record, keyed by xref.

        A level-0 record's end is the byte before the next level-0 record
        starts, not the deepest line among its own sub-records -- CONT/CONC
        continuation lines are merged into their parent's value by ged4py and
        leave no sub-record of their own, so counting nested offsets alone
        would under-report multi-line NOTE/TEXT fields.

        :return: ``{xref: RecordSpan}``, xref without ``@``.
        """
        self._ensure_line_starts()
        index = sorted(self.reader.index0, key=lambda t: t[0])
        offsets = [off for off, _ in index]
        file_size = self.path.stat().st_size
        spans: dict[str, RecordSpan] = {}
        for xref, (off, tag) in self.reader.xref0.items():
            i = bisect.bisect_left(offsets, off)
            end_off = offsets[i + 1] - 1 if i + 1 < len(offsets) else max(off, file_size - 1)
            start_line = self.line_of(off)
            end_line = max(start_line, self.line_of(end_off))
            clean_xref = xref.strip("@")
            spans[clean_xref] = RecordSpan(clean_xref, tag, start_line, end_line)
        return spans

    def header_date(self) -> Any | None:
        """Return the ``HEAD.DATE`` value, used as ``recorded_at``.

        :return: The parsed ged4py ``DateValue``, or ``None`` when absent.
        """
        header = self.reader.header
        return header.sub_tag_value("DATE") if header else None
