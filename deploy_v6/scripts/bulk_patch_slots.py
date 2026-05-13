#!/usr/bin/env python3
"""
bulk_patch_slots.py — §6 Implementation: Invisible Items in All Menu Slots

This script reads all 30 DeluxeMenus YAML files and:
1. Replaces ALL decorative glass pane items (orange/black/gray_stained_glass_pane)
   with the invisible Oraxen item (oraxen:menu_empty)
2. Keeps all functional items (buttons with click commands) EXACTLY as-is
3. Outputs patched YAMLs ready to upload to the server

The invisible item makes the chest GUI transparent so our full-chest
bitmap glyph (rendered via menu_title) shows through.

Usage:
    python3 bulk_patch_slots.py <input_dir> <output_dir>
    
    input_dir:  folder with current menu YAMLs (e.g. server_state/menu_yamls_current/)
    output_dir: folder to write patched YAMLs (e.g. deploy_v6/patched_menus/)

What it does to glass items:
  - material: orange_stained_glass_pane  → material: oraxen:menu_empty
  - material: black_stained_glass_pane   → material: oraxen:menu_empty
  - material: gray_stained_glass_pane    → material: oraxen:menu_empty
  - display_name stays as empty/space (won't show anyway - item is invisible)
  - Removes item_flags from glass entries (not needed for invisible)

What it does NOT touch:
  - menu_title (already has the Tamil glyph codepoint)
  - Functional items (anything with *_click_commands, *_click_requirement)
  - size, open_command, register_command, open_commands
  - Any item that is NOT a glass pane

Additionally fills ALL empty slots (slots not mentioned anywhere) with the
invisible item — this is critical for the overlay technique to work.
"""

import sys
import os
import re
import copy

# Materials that are "decorative glass" — to be replaced
GLASS_MATERIALS = {
    'orange_stained_glass_pane',
    'black_stained_glass_pane',
    'gray_stained_glass_pane',
    'white_stained_glass_pane',
    'light_gray_stained_glass_pane',
}

INVISIBLE_MATERIAL = 'oraxen:menu_empty'


def parse_yaml_simple(text):
    """
    We can't use PyYAML because it may mangle unicode chars (Tamil codepoints).
    Instead, do a careful line-by-line parse that preserves the original formatting
    for non-glass items.
    
    Returns the raw text lines and a structured understanding of items.
    """
    return text


def get_menu_size(text):
    """Extract size: N from the YAML"""
    m = re.search(r'^size:\s*(\d+)', text, re.MULTILINE)
    if m:
        return int(m.group(1))
    return 54  # default


def find_all_occupied_slots(text):
    """Find all slot numbers that are explicitly defined in items"""
    slots = set()
    
    # Match "slot: N"
    for m in re.finditer(r'^\s+slot:\s*(\d+)', text, re.MULTILINE):
        slots.add(int(m.group(1)))
    
    # Match "slots:" arrays (both inline and multiline)
    # Find slots: sections and extract numbers
    in_slots_section = False
    for line in text.split('\n'):
        stripped = line.strip()
        if re.match(r'^slots:', stripped):
            in_slots_section = True
            # Check for inline list: slots: [0, 1, 2]
            inline = re.findall(r'\d+', stripped)
            if inline and '[' in stripped:
                for n in inline:
                    slots.add(int(n))
                in_slots_section = False
            continue
        if in_slots_section:
            if stripped.startswith('- '):
                num = re.search(r'(\d+)', stripped)
                if num:
                    slots.add(int(num.group(1)))
            elif stripped and not stripped.startswith('#'):
                in_slots_section = False
    
    return slots


def is_glass_item_block(block_lines):
    """Check if a block of lines represents a glass pane item"""
    for line in block_lines:
        stripped = line.strip().lower()
        if stripped.startswith('material:'):
            mat = stripped.split(':', 1)[1].strip().strip("'\"").lower()
            if mat in GLASS_MATERIALS:
                return True
    return False


def has_click_commands(block_lines):
    """Check if an item block has any click handlers (= functional item)"""
    for line in block_lines:
        stripped = line.strip().lower()
        if 'click_commands' in stripped or 'click_requirement' in stripped:
            return True
    return False


def get_item_slots(block_lines):
    """Extract slot numbers from an item block"""
    slots = set()
    in_slots = False
    for line in block_lines:
        stripped = line.strip()
        # "slot: N"
        m = re.match(r'slot:\s*(\d+)', stripped)
        if m:
            slots.add(int(m.group(1)))
            continue
        # "slots:" section
        if re.match(r'slots:', stripped):
            in_slots = True
            # inline
            if '[' in stripped:
                for n in re.findall(r'\d+', stripped):
                    slots.add(int(n))
                in_slots = False
            continue
        if in_slots:
            if stripped.startswith('- '):
                num = re.search(r'(\d+)', stripped)
                if num:
                    slots.add(int(num.group(1)))
            elif stripped and not stripped.startswith('#'):
                in_slots = False
    return slots


def split_into_item_blocks(text):
    """
    Split the YAML into:
    - header (everything before 'items:')
    - item blocks (each top-level key under items:)
    """
    lines = text.split('\n')
    
    # Find 'items:' line
    items_idx = None
    for i, line in enumerate(lines):
        if re.match(r'^items:\s*$', line):
            items_idx = i
            break
    
    if items_idx is None:
        return text, []
    
    header = '\n'.join(lines[:items_idx + 1])
    
    # Parse item blocks - each starts with exactly 2-space indent + quoted key + ':'
    item_blocks = []
    current_block = []
    current_key = None
    
    for i in range(items_idx + 1, len(lines)):
        line = lines[i]
        # Check if this is a new top-level item key (2-space or more indent, with a key)
        # Pattern: "  'key':" or "  key:" (2+ spaces, then a key name)
        key_match = re.match(r"^  (['\"]?[\w\-\u0400-\u04FF]+['\"]?)\s*:", line)
        if not key_match and re.match(r"^  '[^']+'\s*:", line):
            key_match = re.match(r"^  ('[^']+')\s*:", line)
        
        if key_match:
            if current_block:
                item_blocks.append((current_key, current_block))
            current_key = key_match.group(1).strip("'\"")
            current_block = [line]
        else:
            current_block.append(line)
    
    if current_block:
        item_blocks.append((current_key, current_block))
    
    return header, item_blocks


def make_invisible_filler_block(key_name, slots):
    """Generate a YAML block for invisible filler items"""
    lines = [f"  '{key_name}':"]
    lines.append(f"    material: {INVISIBLE_MATERIAL}")
    lines.append("    display_name: ' '")
    if len(slots) == 1:
        lines.append(f"    slot: {slots[0]}")
    else:
        lines.append("    slots:")
        for s in sorted(slots):
            lines.append(f"      - {s}")
    return lines


def patch_menu_yaml(text):
    """
    Main patching logic:
    1. Replace glass items with invisible material
    2. Fill any unoccupied slots with invisible items
    """
    menu_size = get_menu_size(text)
    header, item_blocks = split_into_item_blocks(text)
    
    if not item_blocks:
        return text  # nothing to patch
    
    # Track which slots are used by functional items
    functional_slots = set()
    glass_slots = set()
    new_blocks = []
    
    for key, block_lines in item_blocks:
        is_glass = is_glass_item_block(block_lines)
        has_clicks = has_click_commands(block_lines)
        item_slots = get_item_slots(block_lines)
        
        if is_glass and not has_clicks:
            # This is pure decorative glass — collect its slots
            glass_slots.update(item_slots)
        else:
            # Functional item — keep as-is
            functional_slots.update(item_slots)
            new_blocks.append((key, block_lines))
    
    # All empty slots = total slots minus functional slots
    all_slots = set(range(menu_size))
    empty_slots = all_slots - functional_slots
    
    # Build the invisible filler entry covering ALL non-functional slots
    filler_slots = sorted(empty_slots)
    
    if filler_slots:
        filler_block = make_invisible_filler_block('gui_filler', filler_slots)
        new_blocks.insert(0, ('gui_filler', filler_block))
    
    # Reassemble
    result_lines = [header]
    for key, block_lines in new_blocks:
        result_lines.append('\n'.join(block_lines))
    
    return '\n'.join(result_lines) + '\n'


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input_dir> <output_dir>")
        print(f"  input_dir:  folder with current menu YAMLs")
        print(f"  output_dir: folder to write patched YAMLs")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Skip these menus (they have no custom glyph, keep original)
    SKIP_MENUS = {'TitleAnime', 'TitleExclusive', 'TitleMemes', 'TitleMenu'}
    
    files = [f for f in os.listdir(input_dir) if f.endswith('.yml')]
    
    if not files:
        print(f"ERROR: No .yml files found in {input_dir}")
        sys.exit(1)
    
    patched = 0
    skipped = 0
    
    for fname in sorted(files):
        # Check if this is a Title* menu to skip
        base = fname.replace('menu__', '').replace('shop__', '').replace('.yml', '')
        if base in SKIP_MENUS:
            print(f"  SKIP {fname} (no custom glyph)")
            skipped += 1
            continue
        
        input_path = os.path.join(input_dir, fname)
        output_path = os.path.join(output_dir, fname)
        
        with open(input_path, 'r', encoding='utf-8') as f:
            original = f.read()
        
        patched_text = patch_menu_yaml(original)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(patched_text)
        
        # Count changes
        orig_glass = len(re.findall(r'stained_glass_pane', original))
        new_glass = len(re.findall(r'stained_glass_pane', patched_text))
        
        print(f"  OK   {fname} — removed {orig_glass - new_glass} glass refs, added gui_filler")
        patched += 1
    
    print(f"\nDone: {patched} patched, {skipped} skipped")
    print(f"Output: {output_dir}/")
    print(f"\nNext step: upload patched YAMLs to server via deploy.sh")


if __name__ == '__main__':
    main()
