# Custom Rank Pack v2 — Recolored Chevrons

Кастомный pack рангов в стиле WellSetups (101×20 пиксельные шевроны),
полностью перерисованные под твою цветовую схему. Сами PNG генерируются
скриптом `gen_ranks.py` — никакого утечённого арта.

## Список рангов и цветов

| ID | Название | Цвет |
|---|---|---|
| owner   | OWNER   | gold/orange |
| admin   | ADMIN   | crimson red |
| dadmin  | D.ADMIN | purple |
| solomon | SOLOMON | yellow → orange (горизонтальный градиент) |
| osiris  | OSIRIS  | red → white (горизонтальный градиент) |
| phonix  | PHONIX  | blue |
| nebula  | NEBULA  | green |
| triton  | TRITON  | yellow |
| hydra   | HYDRA   | orange |
| aqua    | AQUA    | cyan / aqua (голубой) |
| morph   | MORPH   | pink |
| axolot  | AXOLOT  | red |
| vernal  | VERNAL  | brown |

## Что внутри

```
rank_pack_v2/
├── Ranks/                       # 13 PNG-шевронов 101×20 (твоя палитра)
├── configs/ranks.yml            # ItemsAdder font_images
├── glyphs/wellsetups_ranks.yml  # Oraxen / Nexo glyphs (PUA \uF200..\uF20C)
├── oraxen_pack/pack.mcmeta      # multi-format mcmeta для 1.16.5–1.21.4
├── output/                      # превью всех рангов в один столбик
│   ├── all_ranks_preview.png
│   └── preview_big.png
└── gen_ranks.py                 # генератор (поправь палитру и пересобери)
```

## Установка для ItemsAdder

1. `Ranks/*.png` → `/plugins/ItemsAdder/contents/wellsetups_ranks/textures/`
2. `configs/ranks.yml` → `/plugins/ItemsAdder/contents/wellsetups_ranks/configs/ranks.yml`
3. `/iazip` → пак пересобирается
4. В чате/lore используй: `:wellsetups_ranks_owner:`, `:wellsetups_ranks_solomon:` и т.д.

## Установка для Oraxen

1. `Ranks/*.png` → `/plugins/Oraxen/pack/textures/wellsetups_ranks/`
2. `glyphs/wellsetups_ranks.yml` → `/plugins/Oraxen/glyphs/wellsetups_ranks.yml`
3. `/oraxen reload all`
4. В LuckPerms prefix: `&f<glyph:ws_owner>`, `&f<glyph:ws_solomon>` и т.д.

## Установка для Nexo

1. `Ranks/*.png` → `/plugins/Nexo/pack/assets/minecraft/textures/wellsetups_ranks/`
2. `glyphs/wellsetups_ranks.yml` → `/plugins/Nexo/glyphs/wellsetups_ranks.yml`
3. `/nexo reload`
4. В LuckPerms prefix: `&f<glyph:ws_owner>` и т.д.

## Перекраска / пересборка

Хочешь поменять цвет, оттенок, добавить новый ранг? Открывай `gen_ranks.py`,
правь список `RANKS = [...]` и запускай:

```bash
python3 gen_ranks.py
```

Все картинки пересоберутся автоматически. Размер 101×20 совпадает с
WellSetups — так что в чате они отображаются один в один.

## Совместимость по версиям MC

`pack.mcmeta` содержит `supported_formats: [6, 46]` — пак работает на
Minecraft **1.16.5 → 1.21.4** без переупаковки. На 1.20.2+ клиент видит весь
диапазон и не предупреждает что pack устарел.
