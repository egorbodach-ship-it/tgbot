# Система генерации и развёртывания ресурс-пака (Solomon UI)

## Обзор

Система состоит из нескольких скриптов, которые:
1. **Генерируют** текстуры меню (Solomon-стиль: золотые рамки, оранжевый градиент)
2. **Патчат** YAML-конфиги на сервере (menu_title с shift-глифами)
3. **Добавляют** поддержку MC 1.21.4 (новый формат item model definitions)

---

## Скрипты

### 1. `scripts/gen_solomon.py` — Генератор текстур меню

**Что делает:** Создаёт 256×256 RGBA PNG-текстуры для каждого меню. Каждая текстура содержит:
- Тёплый оранжево-жёлтый радиальный градиент с дамасковым узором
- Золотую рамку с фаской (bevel)
- Звёзды Давида в углах, корону сверху
- Красную табличку с названием меню (кириллица, 7×9 пиксельный шрифт)
- Тёмные слоты (bezels) только в тех позициях, где YAML-конфиг меню использует слоты

**Параметры рендеринга:**
- Канвас: 256×256 пикселей
- `menu.png`: height=280, shift_px=-12 (из-за большего масштаба)
- Все остальные: height=268, shift_px=-8
- ascent=32 (позиционирование относительно сундука)

**Зависимости:**
- `cyr_font_7x9.py` — встроенный кириллический пиксельный шрифт
- `slot_extractor.py` — извлечение позиций слотов из YAML-конфигов
- `Pillow` (PIL) — рендеринг изображений

**Использование:**
```bash
python3 gen_solomon.py --out ../textures_solomon
python3 gen_solomon.py --preview ../../menu_preview --only menu donate
```

**Ключевая функция `shift_px_for(name)`:**
```
КРИТИЧНО: использовать null.png-based shift-глифы (U+0BED, U+0BEC), НЕ space.png!
space.png полностью прозрачен (alpha=0) → MC 1.16.5 BitmapProvider.findCharacterWidth()
возвращает width=0 → advance=+1 (сдвиг не работает!).
null.png непрозрачный → width=1 → advance рассчитывается правильно.
```

### 2. `patch_titles.py` — Патчер menu_title на сервере

**Что делает:** Обновляет `menu_title` / `title` во ВСЕХ YAML-файлах меню на сервере через Pterodactyl API.

**Формат menu_title:**
```
&f + SHIFT8 + SHIFT4 + GLYPH   (для menu.yml, сдвиг -12)
&f + SHIFT8 + GLYPH             (для всех остальных, сдвиг -8)
```

Где:
- `&f` — белый цвет текста (Minecraft color code)
- `SHIFT8` = U+0BED (null.png, height=-10, effective shift = -8)
- `SHIFT4` = U+0BEC (null.png, height=-6, effective shift = -4)
- `GLYPH` = Tamil Unicode символ из default.json (U+0BCB..U+0BE9)

**ВАЖНО:** DeluxeMenus читает файлы из ДВУХ директорий:
- `menu/` + `shop/` — ссылки из config.yml
- `gui_menus/menu/` + `gui_menus/shop/` — автосканирование DM

Скрипт патчит ОБЕ директории (58 файлов). Также патчит:
- TreasureCoCaseReloaded (`invgui.yml`)
- sSeller (`config.yml`)
- Akriwer extras (`akriwer1.yml`, `akriwer2.yml`)

**Использование:**
```bash
python3 patch_titles.py
```

### 3. `scripts/patch_pack_1214.py` — Поддержка MC 1.21.4

**Что делает:**
1. Скачивает текущий pack.zip с сервера
2. Обновляет `pack.mcmeta`: `pack_format: 46`, `supported_formats: {6..46}`
3. Читает legacy overrides из `models/item/*.json`
4. Генерирует 1.21.4-style item model definitions в `items/*.json`
5. Перепаковывает и загружает обратно

**Формат 1.21.4 item model (пример `items/paper.json`):**
```json
{
  "model": {
    "type": "minecraft:range_dispatch",
    "property": "minecraft:custom_model_data",
    "scale": 1,
    "fallback": {
      "type": "minecraft:model",
      "model": "minecraft:item/paper"
    },
    "entries": [
      {
        "threshold": 1,
        "model": {
          "type": "minecraft:model",
          "model": "minecraft:default/caveblock"
        }
      }
    ]
  }
}
```

**Совместимость:**
- 1.16.5 клиенты: используют legacy `overrides` в `models/item/` (не изменены)
- 1.21.4 клиенты: используют новые `items/` definitions

**ВАЖНО:** Файлы `items/*.json` и обновлённый `pack.mcmeta` загружаются в директорию
`/plugins/Oraxen/pack/` на сервере. Oraxen v1.119.0 копирует их в генерируемый pack.zip,
поэтому они **переживают** `oraxen reload pack`.

**Использование:**
```bash
python3 scripts/patch_pack_1214.py
```

---

## Архитектура pack.zip

```
pack.zip
├── pack.mcmeta                          # pack_format: 46, supported_formats: 6..46
├── assets/minecraft/
│   ├── font/default.json                # 61 bitmap font provider (глифы меню + shift)
│   ├── items/                           # NEW: 1.21.4 item model definitions
│   │   ├── paper.json                   # 39 custom_model_data entries
│   │   ├── diamond_sword.json           # 12 entries
│   │   ├── bow.json                     # 1 entry
│   │   └── ... (14 файлов всего)
│   ├── models/
│   │   ├── item/                        # Legacy 1.16.5 overrides
│   │   │   ├── paper.json
│   │   │   └── ...
│   │   ├── default/                     # Custom 3D models
│   │   └── ...
│   └── textures/
│       ├── font/menus/                  # Solomon-style menu textures (28 PNG)
│       ├── items/empty.png              # Transparent texture for invisible items
│       └── ...
```

---

## Кодпоинты глифов (Tamil Unicode block)

Oraxen автоматически назначает кодпоинты в Tamil block начиная с U+0BC2.
**Кодпоинты могут измениться** при добавлении/удалении глифов!

Текущие кодпоинты (из default.json):
| Меню        | Codepoint | Height | Назначение        |
|-------------|-----------|--------|--------------------|
| menu        | U+0BCB    | 280    | Главное меню       |
| donate      | U+0BCC    | 268    | Привилегии         |
| shop        | U+0BCD    | 268    | Магазин            |
| events      | U+0BCE    | 268    | События            |
| ...         | ...       | 268    | ...                |
| skupschik   | U+0BE9    | 268    | Скупщик            |
| shift_8     | U+0BED    | -10    | Сдвиг -8px (null.png) |
| shift_4     | U+0BEC    | -6     | Сдвиг -4px (null.png) |

---

## Критические ограничения

1. **НЕ трогать** `generic_54.png` (ванильная текстура сундука)
2. **НЕ трогать** `inventory.png` (ванильный инвентарь)
3. **НЕ использовать** `<font:...>` теги в menu_title (не работает на DM 1.14.1)
4. **НЕ использовать** space.png-based shift-глифы (U+0BC1, U+0BC4) — они не работают на MC 1.16.5!
5. **НЕ включать** `send_pack_advanced.enabled: true` (крашит SSSpigot2)
6. **НЕ включать** `Pack.generation.protection: true` (портит CRC)
7. **НЕ ставить** `require-resource-pack=true` (кикает игроков)

---

## Порядок развёртывания

1. Сгенерировать текстуры: `python3 scripts/gen_solomon.py --out textures_solomon`
2. Загрузить текстуры на сервер в `/plugins/Oraxen/pack/textures/font/menus/`
3. `oraxen reload pack` (Oraxen пересоберёт и загрузит pack.zip)
4. Пропатчить menu_titles: `python3 patch_titles.py`
5. (Опционально) Добавить 1.21.4 поддержку: `python3 scripts/patch_pack_1214.py`
6. Перезагрузить плагины: `dm reload`, `plugman reload TreasureCoCaseReloaded`, `plugman reload sSeller`
7. Отправить пак игрокам: `oraxen pack send <player>`

---

## Pterodactyl API

- **Base URL:** `https://mgr.hosting-minecraft.pro/api/client/servers/944c2567`
- **Auth:** `Authorization: Bearer <API_KEY>`
- **Endpoints:**
  - `GET /files/contents?file=<path>` — прочитать файл
  - `POST /files/write?file=<path>` — записать файл (body = содержимое)
  - `GET /files/download?file=<path>` — получить URL для скачивания
  - `POST /command` — выполнить команду на сервере (body: `{"command": "..."}`)
  - `GET /files/list?directory=<path>` — список файлов в директории
