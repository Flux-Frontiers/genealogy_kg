"""genealogy_kg/viz3d.py

Interactive 3-D viewer for a grown family tree: a ``QMainWindow`` wrapping a
``pyvistaqt.QtInteractor``, showing what :func:`genealogy_kg.scene.build_family_tree_scene`
composes.

Deliberately smaller than ``gutenberg_kg``'s or ``pycode_kg``'s Qt viewers
(~1500 lines each): no custom picking, no info popups, no filter toggles.
``QtInteractor`` supplies orbit/zoom/pan for free via VTK's default
interactor style -- that is "interactive" without writing camera-control
code. One toolbar action, Cast to Looking Glass, wired straight to
``kg_utils.viz3d.qt.cast_scene_to_looking_glass``, which does the entire cast
on the GUI thread. Picking/popups/filters are a clean follow-up once the
growth/placement logic in ``scene.py`` -- the part that can actually be
wrong -- is proven.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

from pathlib import Path

from kg_utils.store import GraphStore
from kg_utils.viz3d import frame_tree
from kg_utils.viz3d.qt import DEFAULT_QUILT_PRESET, cast_scene_to_looking_glass
from PyQt5.QtWidgets import QAction, QMainWindow, QMessageBox, QToolBar
from pyvistaqt import QtInteractor

from genealogy_kg import scene as render3d
from genealogy_kg.module import GenealogyKG


class FamilyTreeWindow(QMainWindow):
    """Main window: one grown tree, orbit/zoom/pan, one Cast action.

    :param store: The graph store to grow from.
    :param xref: Individual xref without ``@``; founds the tree.
    :param color_by: ``"sex"`` or ``"generation"``.
    :param preset: Quilt preset name for the Cast action.
    :param organic: ``True`` (default) grows real wood; ``False`` draws the
        cheap straight-line schematic instead -- see
        :func:`genealogy_kg.scene.build_family_tree_scene`.
    :param shape: ``"hourglass"`` or ``"canopy"``; see
        :func:`genealogy_kg.scene.build_family_tree_scene`.
    :param max_ancestors: Hourglass ancestor generations, ``None`` for all.
    :param max_descendants: Hourglass descendant generations, ``None`` for all.
    """

    def __init__(
        self,
        store: GraphStore,
        xref: str,
        *,
        color_by: str = "generation",
        preset: str = DEFAULT_QUILT_PRESET,
        organic: bool = True,
        shape: str = "hourglass",
        max_ancestors: int | None = 5,
        max_descendants: int | None = 4,
    ) -> None:
        super().__init__()
        self._store = store
        self._xref = xref
        self._color_by = color_by
        self._preset = preset
        self._organic = organic
        self._shape = shape
        self._max_ancestors = max_ancestors
        self._max_descendants = max_descendants

        self.plotter = QtInteractor(self)
        self.setCentralWidget(self.plotter)

        tree = render3d.build_family_tree_scene(
            store,
            self.plotter,
            xref,
            color_by=color_by,
            organic=organic,
            shape=shape,
            max_ancestors=max_ancestors,
            max_descendants=max_descendants,
        )
        self.setWindowTitle(f"GenealogyKG viz3d -- {tree.title}")

        frame = frame_tree(tree.points)
        self.plotter.camera.position = frame.position
        self.plotter.camera.focal_point = frame.focal_point
        self.plotter.camera.up = frame.up
        self.plotter.reset_camera()

        toolbar = QToolBar("Actions", self)
        self.addToolBar(toolbar)
        cast_action = QAction("Cast to Looking Glass", self)
        cast_action.triggered.connect(self._cast)
        toolbar.addAction(cast_action)

    def _cast(self) -> None:
        """Render the current view off-screen and push it to Looking Glass Bridge."""
        from quiltwright import QUILT_PRESETS  # noqa: PLC0415 - viz3d-only import

        spec = QUILT_PRESETS[self._preset]
        xref, color_by, organic, shape = self._xref, self._color_by, self._organic, self._shape
        store = self._store
        max_ancestors, max_descendants = self._max_ancestors, self._max_descendants

        def build(plotter) -> None:
            render3d.build_family_tree_scene(
                store,
                plotter,
                xref,
                color_by=color_by,
                organic=organic,
                shape=shape,
                max_ancestors=max_ancestors,
                max_descendants=max_descendants,
            )

        result = cast_scene_to_looking_glass(
            build, self.plotter.camera_position, Path("renders") / f"{xref}_cast", spec
        )
        box = QMessageBox.information if result.path else QMessageBox.warning
        box(self, "Cast to Looking Glass", result.message)


def launch(
    repo: Path,
    db: Path | None,
    xref: str,
    *,
    color_by: str = "generation",
    preset: str = DEFAULT_QUILT_PRESET,
    organic: bool = True,
    shape: str = "hourglass",
    max_ancestors: int | None = 5,
    max_descendants: int | None = 4,
    width: int = 1400,
    height: int = 900,
) -> None:
    """Open the interactive viewer for xref's grown family tree.

    :param repo: Repository root; the store lives in ``<repo>/.genealogykg/``.
    :param db: SQLite graph path override, or ``None`` for the default.
    :param xref: Individual xref without ``@``; founds the tree.
    :param color_by: ``"sex"`` or ``"generation"``.
    :param preset: Quilt preset name for the Cast action.
    :param organic: ``True`` (default) grows real wood; ``False`` draws the
        cheap straight-line schematic instead.
    :param shape: ``"hourglass"`` (default) or ``"canopy"``.
    :param max_ancestors: Hourglass ancestor generations, ``None`` for all.
    :param max_descendants: Hourglass descendant generations, ``None`` for all.
    :param width: Window width in pixels.
    :param height: Window height in pixels.
    :raises ValueError: If xref has no relatives to grow toward.
    """
    from PyQt5.QtWidgets import QApplication  # noqa: PLC0415 - viz3d-only import

    with GenealogyKG(repo_root=repo, db_path=db) as kg:
        app = QApplication.instance() or QApplication([])
        window = FamilyTreeWindow(
            kg.store,
            xref,
            color_by=color_by,
            preset=preset,
            organic=organic,
            shape=shape,
            max_ancestors=max_ancestors,
            max_descendants=max_descendants,
        )
        window.resize(width, height)
        window.show()
        app.exec_()


__all__ = ["FamilyTreeWindow", "launch"]
