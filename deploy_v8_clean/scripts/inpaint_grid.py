"""
Take v7 orange textures, surgically remove ONLY the gray grid lines (RGB ~60,60,60),
replacing them with the smooth interior brown/orange gradient.

Keeps EVERYTHING else 1:1 — frame, title, decorative cells, gradient.
"""
import os
import numpy as np
from PIL import Image

IN_DIR = "/home/ubuntu/repos/tgbot/deploy_v7_final/orange_textures"
OUT_DIR = "/home/ubuntu/repos/tgbot/deploy_v8_clean/textures_inpaint"
os.makedirs(OUT_DIR, exist_ok=True)


def is_gray_grid_pixel(r, g, b):
    """The grid separator pixels are roughly RGB(60,60,60) — gray, balanced channels."""
    return (
        45 <= r <= 75
        and 45 <= g <= 75
        and 45 <= b <= 75
        and abs(int(r) - int(g)) < 12
        and abs(int(g) - int(b)) < 12
    )


def inpaint(path_in, path_out):
    img = Image.open(path_in).convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)

    gray_mask = (
        (r >= 45) & (r <= 75)
        & (g >= 45) & (g <= 75)
        & (b >= 45) & (b <= 75)
        & (np.abs(r - g) < 12)
        & (np.abs(g - b) < 12)
    )

    # We only inpaint pixels inside the content area where alpha > 0.
    alpha = arr[:, :, 3]
    target_mask = gray_mask & (alpha > 0)

    if not target_mask.any():
        # Nothing to do
        img.save(path_out)
        return 0

    # For each gray pixel, find the nearest non-gray, non-frame pixel
    # in each of 4 cardinal directions, then average.
    out = arr.copy()
    rgb = arr[:, :, :3].astype(int)

    # Non-grid pixels (interior brown/orange, but NOT the frame, NOT title white)
    # We just want: any non-gray pixel with alpha > 0. We'll let it average so
    # frame leaking near grid lines is rare (frame is 5+ pixels away from
    # most grid lines).
    valid = (~gray_mask) & (alpha > 0)

    ys, xs = np.where(target_mask)
    for y, x in zip(ys, xs):
        samples = []
        # up
        for dy in range(1, 8):
            yy = y - dy
            if yy < 0:
                break
            if valid[yy, x]:
                samples.append(rgb[yy, x])
                break
        # down
        for dy in range(1, 8):
            yy = y + dy
            if yy >= h:
                break
            if valid[yy, x]:
                samples.append(rgb[yy, x])
                break
        # left
        for dx in range(1, 8):
            xx = x - dx
            if xx < 0:
                break
            if valid[y, xx]:
                samples.append(rgb[y, xx])
                break
        # right
        for dx in range(1, 8):
            xx = x + dx
            if xx >= w:
                break
            if valid[y, xx]:
                samples.append(rgb[y, xx])
                break

        if samples:
            avg = np.mean(samples, axis=0).round().astype(np.uint8)
            out[y, x, 0] = avg[0]
            out[y, x, 1] = avg[1]
            out[y, x, 2] = avg[2]
            # alpha unchanged

    Image.fromarray(out).save(path_out)
    return int(target_mask.sum())


if __name__ == "__main__":
    total = 0
    for name in sorted(os.listdir(IN_DIR)):
        if not name.endswith(".png"):
            continue
        n = inpaint(os.path.join(IN_DIR, name), os.path.join(OUT_DIR, name))
        total += n
        print(f"  {name}: {n} gray pixels replaced")
    print(f"\nTotal: {total} gray pixels removed across {len(os.listdir(IN_DIR))} files")
