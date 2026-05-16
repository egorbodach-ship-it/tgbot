"""
Step 2 (v7): draw slot cells for each menu PNG.

For every menu YAML in DM_DIR, find the texture in use (via title → glyph map),
compute total shift from Tamil shift glyphs, and stamp visible cells for every
slot the YAML actually uses.

Cell math (relative to glyph origin):
    mc_x  = -1 - shift_px + col * 18          # slot-left in mc-pixels
    mc_y  = BASE_Y + row * 18                 # slot-top in mc-pixels
    png_x = round(mc_x / scale)
    png_y = round(mc_y / scale)
    cell  = round(16 / scale)
where scale = height_px / 256 (height_px from default.json per glyph).

BASE_Y is configurable via env var V7_BASE_Y (default 36 — see TASK_FOR_NEXT_SESSION).
"""
import os, re, json, sys
import numpy as np
from PIL import Image

DM_DIR  = "tgbot/work_v7/all_dm_menus"
DEFJSON = "tgbot/work_v7/default.json"
SRC_DIR = sys.argv[1] if len(sys.argv) > 1 else "tgbot/work_v7/textures_step1_no_banner"
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "tgbot/work_v7/textures_step2_with_cells"
DIAG    = "--diag" in sys.argv

BASE_Y = int(os.environ.get("V7_BASE_Y", "36"))
print(f"  BASE_Y={BASE_Y}, DIAG={DIAG}")

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

# texture -> (shift_px, set_of_slots)
menu_yamls = {}
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
    if not tex:
        continue
    slots = sorted(set(int(m.group(1)) for m in re.finditer(r"^\s*slot:\s*(\d+)", content, re.MULTILINE)))
    if tex in menu_yamls:
        oldshift, oldslots = menu_yamls[tex]
        menu_yamls[tex] = (oldshift, sorted(set(oldslots) | set(slots)))
    else:
        menu_yamls[tex] = (shift, slots)


def draw_cell(arr, slot, scale, shift_px,
              fill_strength=0.55, border_strength=0.30):
    row, col = slot // 9, slot % 9
    mc_x = -1 - shift_px + col * 18
    mc_y = BASE_Y + row * 18
    x0 = int(round(mc_x / scale))
    y0 = int(round(mc_y / scale))
    cs = int(round(16 / scale))
    x1, y1 = x0 + cs, y0 + cs
    h, w = arr.shape[:2]
    if x1 > w or y1 > h or x0 < 0 or y0 < 0:
        return
    ix0, iy0 = x0 + 1, y0 + 1
    ix1, iy1 = x1 - 1, y1 - 1
    cell = arr[iy0:iy1, ix0:ix1, :3].astype(float)
    if cell.size == 0:
        return
    avg = cell.mean(axis=(0, 1))
    fill = (avg * fill_strength).clip(0, 255).astype(np.uint8)
    edge = (avg * border_strength).clip(0, 255).astype(np.uint8)
    arr[iy0:iy1, ix0:ix1, :3] = fill
    arr[iy0,    ix0:ix1, :3] = edge
    arr[iy1-1,  ix0:ix1, :3] = edge
    arr[iy0:iy1, ix0,    :3] = edge
    arr[iy0:iy1, ix1-1,  :3] = edge


def draw_diag_cross(arr, slot, scale, shift_px):
    """Diagnostic: draw a bright magenta cross at the center of each slot."""
    row, col = slot // 9, slot % 9
    mc_xc = -1 - shift_px + col * 18 + 8
    mc_yc = BASE_Y + row * 18 + 8
    cx = int(round(mc_xc / scale))
    cy = int(round(mc_yc / scale))
    h, w = arr.shape[:2]
    color = (255, 0, 255, 255)
    for d in range(-3, 4):
        if 0 <= cy < h and 0 <= cx + d < w:
            arr[cy, cx + d] = color
        if 0 <= cy + d < h and 0 <= cx < w:
            arr[cy + d, cx] = color


count = 0
for tex_fn in sorted(os.listdir(SRC_DIR)):
    if not tex_fn.endswith(".png"):
        continue
    tex_name = tex_fn[:-4]
    img = Image.open(os.path.join(SRC_DIR, tex_fn)).convert("RGBA")
    arr = np.array(img)
    if tex_name in menu_yamls:
        shift_px, slots = menu_yamls[tex_name]
        h_px = None
        for ch, tn in char_to_tex.items():
            if tn == tex_name:
                h_px = char_to_h[ch]
                break
        if h_px is None:
            h_px = 268
        scale = h_px / 256.0
        for s in slots:
            draw_cell(arr, s, scale, shift_px)
            if DIAG:
                draw_diag_cross(arr, s, scale, shift_px)
        print(f"  {tex_fn}: h={h_px} shift={shift_px} #slots={len(slots)}")
    Image.fromarray(arr).save(os.path.join(OUT_DIR, tex_fn))
    count += 1

print(f"\nProcessed {count} textures into {OUT_DIR}")
