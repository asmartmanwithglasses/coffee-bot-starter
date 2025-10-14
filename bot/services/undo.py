import math
import time
import asyncio
from contextlib import suppress
from typing import Dict, Tuple, Optional
from ..keyboards import undo_delete_kb
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

UNDO_DEADLINE_SEC = 10
UNDO_BIN: Dict[Tuple[int, int], dict] = {}

def remember_deleted(*, user_id: int, order_id: int, item: dict,
                     index: int, chat_id: int, message_id: int) -> Tuple[Tuple[int, int], dict]:
    rec = {
        "item": item, "index": index,
        # строгий дедлайн на монотонических часах
        "deadline": time.monotonic() + UNDO_DEADLINE_SEC,
        "chat_id": chat_id, "message_id": message_id,
        "order_id": order_id,
    }
    key = (user_id, order_id)
    UNDO_BIN[key] = rec
    return key, rec


def get_pending(user_id: int, order_id: int) -> Optional[dict]:
    rec = UNDO_BIN.get((user_id, order_id))
    if not rec: return None
    # если дедлайн вышел — сразу чистим
    if rec["deadline"] <= time.monotonic():
        UNDO_BIN.pop((user_id, order_id), None)
        return None
    return rec


def seconds_left(rec: dict) -> int:
    # округляем «вверх», но по монотонику и без прыжков
    return max(0, math.ceil(rec["deadline"] - time.monotonic()))


def start_undo_countdown(bot: Bot, key: Tuple[int, int]) -> None:
    """Запускает фоновой отсчёт для конкретного сообщения."""
    asyncio.create_task(_countdown_loop(bot, key))


async def _countdown_loop(bot: Bot, key: Tuple[int, int]) -> None:
    last_shown = None
    while True:
        rec = UNDO_BIN.get(key)
        if not rec:
            return
        left = seconds_left(rec)
        if left <= 0:
            break
        if left != last_shown:
            with suppress(TelegramBadRequest):
                await bot.edit_message_reply_markup(
                chat_id=rec["chat_id"],
                message_id=rec["message_id"],
                reply_markup=undo_delete_kb(rec["order_id"], seconds_left=left),
            )
            last_shown = left

        await asyncio.sleep(0.2)

    rec = UNDO_BIN.pop(key, None)
    if not rec:
        return

    with suppress(TelegramBadRequest):
        await bot.edit_message_reply_markup(
            chat_id=rec["chat_id"],
            message_id=rec["message_id"],
            reply_markup=None,
        )
    with suppress(TelegramBadRequest):
        await bot.edit_message_text(
            chat_id=rec["chat_id"],
            message_id=rec["message_id"],
            text=f"🗑 Заказ #{rec['order_id']} удалён навсегда.",
            disable_web_page_preview=True,
        )