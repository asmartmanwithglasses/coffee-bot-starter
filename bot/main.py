from collections import Counter
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram import F
from aiogram.client.default import DefaultBotProperties
import asyncio, os, math
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, BufferedInputFile, CallbackQuery
from dotenv import load_dotenv
from .order_states import OrderState
import time
from .db import init_db, open_db, close_db, DB_PATH
from .catalog import DRINKS, SIZES
from .keyboards import (main_kb, drink_kb, size_kb, milk_kb, resume_or_cancel_kb,
history_actions_kb, history_filter_kb, undo_delete_kb, repeat_confirm_kb,
after_order_kb, BTN_CANCEL, export_periods_kb, confirm_delete_kb, export_drink_kb,
                        top_periods_kb)
from .services.history import send_history_page
from .services.stats import render_stats
from .services.undo import remember_deleted, get_pending, seconds_left, start_undo_countdown, UNDO_DEADLINE_SEC, UNDO_BIN
from .helpers import send_home, start_order_flow, period_bounds, orders_to_csv, iso_from_epoch
from datetime import datetime, timedelta
from .repo import (get_order_by_id, create_order, soft_delete, undo_delete, orders_for_period,
                   drink_counts_between, count_total_orders, ping_db, count_orders)
import logging
# ---------- Конфигурация ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("bot")

load_dotenv()                       # ищем файл .env
TOKEN = os.getenv("BOT_TOKEN")      # достаем токен из переменных окружения
BOT_VERSION = os.getenv("BOT_VERSION", "0.1.0")
STARTED_AT: float | None = None
bot: Bot | None = None              # создаём объект Bot
dp = Dispatcher()                   # диспетчер (следит за событиями)

# ---------- Меню ----------

BTN_RESUME = "Продолжить заказ"

# единый разделитель для записи/чтения истории
SEPARATOR = "\n\n---\n\n"

QUESTION = {
    OrderState.drink.state: ("Что будете пить?", drink_kb()),
    OrderState.size.state: ("Какой размер?", size_kb()),
    OrderState.milk.state: ("Добавить молоко?", milk_kb()),
}

EXPORT_LOCK: set[tuple[int, int]] = set()

def _fmt_uptime(second: int) -> str:
    d, r = divmod(second, 24*3600)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s or not parts: parts.append(f"{s}s")
    return " ".join(parts)

def _parse_drink_token(tok: str | None) -> str | None:
    if not tok:
        return None
    code = tok.strip().lower()
    return code if code in DRINKS else None

async def _undo_countdown(key: tuple[int, int]):
    while True:
        payload = UNDO_BIN.get(key)
        if not payload:
            return

        remain = math.ceil(payload["until"] - time.time())
        if remain <= 0:
            break

        try:
            sec = max(0, int(payload['until'] - time.time()))
            await bot.edit_message_reply_markup(
                chat_id=payload["chat_id"],
                message_id=payload["message_id"],
                reply_markup=undo_delete_kb(payload["order_id"], seconds_left=sec),
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                logger.warning("undo tick error:", e)
                break

        await asyncio.sleep(1)

    # дедлайн вышел: если не восствновили — финализируем
    payload = UNDO_BIN.pop(key, None)
    if payload:
        with suppress(TelegramBadRequest):
            # снимаем клавиатуру (если ещё есть)
            await bot.edit_message_reply_markup(
                chat_id=payload["chat_id"],
                message_id=payload["message_id"],
                reply_markup=None
            )
            # финальный текст
            await bot.edit_message_text(
                chat_id=payload["chat_id"],
                message_id=payload["message_id"],
                text=f"🗑 Заказ #{payload['order_id']} удалён навсегда.",
                disable_web_page_preview=True
            )

def _to_epoch(x):
    if isinstance(x, int):
        return x
    if isinstance(x, datetime):
        return int(x.timestamp())
    return int(x)

def _now_epoch_tz() -> int:
    return int(datetime.now().astimezone().timestamp())

def _now_local() -> datetime:
    return datetime.now().astimezone()

def _bounds_for_top(period: str) -> tuple[int, int]:
    now = _now_local()
    if period == "week":
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        since_dt = start_today - timedelta(days=6)
        until_dt = start_today + timedelta(days=1)
    elif period in ("month", "30d"):
        since_dt = now - timedelta(days=30)
        until_dt = now + timedelta(seconds=1)
    elif period == "all":
        return 0, 2_147_483_647
    else:
        since_dt = now - timedelta(days=30)
        until_dt = now + timedelta(seconds=1)
    return int(since_dt.timestamp()), int(until_dt.timestamp())

def _period_label(period: str) -> str:
    return {
        "week": "за неделю",
        "month": "за месяц",
        "30d": "за 30 дней",
        "all": "за всё время",
    }.get(period, "за 30 дней")

async def do_export(
        message: Message,
        *,
        period: str | None = None,
        d1: str | None = None,
        d2: str | None = None,
        drink: str | None = None,
        user_id: int | None = None,
):
    if d1 and d2:
        since, until = period_bounds(d1, d2)
        filename = f"orders_{d1}_{d2}.csv"
        period_label = f"{d1}-{d2}"
    else:
        period = period or "month"
        since, until = period_bounds(period)
        filename = f"orders_{period}.csv"
        period_label = period

    since, until = _to_epoch(since), _to_epoch(until)

    rows = await orders_for_period(
        user_id=user_id or message.from_user.id,
        since=since,
        until=until,
        drink=drink
    )

    if not rows:
        await message.answer("За указанный период записей нет.")
        return

    if drink:
        filename = filename.replace(".csv", f"_{drink}.csv")

    data = orders_to_csv(rows)
    doc = BufferedInputFile(data, filename=filename)

    drink_label = "Все" if not drink else DRINKS.get(drink, drink.title())
    caption = (
        f"Экспорт: {filename}\n"
        f"Фильтр: {period_label} · {drink_label}\n"
        f"Записей: {len(rows)}"
    )

    await message.answer_document(document=doc, caption=caption)

def _render_top(rows: list[tuple[str, int]], *, title: str, width: int = 12) -> str:
    if not rows:
        return f"{title}\nнет данных"

    total = max(1, sum(cnt for _, cnt in rows))
    lines = [title]
    for drink, cnt in rows:
        bar_len = max(1, int(round((cnt / total) * width)))
        lines.append(f"{drink:<12} | {'▇'*bar_len} {cnt}")
    return "\n".join(lines)

# ---------- 2. Хэндлеры ----------
@dp.message(F.text.in_({BTN_CANCEL, "Отменить заказ 🚫"}))
async def handle_cancel_anywhere(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Заказ отменён ❌", reply_markup=main_kb())

@dp.message(CommandStart())         # реагирует на /start
async def handle_start(message: Message):
    await send_home(message)

@dp.message(F.text == "🧾 Заказ")
async def handle_main_order(message: Message, state: FSMContext):
    await start_order_flow(message, state)

@dp.message(F.text == "📜 История")
async def handle_history_page(message: Message):
    await message.answer("Фильтр по напитку:", reply_markup=history_filter_kb())

@dp.message(F.text == "ℹ️ О боте")
async def handle_main_kb_help(message: Message):
    await message.answer(
        "👋 Бот-демо заказов кофе.\n"
        "• История с пагинацией и undo\n"
        "• Экспорт CSV по периодам\n"
        "• Статистика и топы по напиткам\n\n"
        "Подсказки: используйте кнопки внизу.\n"
        "Команды: /start, /history, /stats, /top, /export",
        disable_web_page_preview=True
    )

@dp.message(F.text == "📊 Статистика")
async def handle_stats_button(message: Message):
    await handle_stats(message)

@dp.message(Command("order"))
async def handle_order_command(message: Message, state: FSMContext):
    await start_order_flow(message, state)


@dp.message(Command("help"))
async def handle_help(message: Message):
    await send_home(message)
    await message.answer("Также доступны: /history и /stats")

@dp.message(F.text == "📜 История")
@dp.message(Command("history"))
async def handle_history(message: Message):
    await message.answer("Фильтр по напитку:", reply_markup=history_filter_kb())

@dp.callback_query(F.data.startswith("history_filter:"))
async def on_history_filter(callback: CallbackQuery):
    await callback.answer()
    drink = callback.data.split(":")[1].lower()
    await send_history_page(callback.message, drink, 0, user_id=callback.from_user.id)

@dp.callback_query(F.data.startswith("history_more:"))
async def on_history_more(callback: CallbackQuery):
    await callback.answer()
    _, drink, off = callback.data.split(":")
    await send_history_page(callback.message, drink, int(off), user_id=callback.from_user.id)

def _start_of_today_epoch() -> int:
    now = datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp())

@dp.message(Command("stats"))
async def handle_stats(message: Message):
    uid = message.from_user.id
    # today
    s_today = _start_of_today_epoch()
    u_today = s_today + 24 * 60 * 60

    today_rows = await drink_counts_between(user_id=uid, since=s_today, until=u_today)
    # all time
    all_rows = await drink_counts_between(user_id=uid, since=0, until=2_147_483_647)

    today_cnt = Counter(dict(today_rows))
    all_cnt = Counter(dict(all_rows))
    total = sum(all_cnt.values())

    text = (
        "*Статистика по напиткам*\n\n"
        "За сегодня:\n" + (render_stats(today_cnt) if today_cnt else "нет данных") + "\n\n"
        "За всё время:\n" + (render_stats(all_cnt) if all_cnt else "нет данных") +
        f"\n\nВсего заказов: *{total}*"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("delete:"))
async def on_delete_first(callback: CallbackQuery):
    await callback.answer()
    order_id = int(callback.data.split(":", 1)[1])
    await callback.message.edit_reply_markup(
        reply_markup=confirm_delete_kb(order_id)
    )

@dp.callback_query(F.data.startswith("delete_confirm:"))
async def on_delete_confirm(callback: CallbackQuery):
    await callback.answer()
    order_id = int(callback.data.split(":", 1)[1])

    ok = await soft_delete(user_id=callback.from_user.id, order_id=order_id)
    if not ok:
        await callback.answer("Не нашёл заказ 😕", show_alert=True)
        return

    key, rec = remember_deleted(
        user_id=callback.from_user.id,
        order_id=order_id,
        item={},  # заглушка — не используется
        index=0,  # заглушка — не используется
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
    )

    left = seconds_left(rec)
    await callback.message.edit_text(
        f"🗑 Заказ #{order_id} удалён. Можно вернуть в течение {UNDO_DEADLINE_SEC} сек.",
        reply_markup=undo_delete_kb(order_id, seconds_left=left),
    )
    start_undo_countdown(callback.message.bot, key)

@dp.callback_query(F.data.startswith("undo_delete:"))
async def on_undo_delete(callback: CallbackQuery):
    await callback.answer()
    order_id = int(callback.data.split(":", 1)[1])

    rec = get_pending(callback.from_user.id, order_id)
    if not rec:
        await callback.answer("Упс, время вышло 😔", show_alert=True)
        return

    UNDO_BIN.pop((callback.from_user.id, order_id), None)

    ok = await undo_delete(user_id=callback.from_user.id, order_id=order_id)
    if not ok:
        await callback.answer("Не получилось вернуть 🤷", show_alert=True)
        return

    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.edit_text(f"✅ Заказ #{order_id} восстановлен.")

@dp.callback_query(F.data.startswith("delete_cancel:"))
async def on_delete_cancel(callback: CallbackQuery):
    await callback.answer("Ок, не удаляем ✋")
    order_id = int(callback.data.split(":", 1)[1])

    await callback.message.edit_reply_markup(
        reply_markup=history_actions_kb(order_id)
    )

@dp.message(Command("order"))
async def handle_order(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await message.answer(
        "🔔 Похоже, у тебя есть *незавершённый заказ*!\n\n"
            "👉 Выбери действте на клавиатуре ниже:",
        reply_markup=resume_or_cancel_kb(),
        parse_mode="Markdown",
        )
    else:
        await state.set_state(OrderState.drink)
        await message.answer("Отлично! Давай начнём заказ 🎉\n\n"
                            "☕ Что будешь пить?",
                         reply_markup=drink_kb()
                         )

@dp.message(F.text == BTN_RESUME)
async def handle_resume_order(message: Message, state: FSMContext):
    state_name = await state.get_state()
    if not state_name:
        await message.answer("Заказов в процессе нет 👉 /order")
        return

    question, keyboard = QUESTION[state_name]
    await message.answer(question, reply_markup=keyboard)

@dp.message(F.text == BTN_CANCEL)
async def handle_cancel_order(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Заказ отменен ❌", reply_markup=main_kb())

@dp.message(Command("top"))
async def handle_top(message: Message):
    parts = message.text.strip().split(maxsplit=1)
    period = parts[1].lower() if len(parts) == 2 else "30d"
    if period not in {"week", "month", "30d", "all"}:
        await message.answer("Формат: /top [week|month|30d|all]")
        return
    since, until = _bounds_for_top(period)
    rows = await drink_counts_between(user_id=message.from_user.id, since=since, until=until)
    rows = [(d, int(c)) for d, c in rows][:5]
    text = _render_top(rows, title=f"🏆 Топ {_period_label(period)}:")
    await message.answer(text, reply_markup=top_periods_kb(active=period))

@dp.callback_query(F.data.startswith("top:p:"))
async def on_top_period(callback: CallbackQuery):
    await callback.answer()
    period = callback.data.split(":")[2]  # week|month|30d|all
    since, until = _bounds_for_top(period)
    rows = await drink_counts_between(user_id=callback.from_user.id, since=since, until=until)
    rows = [(d, int(c)) for d, c in rows][:5]
    text = _render_top(rows, title=f"🏆 Топ {_period_label(period)}:")

    try:
        await callback.message.edit_text(text, reply_markup=top_periods_kb(active=period))
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=top_periods_kb(active=period))

@dp.message(F.text == "🏆 Топ")
async def handle_top_button(message: Message):
    period = "30d"
    since, until = _bounds_for_top(period)
    rows = await drink_counts_between(user_id=message.from_user.id, since=since, until=until)
    rows = [(d, int(c)) for d, c in rows][:5]
    text = _render_top(rows, title=f"🏆 Топ {_period_label(period)}:")
    await message.answer(text, reply_markup=top_periods_kb(active=period))

@dp.message(Command("cancel"))
async def handle_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Заказ отменён ❌\n\nГотов начать заново? ☕", reply_markup=main_kb())

@dp.message(OrderState.drink)
async def handle_drink(message: Message, state: FSMContext):
    drink = message.text.capitalize().lower()
    if drink not in DRINKS:
        await message.answer(f"Такого напитка нет в меню 😅 Напиши один из: {', '.join(DRINKS.values())}")
        return

    await state.update_data(drink=drink)
    await message.answer(f"Отличный выбор, {DRINKS[drink]} ☕✨")

    await state.set_state(OrderState.size)
    await message.answer("А теперь скажи, какой размер хочешь?", reply_markup=size_kb())

@dp.message(OrderState.size)
async def handle_size(message: Message, state: FSMContext):
    if message.text == "↩ Назад":
        await state.update_data(size=None)
        await state.set_state(OrderState.drink)
        await message.answer(
            "Окей, вернемся к напитку. Выбери напиток:",
            reply_markup=drink_kb()
        )
        return

    size = message.text.capitalize().lower()
    if size not in SIZES:
        await message.answer(
            "Размер должен быть: Small / Medium / Large. Попробуй ещё раз.",
            reply_markup=size_kb(),
        )
        return

    await state.update_data(size=size)
    await message.answer(f"👌 Размер {SIZES[size]} записал!")

    await state.set_state(OrderState.milk)
    await message.answer("Хочешь добавить молоко 🥛?", reply_markup=milk_kb())

@dp.message(OrderState.milk)
async def handle_milk(message: Message, state: FSMContext):
    if message.text == "↩ Назад":
        await state.update_data(milk=None)
        await state.set_state(OrderState.size)
        await message.answer(
            "Окей, вернемся к размеру. Выбери размер:",
            reply_markup=size_kb()
        )
        return

    if message.text == BTN_CANCEL or message.text == "Отменить заказ 🚫":
        await state.clear()
        await message.answer("Заказ отменён ❌", reply_markup=main_kb())
        return

    raw = message.text.strip().lower()
    norm = {"yes": "yes", "y": "yes", "да": "yes", "no": "no", "n": "no", "нет": "no"}.get(raw)
    if norm is None:
        await message.answer("Напиши Yes/No или Да/Нет 😊")
        return
    if norm == "yes":
        await message.answer("Добавляю молочко 🥛✨")
    elif norm == "no":
        await message.answer("Хорошо, без молока 👍")
    else:
        await message.answer("Напиши Yes/No или Да/Нет 🙂")
        return

    await state.update_data(milk=norm)
    data = await state.get_data()

    db_order_id = await create_order(
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        drink=data["drink"],
        size=data["size"],
        milk=data["milk"],
        locale=getattr(message.from_user, "language_code", None),
    )
    logger.info("[DB] created order id =", db_order_id)

    summary = (
    f"🧾 *Твой заказ готов!*\n\n"
    f"☕ Напиток: *{DRINKS[data['drink']]}*\n"
    f"📏 Размер: *{SIZES[data['size']]}*\n"
    f"🥛 Молоко: *{'Добавить' if data['milk']=='yes' else 'Без молока'}*\n\n"
    f"Спасибо за заказ! 🙌"

)
    await message.answer(summary, parse_mode="Markdown", reply_markup=after_order_kb())
    await state.clear()
    await send_home(message)

@dp.message(F.text == "➕ Заказать ещё")
async def handle_order_again(message: Message, state: FSMContext):
    await start_order_flow(message, state)

@dp.message(F.text == "🏠 В меню")
async def handle_go_home(message: Message):
    await send_home(message)

@dp.callback_query(F.data.startswith("repeat:"))
async def on_repeat_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    order_id = int(callback.data.split(":", 1)[1])

    if await state.get_state():
        await callback.message.answer(
            "🔔 Похоже, у тебя есть *незавершённый заказ*!\n\n",
            reply_markup=resume_or_cancel_kb()
        )
        return

    row = await get_order_by_id(user_id=callback.from_user.id, order_id=order_id)

    if row is None:
        await callback.answer("Не нашёл такой заказ 😔", show_alert=True)
        return

    oid, drink, size, milk, created = row
    oid = int(oid)
    created = int(created)

    preview_text = (
        f"*Повторить этот заказ?*\n\n"
        f"☕ Напиток: *{DRINKS[drink]}*\n"
        f"📏 Размер: *{SIZES[size]}*\n"
        f"🥛 Молоко: *{'Добавить' if milk == 'yes' else 'Без молока'}*\n\n"
        f"ID: *#{oid}* · {iso_from_epoch(created)}"
    )

    await callback.message.answer(preview_text, reply_markup=repeat_confirm_kb(oid), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("repeat_confirm:"))
async def handle_repeat_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    order_id = int(callback.data.split(":", 1)[1])

    row = await get_order_by_id(user_id=callback.from_user.id, order_id=order_id)
    if row is None:
        await callback.answer("Не нашёл такой заказ 😬", show_alert=True)
        return

    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=None)

    _, drink, size, milk, _ = row

    new_id = await create_order(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        drink=drink,
        size=size,
        milk=milk
    )

    text = (
        "*Твой заказ готов!* 🎉\n\n"
        f"☕️ Напиток: *{DRINKS[drink]}*\n"
        f"📏 Размер: *{SIZES[size]}*\n"
        f"🥛 Молоко: *{'Добавить' if milk == 'yes' else 'Без молока'}*\n\n"
        f"ID: *{new_id}* · {datetime.now().isoformat(timespec='seconds')}"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await state.clear()

@dp.callback_query(F.data == "repeat_cancel")
async def handle_repeat_cancel(callback: CallbackQuery):
    await callback.answer("Окей, не повторяем ✋")
    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=None)

@dp.callback_query(F.data.startswith("drink:"))
async def handle_drink_callback(callback: CallbackQuery):
    drink = callback.data.split(":")[1]
    await callback.message.answer(f"Ты выбрал: {drink} ☕")
    await callback.answer()

@dp.message(Command("export"))
async def handle_export(message: Message):
    parts = message.text.strip().split()

    if len(parts) == 1:
        await do_export(message, period="month")

    elif len(parts) == 2:
        await do_export(message, period=parts[1])

    elif 3 <= len(parts) <= 4:
        if "-" in parts[1] and "-" in parts[2]:
            d1, d2 = parts[1], parts[2]
            drink = _parse_drink_token(parts[3] if len(parts) == 4 else None)
            await do_export(message, d1=d1, d2=d2, drink=drink)
        else:
            period = parts[1]
            drink = _parse_drink_token(parts[2] if len(parts) == 3 else None)
            await do_export(message, period=period, drink=drink)

    else:
        await message.answer("Формат: /export [today|week|month|all] [drink] или /export YYYY-MM-DD YYYY-MM-DD [drink]")

@dp.message(F.text == "📤 Экспорт")
async def handle_month_btn(message: Message):
    await message.answer("Выбери период для экспорта", reply_markup=export_periods_kb())

@dp.callback_query(F.data.startswith("exp:p:"))
async def on_export_period(callback: CallbackQuery):
    await callback.answer()
    period = callback.data.split(":")[2]

    try:
        await callback.message.edit_text(
            "Выбери напиток для экспорта",
            reply_markup=export_drink_kb(period)
        )
    except TelegramBadRequest:
        await callback.message.answer(
            "Выбери напиток для экспорта",
            reply_markup=export_drink_kb(period)
        )

@dp.callback_query(F.data.startswith("exp:d:"))
async def on_export_drink(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split(":")
    period = parts[2]
    drink_code = parts[3]
    drink = None if drink_code == "all" else drink_code

    key = (callback.from_user.id, callback.message.message_id)
    if key in EXPORT_LOCK:
        await callback.answer("Уже обрабатываю…")
        return
    EXPORT_LOCK.add(key)

    try:
        await do_export(
            callback.message,
            period=period,
            drink=drink,
            user_id=callback.from_user.id
        )

        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=None)
        with suppress(TelegramBadRequest):
            await callback.message.edit_text("Готово ✅")
    finally:
        EXPORT_LOCK.discard(key)

@dp.message(Command("health"))
async def handle_health(message: Message):
    if ADMIN_IDS and message.from_user.id not in ADMIN_IDS:
        await message.answer("Команда недоступна.")
        return
    uptime_sec = int(time.time() - (STARTED_AT or time.time()))
    uptime = _fmt_uptime(uptime_sec)

    ok = await ping_db()
    total = await count_total_orders()
    mine = await count_orders(user_id=message.from_user.id)

    text = (
        "<b>Health</b>\n\n"
        f"Версия: <code>{BOT_VERSION}</code>\n"
        f"Аптайм: <code>{uptime}</code>\n"
        f"DB: <code>{DB_PATH.resolve()}</code>\n"
        f"Пинг БД: <code>{'OK' if ok else 'FAIL'}</code>\n"
        f"Заказы (всего): <b>{total}</b>\n"
        f"Твои заказы: <b>{mine}</b>\n"
    )
    await message.answer(text, disable_web_page_preview=True)

@dp.message(Command("whoami"))
async def whoami(message: Message):
    await message.answer(f"your user_id: {message.from_user.id}")

@dp.message(Command("version"))
async def handle_version(message: Message):
    if ADMIN_IDS and message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(f"Версия бота: <code>{BOT_VERSION}</code>")

# ---------- 3. Точка входа ----------

async def main():
    global bot, STARTED_AT
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

    if os.getenv("DROP_PENDING_UPDATES", "false").lower() in {"1", "true", "yes"}:
        await bot.delete_webhook(drop_pending_updates=True)

    await init_db()
    await open_db()

    STARTED_AT = time.time()

    logger.info("Бот запущен...")
    try:
        await dp.start_polling(bot)
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
