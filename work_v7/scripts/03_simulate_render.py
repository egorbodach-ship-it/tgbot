"""
Step 3 (v7): simulate the in-game chest title rendering for one menu PNG.

Outputs a side-by-side PNG showing:
  - The chest GUI (drawn flat-grey at correct scale).
  - The menu PNG glyph rendered at MC font scale with simulated font shadow
    (color * 0.25, offset (+1,+1)) underneath.
  - Red squares overlaying the REAL slot rectangles (where DM puts items).
  - For comparison, draw the cell rectangles we baked into the PNG (yellow outline).

Usage:
  python3 03_simulate_render.py menu       # output simulation_menu.png
  python3 03_simulate_render.py shop       # etc.

Coordinate model (mc-pixels):
  Chest top-left == (0, 0). Chest size = (176, 222) for 6-row chest.
  Title baseline: chest_y + 13   ⇒  baseline_mc_y = 13
  Cursor start_x: chest_x + 8    ⇒  start_mc_x = 8
  Glyph height_mc:  height_px (from default.json)
  Glyph render width_mc:  effective_width_in_png_px * height_mc/256
       (effective_width_in_png_px is read from PNG: the rightmost non-transparent column + 1)
  Glyph top: baseline_mc_y - ascent (ascent = 32 in our cfg)
  Slot top-left in mc:  (7 + col*18, 17 + row*18)  ; cell visible part = 16x16
"""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw

DEFJSON = "tgbot/work_v7/default.json"
TEX_DIR = "tgbot/work_v7/textures_step2_with_cells"
DM_DIR  = "tgbot/work_v7/all_dm_menus"
OUT_DIR = "tgbot/work_v7/simulations"
os.makedirs(OUT_DIR, exist_ok=True)

with open(DEFJSON) as f:
    d = json.load(f)
char_to_tex, char_to_h = {}, {}
for p in d["providers"]:
    if p.get("type") == "bitmap" and p.get("height", 0) > 0:
        if "font/menus" in p.get("file", ""):
            ch = p["chars"][0]
            char_to_tex[ch] = p["file"].replace("font/menus/", "").replace(".png", "")
            char_to_h[ch]   = p["height"]

SHIFT_GLYPHS = {
    "\u0BE7": -1, "\u0BE8": -2, "\u0BE9": -4,
    "\u0BEA": -8, "\u0BEB": -16, "\u0BEC": -32,
    "\u0BED": -64, "\u0BEE": -128, "\u0BEF": -256,
}


def find_yaml_for_tex(tex_name):
    """Find a yaml that uses this tex_name; return (shift_px, slots, title)."""
    import re
    for fn in sorted(os.listdir(DM_DIR)):
        if not fn.endswith(".yml"):
            continue
        with open(os.path.join(DM_DIR, fn)) as f:
            content = f.read()
        tm = re.search(r'^menu_title:\s*"?(.+?)"?\s*$', content, re.MULTILINE)
        if not tm:
            continue
        title = tm.group(1)
        tex, shift = None, 0
        for ch in title:
            if ch in char_to_tex:
                tex = char_to_tex[ch]
            elif ch in SHIFT_GLYPHS:
                shift += SHIFT_GLYPHS[ch]
        if tex == tex_name:
            slots = sorted(set(int(m.group(1)) for m in re.finditer(r"^\s*slot:\s*(\d+)", content, re.MULTILINE)))
            return shift, slots, title
    return None


def simulate(tex_name, scale_factor=8):
    """Render a chest 176x222 mc-px scaled by scale_factor."""
    info = find_yaml_for_tex(tex_name)
    if info is None:
        print(f"  no yaml found for {tex_name}")
        return
    shift_px, slots, title = info
    img = Image.open(os.path.join(TEX_DIR, tex_name + ".png")).convert("RGBA")
    arr = np.array(img)
    h_px = next((char_to_h[ch] for ch, tn in char_to_tex.items() if tn == tex_name), 268)
    scale = h_px / 256.0  # mc-px per png-px

    # Find effective width of glyph in png-pixels (rightmost non-transparent column + 1)
    alpha = arr[..., 3]
    cols_with_pixels = np.where(alpha.any(axis=0))[0]
    if cols_with_pixels.size == 0:
        return
    max_x = int(cols_with_pixels.max()) + 1
    rendered_mc_w = int(round(max_x * scale))
    rendered_mc_h = h_px

    # Resample to "mc-pixel" grid: PIL nearest at integer-sized destination.
    glyph_mc = img.resize((rendered_mc_w, rendered_mc_h), Image.NEAREST)
    glyph_mc_np = np.array(glyph_mc)

    # Chest dims in mc-px
    CHEST_W = 176
    rows_in_menu = (max(slots) // 9 + 1) if slots else 6
    rows_total = max(rows_in_menu, 6)
    CHEST_H = 17 + 18 * rows_total + 14  # chest title area + slot rows + bottom margin

    canvas = np.full((CHEST_H, CHEST_W, 4), (110, 110, 110, 255), dtype=np.uint8)

    # Render shadow + glyph
    glyph_top_mc = 13 - 32  # baseline (13) - ascent (32) = -19
    glyph_left_mc = 8 + shift_px

    def paste_with_alpha(dst, src, x, y, alpha_mul=1.0, color_mul=1.0):
        sh, sw = src.shape[:2]
        dh, dw = dst.shape[:2]
        # crop
        sx0 = max(0, -x); sy0 = max(0, -y)
        sx1 = min(sw, dw - x); sy1 = min(sh, dh - y)
        if sx0 >= sx1 or sy0 >= sy1:
            return
        s = src[sy0:sy1, sx0:sx1].astype(float)
        a = (s[..., 3:4] / 255.0) * alpha_mul
        rgb = s[..., :3] * color_mul
        d = dst[y+sy0:y+sy1, x+sx0:x+sx1].astype(float)
        d[..., :3] = d[..., :3] * (1 - a) + rgb * a
        d[..., 3] = 255
        dst[y+sy0:y+sy1, x+sx0:x+sx1] = d.astype(np.uint8)

    # Shadow first (offset +1,+1, color * 0.25)
    paste_with_alpha(canvas, glyph_mc_np, glyph_left_mc + 1, glyph_top_mc + 1,
                     alpha_mul=1.0, color_mul=0.25)
    # Glyph on top
    paste_with_alpha(canvas, glyph_mc_np, glyph_left_mc, glyph_top_mc)

    # Scale up
    big = Image.fromarray(canvas).resize((CHEST_W*scale_factor, CHEST_H*scale_factor), Image.NEAREST)
    draw = ImageDraw.Draw(big)

    # Draw real slot rectangles in red (16x16 mc, top-left at (7+col*18, 17+row*18))
    for s in slots:
        row, col = s // 9, s % 9
        sx = (7 + col*18) * scale_factor
        sy = (17 + row*18) * scale_factor
        ex = sx + 16 * scale_factor
        ey = sy + 16 * scale_factor
        draw.rectangle([sx, sy, ex-1, ey-1], outline=(255, 0, 0, 255), width=2)
        # center cross
        cx = sx + 8 * scale_factor; cy = sy + 8 * scale_factor
        draw.line([cx-3*scale_factor, cy, cx+3*scale_factor, cy], fill=(255,255,0), width=2)
        draw.line([cx, cy-3*scale_factor, cx, cy+3*scale_factor], fill=(255,255,0), width=2)

    out_path = os.path.join(OUT_DIR, f"sim_{tex_name}.png")
    big.save(out_path)
    print(f"  -> {out_path}  shift={shift_px} h={h_px} #slots={len(slots)}")


if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["menu", "shop"]
    for t in targets:
        simulate(t)
