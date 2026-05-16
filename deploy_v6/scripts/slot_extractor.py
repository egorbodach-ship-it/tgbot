"""
slot_extractor.py — read DeluxeMenus YAML and return the set of slot indices
that are actually used (either as a functional item or as a `gui_filler`).

Used by gen_solomon.py to draw slot bezels ONLY where the menu actually has
something. Empty corner gaps in YAML stay clean (gradient + decor only),
which is what the player asked for ("удали лишние слоты").

Assumes a 9-wide chest layout. Returns rows in {3, 5, 6} (the only valid
single-chest GUI heights). If the YAML has `size: NN`, rows = NN // 9.

Usage:
    from slot_extractor import slots_for_menu
    rows, used_slots = slots_for_menu("/path/to/menu.yml")
    # used_slots = sorted set of int slot indices in [0..rows*9-1]
"""

import os
import re

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def _parse_yaml_safe(text):
    """yaml.safe_load with a fallback that tolerates DeluxeMenus' weird
    duplicated-key files (some shop/*.yml have repeated `slots:` etc.)."""
    if yaml is None:
        raise RuntimeError("PyYAML is required: pip install pyyaml")
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        # Last-ditch: extract slots regexically. Returns None to signal the
        # caller to fall back to extract_slots_via_regex.
        return None


def _walk_slots(node, out):
    """Recursively walk a parsed YAML structure and collect ints from any
    `slot:` (singular) or `slots:` (list) leaf. Robust to nested items.

    Also catches DeluxeMenus' '0-44' range syntax used by BAuction.
    """
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
                                # range like "0-44"
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
    """Brute-force fallback when YAML parser chokes: scan the text for slot
    declarations. Conservative — may over-count, but never under-counts.
    """
    used = set()
    # match "slot: NNN"
    for m in re.finditer(r"^\s*slot\s*:\s*(\d+)\s*$", text, re.M):
        used.add(int(m.group(1)))
    # match "- N" inside `slots:` blocks (heuristic: any standalone "- NNN")
    for m in re.finditer(r"^\s*-\s*(\d+)\s*$", text, re.M):
        used.add(int(m.group(1)))
    # ranges
    for m in re.finditer(r"^\s*-\s*(\d+)\s*-\s*(\d+)\s*$", text, re.M):
        a, b = int(m.group(1)), int(m.group(2))
        used.update(range(a, b + 1))
    return used


def _detect_size(text, parsed):
    """Return chest rows count (3, 5, or 6) inferred from `size:` field.

    DeluxeMenus tolerates non-multiple-of-9 sizes (e.g. 44, 53, 55) and
    rounds UP to the next valid chest size (45, 54, 54). We mirror that.
    """
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
    # Round up to nearest valid chest size (multiple of 9, in 9..54)
    rows = (size + 8) // 9
    if rows > 6:
        rows = 6  # clamp; 55+ in YAML is almost certainly a typo
    if rows in (1, 2, 3, 4, 5, 6):
        return rows
    return None


def slots_for_menu(path):
    """
    Read `path`, return (rows, sorted_list_of_used_slots).

    If the file is unreadable, returns (None, []).
    If we can't determine `size`, returns (None, used_set) — caller decides.
    If we can't parse YAML at all, falls back to a regex sweep.
    """
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

    # Clamp to chest size if known
    if rows:
        max_slot = rows * 9
        used = {s for s in used if 0 <= s < max_slot}

    return (rows, sorted(used))


# ---------------------------------------------------------------------------
# Quick CLI for debugging: python3 slot_extractor.py <yaml_path>
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        rows, slots = slots_for_menu(p)
        print(f"{os.path.basename(p):30s}  rows={rows}  used={len(slots):2d}  {slots}")
