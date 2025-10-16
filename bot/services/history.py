from aiogram.types import Message
from ..catalog import DRINKS, SIZES
from ..keyboards import history_actions_kb, history_more_kb
from ..repo import get_orders_page, count_orders
from ..utils import fmt_ts
import logging

log = logging.getLogger("history")

PAGE_SIZE = 5

def _label_drink(code: str) -> str:
    return DRINKS.get(code, code.title())

def _label_size(code: str) -> str:
    return SIZES.get(code, code.title())

async def send_history_page(
    message: Message,
    drink: str = "all",
    offset: int = 0,
    user_id: int | None = None
):
    uid = user_id or message.from_user.id
    drink_filter = None if drink in (None, "all") else drink

    total = await count_orders(user_id=uid, drink=drink_filter)
    if total == 0:
        text = (
            "История заказа пока пуста 🗃"
            if drink_filter is None else
            f"Нет заказов для {_label_drink(drink)}."
        )
        await message.answer(text)
        return

    rows = await get_orders_page(
        user_id=uid,
        drink=drink_filter,
        offset=offset,
        limit=PAGE_SIZE
    )
    if not rows:
        return

    shown = min(PAGE_SIZE, total - offset)

    if offset == 0:
        f_label = "Все" if drink_filter is None else _label_drink(drink)
        await message.answer(f"История: всего {total} (показано {shown}) · Фильтр: {f_label}")

    log.debug("history: uid=%s drink=%s count=%s offset=%s", uid, drink, total, offset)

    for r in rows:
        oid = r["id"]
        d_code = r["drink"]
        size_code = r["size"]
        milk = r["milk"]
        created = r["created_at"]

        text = (
            f"☕ <b>Напиток:</b> {_label_drink(d_code)}\n"
            f"📏 <b>Размер:</b> {_label_size(size_code)}\n"
            f"🥛 <b>Молоко:</b> {'Добавить' if milk == 'yes' else 'Без молока'}\n"
            f"🕒 <b>Время:</b> {fmt_ts(created)}\n"
            f"ID: <code>#{oid}</code>"
        )
        await message.answer(text, reply_markup=history_actions_kb(oid), parse_mode="HTML")

    remain = total - (offset + shown)
    if remain > 0:
        await message.answer(
            f"Показать ещё {remain}",
            reply_markup=history_more_kb(drink=drink, offset=offset + shown, remain=remain)
        )

def parse_cb(data: str) -> dict:
    if data.startswith("history_filter:"):
        _, drink = data.split(":", 1)
        return {"cmd": "filter", "drink": drink, "offset": 0}
    if data.startswith("history_more:"):
        _, drink, off = data.split(":", 2)
        return {"cmd": "more", "drink": drink, "offset": int(off)}
    return {"cmd": "unknown", "raw": data}
