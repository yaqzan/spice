"""Draw the app icon: three jars on a shelf.

Run this, not an image editor. The geometry lives here once and every output --
the vector favicon, the Android manifest icons, the iOS home-screen icon -- is
generated from the same numbers, so a tweak lands everywhere at once instead of
in whichever file someone remembers to open.

    py -3.11 tools/make_icons.py

Writes into frontend/public/, which Vite copies verbatim into the build.

Why three jars and not one: the app's whole promise is a picture of a SHELF with
the right jars lit up. One jar is a condiment; three on a plank is a rack. The
colours are lifted straight out of rack.py -- turmeric, paprika, oregano -- so
the icon is made of the same pigments as the thing it opens.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'frontend' / 'public'

# ── palette ──────────────────────────────────────────────────────────────────
# styles.css --bg, and the shelf plank from .rack-shelf.
BG = '#16130f'
PLANK = '#57452f'

# Real jars: turmeric, paprika, oregano. Gold / red / green survives being shrunk
# to 32 pixels in a browser tab, where three shades of warm brown would silt up
# into one smudge.
JARS = ('#d4a017', '#c14a20', '#7f8a45')


def shade(hex_colour: str, amount: float = 0.45) -> str:
    """Darken for the cap -- same trick, same factor, as SpiceRack.tsx."""
    value = hex_colour.lstrip('#')
    rgb = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return '#' + ''.join(f'{round(c * (1 - amount)):02x}' for c in rgb)


# ── geometry ─────────────────────────────────────────────────────────────────
# Everything below is expressed inside a 1000x1000 art box. The renderers place
# that box inside whatever padding a given output needs.
#
# A row of three jars is a landscape shape inside a square tile, so the numbers
# are chosen to centre the group on y=500 exactly: cap top at 214, plank bottom
# at 786. Getting this wrong is very visible -- an earlier pass left a dead band
# across the top third and the icon read as sliding off the bottom of the tile.
ART = 1000

JAR_W = 252
JAR_GAP = 52
CAP_TOP = 214
CAP_H = 120
BODY_TOP = 274         # the cap overlaps the body's shoulder, as in the app
SHELF_Y = 734          # the top of the plank; jars stand on it
PLANK_H = 52
PLANK_INSET = 56       # how far the plank overhangs the outermost jars
GLARE_INSET = 36
GLARE_W = 44

_row_w = len(JARS) * JAR_W + (len(JARS) - 1) * JAR_GAP
_row_x = (ART - _row_w) / 2


def jar_boxes() -> list[tuple[float, str]]:
    return [(_row_x + i * (JAR_W + JAR_GAP), colour)
            for i, colour in enumerate(JARS)]


def plank_box() -> tuple[float, float, float, float]:
    left = _row_x - PLANK_INSET
    return (left, SHELF_Y, ART - left, SHELF_Y + PLANK_H)


# ── raster ───────────────────────────────────────────────────────────────────

SUPERSAMPLE = 4        # draw big, shrink down; Pillow has no antialiased shapes


def render_png(size: int, pad: float) -> Image.Image:
    """One square icon. `pad` is the fraction of the edge left as margin.

    A maskable icon is cropped to a circle by the launcher, so it needs a fatter
    margin than one that is displayed as drawn -- hence the parameter rather than
    a constant.
    """
    scale = size * SUPERSAMPLE
    image = Image.new('RGB', (scale, scale), BG)
    draw = ImageDraw.Draw(image, 'RGBA')

    span = scale * (1 - pad * 2)
    offset = scale * pad
    unit = span / ART

    def place(x0, y0, x1, y1):
        return [offset + x0 * unit, offset + y0 * unit,
                offset + x1 * unit, offset + y1 * unit]

    # The plank first, so the jars sit on top of it rather than float above it.
    draw.rounded_rectangle(place(*plank_box()), radius=PLANK_H * unit * 0.45,
                           fill=PLANK)

    for x, colour in jar_boxes():
        draw.rounded_rectangle(place(x, BODY_TOP, x + JAR_W, SHELF_Y + 2),
                               radius=46 * unit, fill=colour)
        draw.rounded_rectangle(place(x, CAP_TOP, x + JAR_W, CAP_TOP + CAP_H),
                               radius=28 * unit, fill=shade(colour))
        draw.rounded_rectangle(
            place(x + GLARE_INSET, BODY_TOP + 74,
                  x + GLARE_INSET + GLARE_W, SHELF_Y - 92),
            radius=GLARE_W * unit / 2, fill=(255, 255, 255, 40))

    return image.resize((size, size), Image.LANCZOS)


# ── vector ───────────────────────────────────────────────────────────────────

def render_svg(pad: float = 0.08) -> str:
    """The same drawing as XML, for the browser tab.

    Kept in step with render_png by construction: both read the constants above,
    so neither can quietly drift from the other.
    """
    span = ART * (1 - pad * 2)
    offset = ART * pad
    k = span / ART

    def rect(x0, y0, x1, y1, r, fill, opacity=None):
        alpha = f' opacity="{opacity}"' if opacity is not None else ''
        return (f'  <rect x="{offset + x0 * k:.1f}" y="{offset + y0 * k:.1f}" '
                f'width="{(x1 - x0) * k:.1f}" height="{(y1 - y0) * k:.1f}" '
                f'rx="{r * k:.1f}" fill="{fill}"{alpha}/>')

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ART} {ART}">',
        '  <!-- Generated by tools/make_icons.py. Edit the geometry there. -->',
        f'  <rect width="{ART}" height="{ART}" rx="0" fill="{BG}"/>',
        rect(*plank_box(), PLANK_H * 0.45, PLANK),
    ]
    for x, colour in jar_boxes():
        parts += [
            rect(x, BODY_TOP, x + JAR_W, SHELF_Y + 2, 46, colour),
            rect(x, CAP_TOP, x + JAR_W, CAP_TOP + CAP_H, 28, shade(colour)),
            rect(x + GLARE_INSET, BODY_TOP + 74, x + GLARE_INSET + GLARE_W,
                 SHELF_Y - 92, GLARE_W / 2, '#ffffff', 0.16),
        ]
    parts.append('</svg>')
    return '\n'.join(parts) + '\n'


# ── .ico ─────────────────────────────────────────────────────────────────────
# Written by hand rather than through Pillow's ICO writer, which re-encodes every
# frame at its own quality settings. These are flat-colour shapes; a byte-exact
# PNG per frame keeps the 16px one crisp.

def write_ico(path: Path, sizes: tuple[int, ...]) -> None:
    frames = []
    for size in sizes:
        image = render_png(size, pad=0.04)
        chunks = []
        raw = b''.join(b'\x00' + image.crop((0, y, size, y + 1)).tobytes()
                       for y in range(size))

        def chunk(tag: bytes, data: bytes) -> bytes:
            return (struct.pack('>I', len(data)) + tag + data
                    + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

        chunks.append(b'\x89PNG\r\n\x1a\n')
        chunks.append(chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2,
                                                 0, 0, 0)))
        chunks.append(chunk(b'IDAT', zlib.compress(raw, 9)))
        chunks.append(chunk(b'IEND', b''))
        frames.append((size, b''.join(chunks)))

    header = struct.pack('<HHH', 0, 1, len(frames))
    entries, blobs, offset = [], [], 6 + 16 * len(frames)
    for size, blob in frames:
        entries.append(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0,
                                   1, 32, len(blob), offset))
        blobs.append(blob)
        offset += len(blob)
    path.write_bytes(header + b''.join(entries) + b''.join(blobs))


# ── outputs ──────────────────────────────────────────────────────────────────
# 0.08 padding for icons shown as drawn -- the background is full-bleed dark, so
# there is no shape needing protection from iOS's corner rounding. 0.19 for the
# maskable one, which a launcher may crop to a circle inscribed in the middle 80%.
PNGS = (
    ('apple-touch-icon.png', 180, 0.08),   # iOS home screen; must be PNG
    ('icon-192.png', 192, 0.08),
    ('icon-512.png', 512, 0.08),
    ('icon-maskable-512.png', 512, 0.19),
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size, pad in PNGS:
        render_png(size, pad).save(OUT / name, optimize=True)
        print(f'wrote {name} ({size}px)')
    (OUT / 'icon.svg').write_text(render_svg(), encoding='utf-8')
    print('wrote icon.svg')
    write_ico(OUT / 'favicon.ico', (16, 32, 48))
    print('wrote favicon.ico (16/32/48)')


if __name__ == '__main__':
    main()
