#!/usr/bin/env python3
"""Compose a single overview PNG with all 28 Solomon menu glyphs in a grid.

This makes it cheap to eyeball every menu at once before deploying.
"""
import os
import sys
from PIL import Image, ImageDraw

_THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS)
from gen_solomon import MENUS  # noqa


def main():
    glyph_dir = os.path.join(_THIS, "..", "textures_solomon")
    out_path = os.path.join(_THIS, "..", "..", "menu_preview", "solomon_overview.png")

    cols = 4
    cell_w, cell_h = 256, 256
    label_h = 24
    rows = (len(MENUS) + cols - 1) // cols

    grid = Image.new("RGBA", (cols * cell_w, rows * (cell_h + label_h)), (24, 24, 28, 255))
    d = ImageDraw.Draw(grid)

    for i, (name, label, _) in enumerate(MENUS):
        r, c = divmod(i, cols)
        x = c * cell_w
        y = r * (cell_h + label_h)
        glyph = Image.open(os.path.join(glyph_dir, f"{name}.png")).convert("RGBA")
        grid.alpha_composite(glyph, (x, y))
        d.text((x + 4, y + cell_h + 4), f"{name} - {label}",
               fill=(220, 200, 160, 255))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    grid.save(out_path)
    print(f"wrote {out_path} ({grid.size[0]}x{grid.size[1]})")


if __name__ == "__main__":
    main()
