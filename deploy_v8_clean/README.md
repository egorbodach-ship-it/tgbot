# Deploy V8 — Хирургический фикс v7 (no grid, всё остальное 1:1)

## Что внутри

| Путь | Назначение |
|---|---|
| `textures_inpaint/` | 28 текстур, побитово равные v7, но с **затёртой фоновой сеткой 9×6** (gray RGB ~60,60,60 pixels). Frame, title-ribbon, цвета, градиент — не тронуты. |
| `scripts/inpaint_grid.py` | Скрипт: ходит по v7 текстурам, маской ловит только серые grid-пиксели (45-75 RGB, balanced channels), для каждого подбирает усреднённый цвет из 4 ближайших не-серых соседей в радиусе 7 px и заменяет. Frame пиксели (bright orange) и title (white) гарантированно не попадают в маску. |
| `yamls_from_server/` | Снимок DM YAML-ов из `/plugins/DeluxeMenus/gui_menus/menu/` и `gui_menus/shop/` на момент деплоя — для справки. |
| `fix_default_menu/panel.yml` | Восстановлен из legacy `/plugins/DeluxeMenus/menu/panel.yml`. В сломанной версии стоял DM template (`menu_title: 'Default Menu'`, `open_command: menu`, items: dirt/grass/...) — он перехватывал команду `/menu`. После фикса: `open_command: panel`, правильное содержимое (rune-шары, доп. зарплата и т.п.). |
| `fix_default_menu/donatePVEOTHER.yml` | Та же история, восстановлен из legacy `/plugins/DeluxeMenus/shop/donatePVEOTHER.yml`. |

## Что чинит

### 1. «Эти серые слоты взади»
В v7 каждая текстура имела «впечатанную» в фон сетку 9×6 из тёмно-серых пиксельных линий — выглядело как полный grid пустых слотов сзади. Удалил **только** их, не трогая ни одного другого пикселя.

### 2. `/menu` открывал «Default Menu»
3 файла одновременно регистрировали команду `/menu`:
- `gui_menus/menu/menu.yml` (правильный — твой)
- `gui_menus/menu/panel.yml` (битый DM-шаблон, `open_command: menu`)
- `gui_menus/shop/donatePVEOTHER.yml` (битый DM-шаблон, `open_command: menu`)

В логе видно: `[DeluxeMenus] command: menu specified for menu: menu already exists for another menu!`. Шаблон выигрывал гонку, открывая Default Menu с дёрном/гравием.

Восстановил оба файла из legacy локаций (правильный контент с `open_command: panel` и т.п.), обновил `menu_title` под актуальные Oraxen codepoints. После `dm reload` варнинг исчез.

## Как задеплоить (через Pterodactyl API)

```bash
KEY="ptlc_..."
BASE="https://mgr.hosting-minecraft.pro/api/client/servers/944c2567"

# 1. Inpainted textures
for f in textures_inpaint/*.png; do
  fname=$(basename "$f")
  ENC=$(python3 -c "import urllib.parse;print(urllib.parse.quote('/plugins/Oraxen/pack/textures/font/menus/$fname'))")
  curl -sf -X POST -H "Authorization: Bearer $KEY" \
    -H "Content-Type: application/octet-stream" \
    --data-binary "@$f" "$BASE/files/write?file=$ENC"
done

# 2. panel.yml + donatePVEOTHER.yml fix
curl -sf -X POST -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/octet-stream" \
  --data-binary "@fix_default_menu/panel.yml" \
  "$BASE/files/write?file=$(python3 -c "import urllib.parse;print(urllib.parse.quote('/plugins/DeluxeMenus/gui_menus/menu/panel.yml'))")"

curl -sf -X POST -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/octet-stream" \
  --data-binary "@fix_default_menu/donatePVEOTHER.yml" \
  "$BASE/files/write?file=$(python3 -c "import urllib.parse;print(urllib.parse.quote('/plugins/DeluxeMenus/gui_menus/shop/donatePVEOTHER.yml'))")"

# 3. Reload pack + DM
curl -s -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"command":"oraxen reload pack"}' "$BASE/command"
sleep 8
curl -s -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"command":"dm reload"}' "$BASE/command"
```

## Как сгенерировать заново (после правки v7)

Если когда-нибудь захочешь изменить базовую v7 текстуру и снова стереть с неё grid — просто положи новые v7 файлы в `deploy_v7_final/orange_textures/` и запусти:

```bash
python3 deploy_v8_clean/scripts/inpaint_grid.py
```

Результат лежит в `deploy_v8_clean/textures_inpaint/`. Заливай как выше.

