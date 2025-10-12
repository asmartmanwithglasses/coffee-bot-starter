from aiogram.types import Message
from ..catalog import DRINKS, SIZES
from ..keyboards import history_actions_kb, history_more_kb
from ..helpers import iso_from_epoch
from ..repo import get_orders_page, count_orders
import logging
log = logging.getLogger("history")

MAX_TS = 2_147_483_647
PAGE_SIZE = 5

def _label_drink(code: str) -> str: return DRINKS.get(code, code.title())
def _label_size(code: str) -> str:  return SIZES.get(code, code.title())

async def send_history_page(message: Message, drink: str = "all", offset: int = 0, user_id: int | None = None):
    uid = user_id or message.from_user.id
    total = await count_orders(user_id=uid, drink=None if drink in (None, "all") else drink)

    if total == 0:
        await message.answer(
            "История заказа пока пуста 🗃" if drink in (None, "all") else f"Нет заказов для {_label_drink(drink)}.")
        return

    rows = await get_orders_page(user_id=uid, drink=None if drink in (None, "all") else drink,
                                 offset=offset, limit=PAGE_SIZE)
    if not rows:
        return

    shown = min(PAGE_SIZE, total - offset)

    if offset == 0:
        await message.answer(f"История: всего {total} (показано {shown})")

    log.debug("history: uid=%s drink=%s count=%s offset=%s", message.from_user.id, drink, total, offset)

    for r in rows:
        oid, d_code, size_code, milk, created = (r["id"], r["drink"], r["size"], r["milk"], r["created_at"])
        text = (
            f"☕ Напиток: *{_label_drink(d_code)}*\n"
            f"📏 Размер: *{_label_size(size_code)}*\n"
            f"🥛 Молоко: *{'Добавить' if milk == 'yes' else 'Без молока'}*\n"
            f"🕒 {iso_from_epoch(created)}\n"
            f"ID: {oid}"
        )
        await message.answer(text, parse_mode="Markdown", reply_markup=history_actions_kb(oid))

    remain = total - (offset + shown)
    if remain > 0:
        await message.answer(f"Показать ещё {remain}",
                             reply_markup=history_more_kb(drink=drink, offset=offset + shown, remain=remain))

def parse_cb(data: str) -> dict:
    if data.startswith("history_filter:"):
        _, drink = data.split(":", 1)
        return {"cmd": "filter", "drink": drink, "offset": 0}
    if data.startswith("history_more:"):
        _, drink, off = data.split(":", 2)
        return {"cmd": "more", "drink": drink, "offset": int(off)}
    return {"cmd": "unknown", "raw": data}
