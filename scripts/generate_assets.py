"""Generate LUNA application assets (logo PNGs, ICO, splash, tray).

Design: a premium lunar mark — a crescent formed by two overlapping discs,
an orbital ring with nodes, and a spark — in moonlit blue/lavender. This is
an original mark; no moon emoji, no cloned logo.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "luna" / "assets"

BG = (11, 15, 23, 255)
DARK = (7, 10, 18, 255)
BLUE = (143, 184, 255, 255)
LAVENDER = (211, 174, 242, 255)
WHITE = (240, 245, 255, 255)
RING = (120, 150, 210, 255)

SIZE = 1024


def lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


def draw_logo(draw: ImageDraw.ImageDraw, scale: float = 1.0, monochrome: bool = False) -> None:
    """Draw the mark centered in a SIZE x SIZE canvas."""
    s = scale
    cx, cy, r = 512 * s, 512 * s, 300 * s

    # orbital ring (ellipse)
    ring_box = (cx - 380 * s, cy - 300 * s, cx + 380 * s, cy + 300 * s)
    ring_width = int(22 * s)
    draw.ellipse(ring_box, outline=RING, width=ring_width)

    # ring nodes (small circles at 3 positions)
    for angle_deg in (30, 150, 270):
        angle = math.radians(angle_deg)
        nx = cx + 380 * s * math.cos(angle)
        ny = cy - 300 * s * math.sin(angle)
        node_r = int(26 * s)
        draw.ellipse(
            (nx - node_r, ny - node_r, nx + node_r, ny + node_r),
            fill=LAVENDER,
        )

    # crescent: big disc minus offset disc
    # main moon disc
    main_box = (cx - r, cy - r, cx + r, cy + r)
    # darker background disc (behind) for depth
    draw.ellipse(main_box, fill=(34, 48, 76, 255))
    # crescent body
    draw.ellipse(main_box, fill=BLUE)
    # cut-out disc shifted up-right to form crescent
    shift = 150 * s
    cut_box = (
        cx - r + shift,
        cy - r - shift,
        cx + r + shift,
        cy + r - shift,
    )
    draw.ellipse(cut_box, fill=(0, 0, 0, 0))
    # overlay ring's inner region to carve crescent against ring: use background
    draw.ellipse(cut_box, fill=BG if not monochrome else (0, 0, 0, 255))

    # crescent glow highlight (thin arc along inner edge)
    glow_r = r - 40 * s
    draw.arc(
        (cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r),
        start=160,
        end=300,
        fill=lerp(BLUE, WHITE, 0.45),
        width=int(10 * s),
    )

    # spark (4-point star) at upper right, outside the ring
    sx, sy = cx + 330 * s, cy - 300 * s
    arm = 54 * s
    draw.line((sx - arm, sy, sx + arm, sy), fill=WHITE, width=int(12 * s))
    draw.line((sx, sy - arm, sx, sy + arm), fill=WHITE, width=int(12 * s))
    draw.ellipse((sx - 16 * s, sy - 16 * s, sx + 16 * s, sy + 16 * s), fill=WHITE)

    # subtle inner shading on crescent bottom
    shade_r = r - 120 * s
    draw.arc(
        (cx - shade_r, cy - shade_r, cx + shade_r, cy + shade_r),
        start=30,
        end=140,
        fill=lerp(BLUE, DARK, 0.35),
        width=int(18 * s),
    )


def render(size: int, monochrome: bool = False, bg: bool = True) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), BG if bg else (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_logo(draw, monochrome=monochrome)
    img = img.resize((size, size), Image.LANCZOS)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 48, 64, 128, 256, 512):
        img = render(size)
        img.save(OUT / f"luna_{size}.png")
        print(f"wrote luna_{size}.png")

    render(64, monochrome=True, bg=False).save(OUT / "luna_tray.png")
    print("wrote luna_tray.png")

    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon = render(256)
    icon.save(OUT / "luna.ico", sizes=ico_sizes)
    print("wrote luna.ico")

    # splash: dark canvas with mark + wordmark (word rendered as vector rects handled in QSS; PNG splash keeps mark only)
    splash = Image.new("RGBA", (1200, 640), BG)
    d = ImageDraw.Draw(splash)
    d.rectangle((0, 0, 1200, 640), fill=BG)
    mark = render(360)
    splash.alpha_composite(mark, (120, 140))
    d.text((560, 280), "LUNA", fill=WHITE, font_size=96)
    d.text((564, 390), "LOCAL-FIRST INTELLIGENT DESKTOP", fill=RING, font_size=28)
    splash.save(OUT / "splash.png")
    print("wrote splash.png")


if __name__ == "__main__":
    main()
