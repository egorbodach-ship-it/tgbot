# Deploy V8 — Clean overlay textures + /menu Default Menu fix

## Что в этой папке

| Папка/файл | Назначение |
|---|---|
| `textures/` | 28 новых чистых текстур меню — **без сетки 9×6**, только сплошной оранжевый фон + рамка + декоративные ячейки только под предметы |
| `scripts/build_textures.py` | Скрипт-генератор: загружает оригинальные текстуры v7, извлекает frame mask (orange/white pixels), кладёт сверху на солидный оранжевый фон с radial gradient, добавляет inset-ячейки на позициях слотов из YAML |
| `yamls_from_server/` | Снимок текущих DM YAML файлов из `/plugins/DeluxeMenus/gui_menus/menu/` и `gui_menus/shop/` на момент деплоя |
| `fix_default_menu/` | Восстановленные `panel.yml` и `donatePVEOTHER.yml` — взяты из legacy `/plugins/DeluxeMenus/menu/` и `/plugins/DeluxeMenus/shop/`, исправлен menu_title под актуальные codepoints |

## Что было сломано

### 1. На текстурах рисовалась сетка 9×6 «взади»

Оригинальный пак (и v7) имеют в каждой текстуре полную сетку 54 слотов (тёмные квадраты) — это видно через оранжевую заливку как «эти серые слоты взади». На рефах с ReallyWorld сетки нет — только декоративные ячейки строго под предметы.

**Фикс**: `build_textures.py` строит каждую текстуру заново:
- Solid orange fill (180, 80, 25) с radial gradient к (130, 55, 18) по краям
- Поверх кладётся detection mask из оригинальной текстуры — только пиксели рамки (bright orange R>200 G<160 B<100), shadow рамки (R 140-200 G 30-90 B<40) и белого title text
- Внутри grid'а рисуются inset-ячейки 13×13 px с тенями только на позициях слотов, прочитанных из соответствующего YAML файла

### 2. /menu открывал «Default Menu» (DM template menu)

В `gui_menus/menu/panel.yml` и `gui_menus/shop/donatePVEOTHER.yml` оказался **шаблон DM по умолчанию**:

```yaml
menu_title: 'Default Menu'
open_command: menu       # <- регистрирует /menu!
size: 9
items:
  'dirt': { material: DIRT, slot: 0 }
  'grass': { material: GRASS_BLOCK, slot: 1 }
  ...
  'diamond_ore': { material: DIAMOND_ORE, slot: 8, display_name: 'Exit' }
```

Из-за этого 3 файла регистрировали команду `/menu` одновременно (menu.yml + panel.yml + donatePVEOTHER.yml), DM выдавал warning `command: menu specified for menu: menu already exists for another menu!` и `/menu` иногда открывал шаблонное меню с дёрном/гравием.

**Фикс**: оба файла восстановлены из правильных legacy копий (`/plugins/DeluxeMenus/menu/panel.yml` → 4170 байт правильного контента с `open_command: panel`), menu_title обновлён под актуальные Oraxen codepoints (`&f௪ௗ` для panel, `&f௪௡` для pveother).

## Как задеплоить (через Pterodactyl API)

```bash
KEY="ptlc_..."
BASE="https://mgr.hosting-minecraft.pro/api/client/servers/944c2567"

# 1. Upload all 28 clean textures
for f in textures/*.png; do
  fname=$(basename "$f")
  ENC=$(python3 -c "import urllib.parse;print(urllib.parse.quote('/plugins/Oraxen/pack/textures/font/menus/$fname'))")
  curl -sf -X POST -H "Authorization: Bearer $KEY" \
    -H "Content-Type: application/octet-stream" \
    --data-binary "@$f" "$BASE/files/write?file=$ENC"
done

# 2. Upload restored panel.yml + donatePVEOTHER.yml
curl -sf -X POST -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/octet-stream" \
  --data-binary "@fix_default_menu/panel.yml" \
  "$BASE/files/write?file=$(python3 -c "import urllib.parse;print(urllib.parse.quote('/plugins/DeluxeMenus/gui_menus/menu/panel.yml'))")"

curl -sf -X POST -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/octet-stream" \
  --data-binary "@fix_default_menu/donatePVEOTHER.yml" \
  "$BASE/files/write?file=$(python3 -c "import urllib.parse;print(urllib.parse.quote('/plugins/DeluxeMenus/gui_menus/shop/donatePVEOTHER.yml'))")"

# 3. Reload
curl -s -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"command":"oraxen reload all"}' "$BASE/command"
sleep 12
curl -s -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"command":"dm reload"}' "$BASE/command"
```

## Как редактировать дальше

### Изменить позицию слотов на текстуре конкретного меню

Открой YAML меню (например `/plugins/DeluxeMenus/gui_menus/menu/menu.yml`), посмотри `slot:` у каждого предмета. Затем запусти:

```bash
cd deploy_v8_clean
python3 scripts/build_textures.py
```

Скрипт прочитает slot'ы из YAML, перерисует текстуры и положит в `textures/`. Затем залей их на сервер и сделай `oraxen reload all`.

### Изменить размер меню

`/plugins/Oraxen/glyphs/menus_overlay.yml`:
- `height` — размер в px (сейчас 260 для menu, 268 для остальных)
- `ascent` — вертикальная позиция (сейчас 32)

### Изменить горизонтальное положение

В `menu_title:` поменяй shift-символ перед глифом меню:

| Сдвиг px | Unicode | Символ |
|---|---|---|
| 1 | U+0BE7 | ௧ |
| 2 | U+0BE8 | ௨ |
| 4 | U+0BE9 | ௩ |
| 8 | U+0BEA | ௪ |
| 16 | U+0BEB | ௫ |
| 32 | U+0BEC | ௬ |

⚠️ Не используй U+0BC0..U+0BC4 — Tamil Combining Marks, MC их приклеивает к предыдущему символу.

После любого `oraxen reload all` коды глифов могут перетасоваться. Если глиф вдруг показывает не то — открой свежий `assets/minecraft/font/default.json` из пака и обнови `menu_title:` под новые коды.

