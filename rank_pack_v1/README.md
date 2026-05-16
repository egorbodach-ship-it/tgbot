# Custom Rank Tag Pack

Кастомный pack рангов с пиктограммами, сгенерирован процедурно. **НЕ использует** утечённые ассеты из WellSetups.

## Что внутри

```
rank_pack/
├── Ranks/                      # 13 PNG-иконок 256×64 (gradient pill + bold text)
├── configs/ranks.yml           # ItemsAdder font_images конфиг
├── glyphs/wellsetups_ranks.yml # Oraxen glyphs конфиг (использует PUA \uF200+)
├── oraxen_pack/pack.mcmeta     # Multi-format mcmeta для 1.16.5-1.21.4
├── output/all_ranks_preview.png # Превью всех рангов в один столбик
└── gen_ranks.py                # Генератор (запусти чтобы пересобрать с другими цветами)
```

## Список рангов и цветов

| ID | Название | Цвет |
|---|---|---|
| owner | OWNER | gold |
| admin | ADMIN | crimson red |
| dadmin | D.ADMIN | purple |
| solomon | SOLOMON | yellow→orange gradient |
| osiris | OSIRIS | red+white gradient |
| phonix | PHONIX | blue |
| nebula | NEBULA | green |
| triton | TRITON | yellow |
| hydra | HYDRA | orange |
| aqua | AQUA | cyan/aqua |
| morph | MORPH | pink |
| axolot | AXOLOT | red |
| vernal | VERNAL | brown |

## Поддержка версий MC (`pack.mcmeta`)

```json
{
  "pack": {
    "pack_format": 6,
    "supported_formats": [6, 46],
    "description": "..."
  }
}
```

`supported_formats: [6, 46]` означает что пак работает на:
- **1.16.5** (format 6) — базовый
- ... до **1.21.4** (format 46) — этот же файл подходит без переупаковки.

> Поле `supported_formats` доступно с MC 1.20.2. На версиях 1.16-1.20.1 клиент видит только `pack_format: 6` и подгружается без проблем. На 1.20.2+ клиент видит весь диапазон и не предупреждает что pack устарел.

## Установка для ItemsAdder

1. Копируешь `Ranks/*.png` → `/plugins/ItemsAdder/contents/wellsetups_ranks/textures/`
2. Копируешь `configs/ranks.yml` → `/plugins/ItemsAdder/contents/wellsetups_ranks/configs/ranks.yml`
3. `/iazip` → пересобирает pack
4. Используй в чате/lore: `:wellsetups_ranks_owner:`, `:wellsetups_ranks_solomon:` и т.д.

## Установка для Oraxen

1. Копируешь `Ranks/*.png` → `/plugins/Oraxen/pack/textures/wellsetups_ranks/`
2. Копируешь `glyphs/wellsetups_ranks.yml` → `/plugins/Oraxen/glyphs/wellsetups_ranks.yml`
3. `/oraxen reload all`
4. Используй в LuckPerms prefix: `&f<glyph:ws_owner>`, `&f<glyph:ws_solomon>`

## Перегенерация

Хочешь другие цвета или название? Поправь `RANKS = [...]` в `gen_ranks.py` и запусти:
```bash
python3 gen_ranks.py
```
