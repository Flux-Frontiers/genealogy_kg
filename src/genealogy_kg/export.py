"""genealogy_kg/export.py

Data exports for The Knowledge Press: The Family (``kpress_family``), which
reads a family as files rather than through this package. This module holds
what every export shares -- the privacy gate and the assignment of people to
family lines -- and the web export itself.

The privacy gate
----------------
Living-person redaction happens at build time, in
:class:`~genealogy_kg.extractor.GedcomExtractor`, and the store does not
record which cutoff it was built with. So an export never trusts the store:
it re-reads the GEDCOM with the export's own cutoff, and for every person that
cutoff treats as living it checks that the store holds only the ``Living``
placeholder. A store built with no cutoff, or a looser one, fails the check
and the export refuses, naming the rebuild that fixes it. After writing, the
export scans every file it wrote for the real names of those people, and
refuses again if any appears (a note in a deceased relative's record can name
a living child). A name someone not living also bears is not scanned for, since
that person's own page must carry it; a note naming a living namesake of an
ancestor is the one leak the scan cannot see. Output is written to a temporary directory and moved into
place only after the scan passes, so a refused export leaves nothing behind.

``include_living=True`` skips both checks and is recorded in the output; it
is for a private family's own machine, never for anything published.

Lines
-----
A line is a surname by birth: the people born with that surname, joined by
parent-to-child edges, from its earliest recorded member. A spouse who
married in belongs to their own birth line, so a marriage between two lines
is a cross-tree link (the orchard's marriage roads). Every person is in
exactly one line, which is what the Swift pack's single ``genre`` column needs.
A person with no recorded surname (a redacted living person, or a placeholder
such as ``(-----)``) takes the line of a parent, the father first, as surnames
usually pass. A file with no surnames at all, such as the Bible's, would leave
everyone over, so the remainder is cut into houses: a house is named for its
head, a person who is the father (or, with no father recorded, the mother) of
at least ``HOUSE_CHILDREN`` children, and holds their descent, father first
again, down to the next head. Anyone still left
over goes to the ``unknown`` line, which no cross-line link touches.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from genealogy_kg import __version__
from genealogy_kg.extractor import LIVING_NAME, GedcomExtractor, _xref
from genealogy_kg.gedcom import GedcomFile

if TYPE_CHECKING:
    from kg_utils.store import GraphStore

    from genealogy_kg.module import GenealogyKG

#: Bumped when a consumer would have to change to read the output.
EXPORT_FORMAT_VERSION: Final[int] = 1

#: Line id for people no surname or parent places in a line.
UNKNOWN_LINE: Final[str] = "unknown"
# Children it takes to head a house, among people with no surname above them:
# counted father first, so a patriarch's wife heads no house of her own.
HOUSE_CHILDREN: Final[int] = 3

#: Names shorter than this are not scanned for: a three-letter name matches
#: inside ordinary words and would refuse every export.
MIN_SCANNED_NAME: Final[int] = 4


class ExportError(RuntimeError):
    """An export was refused, or its input could not be read."""


@dataclass(frozen=True)
class PrivacySettings:
    """How an export treats living people.

    :param living_cutoff_years: Redact people with no death record born within
        this many years, or ``None`` with ``include_living``.
    :param unknown_birth_policy: ``"redact"`` or ``"keep"`` for people with no
        usable birth date and no death record.
    :param include_living: Export with no redaction at all. Recorded in the
        output.
    """

    living_cutoff_years: int | None
    unknown_birth_policy: str = "redact"
    include_living: bool = False

    def __post_init__(self) -> None:
        if self.unknown_birth_policy not in {"keep", "redact"}:
            raise ExportError('unknown_birth_policy must be "keep" or "redact"')
        if self.include_living and self.living_cutoff_years is not None:
            raise ExportError("pass a living cutoff or include_living, not both")
        if not self.include_living and self.living_cutoff_years is None:
            raise ExportError(
                "refusing to export without a living-person cutoff: pass "
                "--living-cutoff N (or set [tool.genealogykg] living_cutoff_years), "
                "or --include-living for a private export"
            )
        if self.living_cutoff_years is not None and self.living_cutoff_years < 0:
            raise ExportError("living_cutoff_years must be >= 0")

    def as_dict(self) -> dict[str, Any]:
        """Return the settings as written into every export's metadata."""
        return {
            "living_cutoff_years": self.living_cutoff_years,
            "unknown_birth_policy": self.unknown_birth_policy,
            "include_living": self.include_living,
        }


# ---------------------------------------------------------------------------
# The privacy gate
# ---------------------------------------------------------------------------


def verify_redaction(kg: GenealogyKG, privacy: PrivacySettings) -> dict[str, str]:
    """Check the store against the GEDCOM under the export's cutoff.

    :param kg: An open GenealogyKG.
    :param privacy: The export's privacy settings.
    :return: The real names of everyone treated as living, each mapped to
        their xref, for :func:`scan_for_names`; less any name someone not
        living also bears, since a living namesake of an ancestor cannot be
        told apart by name and the ancestor's own page must carry it. Empty
        with ``include_living``.
    :raises ExportError: If no GEDCOM source resolves, or the store holds a
        person the cutoff treats as living under anything but the ``Living``
        placeholder.
    """
    if privacy.include_living:
        return {}
    sources = kg.make_extractor().sources
    if not sources:
        raise ExportError(
            "no GEDCOM sources resolved, so redaction cannot be verified; run "
            "'genkg build --source ...' or set [tool.genealogykg] sources"
        )
    extractor = GedcomExtractor(
        kg.repo_root,
        sources=sources,
        living_cutoff_years=privacy.living_cutoff_years,
        unknown_birth_policy=privacy.unknown_birth_policy,
    )
    names: dict[str, str] = {}
    shared: set[str] = set()
    unredacted: list[str] = []
    for source in extractor.sources:
        with GedcomFile(extractor.repo_path / source) as gedcom:
            for ind in gedcom.records("INDI"):
                if not extractor.is_living(ind):
                    shared.update(f.casefold() for f in _name_forms(ind))
                    continue
                node_id = f"person:{_xref(ind)}"
                node = kg.store.node(node_id)
                if node is not None and (
                    node["name"] != LIVING_NAME or kg.store.edges_from(node_id, rel="HAS_EVENT")
                ):
                    unredacted.append(node_id)
                names.update(dict.fromkeys(_name_forms(ind), _xref(ind)))
    if unredacted:
        raise ExportError(
            f"{len(unredacted)} people this export treats as living are not redacted "
            f"in the store (first: {unredacted[0]}). Rebuild with living_cutoff_years = "
            f"{privacy.living_cutoff_years} and unknown_birth_policy = "
            f'"{privacy.unknown_birth_policy}", then export again.'
        )
    return {n: xref for n, xref in names.items() if n.casefold() not in shared}


def _name_forms(ind: Any) -> list[str]:
    """Return the forms of a person's name an export could contain."""
    full = ind.name.format()
    surname = ind.name.surname or ""
    given = ind.name.given or ""
    forms = {full, f"{surname}, {given}".strip(", "), f"{given} {surname}".strip()}
    return [f for f in forms if len(f) >= MIN_SCANNED_NAME]


def _pack_texts(path: Path) -> list[str]:
    """Every text value in a device pack, read through SQLite.

    A pack cannot be scanned as bytes: SQLite stores a cell over about 4 KB
    across overflow pages, each starting with a page pointer, so a name that
    straddles a page boundary is split in the file.
    """
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        texts = [
            value
            for row in con.execute("SELECT name, title, node_title, author, content FROM passages")
            for value in row
            if value
        ]
        texts.extend(v for (v,) in con.execute("SELECT value FROM pack_meta") if v)
    finally:
        con.close()
    return texts


def scan_for_names(root: Path, names: dict[str, str]) -> list[tuple[str, str]]:
    """Find any of *names* under *root*, as whole words, case-insensitively.

    JSON and text files are read whole; a ``.pack`` is read through SQLite
    (see :func:`_pack_texts`). Vector sidecars and the Core ML embedder are
    skipped: they cannot carry a name.

    :param root: Directory to scan, recursively.
    :param names: Name -> the xref of the living person who bears it.
    :return: ``(relative path, xref)`` for every hit; empty when clean.
    """
    if not names:
        return []
    alternatives = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    pattern = re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)
    xref_of = {n.casefold(): xref for n, xref in names.items()}
    hits: list[tuple[str, str]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        if path.suffix == ".vectors" or any(part.endswith(".mlpackage") for part in rel.parts):
            continue
        if path.suffix == ".pack":
            texts = _pack_texts(path)
        else:
            texts = [path.read_bytes().decode("utf-8", errors="replace")]
        for text in texts:
            hits.extend((str(rel), xref_of[m.group(0).casefold()]) for m in pattern.finditer(text))
    return hits


def refuse_on_hits(hits: list[tuple[str, str]]) -> None:
    """Raise if :func:`scan_for_names` found anything, naming who and where.

    The message names the xref, not the name: an xref is not personal data,
    and it is what finds the record to fix.

    :raises ExportError: When *hits* is not empty.
    """
    if hits:
        path, xref = hits[0]
        raise ExportError(
            f"living person {xref}'s name appears in {path} ({len(hits)} hits in all); "
            "nothing was written. A note or source in another record probably names "
            "them: edit the GEDCOM, rebuild, and export again."
        )


# ---------------------------------------------------------------------------
# The graph, loaded once
# ---------------------------------------------------------------------------


@dataclass
class FamilyGraph:
    """Every node and kinship edge an export reads, loaded from the store once.

    :param nodes: Every node by id.
    :param parents: Person id -> parent person ids (from ``PARENT_OF``).
    :param children: Person id -> child person ids.
    :param spouses_of: Family id -> spouse person ids (from ``SPOUSE_IN``).
    :param children_of: Family id -> child person ids (from ``CHILD_IN``).
    :param families_of: Person id -> family ids they are a spouse in.
    :param birth_families: Person id -> family ids they are a child in.
    :param events_of: Person or family id -> event ids (from ``HAS_EVENT``).
    :param place_of: Event id -> place id (from ``OCCURRED_AT``).
    :param within: Place id -> enclosing place id (from ``WITHIN``).
    """

    nodes: dict[str, dict[str, Any]]
    parents: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    children: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    spouses_of: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    children_of: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    families_of: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    birth_families: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    events_of: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    place_of: dict[str, str] = field(default_factory=dict)
    within: dict[str, str] = field(default_factory=dict)

    def of_kind(self, kind: str) -> list[dict[str, Any]]:
        """Return every node of *kind*, ordered by id for stable output."""
        return sorted((n for n in self.nodes.values() if n["kind"] == kind), key=lambda n: n["id"])


def load_graph(store: GraphStore) -> FamilyGraph:
    """Load the nodes and kinship edges an export needs.

    :param store: The graph store.
    :return: The loaded :class:`FamilyGraph`.
    """
    graph = FamilyGraph(nodes={n["id"]: n for n in store.query_nodes()})
    rows = store.con.execute("SELECT src, rel, dst FROM edges ORDER BY src, rel, dst").fetchall()
    for src, rel, dst in rows:
        if rel == "PARENT_OF":
            graph.parents[dst].append(src)
            graph.children[src].append(dst)
        elif rel == "SPOUSE_IN":
            graph.spouses_of[dst].append(src)
            graph.families_of[src].append(dst)
        elif rel == "CHILD_IN":
            graph.children_of[dst].append(src)
            graph.birth_families[src].append(dst)
        elif rel == "HAS_EVENT":
            graph.events_of[src].append(dst)
        elif rel == "OCCURRED_AT":
            graph.place_of[src] = dst
        elif rel == "WITHIN":
            graph.within[src] = dst
    return graph


def _meta(node: dict[str, Any]) -> dict[str, Any]:
    return node.get("metadata") or {}


def _year(value: Any) -> str | None:
    return str(value)[:4] if value else None


def _xref_of(node_id: str) -> str:
    return node_id.split(":", 1)[1]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-") or "x"


def _is_living(node: dict[str, Any]) -> bool:
    return bool(_meta(node).get("living")) or node["name"] == LIVING_NAME


def _surname_key(node: dict[str, Any]) -> str | None:
    """Return a person's surname for grouping, or ``None`` when there is none.

    A surname with no letters is a placeholder for an unrecorded one, as in
    ``Mary (-----)``, and groups nobody.
    """
    surname = str(_meta(node).get("surname") or "").strip()
    return surname.casefold() if any(ch.isalpha() for ch in surname) else None


def _house_name(node: dict[str, Any]) -> str | None:
    """Return the name a house takes from its head: their first name, or ``None``.

    The first word of the recorded name, as a surname-less file writes
    ``Judah (Judas)`` or ``Ruth of Moab``; a word with no letters names nothing.
    """
    words = str(node["name"]).split()
    first = words[0] if words else ""
    return first if any(ch.isalpha() for ch in first) else None


def _parents_father_first(graph: FamilyGraph, people: dict[str, Any], pid: str) -> list[str]:
    """Return a person's recorded parents, the father first."""
    return sorted(
        (p for p in graph.parents.get(pid, []) if p in people),
        key=lambda p: (str(_meta(people[p]).get("sex", "")).upper() != "M", p),
    )


def _birth_key(node: dict[str, Any]) -> tuple[str, str]:
    """Sort key: earliest recorded date first, undated last, then id."""
    return (str(_meta(node).get("occurred_start") or "9999"), node["id"])


# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    """One family line: the people born with one surname, joined by descent.

    :param id: Stable id, ``<surname-slug>-<founder xref>``, or ``unknown``.
    :param surname: Display surname, or a house head's first name.
    :param founder: Person id of the earliest member with no parent in the line
        (a house's head).
    :param members: Person ids in the line, founder first.
    """

    id: str
    surname: str
    founder: str | None
    members: tuple[str, ...]


def assign_lines(graph: FamilyGraph) -> tuple[dict[str, str], list[Line]]:
    """Put every person in exactly one line.

    :param graph: The loaded graph.
    :return: ``(person id -> line id, lines)``, lines ordered by surname and
        then founder.
    """
    people = {n["id"]: n for n in graph.of_kind("person")}
    key = {pid: _surname_key(n) for pid, n in people.items()}

    root = {pid: pid for pid in people}

    def find(pid: str) -> str:
        while root[pid] != pid:
            root[pid] = root[root[pid]]
            pid = root[pid]
        return pid

    for child, parents in graph.parents.items():
        for parent in parents:
            if child in people and parent in people and key[child] and key[child] == key[parent]:
                root[find(child)] = find(parent)

    group: dict[str, str | None] = {pid: find(pid) if key[pid] else None for pid in people}

    # Surname-less people take a parent's group, father first; repeat so a
    # surname-less child of a surname-less parent still finds the grandparent.
    changed = True
    while changed:
        changed = False
        for pid in sorted(people):
            if group[pid] is not None:
                continue
            for parent in _parents_father_first(graph, people, pid):
                if group[parent] is not None:
                    group[pid] = group[parent]
                    changed = True
                    break

    # What is left has no surname anywhere above it. Cut it into houses: a
    # head is a dead person who is the first parent, father first, of
    # HOUSE_CHILDREN or more children, and a house is their descent, father
    # first, down to the next head.
    ungrouped = {pid for pid in people if group[pid] is None}
    headed: Counter[str] = Counter()
    for pid in ungrouped:
        parents = _parents_father_first(graph, people, pid)
        if parents:
            headed[parents[0]] += 1
    heads = {
        pid
        for pid in ungrouped
        if not _is_living(people[pid])
        and _house_name(people[pid])
        and headed[pid] >= HOUSE_CHILDREN
    }
    house_of: dict[str, str | None] = {}

    def house(pid: str) -> str | None:
        if pid in heads:
            return pid
        if pid not in house_of:
            house_of[pid] = None
            for parent in _parents_father_first(graph, people, pid):
                if parent in ungrouped and house(parent):
                    house_of[pid] = house(parent)
                    break
        return house_of[pid]

    house_name: dict[str, str] = {}
    for pid in sorted(ungrouped):
        head = house(pid)
        if head:
            group[pid] = head
            house_name[head] = _house_name(people[head]) or ""

    members: dict[str, list[str]] = defaultdict(list)
    for pid in sorted(people):
        members[group[pid] or UNKNOWN_LINE].append(pid)

    lines: list[Line] = []
    assignment: dict[str, str] = {}
    for gid, pids in members.items():
        if gid == UNKNOWN_LINE:
            line = Line(UNKNOWN_LINE, "Unknown", None, tuple(sorted(pids)))
        else:
            spellings = Counter(
                str(_meta(people[p]).get("surname")).strip()
                for p in pids
                if _surname_key(people[p])
            )
            surname = house_name.get(gid) or max(
                spellings, key=lambda s: (spellings[s], not s.isupper(), s)
            )
            in_line = set(pids)
            roots = [p for p in pids if not any(q in in_line for q in graph.parents.get(p, []))]
            founder = min(roots or pids, key=lambda p: _birth_key(people[p]))
            ordered = [founder] + sorted(
                (p for p in pids if p != founder), key=lambda p: _birth_key(people[p])
            )
            line = Line(f"{_slug(surname)}-{_xref_of(founder)}", surname, founder, tuple(ordered))
        lines.append(line)
        for pid in line.members:
            assignment[pid] = line.id

    lines.sort(key=lambda ln: (ln.id == UNKNOWN_LINE, ln.surname.casefold(), ln.id))
    return assignment, lines


# ---------------------------------------------------------------------------
# The web export
# ---------------------------------------------------------------------------


def _event_entry(graph: FamilyGraph, event_id: str) -> dict[str, Any]:
    node = graph.nodes[event_id]
    meta = _meta(node)
    place = graph.place_of.get(event_id)
    return {
        "type": meta.get("gedcom_tag"),
        "label": node["name"],
        "date": meta.get("occurred_start"),
        "place": _xref_of(place) if place else None,
    }


def _birth_place(graph: FamilyGraph, person_id: str) -> str | None:
    for event_id in graph.events_of.get(person_id, []):
        if _meta(graph.nodes[event_id]).get("gedcom_tag") in {"BIRT", "BAPM", "CHR"}:
            place = graph.place_of.get(event_id)
            if place:
                return _xref_of(place)
    return None


def build_catalog(
    graph: FamilyGraph,
    assignment: dict[str, str],
    lines: list[Line],
    privacy: PrivacySettings,
    sources: list[str],
) -> dict[str, Any]:
    """Build ``catalog.json``: lines, people, families, links and places.

    :param graph: The loaded graph.
    :param assignment: Person id -> line id, from :func:`assign_lines`.
    :param lines: The lines.
    :param privacy: Recorded in the metadata.
    :param sources: GEDCOM file names, recorded in the metadata.
    :return: The catalog as a JSON-ready dict.
    """
    people = []
    for node in graph.of_kind("person"):
        meta = _meta(node)
        living = _is_living(node)
        people.append(
            {
                "id": _xref_of(node["id"]),
                "name": node["name"],
                "surname": None if living else meta.get("surname"),
                "sex": meta.get("sex"),
                "born": None if living else _year(meta.get("occurred_start")),
                "died": None if living else _year(meta.get("occurred_end")),
                "birth_place": None if living else _birth_place(graph, node["id"]),
                "line": assignment[node["id"]],
                "living": living,
            }
        )

    families = []
    links = []
    for node in graph.of_kind("family"):
        spouses = graph.spouses_of.get(node["id"], [])
        families.append(
            {
                "id": _xref_of(node["id"]),
                "spouses": [_xref_of(s) for s in spouses],
                "children": [_xref_of(c) for c in graph.children_of.get(node["id"], [])],
                "married": _year(_meta(node).get("occurred_start")),
            }
        )
        spouse_lines = sorted(
            {assignment[s] for s in spouses if assignment.get(s, UNKNOWN_LINE) != UNKNOWN_LINE}
        )
        if len(spouse_lines) > 1:
            links.append(
                {
                    "family": _xref_of(node["id"]),
                    "lines": spouse_lines,
                    "spouses": [_xref_of(s) for s in spouses],
                    "married": _year(_meta(node).get("occurred_start")),
                }
            )

    event_count: Counter[str] = Counter(graph.place_of.values())
    places = [
        {
            "id": _xref_of(node["id"]),
            "name": node["name"],
            "within": _xref_of(graph.within[node["id"]]) if node["id"] in graph.within else None,
            "events": event_count[node["id"]],
        }
        for node in graph.of_kind("place")
    ]

    line_entries = []
    for line in lines:
        founders: list[str] = []
        if line.founder is not None:
            founders.append(line.founder)
            for family in graph.families_of.get(line.founder, []):
                founders.extend(s for s in graph.spouses_of[family] if s not in founders)
        born = [
            y
            for p in line.members
            if not _is_living(graph.nodes[p])
            and (y := _year(_meta(graph.nodes[p]).get("occurred_start")))
        ]
        line_entries.append(
            {
                "id": line.id,
                "surname": line.surname,
                "grove": line.surname.casefold(),
                "founders": [_xref_of(f) for f in founders],
                "members": [_xref_of(p) for p in line.members],
                "span": [min(born), max(born)] if born else None,
            }
        )

    return {
        "meta": {
            "format": EXPORT_FORMAT_VERSION,
            "generator": f"genealogy_kg {__version__}",
            "generated": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "sources": sources,
            "privacy": privacy.as_dict(),
            "counts": {
                "people": len(people),
                "families": len(families),
                "lines": len(line_entries),
                "links": len(links),
                "places": len(places),
            },
        },
        "lines": line_entries,
        "people": people,
        "families": families,
        "links": links,
        "places": places,
    }


class _RecordReader:
    """Read GEDCOM record lines by span, caching each file once."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._files: dict[str, list[str]] = {}

    def lines(self, module_path: str, start: int, end: int) -> list[str]:
        if module_path not in self._files:
            data = (self.repo_root / module_path).read_bytes()
            self._files[module_path] = data.decode("utf-8", errors="replace").splitlines()
        return self._files[module_path][start - 1 : end]


def person_record(
    graph: FamilyGraph, person_id: str, line_id: str, reader: _RecordReader
) -> dict[str, Any]:
    """Build ``people/<xref>.json``, the record reader's page for one person.

    :param graph: The loaded graph.
    :param person_id: Person node id.
    :param line_id: The person's line.
    :param reader: GEDCOM line reader.
    :return: The page as a JSON-ready dict. A living person's page has no
        summary, events or record lines.
    """
    node = graph.nodes[person_id]
    living = _is_living(node)
    spouses = [
        {"id": _xref_of(s), "family": _xref_of(f)}
        for f in graph.families_of.get(person_id, [])
        for s in graph.spouses_of[f]
        if s != person_id
    ]
    record = None
    if not living and node.get("module_path") and node.get("lineno") and node.get("end_lineno"):
        start, end = int(node["lineno"]), int(node["end_lineno"])
        record = {
            "file": Path(node["module_path"]).name,
            "start": start,
            "end": end,
            "lines": reader.lines(node["module_path"], start, end),
        }
    events = (
        []
        if living
        else sorted(
            (_event_entry(graph, e) for e in graph.events_of.get(person_id, [])),
            key=lambda e: (e["date"] or "9999", e["type"] or ""),
        )
    )
    return {
        "id": _xref_of(person_id),
        "name": node["name"],
        "sex": _meta(node).get("sex"),
        "line": line_id,
        "living": living,
        "summary": None if living else node.get("docstring"),
        "events": events,
        "parents": [_xref_of(p) for p in graph.parents.get(person_id, [])],
        "spouses": spouses,
        "children": [_xref_of(c) for c in graph.children.get(person_id, [])],
        "record": record,
    }


@dataclass(frozen=True)
class WebExport:
    """What :func:`export_web` wrote.

    :param out: The output directory.
    :param people: People written.
    :param lines: Lines in the catalog.
    :param links: Cross-line marriages.
    :param redacted: People treated as living.
    """

    out: Path
    people: int
    lines: int
    links: int
    redacted: int


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _species_table() -> dict[str, Any]:
    from kg_utils.viz3d.species import species_table  # noqa: PLC0415 - NumPy only

    return species_table()


def check_replaceable(out: Path, *, force: bool, marker: str) -> None:
    """Refuse unless *out* is missing, empty, or an earlier export and *force*.

    :param out: The output directory.
    :param force: Whether replacing an earlier export was asked for.
    :param marker: A file name every export of this kind writes.
    :raises ExportError: If *out* may not be replaced.
    """
    if out.exists() and any(out.iterdir()):
        if not force:
            raise ExportError(f"{out} is not empty; pass --force to replace it")
        if not (out / marker).exists():
            raise ExportError(f"{out} holds something other than an export; not replacing it")


def _replace_dir(tmp: Path, out: Path, *, force: bool, marker: str) -> None:
    """Move *tmp* to *out*, replacing an earlier export only with *force*.

    :param marker: A file name every export of this kind writes; an existing
        *out* without it is not ours, and is never removed.
    """
    check_replaceable(out, force=force, marker=marker)
    if out.exists() and any(out.iterdir()):
        shutil.rmtree(out)
    elif out.exists():
        out.rmdir()
    tmp.rename(out)


def export_web(
    kg: GenealogyKG, out: Path, privacy: PrivacySettings, *, force: bool = False
) -> WebExport:
    """Write the web orchard's data: ``catalog.json``, ``people/``, ``species.json``.

    :param kg: An open GenealogyKG.
    :param out: Output directory.
    :param privacy: Living-person settings; see :class:`PrivacySettings`.
    :param force: Replace an earlier export in *out*.
    :return: A :class:`WebExport` summary.
    :raises ExportError: If redaction cannot be verified, a living person's
        name appears in the output, or *out* is not ours to replace.
    """
    names = verify_redaction(kg, privacy)
    graph = load_graph(kg.store)
    assignment, lines = assign_lines(graph)
    sources = [Path(s).name for s in kg.make_extractor().sources]

    out = out.resolve()
    tmp = out.parent / f".{out.name}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    try:
        catalog = build_catalog(graph, assignment, lines, privacy, sources)
        _write_json(tmp / "catalog.json", catalog)
        _write_json(tmp / "species.json", _species_table())
        reader = _RecordReader(kg.repo_root)
        for node in graph.of_kind("person"):
            pid = node["id"]
            _write_json(
                tmp / "people" / f"{_xref_of(pid)}.json",
                person_record(graph, pid, assignment[pid], reader),
            )
        refuse_on_hits(scan_for_names(tmp, names))
        _replace_dir(tmp, out, force=force, marker="catalog.json")
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)

    return WebExport(
        out=out,
        people=len(catalog["people"]),
        lines=len(lines),
        links=len(catalog["links"]),
        redacted=sum(p["living"] for p in catalog["people"]),
    )


__all__ = [
    "EXPORT_FORMAT_VERSION",
    "ExportError",
    "FamilyGraph",
    "Line",
    "PrivacySettings",
    "WebExport",
    "assign_lines",
    "build_catalog",
    "export_web",
    "load_graph",
    "person_record",
    "refuse_on_hits",
    "scan_for_names",
    "verify_redaction",
]
