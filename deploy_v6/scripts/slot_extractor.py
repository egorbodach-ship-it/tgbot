"""
slot_extractor.py — read a menu YAML and return the set of slot indices
that are actually used.

Supports three plugin schemas:
  - DeluxeMenus (`size:` + `items.*.slot/slots`) -> slots_for_menu()
  - TreasureCoCaseReloaded (`<section>.schematic:` ASCII grid) -> slots_for_invgui_section()
  - sSeller (`frame.slots` + `sell_slots` + `sell_all.slot`) -> slots_for_sseller()

All public functions return (rows, sorted_list_of_used_slots).
rows in {3, 5, 6} (the only valid single-chest GUI heights).
"""

import os
import re

try:
    import yaml
except ImportError:
    yaml = None


def _parse_yaml_safe(text):
    if yaml is None:
        raise RuntimeError("PyYAML is required: pip install pyyaml")
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


def _walk_slots(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "slot":
                if isinstance(v, int):
                    out.add(v)
                elif isinstance(v, str) and v.isdigit():
                    out.add(int(v))
            elif k in ("slots", "items-slots"):
                if isinstance(v, list):
                    for entry in v:
                        if isinstance(entry, int):
                            out.add(entry)
                        elif isinstance(entry, str):
                            entry = entry.strip()
                            if entry.isdigit():
                                out.add(int(entry))
                            elif "-" in entry:
                                m = re.match(r"^(\d+)\s*-\s*(\d+)$", entry)
                                if m:
                                    a, b = int(m.group(1)), int(m.group(2))
                                    out.update(range(a, b + 1))
            else:
                _walk_slots(v, out)
    elif isinstance(node, list):
        for item in node:
            _walk_slots(item, out)


def extract_slots_via_regex(text):
    used = set()
    for m in re.finditer(r"^\s*slot\s*:\s*(\d+)\s*$", text, re.M):
        used.add(int(m.group(1)))
    for m in re.finditer(r"^\s*-\s*(\d+)\s*$", text, re.M):
        used.add(int(m.group(1)))
    for m in re.finditer(r"^\s*-\s*(\d+)\s*-\s*(\d+)\s*$", text, re.M):
        a, b = int(m.group(1)), int(m.group(2))
        used.update(range(a, b + 1))
    return used


def _detect_size(text, parsed):
    size = None
    if isinstance(parsed, dict):
        s = parsed.get("size")
        if isinstance(s, int) and s > 0:
            size = s
    if size is None:
        m = re.search(r"^size\s*:\s*(\d+)\s*$", text, re.M)
        if m:
            size = int(m.group(1))
    if size is None:
        return None
    rows = (size + 8) // 9
    if rows > 6:
        rows = 6
    if rows in (1, 2, 3, 4, 5, 6):
        return rows
    return None


def slots_for_menu(path):
    """Read DeluxeMenus YAML, return (rows, sorted_list_of_used_slots)."""
    try:
        with open(path, encoding="utf-8") as fp:
            text = fp.read()
    except (OSError, UnicodeDecodeError):
        return (None, [])
    parsed = _parse_yaml_safe(text)
    rows = _detect_size(text, parsed)
    used = set()
    if parsed is not None:
        _walk_slots(parsed, used)
    if not used:
        used = extract_slots_via_regex(text)
    if rows:
        max_slot = rows * 9
        used = {s for s in used if 0 <= s < max_slot}
    return (rows, sorted(used))


def slots_for_invgui_section(path, section="all_selection"):
    """
    TreasureCoCaseReloaded schematic. Each row of `schematic:` is a string
    with 9 space-separated tokens. A space-token (single space) means
    'empty slot, no bezel'. Any other 1-char token = used slot.
    """
    try:
        with open(path, encoding="utf-8") as fp:
            text = fp.read()
    except (OSError, UnicodeDecodeError):
        return (None, [])
    parsed = _parse_yaml_safe(text)
    if not isinstance(parsed, dict) or section not in parsed:
        return (None, [])
    sec = parsed[section]
    if not isinstance(sec, dict):
        return (None, [])
    schematic = sec.get("schematic")
    if not isinstance(schematic, list) or not schematic:
        return (None, [])
    used = set()
    rows = 0
    for r, row in enumerate(schematic):
        if not isinstance(row, str):
            continue
        tokens = row.split(" ")
        if len(tokens) < 9:
            tokens = tokens + [""] * (9 - len(tokens))
        for c, tok in enumerate(tokens[:9]):
            tok = tok.strip()
            if tok:
                used.add(r * 9 + c)
        rows = r + 1
    if rows in (1, 2, 3, 4, 5, 6):
        actual_rows = rows
    elif rows > 0:
        actual_rows = 6
    else:
        actual_rows = None
    return (actual_rows, sorted(used))


def slots_for_sseller(path):
    """sSeller config.yml: frame.slots + sell_slots + sell_all.slot."""
    try:
        with open(path, encoding="utf-8") as fp:
            text = fp.read()
    except (OSError, UnicodeDecodeError):
        return (None, [])
    parsed = _parse_yaml_safe(text)
    if not isinstance(parsed, dict):
        return (None, [])
    used = set()
    def collect(v):
        if isinstance(v, list):
            for entry in v:
                if isinstance(entry, int):
                    used.add(entry)
                elif isinstance(entry, str) and entry.strip().isdigit():
                    used.add(int(entry.strip()))
    frame = parsed.get("frame", {})
    if isinstance(frame, dict):
        collect(frame.get("slots"))
    collect(parsed.get("sell_slots"))
    sell_all = parsed.get("sell_all", {})
    if isinstance(sell_all, dict):
        s = sell_all.get("slot")
        if isinstance(s, int):
            used.add(s)
    if not used:
        return (None, [])
    max_slot = max(used)
    rows = (max_slot + 9) // 9
    if rows > 6:
        rows = 6
    used = {s for s in used if 0 <= s < rows * 9}
    return (rows, sorted(used))


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        if p.endswith("invgui.yml"):
            rows, slots = slots_for_invgui_section(p, "all_selection")
            tag = "[invgui]"
        elif "sSeller" in p or "/seller/" in p:
            rows, slots = slots_for_sseller(p)
            tag = "[sseller]"
        else:
            rows, slots = slots_for_menu(p)
            tag = "[dm]"
        print(f"{os.path.basename(p):30s} {tag:10s} rows={rows}  used={len(slots):2d}  {slots}")
