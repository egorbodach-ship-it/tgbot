"""
SolomonGrief themed menu generator.
King Solomon / medieval / biblical aesthetic:
  - Star of David (Seal of Solomon) corner ornaments
  - Crown above title plate
  - Gothic arches on top and bottom edges
  - Royal palette: gold + crimson + dark wood
"""
import os
import numpy as np
from PIL import Image

W, H = 256, 256
CX0, CX1 = 0, 168
CY0, CY1 = 18, 143

PAL = {
    "stone_dk":   (45, 30, 20, 255),
    "stone_base": (75, 55, 40, 255),
    "stone_lt":   (110, 85, 60, 255),
    "frame_outer": (30, 15, 5, 255),
    "frame_dk":    (90, 35, 10, 255),
    "frame_gold":  (200, 160, 60, 255),
    "frame_glow":  (255, 215, 100, 255),
    "plate_dk":    (180, 30, 10, 255),    # deep red
    "plate_mid":   (230, 80, 20, 255),    # red-orange
    "plate_lt":    (255, 165, 50, 255),   # bright orange
    "plate_glow":  (255, 220, 100, 255),  # yellow-orange glow
    "plate_outline": (60, 15, 5, 255),
    "gold":        (220, 180, 70, 255),
    "gold_lt":     (255, 220, 110, 255),
    "white":       (255, 255, 255, 255),
}


def init_canvas():
    return np.zeros((H, W, 4), dtype=np.uint8)


def draw_stone_bg(arr):
    rng = np.random.RandomState(42)
    for y in range(CY0+3, CY1-3):
        for x in range(CX0+3, CX1-3):
            n = rng.randint(0, 100)
            if n < 4:
                c = PAL["stone_dk"]
            elif n < 12:
                c = PAL["stone_lt"]
            else:
                c = PAL["stone_base"]
            arr[y, x] = c
    # Brick lines
    for y_brick in range(CY0+3+15, CY1-3, 16):
        for x in range(CX0+3, CX1-3):
            arr[y_brick, x] = PAL["stone_dk"]
    for row_idx, y_start in enumerate(range(CY0+3, CY1-3, 16)):
        offset = 0 if row_idx % 2 == 0 else 16
        for x_brick in range(CX0+3+offset, CX1-3, 32):
            for dy in range(min(15, CY1-3-y_start)):
                yy = y_start + dy
                if 0 <= x_brick < W and 0 <= yy < H and arr[yy, x_brick, 3] != 0:
                    arr[yy, x_brick] = PAL["stone_dk"]


def draw_outer_frame(arr):
    for x in range(CX0, CX1):
        arr[CY0, x] = PAL["frame_outer"]
        arr[CY1-1, x] = PAL["frame_outer"]
    for y in range(CY0, CY1):
        arr[y, CX0] = PAL["frame_outer"]
        arr[y, CX1-1] = PAL["frame_outer"]
    for x in range(CX0+1, CX1-1):
        arr[CY0+1, x] = PAL["gold"]
        arr[CY1-2, x] = PAL["gold"]
    for y in range(CY0+1, CY1-1):
        arr[y, CX0+1] = PAL["gold"]
        arr[y, CX1-2] = PAL["gold"]
    for x in range(CX0+2, CX1-2):
        arr[CY0+2, x] = PAL["frame_dk"]
        arr[CY1-3, x] = PAL["frame_dk"]
    for y in range(CY0+2, CY1-2):
        arr[y, CX0+2] = PAL["frame_dk"]
        arr[y, CX1-3] = PAL["frame_dk"]


def draw_star(arr, cx, cy, size=4):
    """Six-pointed Star of David — two overlapping triangles."""
    for s in range(size + 1):
        for x_off in range(-s, s + 1):
            y = cy - size + s
            x = cx + x_off
            if abs(x_off) <= s and 0 <= x < W and 0 <= y < H:
                arr[y, x] = PAL["gold_lt"] if s == 0 else PAL["gold"]
        for x_off in range(-s, s + 1):
            y = cy + size - s
            x = cx + x_off
            if abs(x_off) <= s and 0 <= x < W and 0 <= y < H:
                cur = tuple(arr[y, x][:3])
                if cur != PAL["gold_lt"][:3]:
                    arr[y, x] = PAL["gold"]
    arr[cy, cx] = PAL["frame_glow"]


def draw_corners(arr):
    draw_star(arr, CX0+10, CY0+10, size=5)
    draw_star(arr, CX1-11, CY0+10, size=5)
    draw_star(arr, CX0+10, CY1-11, size=5)
    draw_star(arr, CX1-11, CY1-11, size=5)


def draw_crown(arr, cx, cy):
    crown_pat = [
        "  X     X     X  ",
        " XX    XXX    XX ",
        " XX    XXX    XX ",
        "XXXXXXXXXXXXXXXXX",
        "XX...XX...XX...XX",
        "XXXXXXXXXXXXXXXXX",
    ]
    for ry, row in enumerate(crown_pat):
        for rx, ch in enumerate(row):
            xx = cx - len(row)//2 + rx
            yy = cy + ry
            if 0 <= xx < W and 0 <= yy < H:
                if ch == "X":
                    if ry < 3:
                        arr[yy, xx] = PAL["gold_lt"] if ry == 0 else PAL["gold"]
                    else:
                        arr[yy, xx] = PAL["gold"] if ry in (3, 5) else PAL["frame_dk"]
                elif ch == ".":
                    arr[yy, xx] = PAL["plate_outline"]


def draw_arch(arr):
    arch_y = CY0 + 6
    for cx in [42, 60, 84, 108, 126]:
        for ry in range(4):
            for rx in range(-2, 3):
                xx = cx + rx
                yy = arch_y + ry
                if 0 <= xx < W and 0 <= yy < H:
                    if ry == 0 and abs(rx) <= 1:
                        arr[yy, xx] = PAL["gold"]
                    elif ry in (1, 2) and abs(rx) == 2:
                        arr[yy, xx] = PAL["gold"]
                    elif ry == 3 and abs(rx) <= 2:
                        arr[yy, xx] = PAL["frame_dk"]
    cy = CY1 - 8
    for cx in [42, 60, 84, 108, 126]:
        arr[cy, cx] = PAL["gold"]
        arr[cy+1, cx] = PAL["gold"]
        arr[cy+2, cx] = PAL["gold"]
        arr[cy+1, cx-1] = PAL["gold"]
        arr[cy+1, cx+1] = PAL["gold"]


def draw_plate(arr, x0=22, y0=22, x1=146, y1=34):
    for x in range(x0, x1):
        arr[y0, x] = PAL["plate_outline"]
        arr[y1-1, x] = PAL["plate_outline"]
    for y in range(y0, y1):
        arr[y, x0] = PAL["plate_outline"]
        arr[y, x1-1] = PAL["plate_outline"]
    for x in range(x0+1, x1-1):
        arr[y0+1, x] = PAL["gold"]
        arr[y1-2, x] = PAL["gold"]
    for y in range(y0+1, y1-1):
        arr[y, x0+1] = PAL["gold"]
        arr[y, x1-2] = PAL["gold"]
    # Vertical gradient: top = bright yellow-orange, middle = orange, bottom = deep red
    # Plus subtle horizontal variation for "fire" feel
    for y in range(y0+2, y1-2):
        t = (y - y0 - 2) / max(1, y1 - y0 - 4)
        if t < 0.3:
            f = t / 0.3
            r = int(PAL["plate_glow"][0] * (1-f) + PAL["plate_lt"][0] * f)
            g = int(PAL["plate_glow"][1] * (1-f) + PAL["plate_lt"][1] * f)
            b = int(PAL["plate_glow"][2] * (1-f) + PAL["plate_lt"][2] * f)
        elif t < 0.7:
            f = (t - 0.3) / 0.4
            r = int(PAL["plate_lt"][0] * (1-f) + PAL["plate_mid"][0] * f)
            g = int(PAL["plate_lt"][1] * (1-f) + PAL["plate_mid"][1] * f)
            b = int(PAL["plate_lt"][2] * (1-f) + PAL["plate_mid"][2] * f)
        else:
            f = (t - 0.7) / 0.3
            r = int(PAL["plate_mid"][0] * (1-f) + PAL["plate_dk"][0] * f)
            g = int(PAL["plate_mid"][1] * (1-f) + PAL["plate_dk"][1] * f)
            b = int(PAL["plate_mid"][2] * (1-f) + PAL["plate_dk"][2] * f)
        for x in range(x0+2, x1-2):
            arr[y, x] = (r, g, b, 255)
    mid_y = (y0 + y1) // 2
    draw_star(arr, x0 - 3, mid_y, size=2)
    draw_star(arr, x1 + 2, mid_y, size=2)


# Bold 7x9 font — clear distinct shapes for Cyrillic
# Each letter designed to be unambiguous: М has clear V dip, Н has flat crossbar,
# Ц has clear descender hook, И has diagonal stroke, etc.
FONT = {
    'А': ['0011100','0111110','1100011','1100011','1111111','1111111','1100011','1100011','1100011'],
    'У': ['1100011','1100011','1100011','0111110','0011100','0001100','0011000','0110000','1100000'],
    'К': ['1100011','1100110','1101100','1111000','1111000','1101100','1100110','1100011','1100011'],
    'Ц': ['1100011','1100011','1100011','1100011','1100011','1100011','1100011','1111111','0000011'],  # descender hook
    'И': ['1100011','1100011','1100111','1101111','1111011','1111011','1110011','1100011','1100011'],  # diagonal /
    'О': ['0111110','1111111','1100011','1100011','1100011','1100011','1100011','1111111','0111110'],
    'Н': ['1100011','1100011','1100011','1111111','1111111','1100011','1100011','1100011','1100011'],  # flat crossbar
    'М': ['1100011','1110111','1111111','1101011','1100011','1100011','1100011','1100011','1100011'],  # V dip in top
    'Е': ['1111111','1100000','1100000','1111110','1111110','1100000','1100000','1100000','1111111'],
    'Ю': ['1101110','1101111','1101111','1111111','1111111','1101111','1101111','1101111','1101110'],
    'П': ['1111111','1100011','1100011','1100011','1100011','1100011','1100011','1100011','1100011'],
    'Д': ['0111110','0110110','0110110','0110110','0110110','0110110','0110110','1111111','1100011'],
    'Т': ['1111111','0011100','0011100','0011100','0011100','0011100','0011100','0011100','0011100'],
    'С': ['0111110','1111111','1100011','1100000','1100000','1100000','1100011','1111111','0111110'],
    'Р': ['1111110','1100011','1100011','1100011','1111110','1100000','1100000','1100000','1100000'],
    'В': ['1111110','1100011','1100011','1100011','1111110','1100011','1100011','1100011','1111110'],
    'З': ['1111110','0000011','0000011','0011110','0011110','0000011','0000011','0000011','1111110'],
    'Б': ['1111111','1100000','1100000','1111110','1111111','1100011','1100011','1100011','1111110'],
    'Г': ['1111111','1100011','1100000','1100000','1100000','1100000','1100000','1100000','1100000'],
    'Я': ['0111111','1100011','1100011','1100011','0111111','0011011','0110011','1100011','1100011'],
    ' ': ['0000000']*9,
}


def draw_text(arr, text, x0=22, x1=146, y_start=23):
    """Draw chunky bold white letters with dark shadow under each pixel for crispness."""
    LW, LH, SP = 7, 9, 1
    chars = list(text.upper())
    total_w = sum(LW for _ in chars) + max(0, len(chars) - 1) * SP
    px = (x0 + x1) // 2 - total_w // 2
    
    # Pass 1: shadow (1px down + right) to make letters pop on red plate
    for ch in chars:
        glyph = FONT.get(ch)
        if glyph:
            for ry, row in enumerate(glyph):
                for rx, c in enumerate(row):
                    if c == '1':
                        xx, yy = px + rx + 1, y_start + ry + 1
                        if 0 <= xx < W and 0 <= yy < H and arr[yy, xx, 3] != 0:
                            cur = arr[yy, xx]
                            # Darken to make shadow
                            arr[yy, xx] = (
                                max(0, int(cur[0] * 0.3)),
                                max(0, int(cur[1] * 0.3)),
                                max(0, int(cur[2] * 0.3)),
                                255
                            )
        px += LW + SP
    
    # Pass 2: white letters on top (full 255,255,255)
    px = (x0 + x1) // 2 - total_w // 2
    for ch in chars:
        glyph = FONT.get(ch)
        if glyph:
            for ry, row in enumerate(glyph):
                for rx, c in enumerate(row):
                    if c == '1':
                        xx, yy = px + rx, y_start + ry
                        if 0 <= xx < W and 0 <= yy < H:
                            arr[yy, xx] = PAL["white"]
        px += LW + SP


def draw_cells(arr, slots, scale=268/256, shift_px=-8, base_y=36):
    for slot in slots:
        row, col = slot // 9, slot % 9
        mc_x = -1 - shift_px + col * 18
        mc_y = base_y + row * 18
        x0 = int(round(mc_x / scale))
        y0 = int(round(mc_y / scale))
        cs = int(round(16 / scale))
        x1, y1 = x0 + cs, y0 + cs
        if x1 > W or y1 > H or x0 < 0 or y0 < 0: continue
        ix0, iy0 = x0+1, y0+1
        ix1, iy1 = x1-1, y1-1
        cell = arr[iy0:iy1, ix0:ix1, :3].astype(float)
        if cell.size == 0: continue
        avg = cell.mean(axis=(0,1))
        f = (avg * 0.50).clip(0,255).astype(np.uint8)
        e = (avg * 0.25).clip(0,255).astype(np.uint8)
        arr[iy0:iy1, ix0:ix1, :3] = f
        arr[iy0, ix0:ix1, :3] = e
        arr[iy1-1, ix0:ix1, :3] = e
        arr[iy0:iy1, ix0, :3] = e
        arr[iy0:iy1, ix1-1, :3] = e


def generate(text="МЕНЮ", slots=None, height=268, shift_px=-8):
    arr = init_canvas()
    draw_stone_bg(arr)
    draw_outer_frame(arr)
    draw_corners(arr)
    draw_arch(arr)
    draw_plate(arr)
    draw_crown(arr, 84, 13)
    draw_text(arr, text)
    if slots:
        scale = height / 256
        draw_cells(arr, slots, scale, shift_px=shift_px)
    return arr


if __name__ == "__main__":
    out_dir = "/projects/sandbox/tgbot/generator/output"
    os.makedirs(out_dir, exist_ok=True)
    
    Image.fromarray(generate(text="", slots=None)).save(f"{out_dir}/solomon_empty.png")
    Image.fromarray(generate(text="МЕНЮ", slots=[10,12,14,16,19,21,23,25,30,32], height=280, shift_px=-16)).save(f"{out_dir}/solomon_menu.png")
    Image.fromarray(generate(text="АУКЦИОН", slots=list(range(45)))).save(f"{out_dir}/solomon_aukcion.png")
    Image.fromarray(generate(text="ДОНАТ", slots=[10,11,12,13,14,15,16,28,32], height=280, shift_px=-16)).save(f"{out_dir}/solomon_donat.png")
    
    imgs = [
        (Image.open(f"{out_dir}/solomon_empty.png").crop((0, 18, 168, 143)), "EMPTY"),
        (Image.open(f"{out_dir}/solomon_menu.png").crop((0, 18, 168, 143)), "MENU"),
        (Image.open(f"{out_dir}/solomon_aukcion.png").crop((0, 18, 168, 143)), "AUKCION"),
        (Image.open(f"{out_dir}/solomon_donat.png").crop((0, 18, 168, 143)), "DONAT"),
    ]
    SCALE = 3
    iw, ih = imgs[0][0].width * SCALE, imgs[0][0].height * SCALE
    combo = Image.new("RGBA", (iw + 40, (ih + 25) * len(imgs)), (25, 20, 15, 255))
    y = 10
    for im, _ in imgs:
        big = im.resize((iw, ih), Image.NEAREST)
        combo.paste(big, (20, y), big)
        y += ih + 25
    combo.save(f"{out_dir}/solomon_preview.png")
    print(f"Saved {combo.size}")
