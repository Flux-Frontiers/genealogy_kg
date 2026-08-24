"""genealogy_kg/extractor.py

GedcomExtractor -- KGExtractor that turns a GEDCOM file into the graph model
described in docs/DESIGN.md: ``person``, ``family``, ``event``, ``place`` and
``source`` nodes; ``CHILD_IN``, ``SPOUSE_IN``, ``PARENT_OF``, ``MARRIED_TO``,
``HAS_EVENT``, ``OCCURRED_AT``, ``CITES`` and ``WITHIN`` edges.

Lineage edges (``CHILD_IN``, ``PARENT_OF``, ``SPOUSE_IN``, ``MARRIED_TO``)
are derived exactly once, from each ``FAM`` record's ``HUSB``/``WIFE``/
``CHIL`` list -- never re-derived from an individual's own ``FAMC``/``FAMS``
pointers, which describe the same relationships from the other side and
would just emit the same edges twice.

Extraction is deterministic: node ids derive from GEDCOM xrefs and tags, and
records are emitted in file order.

Living-person redaction (``living_cutoff_years``): a person with no death or
burial record whose birth (or baptism/christening) falls within that many
years of today is emitted as a bare ``person`` node named ``Living`` -- no
name, dates, events, notes or citations -- and their name is withheld from
every other node's prose too. Off unless configured. Note that ``pack()``
reads the GEDCOM file in place, so the file itself must not travel with a
redacted store.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from datetime import date
from pathlib import Path
from typing import Any

from ged4py.date import DateValueTypes
from kg_utils.extractor import KGExtractor
from kg_utils.specs import EdgeSpec, NodeSpec

from genealogy_kg.gedcom import EVENT_TAGS, GedcomFile, RecordSpan, place_slug
from genealogy_kg.temporal import iso_date, person_temporal_keys, temporal_keys

NODE_KINDS: tuple[str, ...] = ("person", "family", "event", "place", "source")
EDGE_KINDS: tuple[str, ...] = (
    "CHILD_IN",
    "SPOUSE_IN",
    "PARENT_OF",
    "MARRIED_TO",
    "HAS_EVENT",
    "OCCURRED_AT",
    "CITES",
    "WITHIN",
)

#: Name and qualname given to a redacted living person.
LIVING_NAME = "Living"

_EVENT_LABELS: dict[str, str] = {
    "BIRT": "Birth",
    "DEAT": "Death",
    "BURI": "Burial",
    "BAPM": "Baptism",
    "CHR": "Christening",
    "MARR": "Marriage",
    "DIV": "Divorce",
    "RESI": "Residence",
    "OCCU": "Occupation",
    "IMMI": "Immigration",
    "EMIG": "Emigration",
    "CENS": "Census",
}
_SEX_WORDS = {"M": "male", "F": "female"}


def _xref(rec: Any) -> str:
    """Return a record's xref id without the ``@`` delimiters."""
    return (rec.xref_id or "").strip("@")


def _sex_word(sex: Any) -> str:
    if not sex:
        return ""
    s = str(sex).strip().upper()
    return _SEX_WORDS.get(s, str(sex).strip().lower())


def _first_event(rec: Any, tags: tuple[str, ...]) -> Any | None:
    """Return the first sub-record among ``tags`` that is present."""
    for tag in tags:
        ev = rec.sub_tag(tag)
        if ev is not None:
            return ev
    return None


def place_hierarchy(place: str) -> list[str]:
    """Split a comma-separated ``PLAC`` string into its enclosing places.

    :param place: ``"Cincinnati, Hamilton, Ohio, USA"``.
    :return: ``["Cincinnati, Hamilton, Ohio, USA", "Hamilton, Ohio, USA",
        "Ohio, USA", "USA"]``; a string without commas gives a one-item list.
    """
    parts = [part.strip() for part in place.split(",")]
    parts = [part for part in parts if part]
    return [", ".join(parts[i:]) for i in range(len(parts))] or [place.strip()]


class GedcomExtractor(KGExtractor):
    """Extract nodes and edges from one or more GEDCOM files.

    :param repo_path: Repository root; source paths are stored relative to it.
    :param config: Optional configuration dict (unused; sources are explicit).
    :param sources: GEDCOM files to index, as paths relative to ``repo_path``.
    :param living_cutoff_years: Redact people without a death record born
        within this many years of today. ``None`` (the default) redacts nobody.
    """

    def __init__(
        self,
        repo_path: Path,
        config: dict[str, Any] | None = None,
        sources: list[Path] | None = None,
        *,
        living_cutoff_years: int | None = None,
    ) -> None:
        super().__init__(repo_path, config)
        self.sources: list[Path] = list(sources) if sources else []
        self.living_cutoff_years = living_cutoff_years
        self._living_after_year: int | None = (
            date.today().year - living_cutoff_years if living_cutoff_years is not None else None
        )

    # ------------------------------------------------------------------
    # Living-person redaction
    # ------------------------------------------------------------------

    def is_living(self, ind: Any) -> bool:
        """Return whether a person is redacted under ``living_cutoff_years``.

        :param ind: A ged4py ``INDI`` record.
        :return: ``True`` when redaction is on, the person has no ``DEAT`` or
            ``BURI`` record, and their birth year is after the cutoff.
        """
        if self._living_after_year is None:
            return False
        if _first_event(ind, ("DEAT", "BURI")) is not None:
            return False
        birth = _first_event(ind, ("BIRT", "BAPM", "CHR"))
        keys = temporal_keys(birth.sub_tag_value("DATE")) if birth is not None else {}
        born = keys.get("occurred_start") or keys.get("occurred_end")
        return born is not None and int(born[:4]) > self._living_after_year

    def _name(self, ind: Any) -> str:
        """Return a person's formatted name, or ``LIVING_NAME`` when redacted."""
        return LIVING_NAME if self.is_living(ind) else ind.name.format()

    def living_spans(self) -> dict[str, dict[str, tuple[int, int]]]:
        """Return the real line span of every living-redacted person, by source file.

        Nowhere else keeps this: :meth:`_living_person` deliberately omits
        the real span from the graph so a query against a redacted person
        cannot ground a snippet back to their record. But ``pack()``'s
        context padding is computed per *node*, and a legitimate neighbor's
        padded window can still run past its own record into the next one in
        the file -- if that neighbor is a redacted living person, their real
        record leaks through a snippet that "belongs" to someone else
        entirely. ``GenealogyKG.pack()`` uses this to clip that overlap back
        out, regardless of which node's snippet it turned up in.

        :return: ``{source_path: {xref: (lineno, end_lineno)}}``, only for
            files and people actually redacted; empty when redaction is off.
        """
        if self._living_after_year is None:
            return {}
        result: dict[str, dict[str, tuple[int, int]]] = {}
        for source in self.sources:
            rel_path = str(Path(source))
            with GedcomFile(self.repo_path / source) as gedcom:
                spans = gedcom.spans()
                file_spans = {
                    xref: (spans[xref].lineno, spans[xref].end_lineno)
                    for ind in gedcom.records("INDI")
                    if self.is_living(ind) and (xref := _xref(ind)) in spans
                }
            if file_spans:
                result[rel_path] = file_spans
        return result

    def node_kinds(self) -> list[str]:
        """Return the node kinds this extractor emits.

        :return: ``["person", "family", "event", "place", "source"]``.
        """
        return list(NODE_KINDS)

    def edge_kinds(self) -> list[str]:
        """Return the edge relations this extractor emits.

        :return: The relations listed in :data:`EDGE_KINDS`.
        """
        return list(EDGE_KINDS)

    def extract(self) -> Iterator[NodeSpec | EdgeSpec]:
        """Yield the graph for every configured source file.

        :return: Iterator of :class:`NodeSpec` and :class:`EdgeSpec` objects.
        """
        place_ids: dict[str, str] = {}
        for source in self.sources:
            yield from self._extract_file(Path(source), place_ids)

    # ------------------------------------------------------------------
    # Per file
    # ------------------------------------------------------------------

    def _extract_file(
        self, rel_path: Path, place_ids: dict[str, str]
    ) -> Iterator[NodeSpec | EdgeSpec]:
        abs_path = self.repo_path / rel_path
        rel_str = str(rel_path)
        with GedcomFile(abs_path) as gedcom:
            spans = gedcom.spans()
            recorded_at = self._recorded_at(gedcom)

            for src in gedcom.records("SOUR"):
                yield from self._source(src, rel_str, spans)
            for fam in gedcom.records("FAM"):
                yield from self._family(fam, rel_str, spans, recorded_at, place_ids, gedcom)
            for ind in gedcom.records("INDI"):
                yield from self._person(ind, rel_str, spans, recorded_at, place_ids, gedcom)

    @staticmethod
    def _recorded_at(gedcom: GedcomFile) -> str | None:
        header_dv = gedcom.header_date()
        if header_dv is not None and header_dv.kind == DateValueTypes.SIMPLE:
            return iso_date(header_dv.date)
        return None

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def _source(self, src: Any, rel_path: str, spans: dict[str, RecordSpan]) -> Iterator[NodeSpec]:
        xref = _xref(src)
        span = spans.get(xref)
        title = src.sub_tag_value("TITL") or xref
        author = src.sub_tag_value("AUTH")
        publ = src.sub_tag_value("PUBL")
        lines = [f"Source: {title}"]
        if author:
            lines.append(f"Author: {author}")
        if publ:
            lines.append(f"Publication: {publ}")
        yield NodeSpec(
            node_id=f"source:{xref}",
            kind="source",
            name=str(title),
            qualname=str(title),
            source_path=rel_path,
            lineno=span.lineno if span else None,
            end_lineno=span.end_lineno if span else None,
            docstring="\n".join(lines),
            metadata={"gedcom_xref": xref},
        )

    def _cites(self, subject_id: str, rec: Any) -> Iterator[EdgeSpec]:
        for s in rec.sub_tags("SOUR"):
            if getattr(s, "tag", None) == "SOUR" and getattr(s, "xref_id", None):
                yield EdgeSpec(subject_id, f"source:{_xref(s)}", "CITES")

    # ------------------------------------------------------------------
    # Families
    # ------------------------------------------------------------------

    def _family(
        self,
        fam: Any,
        rel_path: str,
        spans: dict[str, RecordSpan],
        recorded_at: str | None,
        place_ids: dict[str, str],
        gedcom: GedcomFile,
    ) -> Iterator[NodeSpec | EdgeSpec]:
        xref = _xref(fam)
        span = spans.get(xref)
        husb = fam.sub_tag("HUSB")
        wife = fam.sub_tag("WIFE")
        children = list(fam.sub_tags("CHIL"))
        marr = fam.sub_tag("MARR")

        husb_name = self._name(husb) if husb else None
        wife_name = self._name(wife) if wife else None
        name = " & ".join(n for n in (husb_name, wife_name) if n) or f"Family {xref}"

        # A living spouse's marriage date is a date about a living person:
        # the family keeps its structure but not its MARR details.
        if marr is not None and any(self.is_living(s) for s in (husb, wife) if s):
            marr = None
        marr_date = marr.sub_tag_value("DATE") if marr else None
        marr_place = marr.sub_tag_value("PLAC") if marr else None

        lines = [f"Family: {name}."]
        if marr_date:
            where = f" in {marr_place}" if marr_place else ""
            lines.append(f"Married {marr_date}{where}.")
        if children:
            lines.append("Children: " + ", ".join(self._name(c) for c in children) + ".")

        metadata: dict[str, Any] = {"gedcom_xref": xref}
        metadata.update(temporal_keys(marr_date, recorded_at=recorded_at))

        yield NodeSpec(
            node_id=f"family:{xref}",
            kind="family",
            name=name,
            qualname=name,
            source_path=rel_path,
            lineno=span.lineno if span else None,
            end_lineno=span.end_lineno if span else None,
            docstring=" ".join(lines),
            metadata=metadata,
        )

        family_id = f"family:{xref}"
        if husb:
            yield EdgeSpec(f"person:{_xref(husb)}", family_id, "SPOUSE_IN")
        if wife:
            yield EdgeSpec(f"person:{_xref(wife)}", family_id, "SPOUSE_IN")
        if husb and wife:
            yield EdgeSpec(f"person:{_xref(husb)}", f"person:{_xref(wife)}", "MARRIED_TO")
        for child in children:
            child_id = f"person:{_xref(child)}"
            yield EdgeSpec(child_id, family_id, "CHILD_IN")
            if husb:
                yield EdgeSpec(f"person:{_xref(husb)}", child_id, "PARENT_OF")
            if wife:
                yield EdgeSpec(f"person:{_xref(wife)}", child_id, "PARENT_OF")

        yield from self._cites(family_id, fam)
        if marr:
            # The MARR event's own SOUR citations are attributed to the event
            # node inside _event(), not to the family -- one attribution, not two.
            yield from self._event(
                family_id, xref, "MARR", marr, 1, rel_path, gedcom, recorded_at, place_ids
            )

    # ------------------------------------------------------------------
    # People
    # ------------------------------------------------------------------

    def _person(
        self,
        ind: Any,
        rel_path: str,
        spans: dict[str, RecordSpan],
        recorded_at: str | None,
        place_ids: dict[str, str],
        gedcom: GedcomFile,
    ) -> Iterator[NodeSpec | EdgeSpec]:
        xref = _xref(ind)
        span = spans.get(xref)
        sex = ind.sub_tag_value("SEX")
        if self.is_living(ind):
            yield from self._living_person(xref, rel_path, sex)
            return
        name = ind.name.format()
        surname = ind.name.surname or ""
        given = ind.name.given or ""
        qualname = f"{surname}, {given}".strip(", ") or name

        birth = _first_event(ind, ("BIRT", "BAPM", "CHR"))
        death = _first_event(ind, ("DEAT", "BURI"))
        occu = ind.sub_tag_value("OCCU")
        father = ind.father
        mother = ind.mother

        lines = [name + (f" ({_sex_word(sex)})" if sex else "") + "."]
        if birth is not None:
            lines.append(self._event_sentence("Born", birth))
        if death is not None:
            lines.append(self._event_sentence("Died", death))
        if occu:
            lines.append(f"Occupation: {occu}.")
        parents = [self._name(p) for p in (father, mother) if p]
        if parents:
            lines.append("Parents: " + " and ".join(parents) + ".")
        spouses = self._spouse_phrases(ind, xref)
        if spouses:
            lines.append("Spouse(s): " + "; ".join(spouses) + ".")
        note = ind.sub_tag_value("NOTE")
        if note:
            lines.append(f"Notes: {note}")

        metadata: dict[str, Any] = {"gedcom_xref": xref}
        if sex:
            metadata["sex"] = str(sex)
        if surname:
            metadata["surname"] = surname
        metadata.update(
            person_temporal_keys(
                birth.sub_tag_value("DATE") if birth else None,
                death.sub_tag_value("DATE") if death else None,
                recorded_at=recorded_at,
            )
        )

        yield NodeSpec(
            node_id=f"person:{xref}",
            kind="person",
            name=name,
            qualname=qualname,
            source_path=rel_path,
            lineno=span.lineno if span else None,
            end_lineno=span.end_lineno if span else None,
            docstring="\n".join(lines),
            metadata=metadata,
        )

        yield from self._cites(f"person:{xref}", ind)

        counts: dict[str, int] = {}
        for tag in EVENT_TAGS:
            for ev in ind.sub_tags(tag):
                counts[tag] = counts.get(tag, 0) + 1
                yield from self._event(
                    f"person:{xref}",
                    xref,
                    tag,
                    ev,
                    counts[tag],
                    rel_path,
                    gedcom,
                    recorded_at,
                    place_ids,
                )

    def _living_person(self, xref: str, rel_path: str, sex: Any) -> Iterator[NodeSpec]:
        """Emit the redacted stand-in for a living person: no name, dates or events.

        ``lineno``/``end_lineno`` are deliberately omitted (never taken from
        ``span``), not just the name and dates: ``KGModule.pack()`` grounds
        snippets by re-reading the source file at a node's line span, so a
        real span here would hand back the living person's actual GEDCOM
        record -- name, dates, notes and all -- defeating the redaction
        above it entirely. With no span, ``pack()`` skips the snippet.
        """
        metadata: dict[str, Any] = {"gedcom_xref": xref, "living": True}
        if sex:
            metadata["sex"] = str(sex)
        yield NodeSpec(
            node_id=f"person:{xref}",
            kind="person",
            name=LIVING_NAME,
            qualname=LIVING_NAME,
            source_path=rel_path,
            lineno=None,
            end_lineno=None,
            docstring=(
                f"Living person; details withheld (living_cutoff_years={self.living_cutoff_years})."
            ),
            metadata=metadata,
        )

    @staticmethod
    def _event_sentence(verb: str, ev: Any) -> str:
        bits = [verb]
        date = ev.sub_tag_value("DATE")
        place = ev.sub_tag_value("PLAC")
        if date:
            bits.append(str(date))
        if place:
            bits.append(f"in {place}")
        return " ".join(bits) + "."

    def _spouse_phrases(self, ind: Any, xref: str) -> list[str]:
        phrases: list[str] = []
        for fam in ind.sub_tags("FAMS"):
            husb = fam.sub_tag("HUSB")
            wife = fam.sub_tag("WIFE")
            spouse = wife if (husb and _xref(husb) == xref) else husb
            if spouse is None:
                continue
            living = self.is_living(spouse)
            marr = None if living else fam.sub_tag("MARR")
            md = marr.sub_tag_value("DATE") if marr else None
            phrase = LIVING_NAME if living else spouse.name.format()
            if md:
                phrase += f", married {md}"
            phrases.append(phrase)
        return phrases

    # ------------------------------------------------------------------
    # Events and places (shared by families and people)
    # ------------------------------------------------------------------

    def _event(
        self,
        owner_id: str,
        owner_xref: str,
        tag: str,
        ev: Any,
        ordinal: int,
        rel_path: str,
        gedcom: GedcomFile,
        recorded_at: str | None,
        place_ids: dict[str, str],
    ) -> Iterator[NodeSpec | EdgeSpec]:
        suffix = f":{tag}" if ordinal == 1 else f":{tag}:{ordinal}"
        event_id = f"event:{owner_xref}{suffix}"
        line = gedcom.line_of(ev.offset)
        date_val = ev.sub_tag_value("DATE")
        place = ev.sub_tag_value("PLAC")
        note = ev.sub_tag_value("NOTE")

        label = _EVENT_LABELS.get(tag, tag.title())
        parts = [label]
        if date_val:
            parts.append(str(date_val))
        if place:
            parts.append(f"in {place}")
        name = " ".join(parts)

        docstring_lines = [name]
        if note:
            docstring_lines.append(str(note))

        metadata: dict[str, Any] = {"gedcom_tag": tag}
        metadata.update(temporal_keys(date_val, recorded_at=recorded_at))

        yield NodeSpec(
            node_id=event_id,
            kind="event",
            name=name,
            qualname=event_id,
            source_path=rel_path,
            lineno=line,
            end_lineno=line,
            docstring="\n".join(docstring_lines),
            metadata=metadata,
        )
        yield EdgeSpec(owner_id, event_id, "HAS_EVENT")

        if place:
            pid = yield from self._place(str(place), rel_path, place_ids)
            yield EdgeSpec(event_id, pid, "OCCURRED_AT")

        yield from self._cites(event_id, ev)

    def _place(
        self, place_str: str, rel_path: str, place_ids: dict[str, str]
    ) -> Generator[NodeSpec | EdgeSpec, None, str]:
        """Emit a place and, via ``WITHIN``, every enclosing place not yet seen.

        Each level of ``"Cincinnati, Hamilton, Ohio, USA"`` becomes its own
        ``place`` node the first time it appears in any string; the chain
        stops at the first level already emitted, whose own ancestors were
        emitted with it. ``place_ids`` is keyed by the normalised level
        string, so ``"A,B"`` and ``"A, B"`` share one node.

        :return: The node id of the innermost place.
        """
        chain = place_hierarchy(place_str)
        previous: str | None = None
        for level in chain:
            pid = place_ids.get(level)
            seen = pid is not None
            if pid is None:
                pid = f"place:{place_slug(level)}"
                place_ids[level] = pid
                yield NodeSpec(
                    node_id=pid,
                    kind="place",
                    name=level,
                    qualname=level,
                    source_path=rel_path,
                    docstring=f"Place: {level}",
                    metadata={},
                )
            if previous is not None:
                yield EdgeSpec(previous, pid, "WITHIN")
            if seen:
                break
            previous = pid
        return place_ids[chain[0]]
