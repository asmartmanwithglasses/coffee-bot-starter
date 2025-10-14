import datetime
import io, csv
from typing import Iterable

from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from .order_states import OrderState
from .keyboards import main_kb, drink_kb, resume_or_cancel_kb
from .catalog import DRINKS, SIZES

async def send_home(msg: Message) -> None:
    drinks_text = "\n".join(DRINKS.values())
    await msg.answer(
        "Привет! Я твой кофейный бот-бариста ☕️\n\n"
        "*Меню напитков:*\n"
        f"{drinks_text}\n\n"
        "Готов оформить заказ? Жми «🧾 Заказ».",
        reply_markup=main_kb(),
        parse_mode="Markdown",
    )
async def start_order_flow(msg: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state:
        await msg.answer(
            "⚠️ Похоже, у тебя есть *незавершённый заказ*!\n\n"
            "Выбери действие на клавиатуре ниже:",
            reply_markup=resume_or_cancel_kb(),
            parse_mode="Markdown",
        )
        return

    await state.set_state(OrderState.drink)
    await msg.answer("Отлично! Давай начнём заказ 🎉\n\n• Что будешь пить?",
                     reply_markup=drink_kb())
def render_order_md(item: dict) -> str:
    drink = DRINKS.get(item["drink"], str(item["drink"]).title())
    size  = SIZES.get(item["size"],  str(item["size"]).title())
    milk  = "Добавить" if item.get("milk") == "yes" else "Без молока"

    return (
        "📦 *История заказа*\n\n"
        f"☕ Напиток: *{drink}*\n"
        f"📏 Размер: *{size}*\n"
        f"🥛 Молоко: *{milk}*\n\n"
        f"ID: *#{item['id']}* · `{item['ts']}`"
    )

def iso_from_epoch(sec: int) -> str:
    return datetime.datetime.fromtimestamp(int(sec), tz=datetime.timezone.utc)\
        .isoformat(timespec="seconds")

def render_order_md_from_db(row: dict) -> str:
    oid, drink, size, milk, created = row
    drink_name = DRINKS.get(drink, drink.title())
    size_name = SIZES.get(size, size.title())
    milk_txt = "Добавить" if milk == "yes" else "Без молока"
    ts_iso = iso_from_epoch(created)

    return (
        "📦 *История заказа*\n\n"
        f"☕ Напиток: *{drink_name}*\n"
        f"📏 Размер: *{size_name}*\n"
        f"🥛 Молоко: *{milk_txt}*\n\n"
        f"ID: *#{oid}* · `{ts_iso}`"
    )

def period_bounds(tag_or_from: str | None = None, to: str | None = None) -> tuple[int, int]:
    now = datetime.datetime.now(datetime.timezone.utc)
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if tag_or_from == "today":
        start = today0
        end = today0 + datetime.timedelta(days=1)

    elif tag_or_from == "week":
        start = today0 - datetime.timedelta(days=now.weekday())
        end = start + datetime.timedelta(days=7)

    elif tag_or_from == "month":
        start = today0.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

    elif (tag_or_from and to
            and len(tag_or_from) == 10 and len(to) == 10):
        y1, m1, d1 = map(int, tag_or_from.split("-"))
        y2, m2, d2 = map(int, to.split("-"))
        start = datetime.datetime(y1, m1, d1, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(y2, m2, d2, tzinfo=datetime.timezone.utc) + datetime.timedelta(days=1)

    else:
        start = today0.replace(day=1)
        end = (start.replace(year=start.year + 1, month=1)
               if start.month == 12 else start.replace(month=start.month + 1))

    return int(start.timestamp()), int(end.timestamp())

def orders_to_csv(rows: Iterable[tuple]) -> bytes:
    buf = io.StringIO(newline="")  # текстовый буфер
    w = csv.writer(buf)

    w.writerow(["id", "created_at", "drink", "size", "milk"])

    for r in rows:
        oid, drink, size, milk, created = r
        iso_from_epoch(created)
        created_iso = iso_from_epoch(created)

        w.writerow([oid, created_iso, drink, size, milk])

    # превратим в bytes
    text = buf.getvalue()
    return text.encode("utf-8")