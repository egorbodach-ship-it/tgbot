import asyncio
import logging
import aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)

BOT_TOKEN = "8585156346:AAESKkjrmH0OTLL5rCyESkCvf1BG4a1_OrQ"
ADMIN_IDS = [7461416813]
SERVER_IP = "94.130.45.174"
SERVER_PORT = 25914

router = Router()

tickets = {}
ticket_counter = 0
user_ticket = {}
admin_ticket = {}
all_users = {}
reports = {}
report_counter = 0
banned_users = set()
applications = {}
app_counter = 0
action_log = []

TEMPLATES_TICKET = {
    "✅ Принято": "✅ Спасибо! Принято в работу.",
    "✅ Исправлено": "✅ Исправлено! Перезайди на сервер.",
    "✅ Решено": "✅ Вопрос решён!",
    "❓ Подробнее": "❓ Опиши подробнее — что, где, когда?",
    "❓ Скриншот": "❓ Пришли скриншот или видео.",
    "❓ Ник": "❓ Напиши ник игрока.",
    "❓ Координаты": "❓ Скинь координаты.",
    "❓ Версия": "❓ Какая версия Minecraft?",
    "🔧 Перезайди": "🔧 Попробуй перезайти.",
    "🔧 Кэш": "🔧 Очисти кэш и перезайди.",
    "🔧 Известный баг": "🔧 Известный баг, работаем.",
    "🔧 Не баг": "ℹ️ Не баг, так задумано.",
    "👋 Удачи": "👋 Удачной игры! ⛏",
}

TEMPLATES_BUG = {
    "✅ Принят": "✅ Баг принят! Исправим.",
    "✅ Исправлено": "✅ Исправлено! Перезайди.",
    "🔧 Знаем": "🔧 Знаем, работаем.",
    "🔧 Не воспроизводится": "🔧 Не воспроизводится. Опиши шаги.",
    "❓ Подробнее": "❓ Опиши баг подробнее.",
    "❓ Скриншот": "❓ Пришли скриншот/видео.",
    "❓ Версия": "❓ Какая версия? Моды?",
    "🔧 Перезайди": "🔧 Попробуй перезайти.",
    "ℹ️ Не баг": "ℹ️ Это не баг.",
    "❌ Не наш": "❌ Не относится к серверу.",
}

TEMPLATES_IDEA = {
    "💡 Отлично": "💡 Отличная идея! Передали.",
    "💡 В планах": "💡 Уже в планах!",
    "💡 Обсудим": "💡 Обсудим в команде.",
    "💡 Частично": "💡 Реализуем частично.",
    "❓ Подробнее": "❓ Как видишь реализацию?",
    "❌ Невозможно": "❌ Технически невозможно.",
    "❌ Не подходит": "❌ Не подходит.",
    "👍 Спасибо": "👍 Спасибо!",
}

TEMPLATES_COMPLAINT = {
    "⚠️ Наказан": "⚠️ Нарушитель наказан!",
    "⚠️ Предупреждён": "⚠️ Выдано предупреждение.",
    "⚠️ Забанен": "⚠️ Забанен.",
    "⚠️ Мут": "⚠️ Выдан мут.",
    "❓ Доказательства": "❓ Пришли скриншот/видео.",
    "❓ Когда": "❓ Когда произошло?",
    "❓ Подробнее": "❓ Опиши подробнее.",
    "ℹ️ Не нарушение": "ℹ️ Не нарушение.",
    "ℹ️ Уже наказан": "ℹ️ Уже наказан ранее.",
    "👍 Спасибо": "👍 Спасибо, разберёмся!",
}

ALL_TEMPLATES = {**TEMPLATES_TICKET, **TEMPLATES_BUG, **TEMPLATES_IDEA, **TEMPLATES_COMPLAINT}

FAQ_DATA = {
    "ip": f"🌐 <b>IP:</b> <code>{SERVER_IP}:{SERVER_PORT}</code>\n🚀 1.21.4 — последняя",
    "how_join": f"🎮 <b>Как зайти:</b>\n\n1. Minecraft 1.21.4+\n2. Сетевая игра → Добавить\n3. <code>{SERVER_IP}:{SERVER_PORT}</code>\n4. Играй! ⛏",
    "wipe": "🗓 <b>Вайпы</b> объявляем заранее!"
}

REPORT_TYPES = {"bug": "🐛 Баг-репорт", "idea": "💡 Идея", "comp": "⚠️ Жалоба"}
REPORT_EMOJI = {"bug": "🐛", "idea": "💡", "comp": "⚠️"}
CLOSED_STATUSES = {"✅ Решено", "❌ Отклонено", "🗄 Закрыто"}

STATUS_FLOW = {
    "📨 Новое": ["✅ Принято", "🔧 В работе", "✅ Решено", "❌ Отклонено"],
    "✅ Принято": ["🔧 В работе", "✅ Решено", "❌ Отклонено"],
    "🔧 В работе": ["✅ Решено", "❌ Отклонено"],
    "✅ Решено": [],
    "❌ Отклонено": [],
    "🗄 Закрыто": [],
}


class BugReport(StatesGroup):
    description = State()
    screenshot = State()

class IdeaForm(StatesGroup):
    description = State()
    screenshot = State()

class ComplaintForm(StatesGroup):
    player_name = State()
    reason = State()
    screenshot = State()

class TicketCreate(StatesGroup):
    description = State()
    screenshot = State()

class AdminReply(StatesGroup):
    message = State()

class LinkNick(StatesGroup):
    nickname = State()

class ModApplication(StatesGroup):
    age = State()
    mc_nick = State()
    play_time = State()
    reason = State()

class BroadcastForm(StatesGroup):
    message = State()
    confirm = State()


def log_action(action, uid=0, details=""):
    action_log.append({"time": datetime.now().strftime("%H:%M:%S"), "action": action, "user_id": uid, "details": details})
    if len(action_log) > 500:
        action_log.pop(0)

def register_user(user):
    if user.id not in all_users:
        all_users[user.id] = {"name": user.full_name, "username": user.username, "mc_nick": None, "joined": datetime.now().strftime("%d.%m.%Y %H:%M"), "ratings": []}
    else:
        all_users[user.id]["name"] = user.full_name
        all_users[user.id]["username"] = user.username

def is_banned(uid): return uid in banned_users
def is_admin(uid): return uid in ADMIN_IDS
def get_mc(uid): return all_users.get(uid, {}).get("mc_nick", "—")

def get_name(uid):
    u = all_users.get(uid, {})
    return u.get("mc_nick") or u.get("name", "???")

def get_report_desc(r):
    """Получить короткое описание обращения для напоминания"""
    if r["type"] == "comp":
        desc = f"Жалоба на {r.get('player_name', '?')}: {r.get('reason', '—')}"
    else:
        desc = r.get("description", "—")
    if len(desc) > 120:
        desc = desc[:120] + "..."
    return desc

async def check_server():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.mcsrvstat.us/3/{SERVER_IP}:{SERVER_PORT}", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    d = await r.json()
                    if d.get("online"):
                        on = d.get("players", {}).get("online", 0)
                        mx = d.get("players", {}).get("max", 0)
                        pl = ""
                        if d.get("players", {}).get("list"):
                            pl = "\n👥 " + ", ".join(p.get("name", "?") for p in d["players"]["list"][:20])
                        return f"🟢 <b>ОНЛАЙН</b>\n\n🌐 <code>{SERVER_IP}:{SERVER_PORT}</code>\n🎮 {d.get('version', '?')}\n👥 {on}/{mx}{pl}"
                    return f"🔴 <b>ОФФЛАЙН</b>\n\n<code>{SERVER_IP}:{SERVER_PORT}</code>"
    except:
        return f"❓ Не удалось\n\n<code>{SERVER_IP}:{SERVER_PORT}</code>"

async def notify_admins(bot, text, reply_markup=None):
    for a in ADMIN_IDS:
        try:
            await bot.send_message(a, text, parse_mode="HTML", reply_markup=reply_markup)
        except:
            pass

async def notify_admins_photo(bot, photo, caption, reply_markup=None):
    for a in ADMIN_IDS:
        try:
            await bot.send_photo(a, photo=photo, caption=caption, parse_mode="HTML", reply_markup=reply_markup)
        except:
            pass


# ============ КЛАВИАТУРЫ ============

def main_user_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🐛 Баг-репорт"), KeyboardButton(text="💡 Идея")],
        [KeyboardButton(text="⚠️ Жалоба"), KeyboardButton(text="🎫 Тикет")],
        [KeyboardButton(text="🟢 Статус сервера"), KeyboardButton(text="❓ FAQ")],
        [KeyboardButton(text="📜 Мои обращения"), KeyboardButton(text="🔗 Привязать ник")],
        [KeyboardButton(text="📝 Заявка на модера")]
    ], resize_keyboard=True, input_field_placeholder="Выбери...")

def main_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👨‍💼 Админ-панель")],
        [KeyboardButton(text="🐛 Баг-репорт"), KeyboardButton(text="💡 Идея")],
        [KeyboardButton(text="⚠️ Жалоба"), KeyboardButton(text="🎫 Тикет")],
        [KeyboardButton(text="🟢 Статус сервера"), KeyboardButton(text="❓ FAQ")],
        [KeyboardButton(text="📜 Мои обращения"), KeyboardButton(text="🔗 Привязать ник")]
    ], resize_keyboard=True, input_field_placeholder="Выбери...")

def get_main_kb(uid):
    return main_admin_kb() if is_admin(uid) else main_user_kb()

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def screen_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⏩ Пропустить")],
        [KeyboardButton(text="❌ Отмена")]
    ], resize_keyboard=True)

def ticket_user_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔒 Закрыть тикет")],
        [KeyboardButton(text="📋 Мой тикет")]
    ], resize_keyboard=True, input_field_placeholder="Пиши админу...")

def faq_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🌐 IP сервера"), KeyboardButton(text="🎮 Как зайти")],
        [KeyboardButton(text="🗓 Вайпы"), KeyboardButton(text="🟢 Статус сервера")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True)

def admin_panel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🎫 Активные тикеты")],
        [KeyboardButton(text="🐛 Баги"), KeyboardButton(text="💡 Идеи"), KeyboardButton(text="⚠️ Жалобы")],
        [KeyboardButton(text="📝 Заявки"), KeyboardButton(text="📋 Логи")],
        [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="🟢 Статус сервера")],
        [KeyboardButton(text="🔙 Назад")]
    ], resize_keyboard=True, input_field_placeholder="Админ-панель...")

def _build_kb(templates, extra=None):
    keys = list(templates.keys())
    rows = []
    for i in range(0, len(keys), 2):
        row = [KeyboardButton(text=keys[i])]
        if i + 1 < len(keys):
            row.append(KeyboardButton(text=keys[i + 1]))
        rows.append(row)
    if extra:
        rows.extend(extra)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Ответ или своё...")

def admin_ticket_chat_kb():
    return _build_kb(TEMPLATES_TICKET, [[KeyboardButton(text="🔒 Закрыть тикет")]])

def report_reply_kb(rtype):
    m = {"bug": TEMPLATES_BUG, "idea": TEMPLATES_IDEA, "comp": TEMPLATES_COMPLAINT}
    return _build_kb(m.get(rtype, TEMPLATES_BUG), [[KeyboardButton(text="🔙 Готово")]])

def rating_kb(tid):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{'⭐' * i}", callback_data=f"rate_{tid}_{i}") for i in range(1, 6)
    ]])

def report_actions_kb(rid):
    r = reports.get(rid)
    if not r:
        return None
    current = r.get("status", "📨 Новое")
    available = STATUS_FLOW.get(current, [])
    rows = []
    if available:
        row = []
        for s in available:
            short = s.replace(" ", "")
            row.append(InlineKeyboardButton(text=s, callback_data=f"rs_{rid}_{short}"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
    rows.append([InlineKeyboardButton(text="💬 Ответить", callback_data=f"rr_{rid}")])
    rows.append([InlineKeyboardButton(text="🗄 Закрыть тихо", callback_data=f"rc_{rid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def report_detail_kb(rid):
    r = reports.get(rid)
    if not r:
        return None
    current = r.get("status", "📨 Новое")
    available = STATUS_FLOW.get(current, [])
    rows = []
    if available:
        row = []
        for s in available:
            short = s.replace(" ", "")
            row.append(InlineKeyboardButton(text=s, callback_data=f"rs_{rid}_{short}"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
    rows.append([InlineKeyboardButton(text="💬 Ответить", callback_data=f"rr_{rid}")])
    if current not in CLOSED_STATUSES:
        rows.append([InlineKeyboardButton(text="🗄 Закрыть тихо", callback_data=f"rc_{rid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def reports_list_kb(rtype, page=0, per_page=8):
    items = [(rid, r) for rid, r in reports.items()
             if r["type"] == rtype and r.get("status", "📨 Новое") not in CLOSED_STATUSES]
    items.sort(key=lambda x: x[0], reverse=True)
    total = len(items)
    start = page * per_page
    page_items = items[start:start + per_page]
    rows = []
    for rid, r in page_items:
        n = get_name(r["user_id"])
        st = r.get("status", "📨")
        desc = r.get("description", r.get("reason", ""))[:15]
        emoji = REPORT_EMOJI.get(rtype, "📌")
        rows.append([InlineKeyboardButton(
            text=f"{emoji} #{rid} {st} | {n}: {desc}...",
            callback_data=f"rv_{rid}"
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"rpage_{rtype}_{page - 1}"))
    if start + per_page < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"rpage_{rtype}_{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data=f"rpage_{rtype}_{page}")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

def app_kb(aid, uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"appacc_{aid}_{uid}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"apprej_{aid}_{uid}")],
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"replygen_{uid}")]
    ])

def tickets_list_kb():
    btns = []
    for tid, t in tickets.items():
        if t["status"] == "open":
            n = get_name(t["user_id"])
            d = t["description"][:20] + "..." if len(t["description"]) > 20 else t["description"]
            btns.append([InlineKeyboardButton(text=f"🎫 #{tid} | {n}: {d}", callback_data=f"take_{tid}")])
    return InlineKeyboardMarkup(inline_keyboard=btns) if btns else None

def confirm_bc_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data="bc_yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data="bc_no")
    ]])


# ============ ЗАКРЫТИЕ ТИКЕТА ============

async def do_close(tid, closed_by, bot):
    t = tickets.get(tid)
    if not t or t["status"] == "closed":
        return
    t["status"] = "closed"
    uid, aid = t["user_id"], t["admin_id"]
    if uid in user_ticket and user_ticket[uid] == tid:
        del user_ticket[uid]
    if aid and aid in admin_ticket and admin_ticket[aid] == tid:
        del admin_ticket[aid]
    log_action("close", uid, f"#{tid} {closed_by}")

    desc_short = t["description"][:100]
    if len(t["description"]) > 100:
        desc_short += "..."

    try:
        await bot.send_message(uid,
            f"⛏ <b>Steal a Mob</b>\n\n"
            f"🔒 Тикет <b>#{tid}</b> закрыт {closed_by}.\n\n"
            f"📝 <b>Ваша проблема:</b>\n<i>{desc_short}</i>\n\n"
            f"⭐ Оцени работу администратора:",
            parse_mode="HTML", reply_markup=rating_kb(tid))
        await bot.send_message(uid, "👇", reply_markup=get_main_kb(uid))
    except:
        pass

    if aid:
        try:
            await bot.send_message(aid, f"🔒 Тикет #{tid} закрыт {closed_by}.", parse_mode="HTML", reply_markup=get_main_kb(aid))
        except:
            pass

    for a in ADMIN_IDS:
        if a != aid:
            try:
                await bot.send_message(a, f"🔒 Тикет #{tid} закрыт {closed_by}.", parse_mode="HTML")
            except:
                pass


# ============ ФОРМАТИРОВАНИЕ ============

def format_report_detail(rid):
    r = reports.get(rid)
    if not r:
        return "❌ Не найдено."
    emoji = REPORT_EMOJI.get(r["type"], "📌")
    tname = REPORT_TYPES.get(r["type"], "Обращение")
    u = all_users.get(r["user_id"], {})
    un = f"@{u.get('username')}" if u.get("username") else "—"
    mc = u.get("mc_nick", "—")

    text = (
        f"{emoji} <b>{tname} #{rid}</b>\n\n"
        f"📌 Статус: <b>{r.get('status', '📨 Новое')}</b>\n"
        f"📅 {r.get('created', '?')}\n\n"
        f"👤 {u.get('name', '?')} ({un})\n"
        f"🎮 Ник: {mc}\n"
        f"🆔 <code>{r['user_id']}</code>\n\n"
    )

    if r["type"] == "comp":
        text += f"🎮 <b>Нарушитель:</b> {r.get('player_name', '?')}\n"
        text += f"📝 <b>Причина:</b>\n{r.get('reason', '—')}\n"
    else:
        text += f"📝 <b>Описание:</b>\n{r.get('description', '—')}\n"

    history = r.get("history", [])
    if history:
        text += "\n📊 <b>История:</b>\n"
        for h in history[-5:]:
            text += f"  <code>{h.get('time', '')}</code> {h.get('from', '')} → {h.get('to', '')} ({h.get('by', '')})\n"

    msgs = r.get("messages", [])
    if msgs:
        text += "\n💬 <b>Переписка:</b>\n"
        for msg in msgs[-8:]:
            who = "👨‍💼" if msg["from"] == "admin" else "👤"
            text += f"  {who} <i>{msg.get('time', '')}</i>: {msg['text'][:80]}\n"

    return text


def format_status_notification(rid):
    r = reports.get(rid)
    if not r:
        return ""
    emoji = REPORT_EMOJI.get(r["type"], "📌")
    tname = REPORT_TYPES.get(r["type"], "Обращение")
    status = r.get("status", "?")
    desc = get_report_desc(r)

    details = {
        "✅ Принято": "Мы получили обращение и начали рассматривать.",
        "🔧 В работе": "Администрация работает над этим.",
        "✅ Решено": "Обращение успешно решено! Спасибо!",
        "❌ Отклонено": "К сожалению, обращение отклонено.",
    }

    return (
        f"⛏ <b>Steal a Mob — Обновление статуса</b>\n\n"
        f"{emoji} {tname} <b>#{rid}</b>\n\n"
        f"📌 Статус: <b>{status}</b>\n"
        f"ℹ️ {details.get(status, 'Статус обновлён.')}\n\n"
        f"📝 <b>Ваше обращение:</b>\n<i>{desc}</i>\n\n"
        f"Вопросы? Создай тикет 🎫"
    )


# ================================================================
#                       /start
# ================================================================

@router.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    if is_banned(uid):
        await m.answer("🚫")
        return
    register_user(m.from_user)

    if uid in admin_ticket:
        t = tickets.get(admin_ticket[uid])
        if t and t["status"] == "taken":
            await m.answer(f"⛏ <b>Steal a Mob</b>\n\n💬 Тикет #{admin_ticket[uid]}", parse_mode="HTML", reply_markup=admin_ticket_chat_kb())
            return
    if uid in user_ticket:
        t = tickets.get(user_ticket[uid])
        if t and t["status"] != "closed":
            await m.answer(f"⛏ <b>Steal a Mob</b>\n\n🎫 Тикет #{user_ticket[uid]}", parse_mode="HTML", reply_markup=ticket_user_kb())
            return

    mc = all_users[uid].get("mc_nick")
    nick = f"\n🎮 Ник: <b>{mc}</b>" if mc else ""
    await m.answer(
        f"⛏ <b>Steal a Mob</b>\n\n"
        f"🌐 <code>{SERVER_IP}:{SERVER_PORT}</code>\n"
        f"🚀 1.21.4 — последняя{nick}\n\n👇",
        parse_mode="HTML", reply_markup=get_main_kb(uid))


# ================================================================
#                  АДМИН-ПАНЕЛЬ
# ================================================================

@router.message(F.text.in_({"👨‍💼 Админ-панель", "/admin"}))
async def btn_admin(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        if m.text == "/admin":
            await m.answer("❌")
        return
    await state.clear()
    await m.answer("👨‍💼 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_panel_kb())


@router.message(F.text == "📊 Статистика")
async def admin_stats(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    ot = sum(1 for t in tickets.values() if t["status"] == "open")
    tt = sum(1 for t in tickets.values() if t["status"] == "taken")
    ct = sum(1 for t in tickets.values() if t["status"] == "closed")
    bugs = sum(1 for r in reports.values() if r["type"] == "bug")
    ideasn = sum(1 for r in reports.values() if r["type"] == "idea")
    comps = sum(1 for r in reports.values() if r["type"] == "comp")
    ab = sum(1 for r in reports.values() if r["type"] == "bug" and r.get("status") not in CLOSED_STATUSES)
    ai = sum(1 for r in reports.values() if r["type"] == "idea" and r.get("status") not in CLOSED_STATUSES)
    ac = sum(1 for r in reports.values() if r["type"] == "comp" and r.get("status") not in CLOSED_STATUSES)
    ar = [r for u in all_users.values() for r in u.get("ratings", [])]
    avg = round(sum(ar) / len(ar), 1) if ar else 0

    await m.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 {len(all_users)} | 🚫 {len(banned_users)}\n\n"
        f"🐛 Баги: {ab} активных / {bugs} всего\n"
        f"💡 Идеи: {ai} / {ideasn}\n"
        f"⚠️ Жалобы: {ac} / {comps}\n"
        f"📝 Заявок: {len(applications)}\n\n"
        f"🎫 ⏳{ot} 💬{tt} 🔒{ct}\n⭐ {avg}/5\n\n"
        f"/ban ID причина\n/unban ID",
        parse_mode="HTML", reply_markup=admin_panel_kb())


@router.message(F.text == "🐛 Баги")
async def admin_bugs(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    kb = reports_list_kb("bug")
    if kb:
        n = sum(1 for r in reports.values() if r["type"] == "bug" and r.get("status") not in CLOSED_STATUSES)
        await m.answer(f"🐛 <b>Активные баги ({n}):</b>", parse_mode="HTML", reply_markup=kb)
    else:
        await m.answer("✅ Нет активных багов!", reply_markup=admin_panel_kb())


@router.message(F.text == "💡 Идеи")
async def admin_ideas(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    kb = reports_list_kb("idea")
    if kb:
        n = sum(1 for r in reports.values() if r["type"] == "idea" and r.get("status") not in CLOSED_STATUSES)
        await m.answer(f"💡 <b>Активные идеи ({n}):</b>", parse_mode="HTML", reply_markup=kb)
    else:
        await m.answer("✅ Нет активных идей!", reply_markup=admin_panel_kb())


@router.message(F.text == "⚠️ Жалобы")
async def admin_comps(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    kb = reports_list_kb("comp")
    if kb:
        n = sum(1 for r in reports.values() if r["type"] == "comp" and r.get("status") not in CLOSED_STATUSES)
        await m.answer(f"⚠️ <b>Активные жалобы ({n}):</b>", parse_mode="HTML", reply_markup=kb)
    else:
        await m.answer("✅ Нет активных жалоб!", reply_markup=admin_panel_kb())


@router.message(F.text == "📝 Заявки")
async def admin_apps(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    pending = [(aid, a) for aid, a in applications.items() if a["status"] == "pending"]
    if not pending:
        await m.answer("✅ Нет заявок.", reply_markup=admin_panel_kb())
        return
    for aid, a in pending[-10:]:
        await m.answer(
            f"📝 <b>Заявка #{aid}</b>\n\n🎂 {a['age']} | 🎮 {a['mc_nick']} | ⏰ {a['play_time']}ч\n📝 {a['reason']}",
            parse_mode="HTML", reply_markup=app_kb(aid, a["user_id"]))


@router.message(F.text == "📋 Логи")
async def admin_logs(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    if not action_log:
        await m.answer("📋 Пусто.", reply_markup=admin_panel_kb())
        return
    text = "📋 <b>Логи:</b>\n\n"
    for l in reversed(action_log[-20:]):
        text += f"<code>[{l['time']}]</code> {l['action']}"
        if l['details']:
            text += f" — {l['details']}"
        text += "\n"
    await m.answer(text, parse_mode="HTML", reply_markup=admin_panel_kb())


@router.message(F.text == "📢 Рассылка")
async def admin_bc(m: types.Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        return
    await state.set_state(BroadcastForm.message)
    await m.answer("📢 Сообщение:", reply_markup=cancel_kb())


@router.message(F.text == "🎫 Активные тикеты")
async def admin_tickets(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    kb = tickets_list_kb()
    taken = [(tid, t) for tid, t in tickets.items() if t["status"] == "taken"]
    text = "🎫 <b>Тикеты</b>\n\n"
    if taken:
        text += "💬 <b>В работе:</b>\n"
        for tid, t in taken:
            text += f"  #{tid} — {get_name(t['user_id'])} ← {all_users.get(t['admin_id'], {}).get('name', '?')}\n"
        text += "\n"
    if kb:
        text += "⏳ <b>Свободные:</b>"
        await m.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        text += "✅ Свободных нет."
        await m.answer(text, parse_mode="HTML", reply_markup=admin_panel_kb())


# ============ ПАГИНАЦИЯ ============

@router.callback_query(F.data.startswith("rpage_"))
async def cb_rpage(cb: types.CallbackQuery):
    parts = cb.data.split("_")
    rtype, page = parts[1], int(parts[2])
    kb = reports_list_kb(rtype, page)
    emoji = REPORT_EMOJI.get(rtype, "📌")

    if kb:
        n = sum(1 for r in reports.values() if r["type"] == rtype and r.get("status") not in CLOSED_STATUSES)
        try:
            await cb.message.edit_text(f"{emoji} <b>Активные ({n}):</b>", parse_mode="HTML", reply_markup=kb)
        except:
            await cb.message.answer(f"{emoji} <b>Активные ({n}):</b>", parse_mode="HTML", reply_markup=kb)
    else:
        try:
            await cb.message.edit_text("✅ Всё обработано!")
        except:
            pass
    await cb.answer()


# ============ ПРОСМОТР ОБРАЩЕНИЯ ============

@router.callback_query(F.data.startswith("rv_"))
async def cb_report_view(cb: types.CallbackQuery):
    rid = int(cb.data.split("_")[1])
    r = reports.get(rid)
    if not r:
        await cb.answer("Не найдено.", show_alert=True)
        return

    text = format_report_detail(rid)
    photo = r.get("photo_id")

    if photo:
        try:
            await cb.message.answer_photo(photo=photo, caption=text, parse_mode="HTML", reply_markup=report_detail_kb(rid))
        except:
            await cb.message.answer(text, parse_mode="HTML", reply_markup=report_detail_kb(rid))
    else:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=report_detail_kb(rid))
    await cb.answer()


# ============ СМЕНА СТАТУСА ============

@router.callback_query(F.data.startswith("rs_"))
async def cb_report_status(cb: types.CallbackQuery, bot: Bot, state: FSMContext):
    parts = cb.data.split("_", 2)
    rid = int(parts[1])
    raw = parts[2]

    status_map = {
        "✅Принято": "✅ Принято",
        "🔧Вработе": "🔧 В работе",
        "✅Решено": "✅ Решено",
        "❌Отклонено": "❌ Отклонено",
    }
    new_status = status_map.get(raw, raw)

    r = reports.get(rid)
    if not r:
        await cb.answer("Нет.", show_alert=True)
        return

    old = r.get("status", "📨 Новое")
    if old == new_status:
        await cb.answer("Уже.", show_alert=True)
        return

    r["status"] = new_status
    r.setdefault("history", []).append({
        "time": datetime.now().strftime("%H:%M"),
        "from": old,
        "to": new_status,
        "by": cb.from_user.full_name
    })
    log_action("status", cb.from_user.id, f"#{rid} {old} → {new_status}")

    try:
        await bot.send_message(r["user_id"], format_status_notification(rid), parse_mode="HTML")
    except:
        pass

    try:
        await cb.message.edit_text(format_report_detail(rid), parse_mode="HTML", reply_markup=report_detail_kb(rid))
    except:
        await cb.message.answer(format_report_detail(rid), parse_mode="HTML", reply_markup=report_detail_kb(rid))

    await cb.answer(f"{old} → {new_status}")

    if new_status in CLOSED_STATUSES:
        return

    rtype = r.get("type", "bug")
    await state.set_state(AdminReply.message)
    await state.update_data(reply_to=r["user_id"], reply_rid=rid, reply_type=rtype)
    await cb.message.answer("💬 Ответить? Шаблоны внизу 👇\n«🔙 Готово» — выйти.", reply_markup=report_reply_kb(rtype))


# ============ ЗАКРЫТЬ ТИХО ============

@router.callback_query(F.data.startswith("rc_"))
async def cb_close_silent(cb: types.CallbackQuery):
    rid = int(cb.data.split("_")[1])
    r = reports.get(rid)
    if not r:
        await cb.answer("Нет.", show_alert=True)
        return

    old = r.get("status", "📨 Новое")
    r["status"] = "🗄 Закрыто"
    r.setdefault("history", []).append({
        "time": datetime.now().strftime("%H:%M"),
        "from": old,
        "to": "🗄 Закрыто",
        "by": cb.from_user.full_name
    })
    log_action("close_silent", cb.from_user.id, f"#{rid}")

    try:
        await cb.message.edit_text(
            format_report_detail(rid) + "\n\n🗄 <i>Закрыто (игрок не уведомлён)</i>",
            parse_mode="HTML", reply_markup=None)
    except:
        pass
    await cb.answer("🗄 Закрыто тихо.")


# ============ ОТВЕТИТЬ НА ОБРАЩЕНИЕ ============

@router.callback_query(F.data.startswith("rr_"))
async def cb_reply(cb: types.CallbackQuery, state: FSMContext):
    rid = int(cb.data.split("_")[1])
    r = reports.get(rid)
    if not r:
        await cb.answer("Нет.", show_alert=True)
        return
    rtype = r.get("type", "bug")
    emoji = REPORT_EMOJI.get(rtype, "📌")
    await state.set_state(AdminReply.message)
    await state.update_data(reply_to=r["user_id"], reply_rid=rid, reply_type=rtype)
    await cb.message.answer(
        f"💬 Ответ на {emoji} #{rid}\nШаблоны внизу 👇\n«🔙 Готово» — выйти.",
        reply_markup=report_reply_kb(rtype))
    await cb.answer()


@router.callback_query(F.data.startswith("replygen_"))
async def cb_reply_gen(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.split("_")[1])
    await state.set_state(AdminReply.message)
    await state.update_data(reply_to=uid, reply_rid=0, reply_type="gen")
    await cb.message.answer(f"💬 Ответ <code>{uid}</code>:", parse_mode="HTML", reply_markup=cancel_kb())
    await cb.answer()


@router.message(AdminReply.message)
async def admin_reply_handler(m: types.Message, state: FSMContext, bot: Bot):
    text = m.text or ""
    d = await state.get_data()
    uid = d["reply_to"]
    rid = d.get("reply_rid", 0)
    rtype = d.get("reply_type", "gen")

    if text in ("🔙 Готово", "❌ Отмена"):
        await state.clear()
        if m.from_user.id in admin_ticket:
            await m.answer("💬", reply_markup=admin_ticket_chat_kb())
        else:
            await m.answer("👇", reply_markup=get_main_kb(m.from_user.id))
        return

    reply_text = ALL_TEMPLATES.get(text, text)

    if rid and rid in reports:
        reports[rid].setdefault("messages", []).append({
            "from": "admin",
            "text": reply_text,
            "time": datetime.now().strftime("%H:%M"),
            "admin": m.from_user.full_name
        })

    try:
        r = reports.get(rid)
        if r:
            emoji = REPORT_EMOJI.get(r["type"], "📌")
            tname = REPORT_TYPES.get(r["type"], "Обращение")
            desc = get_report_desc(r)

            await bot.send_message(uid,
                f"⛏ <b>Steal a Mob — Администрация вам ответила:</b>\n\n"
                f"{emoji} {tname} <b>#{rid}</b>\n"
                f"📝 <b>Ваше обращение:</b> <i>{desc}</i>\n\n"
                f"💬 {reply_text}",
                parse_mode="HTML", reply_markup=get_main_kb(uid))
        else:
            await bot.send_message(uid,
                f"⛏ <b>Steal a Mob — Администрация вам ответила:</b>\n\n"
                f"💬 {reply_text}",
                parse_mode="HTML", reply_markup=get_main_kb(uid))
        await m.answer("✅ Отправлено!")
    except:
        await m.answer("❌ Не доставлено.")

    log_action("reply", m.from_user.id, f"→{uid}: {reply_text[:50]}")


# ============ ОБЩИЕ КНОПКИ ============

@router.message(F.text == "❌ Отмена")
async def btn_cancel(m: types.Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    if uid in admin_ticket and tickets.get(admin_ticket[uid], {}).get("status") == "taken":
        await m.answer("💬", reply_markup=admin_ticket_chat_kb())
        return
    await m.answer("❌", reply_markup=get_main_kb(uid))


@router.message(F.text == "🔒 Закрыть тикет")
async def btn_close(m: types.Message, state: FSMContext, bot: Bot):
    uid = m.from_user.id
    await state.clear()
    if uid in user_ticket:
        t = tickets.get(user_ticket[uid])
        if t and t["status"] != "closed":
            await do_close(user_ticket[uid], "игроком", bot)
            return
    if uid in admin_ticket:
        t = tickets.get(admin_ticket[uid])
        if t and t["status"] != "closed":
            await do_close(admin_ticket[uid], "администратором", bot)
            return
    await m.answer("❌", reply_markup=get_main_kb(uid))


@router.message(F.text == "📋 Мой тикет")
async def btn_my_tkt(m: types.Message):
    uid = m.from_user.id
    if uid in user_ticket:
        tid = user_ticket[uid]
        t = tickets.get(tid)
        if t and t["status"] != "closed":
            s = "⏳ ожидает админа" if t["status"] == "open" else "💬 в работе"
            await m.answer(
                f"🎫 Тикет <b>#{tid}</b> ({s})\n\n"
                f"📝 <b>Ваша проблема:</b>\n{t['description']}",
                parse_mode="HTML", reply_markup=ticket_user_kb())
            return
    await m.answer("❌ Нет активных тикетов.", reply_markup=get_main_kb(uid))


@router.message(F.text == "🟢 Статус сервера")
async def btn_status(m: types.Message):
    register_user(m.from_user)
    w = await m.answer("🔍...")
    await w.edit_text(await check_server(), parse_mode="HTML")


@router.message(F.text.in_({"🔙 Назад", "🔙 Готово"}))
async def btn_back(m: types.Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    if uid in admin_ticket and tickets.get(admin_ticket[uid], {}).get("status") == "taken":
        await m.answer("💬 Тикет.", reply_markup=admin_ticket_chat_kb())
        return
    await m.answer("👇", reply_markup=get_main_kb(uid))


@router.message(F.text == "❓ FAQ")
async def btn_faq(m: types.Message):
    await m.answer("❓ <b>FAQ</b>", parse_mode="HTML", reply_markup=faq_kb())

@router.message(F.text == "🌐 IP сервера")
async def f_ip(m: types.Message):
    await m.answer(FAQ_DATA["ip"], parse_mode="HTML")

@router.message(F.text == "🎮 Как зайти")
async def f_join(m: types.Message):
    await m.answer(FAQ_DATA["how_join"], parse_mode="HTML")

@router.message(F.text == "🗓 Вайпы")
async def f_wipe(m: types.Message):
    await m.answer(FAQ_DATA["wipe"], parse_mode="HTML")


# ============ МОИ ОБРАЩЕНИЯ ============

@router.message(F.text == "📜 Мои обращения")
async def btn_my(m: types.Message):
    uid = m.from_user.id
    register_user(m.from_user)
    text = "📜 <b>Мои обращения:</b>\n\n"
    has = False
    for rid, r in sorted(reports.items(), reverse=True):
        if r["user_id"] == uid:
            has = True
            e = REPORT_EMOJI.get(r["type"], "📌")
            desc = r.get("description", r.get("reason", ""))[:30]
            text += f"{e} #{rid} — {r.get('status', '📨')} | {desc}...\n"
    sm = {"open": "⏳ ожидает", "taken": "💬 в работе", "closed": "🔒 закрыт"}
    for tid, t in sorted(tickets.items(), reverse=True):
        if t["user_id"] == uid:
            has = True
            desc = t["description"][:30]
            text += f"🎫 #{tid} — {sm.get(t['status'], '?')} | {desc}...\n"
    if not has:
        text += "Пусто! Создай обращение через меню."
    await m.answer(text, parse_mode="HTML", reply_markup=get_main_kb(uid))


# ============ ПРИВЯЗКА НИКА ============

@router.message(F.text == "🔗 Привязать ник")
async def btn_link(m: types.Message, state: FSMContext):
    register_user(m.from_user)
    mc = get_mc(m.from_user.id)
    t = "🔗 <b>Привязка ника</b>\n\n"
    if mc != "—":
        t += f"Сейчас: <b>{mc}</b>\n\n"
    t += "Напиши свой ник в Minecraft:"
    await state.set_state(LinkNick.nickname)
    await m.answer(t, parse_mode="HTML", reply_markup=cancel_kb())


@router.message(LinkNick.nickname)
async def link_do(m: types.Message, state: FSMContext):
    if m.text == "❌ Отмена":
        await state.clear()
        await m.answer("❌", reply_markup=get_main_kb(m.from_user.id))
        return
    nick = m.text.strip()
    if len(nick) < 3 or len(nick) > 16 or " " in nick:
        await m.answer("❌ 3-16 символов, без пробелов.", reply_markup=cancel_kb())
        return
    register_user(m.from_user)
    all_users[m.from_user.id]["mc_nick"] = nick
    log_action("link", m.from_user.id, nick)
    await state.clear()
    await m.answer(f"✅ Ник <b>{nick}</b> привязан!", parse_mode="HTML", reply_markup=get_main_kb(m.from_user.id))


# ============ ЗАЯВКА ============

@router.message(F.text == "📝 Заявка на модера")
async def btn_app(m: types.Message, state: FSMContext):
    uid = m.from_user.id
    register_user(m.from_user)
    if any(a["user_id"] == uid and a["status"] == "pending" for a in applications.values()):
        await m.answer("❌ Уже есть активная заявка!", reply_markup=get_main_kb(uid))
        return
    await state.set_state(ModApplication.age)
    await m.answer("📝 <b>Заявка на модератора</b>\n\nСколько тебе лет?", parse_mode="HTML", reply_markup=cancel_kb())


@router.message(ModApplication.age)
async def app_age(m: types.Message, state: FSMContext):
    if m.text == "❌ Отмена":
        await state.clear()
        await m.answer("❌", reply_markup=get_main_kb(m.from_user.id))
        return
    await state.update_data(age=m.text)
    mc = all_users.get(m.from_user.id, {}).get("mc_nick")
    if mc:
        await state.update_data(mc_nick=mc)
        await state.set_state(ModApplication.play_time)
        await m.answer(f"🎮 Ник: <b>{mc}</b>\n\nСколько часов в день играешь?", parse_mode="HTML", reply_markup=cancel_kb())
    else:
        await state.set_state(ModApplication.mc_nick)
        await m.answer("🎮 Твой ник в Minecraft:", reply_markup=cancel_kb())


@router.message(ModApplication.mc_nick)
async def app_nick(m: types.Message, state: FSMContext):
    if m.text == "❌ Отмена":
        await state.clear()
        await m.answer("❌", reply_markup=get_main_kb(m.from_user.id))
        return
    await state.update_data(mc_nick=m.text)
    await state.set_state(ModApplication.play_time)
    await m.answer("Сколько часов в день играешь?", reply_markup=cancel_kb())


@router.message(ModApplication.play_time)
async def app_pt(m: types.Message, state: FSMContext):
    if m.text == "❌ Отмена":
        await state.clear()
        await m.answer("❌", reply_markup=get_main_kb(m.from_user.id))
        return
    await state.update_data(play_time=m.text)
    await state.set_state(ModApplication.reason)
    await m.answer("Почему хочешь стать модератором?", reply_markup=cancel_kb())


@router.message(ModApplication.reason)
async def app_reason(m: types.Message, state: FSMContext, bot: Bot):
    if m.text == "❌ Отмена":
        await state.clear()
        await m.answer("❌", reply_markup=get_main_kb(m.from_user.id))
        return
    global app_counter
    d = await state.get_data()
    u = m.from_user
    un = f"@{u.username}" if u.username else "—"
    app_counter += 1
    aid = app_counter
    applications[aid] = {
        "id": aid, "user_id": u.id, "age": d["age"],
        "mc_nick": d["mc_nick"], "play_time": d["play_time"],
        "reason": m.text, "status": "pending",
        "created": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    log_action("app", u.id, f"#{aid}")
    await notify_admins(bot,
        f"📝 <b>Заявка #{aid}</b>\n\n"
        f"👤 {u.full_name} ({un})\n"
        f"🆔 <code>{u.id}</code>\n\n"
        f"🎂 {d['age']} лет | 🎮 {d['mc_nick']} | ⏰ {d['play_time']}ч/день\n\n"
        f"📝 <b>Мотивация:</b>\n{m.text}",
        reply_markup=app_kb(aid, u.id))
    await m.answer(f"✅ Заявка <b>#{aid}</b> отправлена! ⏳", parse_mode="HTML", reply_markup=get_main_kb(u.id))
    await state.clear()


# ============ СОЗДАНИЕ ОБРАЩЕНИЙ ============

async def _create_report(bot, u, rtype, description, photo_id=None, extra=None):
    global report_counter
    un = f"@{u.username}" if u.username else "—"
    mc = get_mc(u.id)
    report_counter += 1
    rid = report_counter
    r = {
        "id": rid, "type": rtype, "user_id": u.id,
        "description": description, "status": "📨 Новое",
        "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "messages": [], "history": [], "photo_id": photo_id
    }
    if extra:
        r.update(extra)
    reports[rid] = r
    log_action(rtype, u.id, f"#{rid}")

    emoji = REPORT_EMOJI[rtype]
    tname = REPORT_TYPES[rtype]
    cap = (
        f"{emoji} <b>{tname} #{rid}</b>\n\n"
        f"👤 {u.full_name} ({un})\n"
        f"🎮 Ник: {mc}\n"
        f"🆔 <code>{u.id}</code>\n\n"
    )
    if rtype == "comp":
        cap += f"🎮 <b>Нарушитель:</b> {extra.get('player_name', '?')}\n📝 <b>Причина:</b>\n{description}"
    else:
        cap += f"📝 <b>Описание:</b>\n{description}"

    if photo_id:
        await notify_admins_photo(bot, photo_id, cap, reply_markup=report_actions_kb(rid))
    else:
        await notify_admins(bot, cap, reply_markup=report_actions_kb(rid))
    return rid


# --- БАГ ---
@router.message(F.text == "🐛 Баг-репорт")
async def btn_bug(m: types.Message, state: FSMContext):
    if is_banned(m.from_user.id):
        return
    register_user(m.from_user)
    await state.set_state(BugReport.description)
    await m.answer("🐛 <b>Баг-репорт</b>\n\nОпиши баг подробно:", reply_markup=cancel_kb(), parse_mode="HTML")

@router.message(BugReport.description)
async def bug_desc(m: types.Message, state: FSMContext):
    if m.text == "❌ Отмена":
        await state.clear()
        await m.answer("❌", reply_markup=get_main_kb(m.from_user.id))
        return
    await state.update_data(description=m.text)
    await state.set_state(BugReport.screenshot)
    await m.answer("📝 Принято!\n\nОтправь скриншот или нажми «⏩ Пропустить»", reply_markup=screen_kb())

@router.message(BugReport.screenshot, F.text == "⏩ Пропустить")
async def bug_skip(m: types.Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    rid = await _create_report(bot, m.from_user, "bug", d["description"])
    await m.answer(f"✅ Баг-репорт <b>#{rid}</b> отправлен!", reply_markup=get_main_kb(m.from_user.id), parse_mode="HTML")
    await state.clear()

@router.message(BugReport.screenshot, F.photo)
async def bug_photo(m: types.Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    rid = await _create_report(bot, m.from_user, "bug", d["description"], m.photo[-1].file_id)
    await m.answer(f"✅ Баг-репорт <b>#{rid}</b> отправлен!", reply_markup=get_main_kb(m.from_user.id), parse_mode="HTML")
    await state.clear()

@router.message(BugReport.screenshot)
async def bug_wrong(m: types.Message):
    if m.text == "❌ Отмена":
        return
    await m.answer("📸 Отправь фото или нажми «⏩ Пропустить»", reply_markup=screen_kb())


# --- ИДЕЯ ---
@router.message(F.text == "💡 Идея")
async def btn_idea(m: types.Message, state: FSMContext):
    if is_banned(m.from_user.id):
        return
    register_user(m.from_user)
    await state.set_state(IdeaForm.description)
    await m.answer("💡 <b>Предложить идею</b>\n\nОпиши свою идею:", reply_markup=cancel_kb(), parse_mode="HTML")

@router.message(IdeaForm.description)
async def idea_desc(m: types.Message, state: FSMContext):
    if m.text == "❌ Отмена":
        await state.clear()
        await m.answer("❌", reply_markup=get_main_kb(m.from_user.id))
        return
    await state.update_data(description=m.text)
    await state.set_state(IdeaForm.screenshot)
    await m.answer("📝 Принято!\n\nПрикрепить картинку или «⏩ Пропустить»", reply_markup=screen_kb())

@router.message(IdeaForm.screenshot, F.text == "⏩ Пропустить")
async def idea_skip(m: types.Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    rid = await _create_report(bot, m.from_user, "idea", d["description"])
    await m.answer(f"✅ Идея <b>#{rid}</b> отправлена!", reply_markup=get_main_kb(m.from_user.id), parse_mode="HTML")
    await state.clear()

@router.message(IdeaForm.screenshot, F.photo)
async def idea_photo(m: types.Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    rid = await _create_report(bot, m.from_user, "idea", d["description"], m.photo[-1].file_id)
    await m.answer(f"✅ Идея <b>#{rid}</b> отправлена!", reply_markup=get_main_kb(m.from_user.id), parse_mode="HTML")
    await state.clear()

@router.message(IdeaForm.screenshot)
async def idea_wrong(m: types.Message):
    if m.text == "❌ Отмена":
        return
    await m.answer("📸 Фото или «⏩ Пропустить»", reply_markup=screen_kb())


# --- ЖАЛОБА ---
@router.message(F.text == "⚠️ Жалоба")
async def btn_comp(m: types.Message, state: FSMContext):
    if is_banned(m.from_user.id):
        return
    register_user(m.from_user)
    await state.set_state(ComplaintForm.player_name)
    await m.answer("⚠️ <b>Жалоба на игрока</b>\n\nНапиши ник нарушителя:", reply_markup=cancel_kb(), parse_mode="HTML")

@router.message(ComplaintForm.player_name)
async def comp_name(m: types.Message, state: FSMContext):
    if m.text == "❌ Отмена":
        await state.clear()
        await m.answer("❌", reply_markup=get_main_kb(m.from_user.id))
        return
    await state.update_data(player_name=m.text)
    await state.set_state(ComplaintForm.reason)
    await m.answer(f"🎮 Ник: <b>{m.text}</b>\n\nОпиши причину жалобы:", reply_markup=cancel_kb(), parse_mode="HTML")

@router.message(ComplaintForm.reason)
async def comp_reason(m: types.Message, state: FSMContext):
    if m.text == "❌ Отмена":
        await state.clear()
        await m.answer("❌", reply_markup=get_main_kb(m.from_user.id))
        return
    await state.update_data(reason=m.text)
    await state.set_state(ComplaintForm.screenshot)
    await m.answer("📝 Принято!\n\nСкриншот-доказательство или «⏩ Пропустить»", reply_markup=screen_kb())

@router.message(ComplaintForm.screenshot, F.text == "⏩ Пропустить")
async def comp_skip(m: types.Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    rid = await _create_report(bot, m.from_user, "comp", d["reason"], extra={"player_name": d["player_name"], "reason": d["reason"]})
    await m.answer(f"✅ Жалоба <b>#{rid}</b> отправлена!", reply_markup=get_main_kb(m.from_user.id), parse_mode="HTML")
    await state.clear()

@router.message(ComplaintForm.screenshot, F.photo)
async def comp_photo(m: types.Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    rid = await _create_report(bot, m.from_user, "comp", d["reason"], m.photo[-1].file_id, extra={"player_name": d["player_name"], "reason": d["reason"]})
    await m.answer(f"✅ Жалоба <b>#{rid}</b> отправлена!", reply_markup=get_main_kb(m.from_user.id), parse_mode="HTML")
    await state.clear()

@router.message(ComplaintForm.screenshot)
async def comp_wrong(m: types.Message):
    if m.text == "❌ Отмена":
        return
    await m.answer("📸 Фото или «⏩ Пропустить»", reply_markup=screen_kb())


# ============ ТИКЕТ СОЗДАНИЕ ============

@router.message(F.text == "🎫 Тикет")
async def btn_tkt(m: types.Message, state: FSMContext):
    uid = m.from_user.id
    if is_banned(uid):
        return
    register_user(m.from_user)
    if uid in user_ticket and tickets.get(user_ticket[uid], {}).get("status") != "closed":
        await m.answer(f"❌ У тебя уже есть тикет <b>#{user_ticket[uid]}</b>.", parse_mode="HTML", reply_markup=ticket_user_kb())
        return
    await state.set_state(TicketCreate.description)
    await m.answer("🎫 <b>Создать тикет</b>\n\nОпиши свою проблему:", reply_markup=cancel_kb(), parse_mode="HTML")

@router.message(TicketCreate.description)
async def tkt_desc(m: types.Message, state: FSMContext):
    if m.text == "❌ Отмена":
        await state.clear()
        await m.answer("❌", reply_markup=get_main_kb(m.from_user.id))
        return
    await state.update_data(description=m.text)
    await state.set_state(TicketCreate.screenshot)
    await m.answer("📝 Принято!\n\nСкриншот или «⏩ Пропустить»", reply_markup=screen_kb())


async def _create_tkt(bot, u, d, photo_id=None):
    global ticket_counter
    un = f"@{u.username}" if u.username else "—"
    mc = get_mc(u.id)
    ticket_counter += 1
    tid = ticket_counter
    tickets[tid] = {
        "user_id": u.id, "admin_id": None,
        "description": d["description"], "status": "open",
        "created": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    user_ticket[u.id] = tid
    log_action("tkt", u.id, f"#{tid}")
    cap = (
        f"🎫 <b>Новый тикет #{tid}</b>\n\n"
        f"👤 {u.full_name} ({un})\n"
        f"🎮 Ник: {mc}\n"
        f"🆔 <code>{u.id}</code>\n\n"
        f"📝 <b>Проблема:</b>\n{d['description']}"
    )
    take = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✋ Взять тикет", callback_data=f"take_{tid}")]])
    if photo_id:
        await notify_admins_photo(bot, photo_id, cap, reply_markup=take)
    else:
        await notify_admins(bot, cap, reply_markup=take)
    return tid


@router.message(TicketCreate.screenshot, F.text == "⏩ Пропустить")
async def tkt_skip(m: types.Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    tid = await _create_tkt(bot, m.from_user, d)
    await m.answer(
        f"✅ Тикет <b>#{tid}</b> создан!\n\n"
        f"⏳ Ожидай — администратор скоро возьмёт его.",
        reply_markup=ticket_user_kb(), parse_mode="HTML")
    await state.clear()

@router.message(TicketCreate.screenshot, F.photo)
async def tkt_photo(m: types.Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    tid = await _create_tkt(bot, m.from_user, d, m.photo[-1].file_id)
    await m.answer(
        f"✅ Тикет <b>#{tid}</b> создан!\n\n"
        f"⏳ Ожидай — администратор скоро возьмёт его.",
        reply_markup=ticket_user_kb(), parse_mode="HTML")
    await state.clear()

@router.message(TicketCreate.screenshot)
async def tkt_wrong(m: types.Message):
    if m.text == "❌ Отмена":
        return
    await m.answer("📸 Фото или «⏩ Пропустить»", reply_markup=screen_kb())


# ============ ТИКЕТ ВЗЯТЬ ============

@router.callback_query(F.data.startswith("take_"))
async def cb_take(cb: types.CallbackQuery, bot: Bot):
    tid = int(cb.data.split("_")[1])
    t = tickets.get(tid)
    if not t or t["status"] != "open":
        await cb.answer("❌ Недоступен.", show_alert=True)
        return

    admin = cb.from_user
    if not is_admin(admin.id):
        await cb.answer("❌ Нет доступа.", show_alert=True)
        return

    if admin.id in admin_ticket and tickets.get(admin_ticket[admin.id], {}).get("status") == "taken":
        await cb.answer(f"Сначала закрой тикет #{admin_ticket[admin.id]}.", show_alert=True)
        return

    t["status"] = "taken"
    t["admin_id"] = admin.id
    admin_ticket[admin.id] = tid
    log_action("take", admin.id, f"#{tid}")

    user = all_users.get(t["user_id"], {})
    mc = user.get("mc_nick", "—")
    name = user.get("name", "???")

    # Админу — полная инфа
    try:
        await bot.send_message(admin.id,
            f"✅ Ты взял тикет <b>#{tid}</b>\n\n"
            f"👤 Игрок: {name}\n"
            f"🎮 Ник: {mc}\n\n"
            f"📝 <b>Проблема:</b>\n{t['description']}\n\n"
            f"💬 Пиши сюда — сообщения уйдут игроку.\n"
            f"Быстрые ответы внизу 👇",
            parse_mode="HTML", reply_markup=admin_ticket_chat_kb())
    except:
        t["status"] = "open"
        t["admin_id"] = None
        del admin_ticket[admin.id]
        await cb.answer("❌ Напиши /start боту в ЛС!", show_alert=True)
        return

    # Игроку — полное уведомление с его проблемой
    try:
        await bot.send_message(t["user_id"],
            f"⛏ <b>Steal a Mob</b>\n\n"
            f"✅ Твой тикет взял администратор!\n\n"
            f"🎫 Тикет <b>#{tid}</b>\n"
            f"📝 <b>Твоя проблема:</b>\n<i>{t['description']}</i>\n\n"
            f"💬 Можешь писать прямо сюда — все сообщения уйдут администратору.\n"
            f"🔒 Нажми «Закрыть тикет» когда вопрос будет решён.",
            parse_mode="HTML", reply_markup=ticket_user_kb())
    except:
        pass

    for a in ADMIN_IDS:
        if a != admin.id:
            try:
                await bot.send_message(a, f"✅ Тикет #{tid} взял {admin.full_name}", parse_mode="HTML")
            except:
                pass

    await cb.answer(f"Взял тикет #{tid}!")


# ============ ЗАЯВКИ ============

@router.callback_query(F.data.startswith("appacc_"))
async def cb_app_acc(cb: types.CallbackQuery, bot: Bot):
    parts = cb.data.split("_")
    aid, uid = int(parts[1]), int(parts[2])
    a = applications.get(aid)
    if a:
        a["status"] = "accepted"
    log_action("app_ok", cb.from_user.id, f"#{aid}")
    try:
        await bot.send_message(uid,
            "⛏ <b>Steal a Mob — Администрация вам ответила:</b>\n\n"
            "🎉 Твоя заявка на модератора <b>принята</b>!\n"
            "Свяжись с администрацией для получения прав.",
            parse_mode="HTML")
    except:
        pass
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("✅ Принята!")


@router.callback_query(F.data.startswith("apprej_"))
async def cb_app_rej(cb: types.CallbackQuery, bot: Bot):
    parts = cb.data.split("_")
    aid, uid = int(parts[1]), int(parts[2])
    a = applications.get(aid)
    if a:
        a["status"] = "rejected"
    log_action("app_no", cb.from_user.id, f"#{aid}")
    try:
        await bot.send_message(uid,
            "⛏ <b>Steal a Mob — Администрация вам ответила:</b>\n\n"
            "❌ Твоя заявка на модератора <b>отклонена</b>.\n"
            "Попробуй позже!",
            parse_mode="HTML")
    except:
        pass
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("❌ Отклонена.")


# ============ ОЦЕНКА ============

@router.callback_query(F.data.startswith("rate_"))
async def cb_rate(cb: types.CallbackQuery, bot: Bot):
    parts = cb.data.split("_")
    tid, r = int(parts[1]), int(parts[2])
    t = tickets.get(tid)
    if not t:
        await cb.answer("?", show_alert=True)
        return
    uid = cb.from_user.id
    if uid in all_users:
        all_users[uid].setdefault("ratings", []).append(r)
    stars = "⭐" * r
    log_action("rate", uid, f"#{tid}: {stars}")
    if t.get("admin_id"):
        try:
            await bot.send_message(t["admin_id"], f"⭐ Тикет #{tid}: {stars}", parse_mode="HTML")
        except:
            pass
    await cb.message.edit_text(f"Спасибо за оценку! {stars}", reply_markup=None)
    await cb.answer(stars)


# ============ РАССЫЛКА ============

@router.message(BroadcastForm.message)
async def bc_msg(m: types.Message, state: FSMContext):
    if m.text == "❌ Отмена":
        await state.clear()
        await m.answer("❌", reply_markup=admin_panel_kb())
        return
    await state.update_data(bc=m.text)
    await state.set_state(BroadcastForm.confirm)
    await m.answer(
        f"📢 <b>Предпросмотр:</b>\n\n{m.text}\n\n"
        f"👥 Получателей: {len(all_users)}\n\nОтправить?",
        parse_mode="HTML", reply_markup=confirm_bc_kb())

@router.callback_query(F.data == "bc_yes", BroadcastForm.confirm)
async def bc_yes(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
    d = await state.get_data()
    await state.clear()
    sent = err = 0
    await cb.message.edit_text("📢 Рассылка...")
    for uid in all_users:
        if uid in banned_users:
            continue
        try:
            await bot.send_message(uid, f"📢 <b>Steal a Mob</b>\n\n{d['bc']}", parse_mode="HTML")
            sent += 1
        except:
            err += 1
        await asyncio.sleep(0.05)
    log_action("bc", cb.from_user.id, f"{sent}/{err}")
    await cb.message.edit_text(f"✅ Готово! 📨 {sent} | ❌ {err}")
    await cb.answer()

@router.callback_query(F.data == "bc_no", BroadcastForm.confirm)
async def bc_no(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Отменено.")
    await cb.answer()


# ============ КОМАНДЫ ============

@router.message(Command("ban"))
async def cmd_ban(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    args = m.text.split(maxsplit=2)
    if len(args) >= 2:
        try:
            bid = int(args[1])
            r = args[2] if len(args) > 2 else "—"
            banned_users.add(bid)
            log_action("ban", m.from_user.id, f"{bid}: {r}")
            await m.answer(f"🚫 <code>{bid}</code> забанен.\nПричина: {r}", parse_mode="HTML")
            return
        except:
            pass
    await m.answer("Формат: <code>/ban ID причина</code>", parse_mode="HTML")

@router.message(Command("unban"))
async def cmd_unban(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    args = m.text.split()
    if len(args) >= 2:
        try:
            uid = int(args[1])
            banned_users.discard(uid)
            log_action("unban", m.from_user.id, str(uid))
            await m.answer(f"✅ <code>{uid}</code> разбанен.", parse_mode="HTML")
            return
        except:
            pass
    await m.answer("Формат: <code>/unban ID</code>", parse_mode="HTML")

@router.message(Command("close"))
async def cmd_close(m: types.Message, bot: Bot):
    uid = m.from_user.id
    if uid in user_ticket:
        t = tickets.get(user_ticket[uid])
        if t and t["status"] != "closed":
            await do_close(user_ticket[uid], "игроком", bot)
            return
    if uid in admin_ticket:
        t = tickets.get(admin_ticket[uid])
        if t and t["status"] != "closed":
            await do_close(admin_ticket[uid], "администратором", bot)
            return
    await m.answer("❌ Нет активных тикетов.", reply_markup=get_main_kb(uid))


# ============ МАРШРУТИЗАЦИЯ ============

@router.message(F.chat.type == "private")
async def msg_router(message: types.Message, state: FSMContext, bot: Bot):
    cur = await state.get_state()
    if cur is not None:
        return

    uid = message.from_user.id
    if is_banned(uid):
        await message.answer("🚫")
        return

    register_user(message.from_user)
    text = message.text or ""

    # АДМИН В ТИКЕТЕ
    if uid in admin_ticket:
        tid = admin_ticket[uid]
        t = tickets.get(tid)
        if t and t["status"] == "taken":
            desc_short = t["description"][:100]
            if len(t["description"]) > 100:
                desc_short += "..."

            if text in TEMPLATES_TICKET:
                rt = TEMPLATES_TICKET[text]
                try:
                    await bot.send_message(t["user_id"],
                        f"⛏ <b>Steal a Mob — Администрация вам ответила:</b>\n\n"
                        f"🎫 Тикет <b>#{tid}</b>\n"
                        f"📝 <b>Ваша проблема:</b> <i>{desc_short}</i>\n\n"
                        f"💬 {rt}",
                        parse_mode="HTML")
                    await message.answer("✅ Отправлено!", reply_markup=admin_ticket_chat_kb())
                except:
                    await message.answer("❌ Не доставлено.")
                return

            try:
                if text:
                    await bot.send_message(t["user_id"],
                        f"⛏ <b>Steal a Mob — Администрация вам ответила:</b>\n\n"
                        f"🎫 Тикет <b>#{tid}</b>\n"
                        f"📝 <b>Ваша проблема:</b> <i>{desc_short}</i>\n\n"
                        f"💬 {text}",
                        parse_mode="HTML")
                elif message.photo:
                    await bot.send_photo(t["user_id"],
                        photo=message.photo[-1].file_id,
                        caption=(
                            f"⛏ <b>Steal a Mob — Администрация вам ответила:</b>\n\n"
                            f"🎫 Тикет <b>#{tid}</b>\n"
                            f"📝 <b>Ваша проблема:</b> <i>{desc_short}</i>\n\n"
                            f"👨‍💼 Фото от администрации"),
                        parse_mode="HTML")
                else:
                    await bot.send_message(t["user_id"],
                        f"⛏ <b>Steal a Mob — Администрация:</b>\n\n🎫 Тикет <b>#{tid}</b>",
                        parse_mode="HTML")
                    await bot.copy_message(t["user_id"], message.chat.id, message.message_id)
            except:
                pass
            return

    # ИГРОК В ТИКЕТЕ
    if uid in user_ticket:
        tid = user_ticket[uid]
        t = tickets.get(tid)
        if t and t["status"] == "taken" and t["admin_id"]:
            try:
                if text:
                    await bot.send_message(t["admin_id"],
                        f"🎫 <b>#{tid}</b> | 👤 Игрок:\n\n{text}",
                        parse_mode="HTML")
                elif message.photo:
                    await bot.send_photo(t["admin_id"],
                        photo=message.photo[-1].file_id,
                        caption=f"🎫 <b>#{tid}</b> | 👤 Фото от игрока",
                        parse_mode="HTML")
                else:
                    await bot.send_message(t["admin_id"],
                        f"🎫 <b>#{tid}</b> | 👤 Игрок:",
                        parse_mode="HTML")
                    await bot.copy_message(t["admin_id"], message.chat.id, message.message_id)
            except:
                pass
            return

        if t and t["status"] == "open":
            await message.answer(
                f"⏳ Тикет <b>#{tid}</b> ещё не взят.\nДождись администратора.",
                parse_mode="HTML", reply_markup=ticket_user_kb())
            return

    await message.answer("Выбери действие 👇", reply_markup=get_main_kb(uid))


# ============ ЗАПУСК ============

async def main():
    bot = Bot(token=BOT_TOKEN)
    for a in ADMIN_IDS:
        try:
            await bot.send_message(a,
                "🤖 <b>Steal a Mob</b> бот запущен!\n\n/admin — панель управления",
                parse_mode="HTML", reply_markup=main_admin_kb())
            print(f"✅ Админ {a} уведомлён")
        except Exception as e:
            print(f"⚠️ Админ {a}: {e}")

    dp = Dispatcher()
    dp.include_router(router)
    logging.basicConfig(level=logging.INFO)
    print("⛏ Steal a Mob бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())