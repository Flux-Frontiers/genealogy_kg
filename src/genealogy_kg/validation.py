"""genealogy_kg/validation.py

Boundary validation shared by the CLI and MCP server: bounded numeric
ranges and GEDCOM xref normalization. Both surfaces accept external input
(the MCP server explicitly supports the SSE transport beyond a trusted
local environment), so both call these before touching the graph.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import re

#: Search/pack result count.
MAX_K = 100
#: Graph expansion hops from query()/pack() seeds.
MAX_HOP = 5
#: Ancestor/descendant walk depth.
MAX_GENERATIONS = 50
#: Snippet pack size.
MAX_MAX_NODES = 500
#: Natural-language query length, in characters.
MAX_QUERY_LEN = 500

_XREF_RE = re.compile(r"[A-Za-z0-9_.-]+")


def normalize_xref(raw: str) -> str:
    """Normalize a GEDCOM individual pointer to its bare form.

    Accepts ``I7``, ``@I7@``, and ``person:I7`` -- all three show up in
    practice: GEDCOM's own pointer syntax, a bare CLI argument, and an
    agent echoing back a node id it read from a previous tool result.

    :param raw: The xref as given by a caller.
    :return: The bare pointer, e.g. ``"I7"``.
    :raises ValueError: If empty after normalization, or not a plausible
        GEDCOM pointer.
    """
    xref = raw.strip()
    if xref.startswith("person:"):
        xref = xref[len("person:") :]
    if len(xref) >= 2 and xref.startswith("@") and xref.endswith("@"):
        xref = xref[1:-1]
    if not xref or not _XREF_RE.fullmatch(xref):
        raise ValueError(
            f"invalid xref {raw!r}: expected a GEDCOM pointer like 'I7', '@I7@', or 'person:I7'"
        )
    return xref


def bounded_int(name: str, value: int, minimum: int, maximum: int) -> int:
    """Validate that an integer falls within an inclusive range.

    :param name: Parameter name, used in the error message.
    :param value: The value to validate.
    :param minimum: Inclusive lower bound.
    :param maximum: Inclusive upper bound.
    :return: ``value``, unchanged.
    :raises ValueError: If ``value`` is outside ``[minimum, maximum]``.
    """
    if not (minimum <= value <= maximum):
        raise ValueError(f"{name} must be between {minimum} and {maximum}, got {value}")
    return value


def require_query(q: str) -> str:
    """Validate a natural-language query string.

    :param q: The raw query.
    :return: ``q`` stripped of leading/trailing whitespace.
    :raises ValueError: If empty, whitespace-only, or longer than
        :data:`MAX_QUERY_LEN`.
    """
    stripped = q.strip()
    if not stripped:
        raise ValueError("q must not be empty")
    if len(stripped) > MAX_QUERY_LEN:
        raise ValueError(f"q must be at most {MAX_QUERY_LEN} characters, got {len(stripped)}")
    return stripped
