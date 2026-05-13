# ИНСТРУКЦИЯ ДЛЯ НЕЙРОСЕТИ — Деплой §6 (Invisible Items + Full-Chest Overlay)

> **Цель**: Залить на сервер невидимые предметы + пропатченные меню, чтобы bitmap-глифы покрывали весь сундук, а не только заголовок.

> **Статус ДО**: 30/30 заголовков работают (орнаментная полоска). Центр сундука ванильный (серые слоты).

> **Статус ПОСЛЕ**: Все слоты заполнены невидимым Oraxen-предметом → bitmap виден на всю площадь.

---

## ДОСТУПЫ

| Параметр | Значение |
|----------|----------|
| Pterodactyl API base | `https://mgr.hosting-minecraft.pro/api/client/servers/944c2567` |
| Pterodactyl API key | `ptlc_q1LTOfeHyId0pGueJl1WQMYKfK6nqXngMuqcgKRgbQd` |
| Server ID | `944c2567` |
| Core | Paper 1.16.5 (SSSpigot2) |
| Plugins | Oraxen v1.119.0, DeluxeMenus 1.14.1, ProtocolLib 5.1.0 |

---

## API ШПАРГАЛКА

```bash
KEY="ptlc_q1LTOfeHyId0pGueJl1WQMYKfK6nqXngMuqcgKRgbQd"
BASE="https://mgr.hosting-minecraft.pro/api/client/servers/944c2567"

# Загрузить файл на сервер
upload() {
  local LOCAL="$1" REMOTE="$2"
  ENC=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$REMOTE'))")
  curl -sf -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/octet-stream" \
    --data-binary "@$LOCAL" "$BASE/files/write?file=$ENC"
}

# Прочитать файл с сервера
read_remote() {
  ENC=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$1'))")
  curl -sf -H "Authorization: Bearer $KEY" "$BASE/files/contents?file=$ENC"
}

# Выполнить команду в консоли
run_cmd() {
  curl -s -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "{\"command\":\"$1\"}" "$BASE/command"
}

# Список файлов в директории
list_dir() {
  ENC=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$1'))")
  curl -sf -H "Authorization: Bearer $KEY" -H "Accept: application/json" "$BASE/files/list?directory=$ENC"
}
```

---

## ПЛАН ДЕЙСТВИЙ (выполнять последовательно)

### ШАГ 1: Создать прозрачную текстуру 16x16

```python
# Сгенерировать empty.png (16x16 полностью прозрачный PNG)
import struct, zlib

def create_transparent_png(filename, width=16, height=16):
    signature = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
    ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00' + b'\x00\x00\x00\x00' * width
    compressed = zlib.compress(raw_data)
    idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
    idat = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
    iend_crc = zlib.crc32(b'IEND') & 0xffffffff
    iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
    with open(filename, 'wb') as f:
        f.write(signature + ihdr + idat + iend)

create_transparent_png('/tmp/empty.png')
```

### ШАГ 2: Загрузить текстуру на сервер

```bash
upload /tmp/empty.png "/plugins/Oraxen/pack/textures/items/empty.png"
```

### ШАГ 3: Создать и загрузить Oraxen item config

Создай файл `/tmp/menu_empty.yml` с содержимым:

```yaml
menu_empty:
  displayname: "<black> "
  material: PAPER
  excludeFromInventory: true
  Pack:
    generate_model: true
    parent_model: "item/generated"
    textures:
      - items/empty
    custom_model_data: 30000
```

```bash
upload /tmp/menu_empty.yml "/plugins/Oraxen/items/menu_empty.yml"
```

### ШАГ 4: Загрузить 30 пропатченных меню YAML

Для каждого файла из списка ниже:
- `menu__xxx.yml` → загрузить в `/plugins/DeluxeMenus/menu/xxx.yml`
- `shop__xxx.yml` → загрузить в `/plugins/DeluxeMenus/shop/xxx.yml`

**Список файлов (30 штук):**

| Локальный файл | Путь на сервере |
|---|---|
| menu__akriwer.yml | /plugins/DeluxeMenus/menu/akriwer.yml |
| menu__akriwer1.yml | /plugins/DeluxeMenus/menu/akriwer1.yml |
| menu__akriwer2.yml | /plugins/DeluxeMenus/menu/akriwer2.yml |
| menu__arenda.yml | /plugins/DeluxeMenus/menu/arenda.yml |
| menu__donate.yml | /plugins/DeluxeMenus/menu/donate.yml |
| menu__egorchik.yml | /plugins/DeluxeMenus/menu/egorchik.yml |
| menu__events.yml | /plugins/DeluxeMenus/menu/events.yml |
| menu__freek.yml | /plugins/DeluxeMenus/menu/freek.yml |
| menu__grab.yml | /plugins/DeluxeMenus/menu/grab.yml |
| menu__help.yml | /plugins/DeluxeMenus/menu/help.yml |
| menu__media.yml | /plugins/DeluxeMenus/menu/media.yml |
| menu__menu.yml | /plugins/DeluxeMenus/menu/menu.yml |
| menu__obmen.yml | /plugins/DeluxeMenus/menu/obmen.yml |
| menu__panel.yml | /plugins/DeluxeMenus/menu/panel.yml |
| menu__portals.yml | /plugins/DeluxeMenus/menu/portals.yml |
| menu__rtp.yml | /plugins/DeluxeMenus/menu/rtp.yml |
| shop__donateARROW.yml | /plugins/DeluxeMenus/shop/donateARROW.yml |
| shop__donateEGG.yml | /plugins/DeluxeMenus/shop/donateEGG.yml |
| shop__donateITEMS2.yml | /plugins/DeluxeMenus/shop/donateITEMS2.yml |
| shop__donateLIVALKA.yml | /plugins/DeluxeMenus/shop/donateLIVALKA.yml |
| shop__donatePOTIONS.yml | /plugins/DeluxeMenus/shop/donatePOTIONS.yml |
| shop__donatePRED.yml | /plugins/DeluxeMenus/shop/donatePRED.yml |
| shop__donatePVE.yml | /plugins/DeluxeMenus/shop/donatePVE.yml |
| shop__donatePVEOTHER.yml | /plugins/DeluxeMenus/shop/donatePVEOTHER.yml |
| shop__donateRESEURO.yml | /plugins/DeluxeMenus/shop/donateRESEURO.yml |
| shop__donateRESMENU.yml | /plugins/DeluxeMenus/shop/donateRESMENU.yml |
| shop__donateRESMONETA.yml | /plugins/DeluxeMenus/shop/donateRESMONETA.yml |
| shop__donateSHARI.yml | /plugins/DeluxeMenus/shop/donateSHARI.yml |
| shop__donateSHOP.yml | /plugins/DeluxeMenus/shop/donateSHOP.yml |
| shop__donateSPAWNERS.yml | /plugins/DeluxeMenus/shop/donateSPAWNERS.yml |

**Содержимое каждого файла** находится в папке `deploy_v6/patched_menus/` в репозитории `egorbodach-ship-it/tgbot` (ветка `deploy-v6-invisible-items`, или папка `deploy_v6/patched_menus/` в main если была смержена).

**Ключевой принцип патча** — в каждом YAML:
- Все `orange_stained_glass_pane`, `black_stained_glass_pane`, `gray_stained_glass_pane` удалены
- Добавлен блок `gui_filler` с `material: oraxen:menu_empty` на ВСЕ слоты, которые не заняты функциональными предметами (предметы с click_commands)
- `menu_title` НЕ менялся (Tamil-кодпоинты глифов на месте)
- Функциональные предметы (кнопки с lore/click_commands) НЕ менялись

### ШАГ 5: Перезагрузить плагины

```bash
run_cmd "oraxen reload all"
# Подождать 10 секунд (генерация pack)
sleep 10
run_cmd "dm reload"
```

### ШАГ 6: Проверить

```bash
# Проверить что pack перегенерировался
read_remote "/server.properties" | grep resource-pack

# Проверить логи на ошибки
read_remote "/logs/latest.log" | tail -50 | grep -i "error\|menu_empty"

# Отправить pack конкретному игроку
run_cmd "oraxen pack send Devesuch"
```

---

## ПРОВЕРКА В ИГРЕ

1. Зайти как Devesuch
2. `/oraxen pack send Devesuch` (принять ресурс-пак)
3. `/menu` — должен быть виден полный оверлей (оранжево-чёрный дизайн на ВСЕЙ площади сундука)
4. Открыть обычный поставленный в мире сундук — должен быть ванильным (не изменился)
5. `/donate`, `/shop` — проверить что кнопки кликабельны

---

## ЕСЛИ ЧТО-ТО НЕ РАБОТАЕТ

### Проблема: "oraxen:menu_empty" не распознаётся DeluxeMenus
**Решение**: Oraxen должен быть перезагружен ДО dm reload. Порядок: `oraxen reload all` → подождать 10 сек → `dm reload`.

### Проблема: Предметы не невидимые (видна бумага)
**Решение**: Игрок не получил обновлённый ресурс-пак. Выполнить: `oraxen pack send <ник>`. Игрок должен принять пак.

### Проблема: Слоты всё ещё показывают ванильные бевели
**Решение**: Это нормально — бевели рисуются текстурой `generic_54.png`. Невидимые предметы убирают только иконки предметов. Bitmap-глиф из `menu_title` должен перекрывать бевели визуально сверху (ascent:13 + height 71/107/125). Если глиф рендерится только в полоске заголовка — нужно увеличить height/ascent чтобы картинка «спускалась» ниже.

### Проблема: Oraxen перемешал кодпоинты после reload
**Решение**: Прочитать свежий `default.json` из нового pack.zip:
```bash
# Узнать URL нового пака
read_remote "/server.properties" | grep "resource-pack="
# Скачать и проверить кодпоинты
curl -s "<pack_url>" -o /tmp/p.zip
unzip -p /tmp/p.zip assets/minecraft/font/default.json | python3 -c "
import json,sys
data=json.load(sys.stdin)
for p in data['providers']:
    if 'file' in p and 'font/menus' in p.get('file',''):
        print(p['file'], '→', [hex(ord(c)) for c in p['chars'][0]])
"
```
Если кодпоинты сдвинулись — нужно обновить `menu_title:` во всех YAML-ках на новые символы.

---

## ОТКАТ

Загрузить оригинальные YAML-ки обратно:
```bash
# Оригиналы лежат в handoff_v5_for_next.zip → server_state/menu_yamls_current/
# или в backups/menu_yamls_pre_bulk/
# Формат тот же: menu__xxx.yml → /plugins/DeluxeMenus/menu/xxx.yml
```
Потом: `dm reload`

---

## КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ (НЕ НАРУШАТЬ)

1. **НЕ трогать** `assets/minecraft/textures/gui/container/generic_54.png` — ванильная текстура сундука
2. **НЕ трогать** `assets/minecraft/textures/gui/inventory.png` — инвентарь игрока
3. **НЕ использовать** `<font:...>` в menu_title — не работает на DM 1.14.1 + Paper 1.16.5
4. **НЕ ставить** `pack_format: 7` — должен быть `6` для 1.16.5
5. **НЕ включать** `Pack.dispatch.send_pack_advanced.enabled: true` — крашит на SSSpigot2
6. **НЕ включать** `Pack.generation.protection: true` — портит CRC
7. **НЕ делать** `require-resource-pack=true` — кикает игроков при отказе
8. **НЕ коммитить** API ключ в публичные репозитории

---

## КОНТЕКСТ ДЛЯ ПОНИМАНИЯ

Вся предыстория в файле `HANDOFF_v5.md` в том же репозитории. Ключевые моменты:

- **§4**: Почему `<font:...>` не работает (DM 1.14.1 стрипает font-атрибут при legacy-сериализации)
- **§5**: Почему центр сундука ванильный (текстура generic_54.png рисуется ПОВЕРХ глифа)
- **§6**: Правильное решение — invisible items + full-chest image (то что мы сейчас деплоим)
- **§8**: Pitfalls (Oraxen reshuffles codepoints, cracked server quirks, etc.)

Bitmap PNG-ки (28 штук) уже загружены на сервер и работают в заголовках. Их менять не нужно — они покрывают всю площадь сундука, просто раньше их перекрывала текстура слотов.
