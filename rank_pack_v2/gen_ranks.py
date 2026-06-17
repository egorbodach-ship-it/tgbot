"""
Procedural pixel-art rank chevron generator.

Воссоздаёт стиль WellSetups Rank Pack (101x20 пиксельные шевроны),
но с твоей цветовой схемой и кастомными названиями.

Каждый шеврон:
  - Форма: прямоугольник + треугольный «острый» хвост слева
  - Заливка основным цветом + градиент (highlight сверху, shadow снизу)
  - Тёмная обводка по контуру (1px)
  - Белый pixel-font текст с тёмной обводкой по центру
  - Для Solomon / Osiris — горизонтальный градиент между двумя цветами

Все картинки сохраняются в /projects/sandbox/tgbot/rank_pack_v2/Ranks/
"""
import os
import numpy as np
from PIL import Image

OUT_DIR = "/projects/sandbox/tgbot/rank_pack_v2/Ranks"
PREVIEW_DIR = "/projects/sandbox/tgbot/rank_pack_v2/output"
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)

W, H = 101, 20

# id, display name, color1 (primary), color2 (gradient/highlight),
# is_horizontal_gradient
RANKS = [
    ("owner",   "OWNER",   (255, 200, 0),   (255, 235, 130), False),  # gold/orange
    ("admin",   "ADMIN",   (215, 35, 35),   (255, 110, 110), False),  # crimson red
    ("dadmin",  "D.ADMIN", (155, 60, 220),  (200, 130, 255), False),  # purple
    ("solomon", "SOLOMON", (255, 215, 30),  (255, 130, 30),  True),   # yellow→orange gradient
    ("osiris",  "OSIRIS",  (220, 35, 35),   (255, 255, 255), True),   # red→white gradient
    ("phonix",  "PHONIX",  (35, 105, 230),  (130, 175, 255), False),  # blue
    ("nebula",  "NEBULA",  (45, 180, 80),   (130, 230, 140), False),  # green
    ("triton",  "TRITON",  (255, 220, 50),  (255, 245, 150), False),  # yellow
    ("hydra",   "HYDRA",   (255, 135, 30),  (255, 185, 100), False),  # orange
    ("aqua",    "AQUA",    (70, 195, 240),  (160, 230, 255), False),  # cyan/aqua
    ("morph",   "MORPH",   (255, 110, 185), (255, 175, 220), False),  # pink
    ("axolot",  "AXOLOT",  (220, 50, 50),   (255, 110, 110), False),  # red
    ("vernal",  "VERNAL",  (140, 90, 45),   (190, 140, 80),  False),  # brown
]


# 5x7 пиксельный шрифт. Каждая буква — 5 широких / 7 высоких бит.
FONT_5x7 = {
    'A': ['01110','10001','10001','11111','10001','10001','10001'],
    'B': ['11110','10001','10001','11110','10001','10001','11110'],
    'C': ['01111','10000','10000','10000','10000','10000','01111'],
    'D': ['11110','10001','10001','10001','10001','10001','11110'],
    'E': ['11111','10000','10000','11110','10000','10000','11111'],
    'F': ['11111','10000','10000','11110','10000','10000','10000'],
    'G': ['01111','10000','10000','10011','10001','10001','01111'],
    'H': ['10001','10001','10001','11111','10001','10001','10001'],
    'I': ['11111','00100','00100','00100','00100','00100','11111'],
    'J': ['00111','00010','00010','00010','00010','10010','01100'],
    'K': ['10001','10010','10100','11000','10100','10010','10001'],
    'L': ['10000','10000','10000','10000','10000','10000','11111'],
    'M': ['10001','11011','10101','10101','10001','10001','10001'],
    'N': ['10001','11001','10101','10101','10011','10001','10001'],
    'O': ['01110','10001','10001','10001','10001','10001','01110'],
    'P': ['11110','10001','10001','11110','10000','10000','10000'],
    'Q': ['01110','10001','10001','10001','10101','10010','01101'],
    'R': ['11110','10001','10001','11110','10100','10010','10001'],
    'S': ['01111','10000','10000','01110','00001','00001','11110'],
    'T': ['11111','00100','00100','00100','00100','00100','00100'],
    'U': ['10001','10001','10001','10001','10001','10001','01110'],
    'V': ['10001','10001','10001','10001','10001','01010','00100'],
    'W': ['10001','10001','10001','10001','10101','11011','10001'],
    'X': ['10001','10001','01010','00100','01010','10001','10001'],
    'Y': ['10001','10001','10001','01010','00100','00100','00100'],
    'Z': ['11111','00001','00010','00100','01000','10000','11111'],
    '.': ['00000','00000','00000','00000','00000','01100','01100'],
    ' ': ['00000','00000','00000','00000','00000','00000','00000'],
}


def lerp(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def darken(c, factor=0.45):
    return tuple(max(0, int(v * factor)) for v in c)


def lighten(c, factor=1.35):
    return tuple(min(255, int(v * factor)) for v in c)


def make_chevron_shape(width, height):
    """Возвращает 2D bool маску формы шеврона.

    Форма — прямоугольник 101x20 с треугольным «остриём» слева
    (как у админ-шеврона WellSetups: левая сторона входит в точку, правая ровная).
    """
    mask = np.zeros((height, width), dtype=bool)
    # Острие шеврона — на левом краю.
    # Вершина треугольника находится на (0, height/2 - 0.5).
    # Он расширяется до полной высоты к x = tip_w.
    tip_w = 6  # ширина клина-острия
    cy = (height - 1) / 2.0
    for y in range(height):
        # минимальный x для этой строки
        # На вершине клина |y - cy| = 0 → x_min = 0
        # На y=0 или y=h-1 → x_min = tip_w (полная высота уже)
        rel = abs(y - cy) / cy   # 0..1
        x_min = int(round(tip_w * (1 - rel)))
        # инвертируем — клин обращён остриём ВЛЕВО:
        # x_min = (1 - rel) * tip_w → в центре по высоте x_min=tip_w (макс)
        # это даёт стрелку острием влево, основанием вправо.
        # Проверим:
        # rel=0 (центр) → x_min = tip_w  → пустой клин слева до tip_w
        # rel=1 (край)  → x_min = 0      → полная ширина
        # Это даёт ОБРАТНУЮ стрелку (как «<» открытое влево). Не то.
        # Нам нужно острие слева — т.е. в центре по высоте x_min=0,
        # на верх/низ x_min растёт.
        x_min_correct = int(round(tip_w * rel))
        for x in range(x_min_correct, width):
            mask[y, x] = True
    return mask


def fill_with_gradient(arr, mask, color1, color2, horizontal=False):
    """Заполняет mask внутри arr вертикальным или горизонтальным градиентом.

    Вертикальный: color1 вверху → color2 внизу (highlight→shadow по факту,
        но тут используем как general-purpose).
    Горизонтальный: color1 слева → color2 справа.
    """
    h, w = mask.shape
    for y in range(h):
        for x in range(w):
            if not mask[y, x]:
                continue
            if horizontal:
                t = x / max(1, w - 1)
            else:
                t = y / max(1, h - 1)
            r, g, b = lerp(color1, color2, t)
            arr[y, x] = (r, g, b, 255)


def add_emboss(arr, mask, base_color):
    """Добавляет верхний highlight (1px) и нижнюю тень (1px) внутри маски."""
    h, w = mask.shape
    hi = lighten(base_color, 1.45)
    sh = darken(base_color, 0.6)
    for y in range(h):
        for x in range(w):
            if not mask[y, x]:
                continue
            # верхняя кромка: первая опаковая ячейка сверху в этом столбце
            top_edge = (y == 0) or (not mask[y - 1, x])
            if top_edge and y < h - 2:
                # рисуем 1px поверх существующего цвета — смешиваем
                cur = arr[y, x]
                arr[y, x] = (
                    (int(cur[0]) + hi[0]) // 2,
                    (int(cur[1]) + hi[1]) // 2,
                    (int(cur[2]) + hi[2]) // 2,
                    255,
                )
            bot_edge = (y == h - 1) or (not mask[y + 1, x])
            if bot_edge and y > 1:
                cur = arr[y, x]
                arr[y, x] = (
                    (int(cur[0]) + sh[0]) // 2,
                    (int(cur[1]) + sh[1]) // 2,
                    (int(cur[2]) + sh[2]) // 2,
                    255,
                )


def add_outline(arr, mask, color):
    """Добавляет 1px тёмную обводку по контуру маски (за пределами маски)."""
    h, w = mask.shape
    out = arr.copy()
    for y in range(h):
        for x in range(w):
            if mask[y, x]:
                continue
            # Если рядом есть пиксель маски — это контур
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx]:
                    out[y, x] = (color[0], color[1], color[2], 255)
                    break
    return out


def draw_text_on(arr, mask, text):
    """Рисует pixel-font текст белым, с тёмной 1px обводкой, по центру маски.

    Текст пишется в зоне после острия шеврона, выровнен по центру высоты.
    """
    h, w = mask.shape
    LW, LH, SP = 5, 7, 1
    chars = list(text.upper())
    total_w = sum(LW for _ in chars) + max(0, len(chars) - 1) * SP

    # Зона для текста — прямоугольная часть после клина (x ≥ 7).
    text_zone_x_start = 7
    text_zone_w = w - text_zone_x_start - 2  # 2px справа на хвост/обводку

    # Если текст шире зоны — пробуем без межбуквенных промежутков
    if total_w > text_zone_w:
        SP = 0
        total_w = sum(LW for _ in chars) + max(0, len(chars) - 1) * SP

    x_start = text_zone_x_start + (text_zone_w - total_w) // 2
    y_start = (h - LH) // 2  # 6 для h=20 → текст 6..12

    # Сначала тёмная обводка вокруг каждого пикселя
    pixels_to_draw = []
    px = x_start
    for ch in chars:
        glyph = FONT_5x7.get(ch)
        if not glyph:
            px += LW + SP
            continue
        for ry, row in enumerate(glyph):
            for rx, c in enumerate(row):
                if c == '1':
                    yy = y_start + ry
                    xx = px + rx
                    if 0 <= xx < w and 0 <= yy < h and mask[yy, xx]:
                        pixels_to_draw.append((yy, xx))
        px += LW + SP

    # Обводка
    for (yy, xx) in pixels_to_draw:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = yy + dy, xx + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx]:
                    # не перезатирать уже белые буквы
                    if (ny, nx) not in pixels_to_draw:
                        arr[ny, nx] = (0, 0, 0, 255)
    # Сами буквы
    for (yy, xx) in pixels_to_draw:
        arr[yy, xx] = (255, 255, 255, 255)


def generate_rank(rank_id, name, color1, color2, h_grad):
    """Генерирует одну PNG-иконку и сохраняет."""
    arr = np.zeros((H, W, 4), dtype=np.uint8)
    mask = make_chevron_shape(W, H)
    fill_with_gradient(arr, mask, color1, color2, horizontal=h_grad)
    add_emboss(arr, mask, color1 if not h_grad else lerp(color1, color2, 0.5))
    arr = add_outline(arr, mask, darken(color1, 0.35))
    draw_text_on(arr, mask, name)

    img = Image.fromarray(arr, mode='RGBA')
    out_path = os.path.join(OUT_DIR, f"wellsetups_ranks_{rank_id}.png")
    img.save(out_path)
    return out_path


def make_preview():
    """Собирает preview-png со всеми рангами в столбик."""
    upscale = 4
    pad = 8
    label_h = 20
    cell_w = W * upscale + 220
    cell_h = H * upscale + label_h + pad
    cols = 1
    rows = len(RANKS)
    canvas = Image.new('RGBA', (cell_w + 40, rows * cell_h + 40), (28, 28, 28, 255))
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype(
            '/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf', 16)
    except Exception:
        font = ImageFont.load_default()

    for i, (rid, name, c1, c2, h_grad) in enumerate(RANKS):
        path = os.path.join(OUT_DIR, f"wellsetups_ranks_{rid}.png")
        img = Image.open(path).convert('RGBA')
        big = img.resize((img.width * upscale, img.height * upscale), Image.NEAREST)
        x = 20
        y = 20 + i * cell_h
        canvas.paste(big, (x, y + label_h), big)
        draw.text((x, y), f"{name}  ({rid})", fill=(255, 255, 255, 255), font=font)

    out = os.path.join(PREVIEW_DIR, 'all_ranks_preview.png')
    canvas.save(out)
    return out


if __name__ == "__main__":
    print(f"Generating {len(RANKS)} chevron icons (101x20)...")
    for rid, name, c1, c2, h_grad in RANKS:
        path = generate_rank(rid, name, c1, c2, h_grad)
        marker = " [H-grad]" if h_grad else ""
        print(f"  {os.path.basename(path):40s} {c1} → {c2}{marker}")
    print()
    preview = make_preview()
    print(f"Preview: {preview}")
    print(f"All ranks saved to: {OUT_DIR}")
