"""
Procedural rank-tag icon generator.

Generates 13 PNG rank icons (256x64), themed with user-specified colors.
Each icon has:
  - Rounded gradient pill background
  - Inner highlight (top) + shadow (bottom) for embossed look
  - Bold pixel-font rank name centered
  - Tiny decorative dots in corners

No external art is used — everything is procedurally drawn.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT_DIR = "/projects/sandbox/tgbot/rank_pack/Ranks"
os.makedirs(OUT_DIR, exist_ok=True)

# Canvas: 256x64 (Minecraft glyphs render fine, scale_ratio handles in-game size)
W, H = 256, 64

# Each rank: (id_lowercase, display_name, primary_color, secondary_color)
# primary = main pill color, secondary = highlight/accent
RANKS = [
    ("owner",   "OWNER",   (255, 215, 0),   (255, 165, 0)),    # gold gradient
    ("admin",   "ADMIN",   (220, 20, 60),   (139, 0, 0)),      # crimson
    ("dadmin",  "D.ADMIN", (160, 32, 240),  (75, 0, 130)),     # purple
    ("solomon", "SOLOMON", (255, 220, 0),   (255, 140, 0)),    # yellow→orange gradient
    ("osiris",  "OSIRIS",  (220, 20, 60),   (255, 255, 255)),  # red+white
    ("phonix",  "PHONIX",  (30, 100, 220),  (60, 140, 255)),   # blue
    ("nebula",  "NEBULA",  (40, 200, 80),   (80, 240, 120)),   # green
    ("triton",  "TRITON",  (255, 220, 50),  (255, 240, 120)),  # yellow
    ("hydra",   "HYDRA",   (255, 138, 30),  (255, 175, 75)),   # orange
    ("aqua",    "AQUA",    (80, 200, 240),  (130, 230, 255)),  # cyan/aqua
    ("morph",   "MORPH",   (255, 105, 180), (255, 150, 210)),  # pink
    ("axolot",  "AXOLOT",  (220, 60, 60),   (255, 100, 100)),  # red
    ("vernal",  "VERNAL",  (139, 90, 43),   (180, 130, 70)),   # brown
]


def make_pill(width, height, color1, color2, gradient=False):
    """Create a rounded pill with optional gradient."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    radius = height // 2

    for y in range(height):
        for x in range(width):
            # Distance from rounded corners
            cx = x
            cy = y
            in_shape = False
            if x < radius:
                # Left rounded
                d = (radius - x) ** 2 + (y - radius) ** 2
                if d <= radius * radius:
                    in_shape = True
            elif x >= width - radius:
                # Right rounded
                d = (x - (width - radius)) ** 2 + (y - radius) ** 2
                if d <= radius * radius:
                    in_shape = True
            else:
                in_shape = True

            if in_shape:
                if gradient:
                    # Horizontal gradient
                    t = x / max(1, width - 1)
                    r = int(color1[0] * (1 - t) + color2[0] * t)
                    g = int(color1[1] * (1 - t) + color2[1] * t)
                    b = int(color1[2] * (1 - t) + color2[2] * t)
                else:
                    r, g, b = color1
                arr[y, x] = (r, g, b, 255)

    return arr


def add_emboss(arr, color1, color2):
    """Add highlight + shadow to give embossed/glossy look."""
    h, w = arr.shape[:2]
    radius = h // 2

    # Top highlight (1-2px lighter line just below the top edge of the pill)
    for y in range(h):
        for x in range(w):
            if arr[y, x, 3] == 0:
                continue
            # Find local "top edge" — first opaque pixel from the top in this column
            # If we're within 2 px of the top contour, draw highlight
            for dy in range(1, 4):
                if y - dy < 0 or arr[y - dy, x, 3] == 0:
                    # we are within `dy` px of top edge
                    factor = 1.5 - dy * 0.15
                    r = min(255, int(arr[y, x, 0] * factor))
                    g = min(255, int(arr[y, x, 1] * factor))
                    b = min(255, int(arr[y, x, 2] * factor))
                    arr[y, x, 0] = r
                    arr[y, x, 1] = g
                    arr[y, x, 2] = b
                    break

    # Bottom shadow
    for y in range(h - 1, -1, -1):
        for x in range(w):
            if arr[y, x, 3] == 0:
                continue
            for dy in range(1, 3):
                if y + dy >= h or arr[y + dy, x, 3] == 0:
                    factor = 0.65 + dy * 0.1
                    r = max(0, int(arr[y, x, 0] * factor))
                    g = max(0, int(arr[y, x, 1] * factor))
                    b = max(0, int(arr[y, x, 2] * factor))
                    arr[y, x, 0] = r
                    arr[y, x, 1] = g
                    arr[y, x, 2] = b
                    break

    return arr


# Bold pixel font 5x7 — wider strokes for visibility
FONT_5x7 = {
    'A': ['01110','11011','11011','11111','11011','11011','11011'],
    'B': ['11110','11011','11011','11110','11011','11011','11110'],
    'C': ['01111','11000','11000','11000','11000','11000','01111'],
    'D': ['11110','11011','11011','11011','11011','11011','11110'],
    'E': ['11111','11000','11000','11110','11000','11000','11111'],
    'F': ['11111','11000','11000','11110','11000','11000','11000'],
    'G': ['01111','11000','11000','11011','11011','11011','01111'],
    'H': ['11011','11011','11011','11111','11011','11011','11011'],
    'I': ['11111','01100','01100','01100','01100','01100','11111'],
    'J': ['00111','00011','00011','00011','00011','11011','01110'],
    'K': ['11011','11011','11110','11100','11110','11011','11011'],
    'L': ['11000','11000','11000','11000','11000','11000','11111'],
    'M': ['11011','11111','11111','11011','11011','11011','11011'],
    'N': ['11011','11111','11111','11011','11011','11011','11011'],
    'O': ['01110','11011','11011','11011','11011','11011','01110'],
    'P': ['11110','11011','11011','11110','11000','11000','11000'],
    'Q': ['01110','11011','11011','11011','11011','11111','01111'],
    'R': ['11110','11011','11011','11110','11100','11011','11011'],
    'S': ['01111','11000','11000','01110','00011','00011','11110'],
    'T': ['11111','01100','01100','01100','01100','01100','01100'],
    'U': ['11011','11011','11011','11011','11011','11011','01110'],
    'V': ['11011','11011','11011','11011','11011','01110','00100'],
    'W': ['11011','11011','11011','11011','11111','11111','01010'],
    'X': ['11011','11011','01110','00100','01110','11011','11011'],
    'Y': ['11011','11011','11011','01110','00100','00100','00100'],
    'Z': ['11111','00011','00110','01100','11000','11000','11111'],
    '.': ['00000','00000','00000','00000','00000','01100','01100'],
    ' ': ['00000','00000','00000','00000','00000','00000','00000'],
}


def draw_text(arr, text, scale=2):
    """Draw bold centered text on the pill."""
    h, w = arr.shape[:2]
    LW, LH, SP = 5, 7, 1
    # Filter to known chars
    chars = list(text.upper())
    total_w = sum(LW for _ in chars) + max(0, len(chars) - 1) * SP
    total_w_scaled = total_w * scale
    text_h_scaled = LH * scale

    # Center
    x_start = (w - total_w_scaled) // 2
    y_start = (h - text_h_scaled) // 2

    px = x_start
    for ch in chars:
        glyph = FONT_5x7.get(ch)
        if glyph:
            for ry, row in enumerate(glyph):
                for rx, c in enumerate(row):
                    if c == '1':
                        # Draw scale x scale block
                        for dy in range(scale):
                            for dx in range(scale):
                                yy = y_start + ry * scale + dy
                                xx = px + rx * scale + dx
                                if 0 <= xx < w and 0 <= yy < h:
                                    if arr[yy, xx, 3] > 0:  # only on pill
                                        arr[yy, xx] = (255, 255, 255, 255)
        px += (LW + SP) * scale


def add_corner_dots(arr):
    """Add tiny decorative dots near the rounded corners."""
    h, w = arr.shape[:2]
    radius = h // 2
    # Place small bright dots in the inner area near the curve
    dots = [
        (radius // 2 + 2, h // 2),       # left center
        (w - radius // 2 - 3, h // 2),   # right center
    ]
    for cx, cy in dots:
        if 0 <= cx < w and 0 <= cy < h and arr[cy, cx, 3] > 0:
            # Slightly highlight
            r = min(255, arr[cy, cx, 0] + 40)
            g = min(255, arr[cy, cx, 1] + 40)
            b = min(255, arr[cy, cx, 2] + 40)
            arr[cy, cx] = (r, g, b, 255)


def generate_rank(rank_id, name, color1, color2, gradient=False):
    """Generate one rank PNG and save."""
    pill_w, pill_h = 220, 50  # actual pill (centered in 256x64 canvas)
    arr_pill = make_pill(pill_w, pill_h, color1, color2, gradient=gradient)
    arr_pill = add_emboss(arr_pill, color1, color2)
    draw_text(arr_pill, name, scale=2)
    add_corner_dots(arr_pill)

    # Place onto 256x64 canvas centered
    canvas = np.zeros((H, W, 4), dtype=np.uint8)
    px0 = (W - pill_w) // 2
    py0 = (H - pill_h) // 2
    canvas[py0:py0 + pill_h, px0:px0 + pill_w] = arr_pill

    # 1px outline (dark) around pill
    outline_color = tuple(max(0, c - 80) for c in color1) + (255,)
    out_arr = canvas.copy()
    for y in range(H):
        for x in range(W):
            if canvas[y, x, 3] == 0:
                # Check 4-neighbors for opaque pill pixel
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and canvas[ny, nx, 3] > 0:
                        out_arr[y, x] = outline_color
                        break

    img = Image.fromarray(out_arr)
    out_path = os.path.join(OUT_DIR, f"wellsetups_ranks_{rank_id}.png")
    img.save(out_path)
    return out_path


if __name__ == "__main__":
    # Special: solomon and osiris use gradient between two colors
    GRADIENT_RANKS = {"solomon", "osiris"}
    print(f"Generating {len(RANKS)} rank icons...")
    for rank_id, name, c1, c2 in RANKS:
        is_gradient = rank_id in GRADIENT_RANKS
        path = generate_rank(rank_id, name, c1, c2, gradient=is_gradient)
        print(f"  {os.path.basename(path)}  {c1}{'→' + str(c2) if is_gradient else ''}")
    print(f"\nAll saved to {OUT_DIR}")
