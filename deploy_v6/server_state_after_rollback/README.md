# Server state snapshot — 2026-05-16 (cases/skupschik re-added)

## What this folder contains
The exact bytes deployed to the server after re-adding `cases` and `skupschik`
glyphs and re-syncing all 31 menu titles to the resulting Tamil codepoint map.

- `menus_overlay.yml` -> `/plugins/Oraxen/glyphs/menus_overlay.yml` (31 glyphs)
- `default.json` -> snapshot of `assets/minecraft/font/default.json` from the
  generated pack, used to determine the codepoint mapping.
- `yamls_with_new_codepoints/` -> the menu YAMLs with `menu_title:` /
  `all_selection.title:` / `menu.title:` rewritten to match.

## Final glyph -> codepoint map
| Glyph     | Codepoint | Glyph    | Codepoint  |
|-----------|-----------|----------|------------|
| menu      | U+0BCB    | items    | U+0BDC     |
| donate    | U+0BCC    | livalka  | U+0BDD     |
| shop      | U+0BCD    | potions  | U+0BDE     |
| events    | U+0BCE    | pred     | U+0BDF     |
| help      | U+0BCF    | pve      | U+0BE0     |
| portals   | U+0BD0    | pveother | U+0BE1     |
| rtp       | U+0BD1    | resmenu  | U+0BE2     |
| obmen     | U+0BD2    | reseuro  | U+0BE3     |
| arenda    | U+0BD3    | resmoneta| U+0BE4     |
| grab      | U+0BD4    | shari    | U+0BE5     |
| media     | U+0BD5    | spawners | U+0BE6     |
| freek     | U+0BD6    | aukcion  | U+0BE7     |
| panel     | U+0BD7    | **cases**    | **U+0BE8** |
| egorchik  | U+0BD8    | **skupschik**| **U+0BE9** |
| akriwer   | U+0BD9    |          |            |
| arrow     | U+0BDA    |          |            |
| egg       | U+0BDB    |          |            |

## Slot-aware textures (regenerated)
All 30 PNGs in `deploy_v6/textures_solomon/` were regenerated with the live
server YAMLs (snapshotted under `deploy_v6/server_yamls/`) so that slot bezels
are drawn ONLY where each menu actually has an item. Empty corners stay as
the orange-yellow gradient + damask + Stars of David + filigree.

The slot extractor in `deploy_v6/scripts/slot_extractor.py` now supports three
plugin schemas:
  - DeluxeMenus (`size:` + `items.*.slot/slots`) -> `slots_for_menu()`
  - TreasureCoCaseReloaded (`<section>.schematic:` ASCII grid) -> `slots_for_invgui_section()`
  - sSeller (`frame.slots` + `sell_slots` + `sell_all.slot`) -> `slots_for_sseller()`

## What was deployed in this session
1. Uploaded fresh 30 PNG textures to `/plugins/Oraxen/assets/oraxen/textures/font/menus/`.
2. Added `menu_overlay_cases` (PUA `\uF01E`) and `menu_overlay_skupschik`
   (PUA `\uF01F`) back to `menus_overlay.yml`.
3. `oraxen reload pack` -> new pack hash `167f630795cba27ca924b575d3e98552c19ad4c5`.
4. Read fresh `default.json` and verified codepoints stayed aligned for all
   29 pre-existing glyphs (Oraxen happened to assign the same codepoints as
   before because the new glyphs were appended at the end). The two new
   glyphs got U+0BE8 and U+0BE9.
5. Patched `all_selection.title` in `TreasureCoCaseReloaded/invgui.yml` and
   `menu.title` in `sSeller/config.yml` to use the new codepoints.
6. `dm reload`, `plugman reload TreasureCoCaseReloaded`, `plugman reload sSeller`
   -> all reloaded successfully.
7. `oraxen pack send Devesuch` -> new pack delivered.
