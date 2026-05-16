"""
Step 1 (v7): Add a SUBTLE plate around МЕНЮ-style title
Approach B from task: tone the plate with ONLY dark-brown variants so
MC font shadow (color * 0.25) lands within the background brown range
and produces no orange halo.

Plate region in PNG pixel coords (from previous fix scripts):
  y = 20..31, x = 20..148

Background brown is roughly (66-90, 28-45, 7-15). MC chest title font shadow
is drawn at (+1,+1) with color*0.25. So a max brightness of ~110 in any
channel gives shadow <= ~28 — invisible against brown bg.

Plate visual design (sunken/etched look):
  - Outer 1-px border on all 4 sides:   dark brown (40, 17, 4)
  - Top + Left  inner 1-px highlight:   slightly lighter brown (95, 42, 12)
  - Bottom + Right inner 1-px shadow:   very dark (28, 12, 2)
  - Interior fill (where currently brown):  same brown ~ background, untouched
  - The white text (МЕНЮ) is preserved unchanged (sampled from source)
"""
import os, sys
import numpy as np
from PIL import Image

SRC_DIR = sys.argv[1] if len(sys.argv) > 1 else "tgbot/handoff/01_textures_stages/02_banner_removed"
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "tgbot/work_v7/textures_step1_no_banner"
os.makedirs(OUT_DIR, exist_ok=True)

# Plate region (PNG pixel coords)
PY0, PY1 = 20, 32   # exclusive end
PX0, PX1 = 20, 148

# Plate colours — all in dark-brown range so font shadow is invisible
COL_BORDER       = (40, 17, 4, 255)    # outer 1-px border
COL_HL           = (105, 50, 16, 255)  # top/left highlight (1-px inside border)
COL_DK           = (28, 12, 2, 255)    # bottom/right shadow (1-px inside border)
# Interior remains untouched (brown bg with white letters)


def draw_plate(arr):
    h, w = arr.shape[:2]
    # Outer border (4 sides at y=PY0, y=PY1-1, x=PX0, x=PX1-1)
    arr[PY0,    PX0:PX1, :4] = COL_BORDER
    arr[PY1-1,  PX0:PX1, :4] = COL_BORDER
    arr[PY0:PY1, PX0,    :4] = COL_BORDER
    arr[PY0:PY1, PX1-1,  :4] = COL_BORDER

    # Inner highlight (top + left edges, 1 px inside the border)
    arr[PY0+1,    PX0+1:PX1-1, :4] = COL_HL
    arr[PY0+1:PY1-1, PX0+1,    :4] = COL_HL

    # Inner darker edge (bottom + right edges, 1 px inside the border)
    arr[PY1-2,    PX0+1:PX1-1, :4] = COL_DK
    arr[PY0+1:PY1-1, PX1-2,    :4] = COL_DK

    return arr


def process(src_path, out_path):
    img = Image.open(src_path).convert("RGBA")
    arr = np.array(img)
    # Save white-text mask BEFORE we draw plate, so we can restore letters
    interior = arr[PY0:PY1, PX0:PX1]
    is_white = (
        (interior[..., 0] > 200) &
        (interior[..., 1] > 200) &
        (interior[..., 2] > 200) &
        (interior[..., 3] > 0)
    )
    saved_letters = interior[is_white].copy()
    saved_yx = np.argwhere(is_white)

    draw_plate(arr)

    # Restore white letters that we may have over-painted
    for (yy, xx), col in zip(saved_yx, saved_letters):
        arr[PY0 + yy, PX0 + xx] = col

    Image.fromarray(arr).save(out_path)


if __name__ == "__main__":
    cnt = 0
    for fn in sorted(os.listdir(SRC_DIR)):
        if not fn.endswith(".png"):
            continue
        process(os.path.join(SRC_DIR, fn), os.path.join(OUT_DIR, fn))
        cnt += 1
    print(f"Processed {cnt} PNGs into {OUT_DIR}")
