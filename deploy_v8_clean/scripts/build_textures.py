"""
Generate clean menu overlay textures:
- Orange warm background (no 9x6 grid)
- Original frame + title ribbon preserved (extracted from current pack)
- Decorative inset cells drawn ONLY at slot positions provided
- Final canvas 256x256 (content at top-left 168x125)
"""
import os
import sys
import yaml
import math
from pathlib import Path
from PIL import Image
import numpy as np

# Slot grid mapping (from analysis of menu.png):
# - Content area: 168x125 px positioned at (0, 18) inside a 256x256 canvas
# - Title ribbon: y=18..32 (~15px)
# - Slot row 0 starts y=38 (after first separator at y=33-36)
# - Cell width=13, height=13, pitch=18 in both axes
# - First cell origin: x=2, y=20 (then cells at 2+c*18, 20+r*18)
CELL_W = 13
CELL_H = 13
PITCH = 18
ORIGIN_X = 2  # offset in 168x125 content
ORIGIN_Y = 20

# 256x256 canvas: content placed at (0, 18). So in canvas coords:
CANVAS_OFFSET_X = 0
CANVAS_OFFSET_Y = 18

# Warm orange palette
BG_MID    = (180, 80, 25, 255)
BG_DARK   = (130, 55, 18, 255)
BG_BRIGHT = (210, 110, 40, 255)
CELL_FILL = (90, 35, 8, 255)         # dark cell interior
CELL_SHADOW = (45, 18, 4, 255)       # top-left inset shadow
CELL_HILIGHT = (230, 130, 55, 255)   # bottom-right highlight
CELL_BORDER = (160, 65, 20, 255)     # outer frame around cell


def make_orange_bg(w, h):
    """Solid warm orange background with subtle radial gradient + noise."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    cx, cy = w / 2, h / 2
    maxd = math.hypot(cx, cy)
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, y - cy) / maxd  # 0..1
            # interpolate from BG_BRIGHT (center) to BG_DARK (edges)
            t = min(d * 1.15, 1.0)
            r = int(BG_BRIGHT[0] * (1 - t) + BG_DARK[0] * t)
            g = int(BG_BRIGHT[1] * (1 - t) + BG_DARK[1] * t)
            b = int(BG_BRIGHT[2] * (1 - t) + BG_DARK[2] * t)
            # subtle diagonal-line noise
            n = ((x * 3 + y * 5) % 17) - 8
            arr[y, x] = [
                max(0, min(255, r + n // 2)),
                max(0, min(255, g + n // 3)),
                max(0, min(255, b + n // 4)),
                255,
            ]
    return arr


def detect_frame_mask(source_path):
    """Extract a mask of frame pixels from the source texture (orange/white/bright)."""
    src = Image.open(source_path).convert('RGBA').crop((0, 18, 168, 143))
    arr = np.array(src)
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    # Frame pixels: bright orange, dark-frame orange, or white title
    bright_orange = (r > 200) & (g < 160) & (b < 100)
    dark_orange = (r >= 140) & (r <= 200) & (g >= 30) & (g <= 90) & (b < 40)
    white = (r > 200) & (g > 200) & (b > 200)
    mask = (bright_orange | dark_orange | white) & (a > 0)
    return mask, arr


def draw_inset_cell(arr, cx, cy, w=13, h=13):
    """Draw an inset (recessed) decorative cell centered at (cx, cy)."""
    x0 = cx - w // 2
    y0 = cy - h // 2
    x1 = x0 + w
    y1 = y0 + h
    H, W = arr.shape[:2]
    # Fill interior
    for y in range(max(0, y0 + 1), min(H, y1 - 1)):
        for x in range(max(0, x0 + 1), min(W, x1 - 1)):
            arr[y, x] = CELL_FILL
    # Top edge (shadow)
    for x in range(max(0, x0), min(W, x1)):
        if 0 <= y0 < H:
            arr[y0, x] = CELL_SHADOW
    # Left edge (shadow)
    for y in range(max(0, y0), min(H, y1)):
        if 0 <= x0 < W:
            arr[y, x0] = CELL_SHADOW
    # Bottom edge (highlight)
    if 0 <= y1 - 1 < H:
        for x in range(max(0, x0 + 1), min(W, x1)):
            arr[y1 - 1, x] = CELL_HILIGHT
    # Right edge (highlight)
    if 0 <= x1 - 1 < W:
        for y in range(max(0, y0 + 1), min(H, y1)):
            arr[y, x1 - 1] = CELL_HILIGHT


def build_texture(source_path, slot_indices, out_path):
    """Build a clean texture for one menu."""
    frame_mask, frame_arr = detect_frame_mask(source_path)
    bg = make_orange_bg(168, 125)  # 168x125 content area
    # Overlay frame on background
    for y in range(125):
        for x in range(168):
            if frame_mask[y, x]:
                bg[y, x] = frame_arr[y, x]
    # Draw inset cells at slot positions (within content area coords)
    for slot in slot_indices:
        r = slot // 9
        c = slot % 9
        cx = ORIGIN_X + c * PITCH + CELL_W // 2
        cy = ORIGIN_Y + r * PITCH + CELL_H // 2
        if 0 <= cx < 168 and 0 <= cy < 125:
            draw_inset_cell(bg, cx, cy, CELL_W, CELL_H)
    # Compose into 256x256 with transparent padding
    canvas = np.zeros((256, 256, 4), dtype=np.uint8)
    canvas[CANVAS_OFFSET_Y:CANVAS_OFFSET_Y + 125, CANVAS_OFFSET_X:CANVAS_OFFSET_X + 168] = bg
    Image.fromarray(canvas).save(out_path)
    print(f'  -> {out_path} ({len(slot_indices)} slots)')


def extract_slots_from_yaml(yaml_path):
    """Parse a DM YAML and return list of slot indices that have items."""
    try:
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f'  WARN parsing {yaml_path}: {e}')
        return []
    if not isinstance(data, dict):
        return []
    items = data.get('items', {})
    if not isinstance(items, dict):
        return []
    slots = []
    for key, val in items.items():
        if not isinstance(val, dict):
            continue
        s = val.get('slot')
        if s is None:
            try:
                s = int(key)
            except (TypeError, ValueError):
                continue
        try:
            slots.append(int(s))
        except (TypeError, ValueError):
            pass
    return sorted(set(slots))


def main():
    base = Path('/home/ubuntu/repos/tgbot/deploy_v7_final')
    yaml_dir = base / 'patched_menus'
    src_textures = base / 'orange_textures'
    out_dir = Path('/home/ubuntu/repos/tgbot/deploy_v8_clean/textures')
    out_dir.mkdir(parents=True, exist_ok=True)

    # Map each source texture name to its YAML file
    # YAML files are in menu/ and shop/ subdirs; pick the one matching the texture name
    yaml_files = list(yaml_dir.glob('*/*.yml'))
    yaml_map = {}
    for yp in yaml_files:
        stem = yp.stem
        # Direct match by file stem
        yaml_map.setdefault(stem, yp)
        # Also map stripped donate prefix variants (donateSHARI -> shari)
        if stem.lower().startswith('donate'):
            short = stem[6:].lower()
            yaml_map.setdefault(short, yp)

    # Texture name -> slots
    texture_slot_map = {}
    for tex in sorted(src_textures.glob('*.png')):
        name = tex.stem
        yp = yaml_map.get(name) or yaml_map.get(name.lower())
        slots = extract_slots_from_yaml(yp) if yp else []
        texture_slot_map[name] = slots
        print(f'{name}: yaml={yp.name if yp else "MISSING"} slots={slots}')

    # Build textures
    for tex in sorted(src_textures.glob('*.png')):
        name = tex.stem
        slots = texture_slot_map.get(name, [])
        build_texture(str(tex), slots, str(out_dir / f'{name}.png'))


if __name__ == '__main__':
    main()
