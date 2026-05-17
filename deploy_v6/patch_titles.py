#!/usr/bin/env python3
"""Patch all menu_titles on the server to add shift prefixes."""
import urllib.parse
import subprocess
import re
import sys
import time

KEY = "ptlc_q1LTOfeHyId0pGueJl1WQMYKfK6nqXngMuqcgKRgbQd"
BASE = "https://mgr.hosting-minecraft.pro/api/client/servers/944c2567"

# IMPORTANT: Must use null.png-based shift glyphs, NOT space.png-based!
# space.png is fully transparent (alpha=0) → MC 1.16.5 BitmapProvider
# computes char_width=0 → advance=+1 (no shift at all!).
# null.png is opaque white → char_width=1 → advance works correctly.
SHIFT8 = "\u0BED"  # shift -8 (null.png, h=-10)
SHIFT4 = "\u0BEC"  # shift -4 (null.png, h=-6)

# Menu glyph codepoints from pack default.json
MENU_GLYPHS = {
    "menu":      "\u0BCB",  # h=280, needs -12 shift
    "donate":    "\u0BCC",
    "shop":      "\u0BCD",
    "events":    "\u0BCE",
    "help":      "\u0BCF",
    "portals":   "\u0BD0",
    "rtp":       "\u0BD1",
    "obmen":     "\u0BD2",
    "arenda":    "\u0BD3",
    "grab":      "\u0BD4",
    "media":     "\u0BD5",
    "freek":     "\u0BD6",
    "panel":     "\u0BD7",
    "akriwer":   "\u0BD9",
    "arrow":     "\u0BDA",
    "egg":       "\u0BDB",
    "items":     "\u0BDC",
    "livalka":   "\u0BDD",
    "potions":   "\u0BDE",
    "pred":      "\u0BDF",
    "pve":       "\u0BE0",
    "pveother":  "\u0BE1",
    "resmenu":   "\u0BE2",
    "reseuro":   "\u0BE3",
    "resmoneta": "\u0BE4",
    "shari":     "\u0BE5",
    "spawners":  "\u0BE6",
    "aukcion":   "\u0BE7",
    "cases":     "\u0BE8",
    "skupschik": "\u0BE9",
}

# DeluxeMenus files: (menu_name, server_path)
# IMPORTANT: DM reads from BOTH menu/ AND gui_menus/ directories.
# gui_menus/ is the primary auto-scanned dir; menu/ is referenced by config.yml.
# We must patch BOTH to ensure consistency.
DM_FILES = [
    # --- menu/ (referenced by config.yml file: directives) ---
    ("menu",      "/plugins/DeluxeMenus/menu/menu.yml"),
    ("donate",    "/plugins/DeluxeMenus/menu/donate.yml"),
    ("events",    "/plugins/DeluxeMenus/menu/events.yml"),
    ("help",      "/plugins/DeluxeMenus/menu/help.yml"),
    ("portals",   "/plugins/DeluxeMenus/menu/portals.yml"),
    ("rtp",       "/plugins/DeluxeMenus/menu/rtp.yml"),
    ("obmen",     "/plugins/DeluxeMenus/menu/obmen.yml"),
    ("arenda",    "/plugins/DeluxeMenus/menu/arenda.yml"),
    ("grab",      "/plugins/DeluxeMenus/menu/grab.yml"),
    ("media",     "/plugins/DeluxeMenus/menu/media.yml"),
    ("panel",     "/plugins/DeluxeMenus/menu/panel.yml"),
    ("akriwer",   "/plugins/DeluxeMenus/menu/akriwer.yml"),
    ("freek",     "/plugins/DeluxeMenus/menu/freek.yml"),
    ("shop",      "/plugins/DeluxeMenus/shop/donateSHOP.yml"),
    ("arrow",     "/plugins/DeluxeMenus/shop/donateARROW.yml"),
    ("egg",       "/plugins/DeluxeMenus/shop/donateEGG.yml"),
    ("items",     "/plugins/DeluxeMenus/shop/donateITEMS2.yml"),
    ("livalka",   "/plugins/DeluxeMenus/shop/donateLIVALKA.yml"),
    ("potions",   "/plugins/DeluxeMenus/shop/donatePOTIONS.yml"),
    ("pred",      "/plugins/DeluxeMenus/shop/donatePRED.yml"),
    ("pve",       "/plugins/DeluxeMenus/shop/donatePVE.yml"),
    ("pveother",  "/plugins/DeluxeMenus/shop/donatePVEOTHER.yml"),
    ("resmenu",   "/plugins/DeluxeMenus/shop/donateRESMENU.yml"),
    ("reseuro",   "/plugins/DeluxeMenus/shop/donateRESEURO.yml"),
    ("resmoneta", "/plugins/DeluxeMenus/shop/donateRESMONETA.yml"),
    ("shari",     "/plugins/DeluxeMenus/shop/donateSHARI.yml"),
    ("spawners",  "/plugins/DeluxeMenus/shop/donateSPAWNERS.yml"),
    # --- gui_menus/ (DM auto-scans this directory) ---
    ("menu",      "/plugins/DeluxeMenus/gui_menus/menu/menu.yml"),
    ("donate",    "/plugins/DeluxeMenus/gui_menus/menu/donate.yml"),
    ("events",    "/plugins/DeluxeMenus/gui_menus/menu/events.yml"),
    ("help",      "/plugins/DeluxeMenus/gui_menus/menu/help.yml"),
    ("portals",   "/plugins/DeluxeMenus/gui_menus/menu/portals.yml"),
    ("rtp",       "/plugins/DeluxeMenus/gui_menus/menu/rtp.yml"),
    ("obmen",     "/plugins/DeluxeMenus/gui_menus/menu/obmen.yml"),
    ("arenda",    "/plugins/DeluxeMenus/gui_menus/menu/arenda.yml"),
    ("grab",      "/plugins/DeluxeMenus/gui_menus/menu/grab.yml"),
    ("media",     "/plugins/DeluxeMenus/gui_menus/menu/media.yml"),
    ("panel",     "/plugins/DeluxeMenus/gui_menus/menu/panel.yml"),
    ("akriwer",   "/plugins/DeluxeMenus/gui_menus/menu/akriwer.yml"),
    ("freek",     "/plugins/DeluxeMenus/gui_menus/menu/freek.yml"),
    ("shop",      "/plugins/DeluxeMenus/gui_menus/shop/donateSHOP.yml"),
    ("arrow",     "/plugins/DeluxeMenus/gui_menus/shop/donateARROW.yml"),
    ("egg",       "/plugins/DeluxeMenus/gui_menus/shop/donateEGG.yml"),
    ("items",     "/plugins/DeluxeMenus/gui_menus/shop/donateITEMS2.yml"),
    ("livalka",   "/plugins/DeluxeMenus/gui_menus/shop/donateLIVALKA.yml"),
    ("potions",   "/plugins/DeluxeMenus/gui_menus/shop/donatePOTIONS.yml"),
    ("pred",      "/plugins/DeluxeMenus/gui_menus/shop/donatePRED.yml"),
    ("pve",       "/plugins/DeluxeMenus/gui_menus/shop/donatePVE.yml"),
    ("pveother",  "/plugins/DeluxeMenus/gui_menus/shop/donatePVEOTHER.yml"),
    ("resmenu",   "/plugins/DeluxeMenus/gui_menus/shop/donateRESMENU.yml"),
    ("reseuro",   "/plugins/DeluxeMenus/gui_menus/shop/donateRESEURO.yml"),
    ("resmoneta", "/plugins/DeluxeMenus/gui_menus/shop/donateRESMONETA.yml"),
    ("shari",     "/plugins/DeluxeMenus/gui_menus/shop/donateSHARI.yml"),
    ("spawners",  "/plugins/DeluxeMenus/gui_menus/shop/donateSPAWNERS.yml"),
]

# Akriwer extras (same glyph as akriwer)
AKRIWER_EXTRA = [
    "/plugins/DeluxeMenus/menu/akriwer1.yml",
    "/plugins/DeluxeMenus/menu/akriwer2.yml",
    "/plugins/DeluxeMenus/gui_menus/menu/akriwer1.yml",
    "/plugins/DeluxeMenus/gui_menus/menu/akriwer2.yml",
]


def read_remote(path):
    enc = urllib.parse.quote(path)
    url = f"{BASE}/files/contents?file={enc}"
    r = subprocess.run(
        ["curl", "-sf", "--connect-timeout", "10", "--max-time", "30",
         "-H", f"Authorization: Bearer {KEY}", url],
        capture_output=True, timeout=35
    )
    return r.stdout.decode("utf-8", errors="replace")


def write_remote(path, content):
    enc = urllib.parse.quote(path)
    url = f"{BASE}/files/write?file={enc}"
    r = subprocess.run(
        ["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}",
         "-X", "POST",
         "-H", f"Authorization: Bearer {KEY}",
         "-H", "Content-Type: application/octet-stream",
         "--data-binary", "@-", url],
        input=content.encode("utf-8"),
        capture_output=True, timeout=35
    )
    return r.stdout.decode().strip()


def build_title(name):
    glyph = MENU_GLYPHS[name]
    if name == "menu":
        return SHIFT8 + SHIFT4 + glyph  # -12 total
    return SHIFT8 + glyph  # -8


def patch_dm_file(name, path):
    content = read_remote(path)
    if not content or content.startswith("<!DOCTYPE"):
        print(f"  SKIP {name:15s} (file not found at {path})")
        return False

    new_title = build_title(name)
    # Replace menu_title value
    new_content, n = re.subn(
        r'(menu_title:\s*["\']?)([^"\'\n]*?)(["\']?\s*)$',
        lambda m: m.group(1) + new_title + m.group(3),
        content, count=1, flags=re.MULTILINE
    )
    if n == 0:
        print(f"  WARN {name:15s} no menu_title found in {path}")
        return False

    code = write_remote(path, new_content)
    title_hex = " ".join(hex(ord(c)) for c in new_title)
    ok = code == "204"
    print(f"  {'OK' if ok else 'FAIL':4s} {name:15s} → {title_hex}  ({code})")
    return ok


def main():
    ok = 0
    fail = 0

    print("=== Patching DeluxeMenus files ===")
    for name, path in DM_FILES:
        time.sleep(0.3)  # rate limit
        if patch_dm_file(name, path):
            ok += 1
        else:
            fail += 1

    print("\n=== Patching akriwer extras ===")
    for path in AKRIWER_EXTRA:
        time.sleep(0.3)
        content = read_remote(path)
        if not content or content.startswith("<!DOCTYPE"):
            print(f"  SKIP {path} (not found)")
            continue
        new_title = build_title("akriwer")
        new_content, n = re.subn(
            r'(menu_title:\s*["\']?)([^"\'\n]*?)(["\']?\s*)$',
            lambda m: m.group(1) + new_title + m.group(3),
            content, count=1, flags=re.MULTILINE
        )
        if n == 0:
            print(f"  WARN no menu_title in {path}")
            continue
        code = write_remote(path, new_content)
        print(f"  {'OK' if code=='204' else 'FAIL':4s} akriwer_extra → {path}")
        if code == "204":
            ok += 1

    print("\n=== Patching TreasureCoCaseReloaded ===")
    time.sleep(0.3)
    cases_path = "/plugins/TreasureCoCaseReloaded/invgui.yml"
    content = read_remote(cases_path)
    if content and not content.startswith("<!DOCTYPE"):
        new_title = build_title("cases")
        # This file uses title: not menu_title:
        new_content, n = re.subn(
            r"(title:\s*['\"]?)([^'\"\n]*?)(['\"]?\s*)$",
            lambda m: m.group(1) + new_title + m.group(3),
            content, count=1, flags=re.MULTILINE
        )
        code = write_remote(cases_path, new_content)
        print(f"  {'OK' if code=='204' else 'FAIL':4s} cases (TreasureCoCase)")
        if code == "204":
            ok += 1
    else:
        print("  SKIP TreasureCoCaseReloaded (not found)")

    print("\n=== Patching sSeller ===")
    time.sleep(0.3)
    seller_path = "/plugins/sSeller/config.yml"
    content = read_remote(seller_path)
    if content and not content.startswith("<!DOCTYPE"):
        new_title = build_title("skupschik")
        # This file uses title: under menu section
        new_content, n = re.subn(
            r"(title:\s*['\"]?)([^'\"\n]*?)(['\"]?\s*)$",
            lambda m: m.group(1) + new_title + m.group(3),
            content, count=1, flags=re.MULTILINE
        )
        code = write_remote(seller_path, new_content)
        print(f"  {'OK' if code=='204' else 'FAIL':4s} skupschik (sSeller)")
        if code == "204":
            ok += 1
    else:
        print("  SKIP sSeller (not found)")

    print(f"\n=== Done: {ok} OK, {fail} failed ===")


if __name__ == "__main__":
    main()
