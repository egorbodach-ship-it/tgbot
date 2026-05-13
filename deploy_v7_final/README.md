# Deploy V7 — Final menu overlay system

## Что в этой папке

| Папка/файл | Назначение |
|---|---|
| `backup_20260513/` | Полный бэкап до изменений (текущий пак, все DM menu YAML, Oraxen glyphs config) |
| `orange_textures/` | 28 новых PNG текстур меню — тёплый оранжевый фон вместо чёрного, с паттерном и градиентом. Оригинальная рамка/title-ribbon сохранены нетронутыми. |
| `patched_menus/` | 30 DeluxeMenus YAML файлов с правильными кодпоинтами Oraxen и shift 8px влево. Стёкла (`*_stained_glass_pane`) удалены. |
| `codepoints.json` | Актуальная карта имя_меню → U+XXXX на момент деплоя |

## Принципы работы

### Кодпоинты Oraxen
Oraxen автоматически назначает кодпоинты из Tamil-блока (`U+0BCB..U+0BE6`) нашим 28 глифам меню. **После каждого `oraxen reload all` коды могут сдвигаться** — если меню показывает не ту текстуру, нужно достать свежую карту из `assets/minecraft/font/default.json` в паке и обновить `menu_title:` в YAML файлах.

### Shift-символы (сдвиг влево)
DM 1.14.1 на Paper 1.16.5 стрипает `<font:...>` теги, но **пропускает raw Unicode символы** в `menu_title`. Для сдвига влево используй Tamil Digits (**НЕ** combining marks U+0BC0..U+0BC4):

| Сдвиг | Unicode | Символ |
|---|---|---|
| 1px  | U+0BE7 | ௧ |
| 2px  | U+0BE8 | ௨ |
| 4px  | U+0BE9 | ௩ |
| **8px**  | **U+0BEA** | **௪** ← используется сейчас |
| 16px | U+0BEB | ௫ |
| 32px | U+0BEC | ௬ |
| 64px | U+0BED | ௭ |
| 128px| U+0BEE | ௮ |

Формула title: `&f` + `<SHIFT>` + `<GLYPH>`.

**⚠️ НЕ использовать** `U+0BC0..U+0BC4` — это Tamil Combining Marks, MC их приклеивает к предыдущему символу.

### Размер меню
Настраивается в `/plugins/Oraxen/glyphs/menus_overlay.yml`:
- `height` = размер текстуры в px (текущее: 260)
- `ascent` = позиция по вертикали (текущее: 32)

Оригинал ReallyWorld: `ascent=31, height=256`.
Увеличивать `height` → меню крупнее. При этом пропорционально меняй `ascent` (~height/8 + 5).

## Как задеплоить

```bash
export PTERODACTYL_KEY="ptlc_xxx"
BASE="https://mgr.hosting-minecraft.pro/api/client/servers/944c2567"

# 1. Upload all 28 orange textures
for f in orange_textures/*.png; do
    fname=$(basename "$f")
    ENC=$(python3 -c "import urllib.parse;print(urllib.parse.quote('/plugins/Oraxen/pack/textures/font/menus/$fname'))")
    curl -X POST -H "Authorization: Bearer $PTERODACTYL_KEY" \
        -H "Content-Type: application/octet-stream" \
        --data-binary "@$f" "$BASE/files/write?file=$ENC"
done

# 2. Upload all 30 patched DM YAMLs
for dir in menu shop; do
    for f in patched_menus/$dir/*.yml; do
        fname=$(basename "$f")
        ENC=$(python3 -c "import urllib.parse;print(urllib.parse.quote('/plugins/DeluxeMenus/gui_menus/$dir/$fname'))")
        curl -X POST -H "Authorization: Bearer $PTERODACTYL_KEY" \
            -H "Content-Type: application/octet-stream" \
            --data-binary "@$f" "$BASE/files/write?file=$ENC"
    done
done

# 3. Reload
curl -X POST -H "Authorization: Bearer $PTERODACTYL_KEY" -H "Content-Type: application/json" \
    -d '{"command":"oraxen reload all"}' "$BASE/command"
sleep 15
curl -X POST -H "Authorization: Bearer $PTERODACTYL_KEY" -H "Content-Type: application/json" \
    -d '{"command":"dm reload"}' "$BASE/command"

# 4. Send pack to player
curl -X POST -H "Authorization: Bearer $PTERODACTYL_KEY" -H "Content-Type: application/json" \
    -d '{"command":"oraxen pack send Devesuch"}' "$BASE/command"
```

## Rollback

Если что-то сломается — файлы в `backup_20260513/` содержат состояние **до** изменений:
- Загрузи файлы из `backup_20260513/deluxemenus/gui_menus/` обратно в `/plugins/DeluxeMenus/gui_menus/`
- Загрузи `backup_20260513/oraxen/glyphs/menus_overlay.yml` обратно в `/plugins/Oraxen/glyphs/`
- Выполни `oraxen reload all` + `dm reload`

## ВАЖНО — корневые проблемы, которые мы решили

1. **Оказывается DM читает из `/plugins/DeluxeMenus/gui_menus/` а не `/plugins/DeluxeMenus/menu/`.** Полсессии редактировали не тот файл!
2. **ServerMenu plugin** перехватывал `/menu` — отключен (jar переименован в `.disabled`).
3. **Oraxen перенумеровывает кодпоинты при каждом reload.** После любого `oraxen reload all` проверяй `codepoints.json` и обновляй YAML.
4. **Tamil Combining Marks (U+0BC0..U+0BC4)** для shift НЕ работают (они диакритика). Используй Tamil Digits (U+0BE7..U+0BEF).
5. **pack_format: 6** (для MC 1.16.5), не 7.
