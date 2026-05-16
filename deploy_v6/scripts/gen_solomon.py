#!/usr/bin/env python3
"""
gen_solomon.py — Solomon-themed menu glyph generator.

Produces 256×256 RGBA PNGs that, when rendered with Oraxen glyph parameters
(height=280 for `menu`, height=268 for everything else, ascent=32), tile
exactly over a Minecraft 1.16.5 chest GUI's slot area.

Style: stone background, gold ornate frame, Star-of-David corners, crown,
orange→red gradient nameplate, white 7×9 Cyrillic title with drop-shadow.

Usage:
    python3 gen_solomon.py --out ../textures_solomon
    python3 gen_solomon.py --preview ../../menu_preview --only menu donate

Layout assumptions (from TASK_FOR_NEXT_SESSION.md):
    - PNG canvas: 256 × 256 RGBA
    - Glyph render scale = height / 256
        - menu.png: height=280 → scale ≈ 1.094  (shift_px = -12)
        - others:  height=268 → scale ≈ 1.047  (shift_px = -8)
    - ascent = 32 → top of glyph at chest_y - 19 mc-px
    - Slot top-left in mc relative to top-of-glyph:
        rel_x = -1 - shift_px + col * 18
        rel_y = 36           + row * 18
        cell_mc = 16
"""

import argparse
import os
import sys
import math
import random

from PIL import Image, ImageDraw, ImageFilter

# Ensure the script can find the embedded font module regardless of cwd.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
from cyr_font_7x9 import render_text  # noqa: E402


# ---------------------------------------------------------------------------
# Menu manifest — name → (label, rows). Labels are upper-cased for the
# pixel font. Rows match what the live YAML expects (rounded up to multiple
# of 9 / 9). Source: HANDOFF_v5.md §3.4 cross-checked against live patched_menus.
# ---------------------------------------------------------------------------

# rows: chest rows visible (3, 5, or 6 — these are the only valid chest heights
#       supported by Minecraft 1.16.5 single-chest GUI; 4 is technically valid
#       (size 36) but not used here).
MENUS = [
    # (name,        label,           rows)
    ("menu",       "МЕНЮ",           6),
    ("donate",     "ПРИВИЛЕГИИ",     5),
    ("shop",       "МАГАЗИН",        6),
    ("events",     "СОБЫТИЯ",        5),
    ("help",       "ПОМОЩЬ",         5),
    ("portals",    "ПОРТАЛЫ",        5),
    ("rtp",        "ТЕЛЕПОРТ",       5),
    ("obmen",      "ОБМЕН",          3),
    ("arenda",     "АРЕНДА",         5),
    ("grab",       "ГРАБ",           5),
    ("media",      "МЕДИА",          5),
    ("freek",      "НАГРАДЫ",        6),
    ("panel",      "ПАНЕЛЬ",         5),
    ("egorchik",   "ЕГОРЧИК",        5),
    ("akriwer",    "АКРИВЕР",        5),
    ("arrow",      "СТРЕЛЫ",         5),
    ("egg",        "ЯЙЦА",           6),
    ("items",      "ПРЕДМЕТЫ",       6),
    ("livalka",    "ЛИВАЛКА",        5),
    ("potions",    "ЗЕЛЬЯ",          6),
    ("pred",       "ХИЩНИКИ",        5),
    ("pve",        "ПВЕ",            5),
    ("pveother",   "ПВЕ ДРУГИЕ",     5),
    ("resmenu",    "РЕСУРСЫ",        5),
    ("reseuro",    "РЕСУРСЫ ЕВРО",   5),
    ("resmoneta",  "РЕСУРСЫ МОНЕТА", 5),
    ("shari",      "СФЕРЫ",          6),
    ("spawners",   "СПАВНЕРЫ",       5),
]


# ---------------------------------------------------------------------------
# Rendering parameters
# ---------------------------------------------------------------------------

CANVAS = 256

# Per-name glyph render height (matches Oraxen menus_overlay.yml `height:`).
# Default is 268; only `menu` is tuned to 280 to keep the chest center centered.
def render_height_for(name):
    return 280 if name == "menu" else 268

def shift_px_for(name):
    # See math in TASK_FOR_NEXT_SESSION.md §"Чтобы меню по центру"
    return -12 if name == "menu" else -8


# ---------------------------------------------------------------------------
# Solomon palette (orange/red brand ↔ gothic gold/stone)
# ---------------------------------------------------------------------------

# Base stone
COL_STONE_DARK   = (38, 32, 28, 255)        # near-black warm
COL_STONE_MID    = (62, 52, 44, 255)
COL_STONE_LIGHT  = (88, 74, 62, 255)
COL_STONE_HL     = (112, 96, 80, 255)        # rare highlight pixel

# Gold frame
COL_GOLD_DEEP    = (107, 70, 18, 255)
COL_GOLD_MID     = (191, 138, 36, 255)
COL_GOLD_BRIGHT  = (255, 213, 92, 255)
COL_GOLD_HILITE  = (255, 240, 168, 255)

# Orange/red nameplate gradient
COL_PLATE_TOP    = (255, 160, 40, 255)
COL_PLATE_BOTTOM = (170, 25,  10, 255)
COL_PLATE_RIM_LT = (255, 215, 100, 255)
COL_PLATE_RIM_DK = (95, 12, 5, 255)

# Slot inset
COL_SLOT_BG      = (28, 22, 18, 255)
COL_SLOT_RIM_LT  = (78, 66, 54, 255)
COL_SLOT_RIM_DK  = (16, 12, 10, 255)

# Text
COL_TEXT         = (255, 248, 224, 255)
COL_TEXT_SHADOW  = (60,  10,   0, 255)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mc_to_png(mc_v, scale):
    """Convert a mc-pixel value to PNG-pixel (rounded)."""
    return int(round(mc_v / scale))


def chest_visible_box(rows, scale, shift_px):
    """
    Return (x0, y0, x1, y1) on the 256x256 PNG covering the visible
    chest top portion (slots area + 1-row margin around).

    visible area = full chest title strip + slots area, ~17+rows*18 mc-px tall.
    Width = 176 mc-px (centered on chest), expressed in PNG-px.
    """
    # Chest left edge in mc rel to glyph origin: chest_x - glyph_origin_x
    # glyph_origin_x = chest_x + 8 + shift_px  →  chest_left_rel = -8 - shift_px
    left_mc  = -8 - shift_px               # = 0 for menu, -? for others
    right_mc = left_mc + 176               # chest width = 176 mc-px
    top_mc   = 0                           # top of glyph
    bottom_mc = 17 + rows * 18 + 14        # +14 for gap before player inv

    return (
        max(0, mc_to_png(left_mc,  scale)),
        max(0, mc_to_png(top_mc,   scale)),
        min(CANVAS, mc_to_png(right_mc, scale)),
        min(CANVAS, mc_to_png(bottom_mc, scale)),
    )


def slot_rect_png(row, col, scale, shift_px):
    """Return (x0, y0, x1, y1) in PNG-px for one chest slot's visible square."""
    rel_x_mc = -1 - shift_px + col * 18
    rel_y_mc = 36           + row * 18
    x0 = mc_to_png(rel_x_mc, scale)
    y0 = mc_to_png(rel_y_mc, scale)
    side = max(1, mc_to_png(16, scale))
    return (x0, y0, x0 + side, y0 + side)


# ---------------------------------------------------------------------------
# Drawing primitives
# ---------------------------------------------------------------------------

def fill_stone(img, box, seed):
    """Procedural stone block fill with subtle noise + cracks."""
    rng = random.Random(seed)
    px = img.load()
    x0, y0, x1, y1 = box

    # Base dithered fill
    for y in range(y0, y1):
        for x in range(x0, x1):
            r = rng.random()
            if r < 0.04:
                col = COL_STONE_HL
            elif r < 0.20:
                col = COL_STONE_LIGHT
            elif r < 0.55:
                col = COL_STONE_MID
            else:
                col = COL_STONE_DARK
            px[x, y] = col

    # Mortar lines (faint horizontal seams)
    for sy in range(y0 + 8, y1, 14):
        for x in range(x0, x1):
            if rng.random() < 0.7:
                px[x, sy] = COL_STONE_DARK

    # A handful of crack lines for texture
    for _ in range((x1 - x0) // 30):
        cx = rng.randint(x0 + 4, x1 - 4)
        cy = rng.randint(y0 + 4, y1 - 4)
        for step in range(rng.randint(3, 8)):
            if 0 <= cx < x1 and 0 <= cy < y1:
                px[cx, cy] = COL_STONE_DARK
            cx += rng.choice([-1, 0, 1])
            cy += rng.choice([0, 1])


def draw_gold_frame(img, box, thickness=3):
    """Ornate gold frame with bevel: dark→mid→bright→hilite from outside in."""
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    layers = [
        (0, COL_GOLD_DEEP),
        (1, COL_GOLD_MID),
        (2, COL_GOLD_BRIGHT),
        (3, COL_GOLD_HILITE),
    ]
    # outer dark ring
    d.rectangle([x0, y0, x1 - 1, y1 - 1], outline=COL_GOLD_DEEP)

    for offset, col in layers[:thickness]:
        d.rectangle(
            [x0 + offset, y0 + offset, x1 - 1 - offset, y1 - 1 - offset],
            outline=col,
        )

    # inner dark hairline (separates frame from interior)
    inner = thickness
    d.rectangle(
        [x0 + inner, y0 + inner, x1 - 1 - inner, y1 - 1 - inner],
        outline=COL_GOLD_DEEP,
    )


def draw_star_of_david(img, cx, cy, radius, color=COL_GOLD_BRIGHT, outline=COL_GOLD_DEEP):
    """
    Two interlocking equilateral triangles.

    Coordinates:
        upward triangle:    apex top, base bottom
        downward triangle:  apex bottom, base top
    """
    d = ImageDraw.Draw(img)
    # Up triangle
    up = [
        (cx,             cy - radius),
        (cx - radius * 0.866, cy + radius * 0.5),
        (cx + radius * 0.866, cy + radius * 0.5),
    ]
    # Down triangle
    dn = [
        (cx,             cy + radius),
        (cx - radius * 0.866, cy - radius * 0.5),
        (cx + radius * 0.866, cy - radius * 0.5),
    ]
    d.polygon(up, fill=color, outline=outline)
    d.polygon(dn, fill=color, outline=outline)


def draw_crown(img, cx, cy, half_w=10, h=8, color=COL_GOLD_BRIGHT, outline=COL_GOLD_DEEP):
    """Stylized 3-spike crown."""
    d = ImageDraw.Draw(img)
    # base bar
    d.rectangle(
        [cx - half_w, cy + h // 2, cx + half_w, cy + h // 2 + 2],
        fill=color, outline=outline,
    )
    # 3 spikes (left, center, right)
    spikes = [
        (cx - half_w, cy + h // 2 - 1, cx - half_w + 4, cy + h // 2 - 1, cx - half_w + 2, cy - h // 2),
        (cx - 2,      cy + h // 2 - 1, cx + 2,           cy + h // 2 - 1, cx,             cy - h),
        (cx + half_w - 4, cy + h // 2 - 1, cx + half_w, cy + h // 2 - 1, cx + half_w - 2, cy - h // 2),
    ]
    for x1, y1, x2, y2, tx, ty in spikes:
        d.polygon([(x1, y1), (x2, y2), (tx, ty)], fill=color, outline=outline)
    # gem dots
    for sx in (cx - half_w + 2, cx, cx + half_w - 2):
        d.point((sx, cy - h // 2 + 1), fill=COL_PLATE_RIM_LT)


def draw_nameplate(img, box, label):
    """Orange→red vertical-gradient plaque with gold rim and bevelled edges,
    centered cyrillic label.

    Designed so the MC font shadow under the plaque region is invisible:
    the bottom-right pixel of every plaque pixel is intentionally dark
    already (gradient fades to dark red at bottom), so MC's auto +1/+1 shadow
    overlap stays inside the plaque area instead of leaking onto stone."""
    x0, y0, x1, y1 = box
    pl_w = x1 - x0
    pl_h = y1 - y0

    plate = Image.new("RGBA", (pl_w, pl_h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(plate)

    # Gradient fill
    for y in range(pl_h):
        t = y / max(1, pl_h - 1)
        r = int(COL_PLATE_TOP[0] * (1 - t) + COL_PLATE_BOTTOM[0] * t)
        g = int(COL_PLATE_TOP[1] * (1 - t) + COL_PLATE_BOTTOM[1] * t)
        b = int(COL_PLATE_TOP[2] * (1 - t) + COL_PLATE_BOTTOM[2] * t)
        pdraw.line([(0, y), (pl_w - 1, y)], fill=(r, g, b, 255))

    # bevel + rim
    pdraw.rectangle([0, 0, pl_w - 1, pl_h - 1], outline=COL_PLATE_RIM_DK)
    pdraw.rectangle([1, 1, pl_w - 2, pl_h - 2], outline=COL_PLATE_RIM_LT)
    pdraw.rectangle([2, 2, pl_w - 3, pl_h - 3], outline=COL_GOLD_DEEP)

    # decorative end-caps (left/right gold pinion)
    for cap_x in (3, pl_w - 4):
        pdraw.line([(cap_x, 4), (cap_x, pl_h - 5)], fill=COL_GOLD_BRIGHT)

    # Render text and paste centered
    text_img = render_text(label, color=COL_TEXT, shadow=COL_TEXT_SHADOW, scale=1, spacing=1)
    tw, th = text_img.size
    if tw > pl_w - 12:
        # If it's too wide, fall back to scale=1 with tighter spacing handled
        # by render_text already; just clip if needed.
        pass
    tx = (pl_w - tw) // 2
    ty = (pl_h - th) // 2
    plate.alpha_composite(text_img, (tx, ty))

    img.alpha_composite(plate, (x0, y0))


def draw_slot_inset(img, rect):
    """Draw one chest slot as a darker recessed cell with bevel."""
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect
    # interior fill (slightly transparent so a hint of stone shows)
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=COL_SLOT_BG)
    # top+left rim dark (recessed look)
    d.line([(x0, y0), (x1 - 1, y0)], fill=COL_SLOT_RIM_DK)
    d.line([(x0, y0), (x0, y1 - 1)], fill=COL_SLOT_RIM_DK)
    # bottom+right rim light
    d.line([(x0 + 1, y1 - 1), (x1 - 1, y1 - 1)], fill=COL_SLOT_RIM_LT)
    d.line([(x1 - 1, y0 + 1), (x1 - 1, y1 - 1)], fill=COL_SLOT_RIM_LT)


# ---------------------------------------------------------------------------
# Composer
# ---------------------------------------------------------------------------

def render_menu_glyph(name, label, rows):
    """Build the 256×256 glyph PNG for a single menu."""
    height = render_height_for(name)
    shift  = shift_px_for(name)
    scale  = height / CANVAS

    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))

    box = chest_visible_box(rows, scale, shift)
    bx0, by0, bx1, by1 = box

    # 1. Stone backdrop
    fill_stone(img, box, seed=hash(name) & 0xFFFFFFFF)

    # 2. Gold frame (4 px thick)
    draw_gold_frame(img, box, thickness=3)

    # 3. Stars of David in each corner of the frame's interior
    star_r = 6
    pad = 6 + star_r
    for cx, cy in [(bx0 + pad, by0 + pad),
                   (bx1 - pad - 1, by0 + pad),
                   (bx0 + pad, by1 - pad - 1),
                   (bx1 - pad - 1, by1 - pad - 1)]:
        draw_star_of_david(img, cx, cy, star_r)

    # 4. Title nameplate centered horizontally near the top
    plate_w = min(110, (bx1 - bx0) - 40)
    # height of a single 7×9 line of text + padding
    plate_h = 16
    plate_cx = (bx0 + bx1) // 2
    plate_top = by0 + 6   # tucked just below the gold frame top edge
    plate_box = (plate_cx - plate_w // 2,
                 plate_top,
                 plate_cx + plate_w // 2,
                 plate_top + plate_h)

    # 5. Crown above the nameplate
    crown_cy = plate_top - 1
    crown_cx = plate_cx
    if crown_cy - 8 >= by0:
        draw_crown(img, crown_cx, crown_cy + 4, half_w=10, h=7)

    draw_nameplate(img, plate_box, label)

    # 6. Slot grid — exactly where MC will draw the 9×N slot bezels
    for r in range(rows):
        for c in range(9):
            rect = slot_rect_png(r, c, scale, shift)
            # Skip if rect would extend outside canvas
            if rect[2] > CANVAS or rect[3] > CANVAS:
                continue
            draw_slot_inset(img, rect)

    return img


def render_preview(name, label, rows, glyph_img):
    """
    Compose a fake screenshot of how the chest will look in-game.

    Builds:
        - generic chest GUI background (light grey, with title + slots)
        - overlays our glyph at the correct scale/offset
        - shows the orange→red plate, crown, slots overlaying the bezels.

    Output is roughly chest-sized (176 mc-px wide) at 4× zoom for clarity.
    """
    height = render_height_for(name)
    shift  = shift_px_for(name)
    scale  = height / CANVAS

    # Vanilla chest interior dimensions (mc-px)
    chest_w_mc = 176
    chest_h_mc = 17 + rows * 18 + 14 + 4 * 18 + 16  # interior + player inv

    zoom = 4
    canvas_w = chest_w_mc * zoom
    canvas_h = chest_h_mc * zoom
    bg = Image.new("RGBA", (canvas_w, canvas_h), (198, 198, 198, 255))
    d = ImageDraw.Draw(bg)

    # Outer dark border to evoke chest GUI frame
    d.rectangle([0, 0, canvas_w - 1, canvas_h - 1], outline=(80, 80, 80))

    # Slot bezels (grey)
    for r in range(rows):
        for c in range(9):
            sx = (7 + c * 18) * zoom
            sy = (17 + r * 18) * zoom
            d.rectangle(
                [sx, sy, sx + 16 * zoom - 1, sy + 16 * zoom - 1],
                fill=(139, 139, 139, 255),
                outline=(55, 55, 55, 255),
            )

    # Title strip (vanilla chest: grey, taller than slot row)
    # (we don't bother drawing the actual "Inventory" text — irrelevant)

    # Now paste our glyph, scaled by `scale * zoom` (PNG-px → mc-px → screen-px)
    glyph_render_w = int(round(CANVAS * scale * zoom))
    glyph_render_h = int(round(CANVAS * scale * zoom))
    g_resized = glyph_img.resize((glyph_render_w, glyph_render_h), Image.NEAREST)

    # Glyph origin in mc rel to chest_x: 8 + shift_px
    origin_mc_x = 8 + shift
    origin_mc_y = -19  # ascent = 32 places top at chest_y - 19
    paste_x = origin_mc_x * zoom
    paste_y = origin_mc_y * zoom
    bg.alpha_composite(g_resized, (paste_x, paste_y))

    # Player inventory simulated as 4 rows + hotbar of vanilla slots
    inv_top = (17 + rows * 18 + 14) * zoom
    for r in range(3):
        for c in range(9):
            sx = (7 + c * 18) * zoom
            sy = inv_top + r * 18 * zoom
            d.rectangle(
                [sx, sy, sx + 16 * zoom - 1, sy + 16 * zoom - 1],
                fill=(139, 139, 139, 255),
                outline=(55, 55, 55, 255),
            )
    # hotbar (with 4-px gap)
    hot_y = inv_top + (3 * 18 + 4) * zoom
    for c in range(9):
        sx = (7 + c * 18) * zoom
        d.rectangle(
            [sx, hot_y, sx + 16 * zoom - 1, hot_y + 16 * zoom - 1],
            fill=(139, 139, 139, 255),
            outline=(55, 55, 55, 255),
        )

    return bg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=os.path.join(_THIS_DIR, "..", "textures_solomon"),
                   help="Output directory for 256x256 glyph PNGs.")
    p.add_argument("--preview", default=None,
                   help="Optional dir for full-chest preview PNGs.")
    p.add_argument("--only", nargs="*", default=None,
                   help="Generate only specific menu names (default: all 28).")
    p.add_argument("--list", action="store_true",
                   help="List menu names and exit.")
    args = p.parse_args()

    if args.list:
        for name, label, rows in MENUS:
            print(f"{name:12s}  rows={rows}  label={label}")
        return

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    preview_dir = None
    if args.preview:
        preview_dir = os.path.abspath(args.preview)
        os.makedirs(preview_dir, exist_ok=True)

    targets = MENUS if not args.only else [m for m in MENUS if m[0] in args.only]
    if args.only and len(targets) != len(args.only):
        missing = set(args.only) - {m[0] for m in MENUS}
        print(f"WARNING: unknown menu names: {missing}", file=sys.stderr)

    for name, label, rows in targets:
        glyph = render_menu_glyph(name, label, rows)
        out_path = os.path.join(out_dir, f"{name}.png")
        glyph.save(out_path)
        print(f"  wrote {out_path}")

        if preview_dir:
            prev = render_preview(name, label, rows, glyph)
            prev_path = os.path.join(preview_dir, f"solomon_{name}.png")
            prev.save(prev_path)
            print(f"        preview → {prev_path}")

    print(f"\nDone: {len(targets)} glyph(s) → {out_dir}")
    if preview_dir:
        print(f"      {len(targets)} preview(s) → {preview_dir}")


if __name__ == "__main__":
    main()
