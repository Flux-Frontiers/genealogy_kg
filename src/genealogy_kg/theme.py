"""genealogy_kg/theme.py

Colour vocabulary and generation-depth walk shared by the 2-D (``viz.py``)
and 3-D (``scene.py``) renderers.

Deliberately dependency-free -- no plotly, no pyvista, no PyQt -- so either
renderer's optional extra can be installed alone. ``pycode_kg.theme`` is the
fleet precedent: before that split, its kind-to-colour mapping was defined
three times (2-D pyvis, 3-D PyVista, node-radius layout) and the copies had
drifted. The same drift is possible here: without this module, ``scene.py``
importing anything from ``viz.py`` -- even a colour constant -- would drag
``plotly`` into a bare ``pip install "genealogy-kg[viz3d]"``, breaking that
extra's independent-install contract.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from typing import Any, Final

from kg_utils.store import GraphStore

#: How a person is coloured when ``color_by="sex"``, from the Okabe-Ito
#: colourblind-safe palette.
#:
#: The obvious blue/rose pairing does not survive colour-vision deficiency:
#: simulating the three dichromacies and measuring CIELAB distance, rose
#: against grey collapses to dE 7 under protanopia -- indistinguishable. Blue
#: against orange holds a worst case of dE 30 across all three, because the
#: pair separates in luminance as well as hue, so it also survives greyscale
#: printing.
SEX_COLOR: Final[dict[str, str]] = {
    "person_male": "#0072B2",
    "person_female": "#E69F00",
    "person_unknown": "#7F7F7F",
}

#: Generation offsets are clamped into this range before colouring. Beyond
#: four generations either way the ramp has no headroom left to distinguish.
GENERATION_MIN: Final[int] = -4
GENERATION_MAX: Final[int] = 4

#: Colour per signed generation offset from the chosen root: ancestors cool,
#: the root a neutral pivot, descendants warm. ColorBrewer's RdBu, which is
#: diverging *in luminance* on each arm rather than in hue alone -- the
#: property that keeps the steps apart under colour-vision deficiency. A
#: blue-gold-green ramp measured a worst adjacent step of dE 9 (two shades a
#: tritanope cannot separate); this one holds dE 16.
GENERATION_COLOR: Final[dict[int, str]] = {
    -4: "#053061",
    -3: "#2166AC",
    -2: "#4393C3",
    -1: "#92C5DE",
    0: "#E6E6E6",
    1: "#F4A582",
    2: "#D6604D",
    3: "#B2182B",
    4: "#67001F",
}


def sex_kind(node: Mapping[str, Any]) -> str:
    """Map a node onto its render kind for sex colouring.

    ``person_male`` / ``person_female`` / ``person_unknown`` are display kinds
    only -- the store holds plain ``person``.

    :param node: Node dict.
    :return: A key of :data:`SEX_COLOR` for people, else the stored kind.
    """
    if node.get("kind") != "person":
        return str(node.get("kind", ""))
    sex = str((node.get("metadata") or {}).get("sex", "")).upper()
    if sex.startswith("M"):
        return "person_male"
    if sex.startswith("F"):
        return "person_female"
    return "person_unknown"


def generation_depths(store: GraphStore, root_id: str) -> dict[str, int]:
    """Return each person's signed generation offset from ``root_id``.

    Children are ``+1``, parents ``-1``, and spouses share their partner's
    offset. Walking up and back down therefore lands cousins on ``0``, which
    is what a genealogist means by "the same generation". Breadth-first, so
    the offset found is the one along the shortest kinship path.

    :param store: The graph store.
    :param root_id: Node id to measure from, such as ``person:I1``.
    :return: Node id to offset, including ``root_id`` at ``0``.
    """
    depths: dict[str, int] = {root_id: 0}
    queue: deque[str] = deque([root_id])
    while queue:
        cur = queue.popleft()
        here = depths[cur]
        steps: list[tuple[str, int]] = []
        for edge in store.edges_from(cur, rel="PARENT_OF"):
            steps.append((edge["dst"], here + 1))
        for parent in store.callers_of(cur, rel="PARENT_OF"):
            steps.append((parent["id"], here - 1))
        for edge in store.edges_from(cur, rel="MARRIED_TO"):
            steps.append((edge["dst"], here))
        for spouse in store.callers_of(cur, rel="MARRIED_TO"):
            steps.append((spouse["id"], here))
        for node_id, offset in steps:
            if node_id not in depths:
                depths[node_id] = offset
                queue.append(node_id)
    return depths


def generation_key(offset: int) -> str:
    """Clamp a signed generation offset into a :data:`GENERATION_COLOR` key.

    :param offset: Signed generation offset from some root.
    :return: ``"gen{n}"`` with ``n`` clamped to
        ``[GENERATION_MIN, GENERATION_MAX]``.
    """
    return f"gen{max(GENERATION_MIN, min(GENERATION_MAX, offset))}"


__all__ = [
    "GENERATION_COLOR",
    "GENERATION_MAX",
    "GENERATION_MIN",
    "SEX_COLOR",
    "generation_depths",
    "generation_key",
    "sex_kind",
]
