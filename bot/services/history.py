from aiogram.types import Message
from ..catalog import DRINKS, SIZES
from ..keyboards import history_actions_kb, history_more_kb
from ..repo import orders_for_period, user_order_number
from ..utils import fmt_ts
import logging

log = logging.getLogger("history")

PAGE_SIZE = 5

def _label_drink(code: str) -> str:
    return DRINKS.get(code, code.title())

def _label_size(code: str) -> str:
    return SIZES.get(code, code.title())

async def send_history_page(message: Message, drink: str, offset: int, *, user_id: int, page_size: int = 5) -> None:
    drink_code = None if (drink is None or drink.lower() == "all") else drink.lower()

    rows = await orders_for_period(
        user_id=user_id,
        since=0,
        until=2_147_483_647,
        drink=drink_code
    )

    if not rows:
        await message.answer("История заказа пока пуста 🧾")
        return

    page = rows[offset: offset + page_size]
    remain = max(0, len(rows) - (offset + page_size))

    for oid, dcode, size, milk, created in page:
        mine_no = await user_order_number(user_id, int(created))
        text = (
            f"☕ <b>Напиток:</b> {DRINKS.get(dcode, dcode.title())}\n"
            f"📏 <b>Размер:</b> {SIZES.get(size, size.title())}\n"
            f"🥛 <b>Молоко:</b> {'Добавить' if milk == 'yes' else 'Без молока'}\n"
            f"🕒 {fmt_ts(created)}\n"
            f"ID: <code>#{oid}</code> · Ваш №<b>{mine_no}</b>"
        )
        kb = history_actions_kb(oid, display_no=mine_no)
        await message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

    if remain > 0:
        await message.answer(
            "Показать ещё?",
            reply_markup=history_more_kb(drink=drink if drink else "all", offset=offset + page_size, remain=remain)
        )

def parse_cb(data: str) -> dict:
    if data.startswith("history_filter:"):
        _, drink = data.split(":", 1)
        return {"cmd": "filter", "drink": drink, "offset": 0}
    if data.startswith("history_more:"):
        _, drink, off = data.split(":", 2)
        return {"cmd": "more", "drink": drink, "offset": int(off)}
    return {"cmd": "unknown", "raw": data}
