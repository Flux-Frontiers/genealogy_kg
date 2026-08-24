"""genealogy_kg/viz.py

2-D renderings of a genealogy graph, in the two views the design calls for:

* the **ontological** view -- the ``person``/``family`` network, drawn by
  :func:`network_html`;
* the **semantic** view -- a pedigree/descent chart, drawn by
  :func:`pedigree_figure`.

The network renderer itself is ``kg_utils.viz.build_graph_html``, shared with
every other KG module; what lives here is only the part that is genuinely
about a *family* graph: which kinds exist, how sex and generation are
coloured, and which fields are worth showing on hover. That split is the
fleet pattern -- see ``pycode_kg.graph_html`` for the code-graph equivalent.

The pedigree chart walks :func:`genealogy_kg.lineage.tree_data`, the same walk
``ascii_tree`` renders, so the boxes-and-connectors chart and the ASCII art
cannot drift into two independent layouts.

Nothing here is imported at package import time: ``plotly`` and (through
``kg_utils.viz``) ``pyvis`` arrive with the ``viz`` extra, and both entry
points -- ``cli/cmd_viz.py`` and ``adapter.display()`` -- import this module
inside the call, so a bare install never pulls either.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

import plotly.graph_objects as go
from kg_utils.store import GraphStore
from kg_utils.viz import (
    GraphTheme,
    KindStyle,
    TooltipRow,
    TooltipSpec,
    build_graph_html,
    select_nodes,
)

from genealogy_kg.extractor import NODE_KINDS
from genealogy_kg.lineage import life_span, tree_data
from genealogy_kg.module import DEFAULT_GENEALOGY_RELS
from genealogy_kg.theme import (
    GENERATION_COLOR,
    GENERATION_MAX,
    GENERATION_MIN,
    SEX_COLOR,
    generation_depths,
    generation_key,
    sex_kind,
)

#: Shape per sex -- the redundant encoding that makes the charts readable with
#: no colour at all. Square for male and circle for female is the convention
#: printed pedigree charts have used for a century, so this is what a
#: genealogist already expects rather than a novelty of ours.
SEX_SHAPE: Final[dict[str, str]] = {
    "person_male": "square",
    "person_female": "dot",
    "person_unknown": "triangleDown",
}

#: The same distinction in plotly's marker vocabulary, for the pedigree chart.
SEX_SYMBOL: Final[dict[str, str]] = {
    "person_male": "square",
    "person_female": "circle",
    "person_unknown": "diamond",
}

#: How the non-person kinds are coloured in the ontological view.
KIND_COLOR: Final[dict[str, str]] = {
    "family": "#009E73",
    "event": "#56B4E9",
    "place": "#CC79A7",
    "source": "#F0E442",
}

#: vis.js shape per kind, so the view stays readable without the legend.
#: People take their shape from :data:`SEX_SHAPE` instead, so ``square`` and
#: ``dot`` are spoken for -- hence hexagon for a place.
KIND_SHAPE: Final[dict[str, str]] = {
    "person": "dot",
    "family": "diamond",
    "event": "triangle",
    "place": "hexagon",
    "source": "star",
}

#: Node diameter in pixels per kind. People dominate; the rest support them.
KIND_SIZE: Final[dict[str, int]] = {
    "person": 18,
    "family": 12,
    "event": 9,
    "place": 10,
    "source": 8,
}

#: Edge colour per relation. The two lineage relations are the loud ones;
#: the membership edges they are derived from stay muted so a dense family
#: does not read as a hairball.
REL_COLOR: Final[dict[str, str]] = {
    "PARENT_OF": "#4C78A8",
    "MARRIED_TO": "#D1657A",
    "CHILD_IN": "#C3CEDA",
    "SPOUSE_IN": "#E4CAD1",
    "HAS_EVENT": "#9ED1CE",
    "OCCURRED_AT": "#AECBA0",
    "CITES": "#CDBFDA",
    "WITHIN": "#B6BFC8",
}


def _lifespan_row(node: Mapping[str, Any]) -> str:
    """Render a hover-tooltip row: ``"person - 1820-1891"``.

    A ``TooltipRow`` callback (see :data:`GENEALOGY_TOOLTIP` below), not
    called directly -- passed by reference, which static call-graph analysis
    can miss and flag as unreferenced.

    :param node: The hovered node.
    :return: ``"<kind> - <life span>"``, or just ``<kind>`` when undated.
    """
    kind = str(node.get("kind", ""))
    span = life_span(node)
    return f"{kind} - {span}" if span else kind


def _source_row(node: Mapping[str, Any]) -> str:
    """Render a hover-tooltip row: ``"family.ged:42"``.

    A ``TooltipRow`` callback, same as :func:`_lifespan_row`.

    :param node: The hovered node.
    :return: ``"<path>:<line>"``, or just ``<path>`` when the node has no
        line number (e.g. a redacted living person).
    """
    path = node.get("module_path") or ""
    line = node.get("lineno")
    return f"{path}:{line}" if path and line else str(path)


#: Which genealogy fields are worth showing on hover. ``docstring`` holds the
#: extractor's prose summary of the record, which is the useful body text.
GENEALOGY_TOOLTIP: Final[TooltipSpec] = TooltipSpec(
    title="name",
    rows=(
        TooltipRow(_lifespan_row),
        TooltipRow("qualname"),
        TooltipRow(_source_row, prefix="GEDCOM "),
    ),
    body="docstring",
)


def network_theme(*, color_by: str = "sex", depths: dict[str, int] | None = None) -> GraphTheme:
    """Build the visual vocabulary for the ontological view.

    :param color_by: ``"sex"`` (default) or ``"generation"``.
    :param depths: Signed generation offsets from :func:`generation_depths`;
        required when ``color_by="generation"``.
    :return: A :class:`~kg_utils.viz.GraphTheme`.
    :raises ValueError: If ``color_by`` is unknown, or ``"generation"`` is
        requested without ``depths``.
    """
    if color_by not in ("sex", "generation"):
        raise ValueError(f"color_by must be 'sex' or 'generation', got {color_by!r}")
    if color_by == "generation" and depths is None:
        raise ValueError("color_by='generation' needs depths from generation_depths()")

    kinds: dict[str, KindStyle] = {
        kind: KindStyle(color=KIND_COLOR[kind], shape=KIND_SHAPE[kind], size=KIND_SIZE[kind])
        for kind in KIND_COLOR
    }

    if color_by == "sex":
        for key, color in SEX_COLOR.items():
            kinds[key] = KindStyle(color=color, shape=SEX_SHAPE[key], size=KIND_SIZE["person"])
        resolve = sex_kind
    else:
        assert depths is not None
        # Colour carries the generation, shape still carries the sex. Dropping
        # to a single shape here would throw away the one cue that needs no
        # colour vision at all, for no gain.
        for offset, color in GENERATION_COLOR.items():
            for sex_key, shape in SEX_SHAPE.items():
                kinds[f"gen{offset}_{sex_key}"] = KindStyle(
                    color=color, shape=shape, size=KIND_SIZE["person"]
                )
        for sex_key, shape in SEX_SHAPE.items():
            kinds[sex_key] = KindStyle(
                color=SEX_COLOR["person_unknown"], shape=shape, size=KIND_SIZE["person"]
            )

        def resolve(node: Mapping[str, Any]) -> str:
            if node.get("kind") != "person":
                return str(node.get("kind", ""))
            sex_key = sex_kind(node)
            offset = depths.get(str(node.get("id", "")))
            if offset is None:
                # Outside the walk: no generation to show, but keep the shape.
                return sex_key
            return f"{generation_key(offset)}_{sex_key}"

    return GraphTheme(
        kinds=kinds,
        fallback=KindStyle(color=SEX_COLOR["person_unknown"], shape="dot", size=10),
        relations=REL_COLOR,
        relation_fallback="#B6BFC8",
        resolve_kind=resolve,
    )


def network_html(
    store: GraphStore,
    *,
    root_id: str | None = None,
    hops: int = 2,
    max_nodes: int = 250,
    color_by: str = "sex",
    height: str = "800px",
) -> str:
    """Render the person/family network as a self-contained HTML page.

    With ``root_id`` the picture is that person's kinship neighbourhood, grown
    ``hops`` edges out; without one it is the whole graph, truncated to
    ``max_nodes``. Rooting is the better framing whenever there is a subject:
    a budget applied to the whole graph keeps an arbitrary slice, while an
    expansion keeps everyone actually related to them.

    :param store: The graph store.
    :param root_id: Node id to centre on, such as ``person:I1``, or ``None``
        for the whole graph.
    :param hops: Edges to expand from ``root_id``.
    :param max_nodes: Node budget; a graph stops being readable well below it.
    :param color_by: ``"sex"`` (default) or ``"generation"``.
    :param height: CSS height for the canvas.
    :return: A self-contained HTML document.
    :raises ValueError: If ``root_id`` is not in the store, or the store holds
        no matching nodes.
    """
    if root_id is not None:
        if store.node(root_id) is None:
            raise ValueError(f"no such node: {root_id}")
        reachable = store.expand({root_id}, hop=hops, rels=DEFAULT_GENEALOGY_RELS)
        nodes = [n for n in (store.node(i) for i in reachable) if n is not None]
    else:
        nodes = store.query_nodes(kinds=list(NODE_KINDS))

    if not nodes:
        raise ValueError("no nodes to draw")

    total = len(nodes)
    if total > max_nodes:
        nodes, _ = select_nodes(nodes, max_nodes, None, "path")

    edges = store.edges_within({n["id"] for n in nodes})
    depths = generation_depths(store, root_id) if color_by == "generation" and root_id else None
    if color_by == "generation" and depths is None:
        raise ValueError("color_by='generation' needs a root_id to measure from")

    return build_graph_html(
        nodes,
        edges,
        theme=network_theme(color_by=color_by, depths=depths),
        tooltip=GENEALOGY_TOOLTIP,
        height=height,
        highlight_ids={root_id} if root_id else None,
    )


def _place(tree: dict[str, Any]) -> tuple[list[dict[str, Any]], list[tuple[int, int]]]:
    """Assign each person a position: generation down, siblings across.

    A leaf takes the next free column; a parent centres over its children.
    That is the first pass of the classic tidy-tree layout, and it is all a
    pedigree needs -- the walk is already depth-capped, so the pathological
    cases a full Reingold-Tilford pass exists to fix cannot arise here.

    :param tree: A :func:`~genealogy_kg.lineage.tree_data` root.
    :return: ``(placed, links)``; ``links`` holds ``(parent, child)`` indices
        into ``placed``.
    """
    placed: list[dict[str, Any]] = []
    links: list[tuple[int, int]] = []
    next_column = 0.0

    def walk(subtree: dict[str, Any], depth: int, parent: int | None) -> int:
        nonlocal next_column
        index = len(placed)
        placed.append({})
        children = [walk(child, depth + 1, index) for child in subtree["children"]]
        if children:
            x = (placed[children[0]]["x"] + placed[children[-1]]["x"]) / 2
        else:
            x = next_column
            next_column += 1
        placed[index] = {
            "x": x,
            "y": -depth,
            "depth": depth,
            "label": subtree["label"],
            "node": subtree["node"],
        }
        if parent is not None:
            links.append((parent, index))
        return index

    walk(tree, 0, None)
    return placed, links


def pedigree_figure(
    store: GraphStore,
    person_id: str,
    *,
    direction: str = "descendants",
    generations: int = 4,
    color_by: str = "sex",
) -> go.Figure:
    """Render a pedigree/descent chart as boxes and connectors.

    The visual upgrade path from ``ascii_tree``: same walk, same orientation
    (root at the top, each generation a row below), drawn rather than typed.

    :param store: The graph store.
    :param person_id: Node id such as ``person:I1``.
    :param direction: ``"descendants"`` (default) or ``"ancestors"``.
    :param generations: Maximum generations to walk.
    :param color_by: ``"sex"`` (default) or ``"generation"``.
    :return: A plotly ``Figure``.
    :raises ValueError: If ``person_id`` is unknown, or ``direction`` /
        ``color_by`` is not one of the accepted values.
    """
    if color_by not in ("sex", "generation"):
        raise ValueError(f"color_by must be 'sex' or 'generation', got {color_by!r}")

    tree = tree_data(store, person_id, direction=direction, generations=generations)
    if tree is None:
        raise ValueError(f"no such person: {person_id}")

    placed, links = _place(tree)

    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for parent, child in links:
        px, py = placed[parent]["x"], placed[parent]["y"]
        cx, cy = placed[child]["x"], placed[child]["y"]
        waist = py - 0.5
        edge_x += [px, px, cx, cx, None]
        edge_y += [py, waist, waist, cy, None]

    if color_by == "sex":
        colors = [SEX_COLOR[sex_kind(p["node"])] for p in placed]
    else:
        # Depth is already the generation offset here; walking ancestors just
        # makes it count the other way.
        sign = 1 if direction == "descendants" else -1
        colors = [
            GENERATION_COLOR[max(GENERATION_MIN, min(GENERATION_MAX, sign * p["depth"]))]
            for p in placed
        ]

    labels = []
    for person in placed:
        name = person["node"].get("name") or person["node"]["id"]
        span = life_span(person["node"])
        labels.append(f"{name}<br>{span}" if span else str(name))

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line={"color": "#98A4B0", "width": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[p["x"] for p in placed],
            y=[p["y"] for p in placed],
            mode="markers+text",
            marker={
                # Shape always carries sex, whatever colour is carrying, so
                # the chart still reads with no colour vision at all.
                "symbol": [SEX_SYMBOL[sex_kind(p["node"])] for p in placed],
                "size": 26,
                "color": colors,
                "line": {"color": "#33383D", "width": 1.5},
            },
            text=labels,
            textposition="bottom center",
            textfont={"size": 10},
            hovertext=[p["label"] for p in placed],
            hoverinfo="text",
            showlegend=False,
        )
    )

    root_name = tree["node"].get("name") or person_id
    columns = max(p["x"] for p in placed) - min(p["x"] for p in placed) + 1
    depth = max(p["depth"] for p in placed)
    figure.update_layout(
        title=f"{direction.capitalize()} of {root_name}",
        xaxis={"visible": False},
        yaxis={"visible": False},
        width=max(760, int(columns * 110)),
        height=max(420, (depth + 1) * 150),
        margin={"l": 40, "r": 40, "t": 60, "b": 40},
        plot_bgcolor="white",
        hoverlabel={"align": "left"},
    )
    return figure


__all__ = [
    "GENEALOGY_TOOLTIP",
    "GENERATION_COLOR",
    "KIND_COLOR",
    "REL_COLOR",
    "SEX_COLOR",
    "SEX_SHAPE",
    "SEX_SYMBOL",
    "generation_depths",
    "network_html",
    "network_theme",
    "pedigree_figure",
    "sex_kind",
]
