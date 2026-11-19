#!/usr/bin/env python3
"""Draw the GenealogyKG logo in Art Techno and write every size the repo uses.

The mark is the hourglass chart: the root person is the die, ancestors widen
above in copper, descendants widen below in gold, and a faint hourglass
outline holds them. The palette, drawing helpers and outlined lettering come
from the Art Techno brand build, so the SVGs render the same everywhere.

Usage::

    python scripts/build_logo.py

Needs ``fonttools`` and Pillow, Google Chrome for the PNG renders, and a clone
of https://github.com/Flux-Frontiers/art_techno beside this repo. Set ``CHROME``
to the browser binary if it is not at the default macOS path.

Writes:

- ``assets/genealogykg_logo.svg`` and ``assets/genealogykg_logo.png``: the
  square mark (1024 px PNG)
- ``assets/genealogykg_icon.svg``: the mark reduced for 64 px and below
- ``assets/genealogykg_banner.svg`` and ``assets/genealogykg_banner.png``
- ``docs/assets/logo.png`` and ``docs/assets/favicon.png``: the docs site's
  header logo and favicon, from the icon
"""

import importlib.util
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
AT_BUILD = ROOT.parent / "art_techno" / "docs" / "brand" / "build.py"

_spec = importlib.util.spec_from_file_location("at_build", AT_BUILD)
at = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(at)

f, line, pad, via, diamond, clipped_rect = (
    at.f,
    at.line,
    at.pad,
    at.via,
    at.diamond,
    at.clipped_rect,
)
OBSIDIAN, PANEL, COPPER, GOLD, GREEN, MINT, SILK = (
    at.OBSIDIAN,
    at.PANEL,
    at.COPPER,
    at.GOLD,
    at.GREEN,
    at.MINT,
    at.SILK,
)

NAME = "GENEALOGYKG"
PART = "LINEAGE AS A GRAPH"


def rect(
    x: float, y: float, w: float, h: float, fill: str, stroke: str = "", width: float = 0
) -> str:
    s = f' stroke="{stroke}" stroke-width="{f(width)}"' if stroke else ""
    return f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" fill="{fill}"{s}/>'


def package(x: float, y: float, r: float, c: float, width: float) -> str:
    """A chip package: a dark square with 45-degree corners in a gold line.

    :param x: Center x.
    :param y: Center y.
    :param r: Half the side length.
    :param c: Corner cut.
    :param width: Stroke width.
    """
    return (
        f'<path d="{clipped_rect(x - r, y - r, 2 * r, 2 * r, c)}" fill="{PANEL}" '
        f'stroke="{GOLD}" stroke-width="{f(width)}"/>'
    )


def die(x: float, y: float, s: float, core: str) -> str:
    """A square green die in a gold line, centered on ``x, y``.

    :param x: Center x.
    :param y: Center y.
    :param s: Side length.
    :param core: Color of the square at its center.
    """
    return rect(x - s / 2, y - s / 2, s, s, GREEN, GOLD, s / 9) + rect(
        x - s / 6, y - s / 6, s / 3, s / 3, core
    )


def node(x: float, y: float, r: float) -> str:
    """A descendant: a gold pad with a green core."""
    return pad(x, y, r, GOLD) + pad(x, y, r * 0.44, GREEN)


def elbow(x0: float, y0: float, x1: float, y1: float, ymid: float, color: str, width: float) -> str:
    """A square-cornered parent-child link through the horizontal ``ymid``."""
    return line([(x0, y0), (x0, ymid), (x1, ymid), (x1, y1)], color, width)


def hourglass() -> str:
    """Ancestors widen above the root person, descendants below, on a 512 field."""
    cx, cy = 256, 212
    out = []
    # The hourglass outline: two faint gold hairlines ending in diamonds.
    for pts in (((120, 70), (232, 212), (120, 354)), ((392, 70), (280, 212), (392, 354))):
        d = "M" + "L".join(f"{f(x)} {f(y)}" for x, y in pts)
        out.append(
            f'<path d="{d}" fill="none" stroke="{GOLD}" stroke-width="2" stroke-opacity=".5"/>'
        )
        out.append(diamond(*pts[0], 5, GOLD) + diamond(*pts[2], 5, GOLD))
    # Ancestors (sgn -1, copper vias) and descendants (sgn 1, gold nodes).
    for sgn, color in ((-1, COPPER), (1, GOLD)):
        g1 = [(216, cy + sgn * 64), (296, cy + sgn * 64)]
        g2 = [(x, cy + sgn * 120) for x in (176, 236, 276, 336)]
        for x, y in g1:
            out.append(elbow(cx, cy + sgn * 24, x, y - sgn * 10, cy + sgn * 40, color, 5))
        for (px, py), kids in zip(g1, (g2[:2], g2[2:]), strict=True):
            for x, y in kids:
                out.append(elbow(px, py + sgn * 10, x, y - sgn * 9, py + sgn * 30, color, 4))
        for x, y in g1 + g2:
            out.append(via(x, y, 8, COPPER) if sgn < 0 else node(x, y, 11))
    out.append(die(cx, cy, 48, SILK))
    return "".join(out)


def hourglass_small() -> str:
    """The hourglass reduced for 64 px and below: two ancestors, the die, two descendants."""
    out = []
    for sgn, color in ((-1, COPPER), (1, GOLD)):
        for x in (20, 44):
            pts = [(32, 32 + sgn * 7), (32, 32 + sgn * 12), (x, 32 + sgn * 12), (x, 32 + sgn * 20)]
            out.append(line(pts, color, 2.8))
            out.append(pad(x, 32 + sgn * 21, 3.6, color))
    out.append(die(32, 32, 13, GOLD))
    return "".join(out)


def frame(w: float, h: float, inset: float, c: float, heavy: float) -> str:
    """Double frame with 45-degree corners and a green diamond at each corner.

    :param w: Canvas width.
    :param h: Canvas height.
    :param inset: Distance of the heavy line from the canvas edge.
    :param c: Corner cut of the heavy line.
    :param heavy: Stroke width of the heavy line.
    """
    out = [
        f'<path d="{clipped_rect(inset, inset, w - 2 * inset, h - 2 * inset, c)}" fill="none" stroke="{GOLD}" stroke-width="{f(heavy)}"/>',
        f'<path d="{clipped_rect(inset * 1.9, inset * 1.9, w - 3.8 * inset, h - 3.8 * inset, c * 0.75)}" fill="none" stroke="{GOLD}" stroke-width="{f(heavy * 0.4)}" stroke-opacity=".6"/>',
    ]
    d = inset * 1.45 + c * 0.4375
    for cx, cy in ((d, d), (w - d, d), (d, h - d), (w - d, h - d)):
        out.append(diamond(cx, cy, inset * 0.5, GREEN))
    return "".join(out)


def svg(w: int, h: int, title: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f"<title>{title}</title>"
        f'<rect width="{w}" height="{h}" fill="{OBSIDIAN}"/>{body}</svg>\n'
    )


def mark(display, mono) -> str:
    """512 square mark: the hourglass, the name and the part line beneath."""
    body = frame(512, 512, 10, 26, 5) + hourglass()
    body += display.path(NAME, 256, 430, 40, 0.2, "middle", GOLD)
    body += mono.path(PART, 256, 462, 13.5, 0.3, "middle", MINT)
    return svg(512, 512, "GenealogyKG mark, Art Techno", body)


def icon() -> str:
    """64 icon: the reduced hourglass in one heavy frame, no lettering."""
    body = f'<path d="{clipped_rect(2.5, 2.5, 59, 59, 7.5)}" fill="none" stroke="{GOLD}" stroke-width="3"/>'
    return svg(64, 64, "GenealogyKG icon, Art Techno", body + hourglass_small())


def banner(display, mono) -> str:
    """1280 x 320 banner: the hourglass left, the name and part line right.

    The name is set as large as the room right of the hourglass allows, and the
    pair is centered on the banner's height.
    """
    s = 0.78
    body = frame(1280, 320, 10, 18, 3)
    body += f'<g transform="translate({f(230 - 256 * s)} {f(160 - 212 * s)}) scale({s})">{hourglass()}</g>'
    cx, room, gap = 820, 760, 34
    size = min(120, 120 * room / display.width(NAME, 120, 0.2))
    part = min(26, 26 * room / mono.width(PART, 26, 0.3))
    cap = display.cap * size / display.upm
    pcap = mono.cap * part / mono.upm
    base = (320 - (cap + gap + pcap)) / 2 + cap
    body += display.path(NAME, cx, base, size, 0.2, "middle", GOLD)
    body += mono.path(PART, cx, base + gap + pcap, part, 0.3, "middle", MINT)
    return svg(1280, 320, "GenealogyKG banner, Art Techno", body)


def render(src: Path, out: Path, w: int, h: int) -> None:
    """Render the SVG ``src`` to ``out`` at ``w`` x ``h`` px with headless Chrome.

    :param src: SVG file; its ``width`` attribute sets the CSS width.
    :param out: PNG to write.
    :param w: Output width in px.
    :param h: Output height in px.
    """
    svg_w = int(src.read_text().split('width="', 1)[1].split('"', 1)[0])
    subprocess.run(
        [
            at.CHROME,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size={svg_w},{svg_w * h // w}",
            f"--force-device-scale-factor={w / svg_w}",
            f"--screenshot={out}",
            src.as_uri(),
        ],
        check=True,
        capture_output=True,
    )


def resized(master: Path, dest: Path, px: int) -> None:
    Image.open(master).convert("RGB").resize((px, px), Image.LANCZOS).save(dest, optimize=True)


def main() -> None:
    at.fetch_fonts()
    display = at.Face(at.CACHE / "JosefinSans.ttf", weight=600)
    mono = at.Face(at.CACHE / "IBMPlexMono-Medium.ttf")

    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    mark_svg = assets / "genealogykg_logo.svg"
    icon_svg = assets / "genealogykg_icon.svg"
    banner_svg = assets / "genealogykg_banner.svg"
    mark_svg.write_text(mark(display, mono))
    icon_svg.write_text(icon())
    banner_svg.write_text(banner(display, mono))

    mark_png = mark_svg.with_suffix(".png")
    render(mark_svg, mark_png, 1024, 1024)
    render(banner_svg, banner_svg.with_suffix(".png"), 2560, 640)
    docs = ROOT / "docs" / "assets"
    docs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        icon_png = Path(tmp) / "icon.png"
        render(icon_svg, icon_png, 1024, 1024)
        resized(icon_png, docs / "logo.png", 256)
        resized(icon_png, docs / "favicon.png", 32)


if __name__ == "__main__":
    main()
