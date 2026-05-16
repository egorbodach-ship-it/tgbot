#!/usr/bin/env python3
"""
gen_solomon.py — Solomon-themed menu glyph generator.

Produces 256×256 RGBA PNGs that, when rendered with Oraxen glyph parameters
(height=280 for `menu`, height=268 for everything else, ascent=32), tile
exactly over a Minecraft 1.16.5 chest GUI's slot area.

Style: warm orange→yellow radial gradient backdrop with subtle damask
diamonds, ornate gold frame with bevel, Star-of-David corners, crown,
deep red→orange nameplate, bold white 7×9 Cyrillic title with drop-shadow.

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
    # egorchik intentionally skipped — keeps the original Minecraft title
    # texture (the player wants the Mojang-style logo there, not Solomon).
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
    # New Solomon glyphs for plugins outside DeluxeMenus.
    # aukcion: BAuction /plugins/BAuction/menu/home.yml (size=54, all slots)
    # cases:   TreasureCoCaseReloaded /plugins/TreasureCoCaseReloaded/invgui.yml (6×9)
    # skupschik: sSeller /plugins/sSeller/config.yml (5×9)
    ("aukcion",    "АУКЦИОН",        6),
    ("cases",      "КЕЙСЫ",          6),
    ("skupschik",  "СКУПЩИК",        6),
]


# ---------------------------------------------------------------------------
# Per-menu YAML lookup — used to draw slot bezels ONLY at slots that the
# YAML actually uses (no more bezels in pure-decoration corners).
# Entry None = "draw the full grid as before" (fallback for unknown menus).
# ---------------------------------------------------------------------------
SERVER_YAMLS_DIR = os.path.join(_THIS_DIR, "..", "server_yamls")

YAML_LOOKUP = {
    # name → relative yaml path inside server_yamls/
    "menu":      "menu/menu.yml",
    "donate":    "menu/donate.yml",
    "events":    "menu/events.yml",
    "help":      "menu/help.yml",
    "portals":   "menu/portals.yml",
    "rtp":       "menu/rtp.yml",
    "obmen":     "menu/obmen.yml",
    "arenda":    "menu/arenda.yml",
    "grab":      "menu/grab.yml",
    "media":     "menu/media.yml",
    "panel":     "menu/panel.yml",
    "akriwer":   "menu/akriwer.yml",
    # The big shops via DeluxeMenus
    "shop":      "shop/donateSHOP.yml",
    "freek":     None,  # not in DM — leave full
    "arrow":     "shop/donateARROW.yml",
    "egg":       "shop/donateEGG.yml",
    "items":     "shop/donateITEMS2.yml",
    "livalka":   "shop/donateLIVALKA.yml",
    "potions":   "shop/donatePOTIONS.yml",
    "pred":      "shop/donatePRED.yml",
    "pve":       "shop/donatePVE.yml",
    "pveother":  "shop/donatePVEOTHER.yml",
    "resmenu":   "shop/donateRESMENU.yml",
    "reseuro":   "shop/donateRESEURO.yml",
    "resmoneta": "shop/donateRESMONETA.yml",
    "shari":     "shop/donateSHARI.yml",
    "spawners":  "shop/donateSPAWNERS.yml",
    # External plugins
    "aukcion":   "bauc/home.yml",
    "cases":     "case/invgui.yml",      # TreasureCoCaseReloaded all_selection schematic
    "skupschik": "seller/config.yml",    # sSeller frame+sell_slots+sell_all.slot
}


def used_slots_for(name, fallback_rows):
    """
    Look up the YAML for `name` and return (rows, used_slot_set).
    If no YAML is configured or extraction fails, returns
    (fallback_rows, set(range(fallback_rows*9))) — i.e. full grid.
    """
    rel = YAML_LOOKUP.get(name)
    if rel is None:
        return fallback_rows, set(range(fallback_rows * 9))
    path = os.path.join(SERVER_YAMLS_DIR, rel)
    try:
        from slot_extractor import (
            slots_for_menu,
            slots_for_invgui_section,
            slots_for_sseller,
        )
        if name == "cases":
            rows, slots = slots_for_invgui_section(path, "all_selection")
        elif name == "skupschik":
            rows, slots = slots_for_sseller(path)
        else:
            rows, slots = slots_for_menu(path)
    except Exception as e:
        print(f"  WARN [{name}] slot extraction failed: {e}", file=sys.stderr)
        return fallback_rows, set(range(fallback_rows * 9))
    if rows is None:
        rows = fallback_rows
    if not slots:
        return rows, set(range(rows * 9))
    return rows, set(slots)


# ---------------------------------------------------------------------------
# Rendering parameters
# ---------------------------------------------------------------------------

CANVAS = 256

# Per-name glyph render height (matches Oraxen menus_overlay.yml `height:`).
# Default is 268; only `menu` is tuned to 280 to keep the chest center centered.
def render_height_for(name):
    return 280 if name == "menu" else 268

def shift_px_for(name):
    # IMPORTANT: this MUST match what's actually in the menu_title:
    # - If menu_title is just "ோ" (a single Tamil char, no shift prefix)
    #   then the glyph's top-left in chest is at MC px (chest_x + 8, chest_y - 19),
    #   so shift_px must be 0.
    # - If menu_title contains a leading shift glyph like "\uF823ோ" with
    #   advance=-8, then shift_px should be -8.
    #
    # Live YAMLs currently use the simple form (no shift prefix), so we use 0.
    # If this changes, update the menu_title for ALL menus AND change this
    # function in lockstep.
    return 0


# ---------------------------------------------------------------------------
# Solomon palette (orange→yellow brand gradient + ornate gold accents)
# ---------------------------------------------------------------------------

# Backdrop gradient (radial: bright yellow at center → deep orange at edges)
COL_BG_CENTER    = (255, 224, 110, 255)     # warm yellow
COL_BG_MID       = (255, 168,  46, 255)     # saturated orange
COL_BG_EDGE      = (188,  72,  10, 255)     # deep burnt orange
COL_BG_VIGNETTE  = (108,  32,   6, 255)     # near-black warm (corners)

# Damask / arabesque pattern accents on the backdrop
COL_DAMASK_LT    = (255, 220, 130, 60)      # subtle highlight
COL_DAMASK_DK    = (140,  56,  10, 70)      # subtle shadow line

# Gold frame
COL_GOLD_DEEP    = (107,  70,  18, 255)
COL_GOLD_MID     = (191, 138,  36, 255)
COL_GOLD_BRIGHT  = (255, 213,  92, 255)
COL_GOLD_HILITE  = (255, 240, 168, 255)

# Red nameplate (now red→deep red, contrasts strongly with orange/yellow bg)
COL_PLATE_TOP    = (210,  50,  20, 255)
COL_PLATE_BOTTOM = (135,  18,   8, 255)
COL_PLATE_RIM_LT = (255, 215, 100, 255)
COL_PLATE_RIM_DK = ( 70,   8,   4, 255)

# Slot inset
COL_SLOT_BG      = ( 28,  22,  18, 255)
COL_SLOT_RIM_LT  = ( 78,  66,  54, 255)
COL_SLOT_RIM_DK  = ( 16,  12,  10, 255)

# Text
COL_TEXT         = (255, 248, 224, 255)
COL_TEXT_SHADOW  = ( 60,  10,   0, 255)


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
    # Bottom of the chest's slot grid in mc-px relative to top-of-glyph.
    # Top-left of slot row r in chest-coords is (chest_y + 17 + r*18); top of
    # glyph sits at chest_y - 19. So slot-row bottom = 17 + r*18 + 16 = 33 + r*18.
    # We add a small +6 mc-px margin so the gold frame extends visibly past
    # the last slot row before the player-inventory begins.
    bottom_mc = 33 + rows * 18 + 6

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

def fill_orange_yellow_gradient(img, box, seed):
    """
    Backdrop: warm orange→yellow radial gradient, with soft corner vignette
    and a subtle damask diamond pattern on top.

    Designed to feel "regal/Solomon" without being noisy: the eye is drawn
    to the center where the nameplate sits, and the corners darken to make
    the gold frame and Stars of David stand out.
    """
    rng = random.Random(seed)
    px = img.load()
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    cx = x0 + w / 2.0
    cy = y0 + h / 2.0
    # Use a tight radius so the gradient finishes well within the frame.
    max_r = math.hypot(w / 2.0, h / 2.0)

    def lerp(c1, c2, t):
        return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(4))

    for y in range(y0, y1):
        for x in range(x0, x1):
            # normalized radial distance 0..1
            dx = (x - cx) / max_r
            dy = (y - cy) / max_r
            r = math.sqrt(dx * dx + dy * dy)
            if r > 1.0:
                r = 1.0

            # Three-stop gradient: yellow center → orange mid → deep edge
            if r < 0.55:
                t = r / 0.55
                col = lerp(COL_BG_CENTER, COL_BG_MID, t)
            else:
                t = (r - 0.55) / 0.45
                col = lerp(COL_BG_MID, COL_BG_EDGE, t)

            # Corner vignette: gentle, only kicks in past r=0.85
            if r > 0.85:
                vt = (r - 0.85) / 0.15
                col = lerp(col, COL_BG_VIGNETTE, vt * 0.7)

            # Light film grain to break up banding (very subtle)
            jitter = rng.randint(-4, 4)
            col = (
                max(0, min(255, col[0] + jitter)),
                max(0, min(255, col[1] + jitter)),
                max(0, min(255, col[2] + jitter)),
                255,
            )
            px[x, y] = col

    # ---- Damask diamond grid overlay -----------------------------------
    # Plot a diamond (Manhattan-distance ring) every 24 px in both axes.
    # Two-tone: highlight on top-left edge, shadow on bottom-right.
    grid = 24
    diamond_r = 8
    for cy_d in range(y0 + grid // 2, y1, grid):
        for cx_d in range(x0 + grid // 2, x1, grid):
            for dy in range(-diamond_r, diamond_r + 1):
                for dx in range(-diamond_r, diamond_r + 1):
                    md = abs(dx) + abs(dy)
                    if md == diamond_r or md == diamond_r - 1:
                        xi = cx_d + dx
                        yi = cy_d + dy
                        if x0 <= xi < x1 and y0 <= yi < y1:
                            base = px[xi, yi]
                            if dx + dy < 0:  # top-left half: highlight
                                hi = COL_DAMASK_LT
                                a = hi[3] / 255.0
                                px[xi, yi] = (
                                    int(base[0] * (1 - a) + hi[0] * a),
                                    int(base[1] * (1 - a) + hi[1] * a),
                                    int(base[2] * (1 - a) + hi[2] * a),
                                    255,
                                )
                            else:  # bottom-right half: shadow
                                sh = COL_DAMASK_DK
                                a = sh[3] / 255.0
                                px[xi, yi] = (
                                    int(base[0] * (1 - a) + sh[0] * a),
                                    int(base[1] * (1 - a) + sh[1] * a),
                                    int(base[2] * (1 - a) + sh[2] * a),
                                    255,
                                )


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


def draw_filigree(img, box):
    """
    Decorative gold filigree along the inside edge of the frame:
    short curls in each corner + a small cartouche at the bottom center.

    Uses small dot strokes to evoke embossed metalwork without being noisy.
    """
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    inset = 14    # pixels inside the gold frame
    curl_r = 5    # curl radius

    # Four corner curls (quarter-circles facing inward)
    for cx, cy, q in [
        (x0 + inset, y0 + inset, 0),                   # top-left
        (x1 - inset - 1, y0 + inset, 1),               # top-right
        (x0 + inset, y1 - inset - 1, 2),               # bottom-left
        (x1 - inset - 1, y1 - inset - 1, 3),           # bottom-right
    ]:
        # curl arc + inner dot
        for theta in range(0, 91, 10):
            rad = math.radians(theta)
            # rotate the quadrant-aligned arc to face inward
            dx = math.cos(rad) * curl_r
            dy = math.sin(rad) * curl_r
            if q == 1:
                dx = -dx
            elif q == 2:
                dy = -dy
            elif q == 3:
                dx, dy = -dx, -dy
            xi = int(round(cx + dx))
            yi = int(round(cy + dy))
            d.point((xi, yi), fill=COL_GOLD_BRIGHT)
            d.point((xi + (1 if q in (0, 2) else -1), yi), fill=COL_GOLD_DEEP)

        # central dot
        d.point((cx, cy), fill=COL_GOLD_HILITE)

    # Bottom-center cartouche: small horizontal flourish (- ◇ -)
    cy = y1 - inset - 1
    cx = (x0 + x1) // 2
    d.line([(cx - 14, cy), (cx - 6, cy)], fill=COL_GOLD_BRIGHT)
    d.line([(cx + 6, cy), (cx + 14, cy)], fill=COL_GOLD_BRIGHT)
    d.line([(cx - 14, cy + 1), (cx - 6, cy + 1)], fill=COL_GOLD_DEEP)
    d.line([(cx + 6, cy + 1), (cx + 14, cy + 1)], fill=COL_GOLD_DEEP)
    # tiny diamond
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if abs(dx) + abs(dy) == 3:
                d.point((cx + dx, cy + dy), fill=COL_GOLD_BRIGHT)
            elif abs(dx) + abs(dy) == 2:
                d.point((cx + dx, cy + dy), fill=COL_GOLD_HILITE)


def draw_plate_glow(img, box):
    """Soft warm-yellow glow halo around the nameplate to lift it off the bg."""
    x0, y0, x1, y1 = box
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    glow_w = (x1 - x0) + 18
    glow_h = (y1 - y0) + 14
    glow = Image.new("RGBA", (glow_w, glow_h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    # 3 concentric rounded rectangles, alpha decreasing outward
    for i, alpha in enumerate([90, 60, 30]):
        pad = i * 3
        gd.rectangle(
            [pad, pad, glow_w - 1 - pad, glow_h - 1 - pad],
            outline=(255, 220, 120, alpha),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=3))
    img.alpha_composite(glow, (cx - glow_w // 2, cy - glow_h // 2))


def draw_nameplate(img, box, label):
    """Red→deep red vertical-gradient plaque with gold rim and bevelled edges,
    centered bold cyrillic label.

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

    # Render text and paste centered (BOLD now)
    text_img = render_text(label, color=COL_TEXT, shadow=COL_TEXT_SHADOW,
                           scale=1, spacing=2, bold=True)
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

    # Pull the actually-used slots from the live YAML on the server (if known).
    # `actual_rows` may differ from `rows` we hard-coded; trust the YAML.
    actual_rows, used_slots = used_slots_for(name, rows)
    rows = actual_rows

    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))

    box = chest_visible_box(rows, scale, shift)
    bx0, by0, bx1, by1 = box

    # 1. Orange→yellow gradient backdrop with damask pattern
    fill_orange_yellow_gradient(img, box, seed=hash(name) & 0xFFFFFFFF)

    # 2. Gold frame (4 px thick)
    draw_gold_frame(img, box, thickness=3)

    # 3. Gold filigree curls inside the frame
    draw_filigree(img, box)

    # 4. Stars of David in each corner of the frame's interior
    star_r = 6
    pad = 6 + star_r
    for cx, cy in [(bx0 + pad, by0 + pad),
                   (bx1 - pad - 1, by0 + pad),
                   (bx0 + pad, by1 - pad - 1),
                   (bx1 - pad - 1, by1 - pad - 1)]:
        draw_star_of_david(img, cx, cy, star_r)

    # 5. Title nameplate centered horizontally near the top.
    # Width auto-fits the bold label so long names like "РЕСУРСЫ МОНЕТА" still
    # read clearly. 7px glyph + 1px bold-pad + 2px spacing = 10 px per char.
    char_advance = 10
    label_pixels = len(label) * char_advance + 12  # +12 padding
    plate_w = max(96, min(label_pixels, (bx1 - bx0) - 28))
    plate_h = 18
    plate_cx = (bx0 + bx1) // 2
    plate_top = by0 + 7
    plate_box = (plate_cx - plate_w // 2,
                 plate_top,
                 plate_cx + plate_w // 2,
                 plate_top + plate_h)

    # Halo behind plate
    draw_plate_glow(img, plate_box)

    # 6. Crown above the nameplate
    crown_cy = plate_top - 1
    crown_cx = plate_cx
    if crown_cy - 8 >= by0:
        draw_crown(img, crown_cx, crown_cy + 4, half_w=10, h=7)

    draw_nameplate(img, plate_box, label)

    # 7. Slot grid — only at slots that the YAML actually uses, so that
    # decorative empty corners (gradient + damask) stay visible.
    for r in range(rows):
        for c in range(9):
            slot_idx = r * 9 + c
            if slot_idx not in used_slots:
                continue
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
