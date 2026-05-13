# Deploy V6 — Full-Chest Overlay (Invisible Items)

## Что это

Реализация §6 из HANDOFF_v5.md — техника "invisible items + full-chest image":
- Все декоративные стёкла (orange/black/gray glass panes) заменены на невидимый Oraxen-предмет
- Невидимый предмет заполняет ВСЕ пустые слоты меню
- Bitmap-глиф из `menu_title` теперь виден на всю площадь сундука (слот-бевели больше не перекрывают)

## Структура

```
deploy_v6/
├── deploy.sh                    ← ГЛАВНЫЙ СКРИПТ (запусти его)
├── README.md                    ← ты читаешь это
├── oraxen_items/
│   └── menu_empty.yml           ← Oraxen item config (invisible paper)
├── oraxen_glyphs/               ← (glyph config не меняется, уже на сервере)
├── textures/
│   └── empty.png                ← 16x16 прозрачная текстура
├── patched_menus/               ← 30 пропатченных YAML-ок DeluxeMenus
│   ├── menu__menu.yml
│   ├── menu__donate.yml
│   ├── shop__donateSHOP.yml
│   └── ... (всего 30)
└── scripts/
    └── bulk_patch_slots.py      ← скрипт которым генерировались patched_menus/
```

## Как деплоить

```bash
export PTERODACTYL_KEY="ptlc_xxxxx"   # твой ключ
cd deploy_v6/
bash deploy.sh
```

Скрипт сам:
1. Загрузит `empty.png` → `/plugins/Oraxen/pack/textures/items/empty.png`
2. Загрузит `menu_empty.yml` → `/plugins/Oraxen/items/menu_empty.yml`
3. Загрузит все 30 YAML → `/plugins/DeluxeMenus/menu/` и `/shop/`
4. Выполнит `oraxen reload all` (перегенерирует pack)
5. Выполнит `dm reload` (перезагрузит меню)
6. Проверит результат

## После деплоя

1. Зайди на сервер как Devesuch
2. `/oraxen pack send Devesuch` (обновить ресурспак)
3. `/menu` — должен быть виден полный оверлей
4. Открой обычный поставленный сундук — должен быть ванильным

## Откат

Загрузи файлы из `backups/menu_yamls_pre_bulk/` обратно:
```bash
# Из handoff_v5_for_next.zip → server_state/menu_yamls_current/ (оригиналы)
```
Затем `dm reload`.

## Важно

- `menu_title` НЕ менялся — Tamil-кодпоинты глифов остались как есть
- Если Oraxen переназначил кодпоинты после reload — перечитай `default.json` из нового pack.zip
- Невидимый предмет использует `custom_model_data: 30000` — убедись что этот CMD свободен
- НЕ трогай `generic_54.png` / `inventory.png` (vanilla textures)
