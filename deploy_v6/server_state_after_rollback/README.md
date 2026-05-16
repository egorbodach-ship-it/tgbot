# Codepoint Rollback — 2026-05-16

## What was wrong
Adding `menu_overlay_cases` and `menu_overlay_skupschik` to `/plugins/Oraxen/glyphs/menus_overlay.yml`
caused Oraxen v1.119.0 to reshuffle Tamil codepoints in `assets/minecraft/font/default.json`
on `oraxen reload pack`. The 30 DeluxeMenus YAMLs all had hard-coded Tamil chars in
`menu_title:` that pointed to the OLD codepoints, so menus rendered with the wrong glyph
(everything visually shifted by a few codepoints).

## Fix applied
1. Removed `menu_overlay_cases` and `menu_overlay_skupschik` from `menus_overlay.yml`
   (kept everything from `menu_overlay_menu` through `menu_overlay_aukcion` — 29 glyphs).
2. Re-uploaded `menus_overlay.yml` to `/plugins/Oraxen/glyphs/menus_overlay.yml`.
3. Ran `oraxen reload pack` → new pack hash `be7fbe61ed4318cf6ce443273a62e78b072d0eb9`.
4. Re-read the freshly generated `default.json` to learn the NEW Tamil codepoints
   (Oraxen still reshuffled them — `menu` is now U+0BCB, not U+0BC6 as in HANDOFF v5).
5. Rewrote `menu_title:` in all 29 DeluxeMenus YAMLs to point to the new codepoints.
6. Re-uploaded all 29 YAMLs to `/plugins/DeluxeMenus/menu/` and `/plugins/DeluxeMenus/shop/`.
7. Ran `dm reload` → "31 menus loaded" without new errors.
8. Sent the new pack to Devesuch via `oraxen pack send Devesuch`.

## Final glyph -> codepoint map (post-rollback)
| Glyph | Codepoint | Glyph | Codepoint |
|---|---|---|---|
| menu | U+0BCB | egg | U+0BDB |
| donate | U+0BCC | items | U+0BDC |
| shop | U+0BCD | livalka | U+0BDD |
| events | U+0BCE | potions | U+0BDE |
| help | U+0BCF | pred | U+0BDF |
| portals | U+0BD0 | pve | U+0BE0 |
| rtp | U+0BD1 | pveother | U+0BE1 |
| obmen | U+0BD2 | resmenu | U+0BE2 |
| arenda | U+0BD3 | reseuro | U+0BE3 |
| grab | U+0BD4 | resmoneta | U+0BE4 |
| media | U+0BD5 | shari | U+0BE5 |
| freek | U+0BD6 | spawners | U+0BE6 |
| panel | U+0BD7 | aukcion | U+0BE7 |
| egorchik | U+0BD8 | | |
| akriwer | U+0BD9 | | |
| arrow | U+0BDA | | |

(`freek` glyph U+0BD6 has no DeluxeMenus YAML on the server — `freek.yml` does not exist
in `/plugins/DeluxeMenus/menu/`. It only existed earlier as a name in HANDOFF_v5 docs.)

## Files in this folder
- `menus_overlay.yml` — exact bytes uploaded to `/plugins/Oraxen/glyphs/menus_overlay.yml`
- `default.json` — exact bytes from the new pack (`assets/minecraft/font/default.json`)
- `yamls_with_new_codepoints/*.yml` — exact bytes uploaded to DeluxeMenus

## Re-adding cases / skupschik in the future (without breaking everything)
Two correct paths:

### Path A — Lock the codepoints (preferred)
Set `Pack.import.automatically_generate_glyph_files: false` in `Oraxen/settings.yml`
and register your own `default.json` with explicit `chars` (PUA codepoints). Then Oraxen
won't auto-derive Tamil codepoints and adding new glyphs won't reshuffle anything.

### Path B — Re-sync after every reload
After every `oraxen reload pack`, run a script that:
1. Downloads the fresh pack zip,
2. Reads `assets/minecraft/font/default.json` to learn the new codepoints,
3. Rewrites `menu_title:` in all 30 DeluxeMenus YAMLs,
4. `dm reload`.

The exact procedure used here can serve as a template for that script.
