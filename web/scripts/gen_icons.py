"""Generate NovaMind AI app icons as real PNGs.

Creates:
  public/icons/icon-192x192.png
  public/icons/icon-512x512.png

Each is a rounded-square gradient background with a simple brain/spark glyph
and a few decorative stars, matching the brand identity (indigo → purple → pink).
"""
from PIL import Image, ImageDraw
import math, os, sys

OUT = os.path.dirname(os.path.abspath(__file__)) + '/../public/icons'
os.makedirs(OUT, exist_ok=True)

def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

GRAD = [
    (79, 70, 229),    # indigo-600
    (147, 51, 234),   # purple-600
    (236, 72, 153),   # pink-500
]

def gradient_bg(size, radius):
    img = Image.new('RGB', (size, size), (255, 255, 255))
    px = img.load()
    diag = math.sqrt(2) * size
    for y in range(size):
        for x in range(size):
            # Project onto the gradient diagonal so colors blend smoothly.
            t = (x + y) / (2 * size)
            # Map to one of the three stops.
            if t < 0.5:
                c = lerp_color(GRAD[0], GRAD[1], t * 2)
            else:
                c = lerp_color(GRAD[1], GRAD[2], (t - 0.5) * 2)
            px[x, y] = c
    # Apply rounded-square mask.
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out

def brain_glyph(draw, cx, cy, w, color):
    """Stylised brain: two C-curves meeting at the centerline."""
    s = w
    # Outer outline thickness
    line_w = max(2, s // 16)
    # Left lobe (open-right C)
    draw.arc((cx - s // 2, cy - s // 2, cx, cy + s // 2),
             start=200, end=160, fill=color, width=line_w)
    # Right lobe (open-left C)
    draw.arc((cx, cy - s // 2, cx + s // 2, cy + s // 2),
             start=20, end=-20, fill=color, width=line_w)
    # Horizontal connecting lines
    for dy in (-s // 4, 0, s // 4):
        draw.line((cx - s // 2 + line_w, cy + dy, cx + s // 2 - line_w, cy + dy),
                  fill=color, width=line_w)

def stars(draw, size, color):
    for (x, y, r, op) in [
        (0.78 * size, 0.18 * size, size // 64, 1.0),
        (0.16 * size, 0.74 * size, size // 96, 0.9),
        (0.86 * size, 0.80 * size, size // 48, 1.0),
        (0.10 * size, 0.30 * size, size // 110, 0.7),
    ]:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color + (int(255 * op),))

def make(size):
    radius = int(size * 0.22)
    img = gradient_bg(size, radius)
    draw = ImageDraw.Draw(img)
    # Brain glyph centered, ~55% of icon size
    g = int(size * 0.55)
    brain_glyph(draw, size // 2, size // 2, g, (255, 255, 255))
    stars(draw, size, (255, 255, 255))
    out = os.path.normpath(os.path.join(OUT, f'icon-{size}x{size}.png'))
    img.save(out, 'PNG', optimize=True)
    print(f'wrote {out}')

if __name__ == '__main__':
    for sz in (192, 512):
        make(sz)
