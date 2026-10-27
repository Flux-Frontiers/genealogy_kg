"""Hourglass stills, camera fitted tightly to the tree's own points."""

import math
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

from genealogy_kg import scene
from genealogy_kg.module import GenealogyKG

W = H = 1800
FOV = 30.0  # vertical view angle, degrees
MARGIN = 0.85  # fraction of the half-frame the extreme point may reach


def fit_camera(pl, pts, direction):
    """Place the camera along `direction` so `pts` just fill the frame."""
    fwd = -np.asarray(direction, float)
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    c0 = pts.mean(0)
    rel = pts - c0
    r, u, w = rel @ right, rel @ up, rel @ fwd
    # Recenter on the extents in the image plane, not the centroid.
    c = c0 + right * (r.max() + r.min()) / 2 + up * (u.max() + u.min()) / 2
    rel = pts - c
    r, u, w = rel @ right, rel @ up, rel @ fwd
    t = math.tan(math.radians(FOV) / 2) * MARGIN
    d = max(np.max(np.abs(u) / t + w), np.max(np.abs(r) / (t * W / H) + w))
    pl.camera.view_angle = FOV
    pl.camera.focal_point = c
    pl.camera.position = c - fwd * d
    pl.camera.up = up
    pl.reset_camera_clipping_range()


WORDS = {"M": ("father", "son", "husband"), "F": ("mother", "daughter", "wife")}
NEUTRAL = ("parent", "child", "spouse")


def relation(hp, pid, store):
    """Plain-English relationship of pid to the focal person."""
    node = store.node(pid) or {}
    sex = str((node.get("metadata") or {}).get("sex", "")).upper()[:1]
    parent_w, child_w, spouse_w = WORDS.get(sex, NEUTRAL)
    g = hp.generation[pid]
    if pid == hp.root_id:
        return "focal person"
    i = hp.wood_person.index(pid)
    up = hp.wood_person[int(hp.wood_parents[i])]
    married_in = g >= 0 and up is not None and hp.generation.get(up) == g
    if g == 0:
        return spouse_w
    n = abs(g)
    base = parent_w if g < 0 else child_w
    if n == 1:
        rel = base
    elif n == 2:
        rel = "grand" + base
    elif n == 3:
        rel = "great-grand" + base
    else:
        rel = f"{n - 2}x great-grand" + base
    return rel + "-in-law" if married_in else rel


def label(hp, pid, store):
    node = store.node(pid) or {}
    born = str((node.get("metadata") or {}).get("occurred_start") or "")[:4]
    name = node.get("name") or pid
    return f"{name}\n{relation(hp, pid, store)}" + (f", b. {born}" if born else "")


repo, xref, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
with GenealogyKG(repo_root=Path(repo)) as kg:
    for organic in (True, False):
        mode = "organic" if organic else "schematic"
        for view, d in (("side", (1.0, 0.0, 0.0)), ("raised", (1.0, -1.0, 0.7))):
            pl = pv.Plotter(off_screen=True, window_size=(W, H))
            pl.set_background("#F4F1EA")
            t = scene.build_family_tree_scene(
                kg.store, pl, xref, shape="hourglass", organic=organic
            )
            fit_camera(pl, t.points, d)
            hp = t.positions
            ids = list(hp.person_positions)
            pl.add_point_labels(
                np.array([hp.person_positions[i] for i in ids]),
                [label(hp, i, kg.store) for i in ids],
                font_size=13,
                point_size=0,
                shape_color="white",
                shape_opacity=0.75,
                text_color="#222222",
                always_visible=True,
                margin=2,
            )
            pl.add_text(t.title, font_size=9, color="#333333")
            name = (kg.store.node(hp.root_id) or {}).get("name") or xref
            slug = "-".join("".join(ch if ch.isalnum() else " " for ch in name).lower().split())
            path = out / f"{slug}_hourglass_{mode}_{view}.png"
            pl.screenshot(str(path))
            pl.close()
            print(path)
