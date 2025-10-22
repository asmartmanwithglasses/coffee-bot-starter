from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from .catalog import DRINKS

BTN_CANCEL = "Отменить заказ 🚫"


def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧾 Заказ"), KeyboardButton(text="📜 История")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🏆 Топ")],
            [KeyboardButton(text="ℹ️ О боте"), KeyboardButton(text="📤 Экспорт")],
        ],
        resize_keyboard=True,
    )


def drink_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Latte"), KeyboardButton(text="Cappuccino")],
            [KeyboardButton(text="Americano"), KeyboardButton(text="Flat White")],
            [KeyboardButton(text="Mocha")],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def size_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Small"), KeyboardButton(text="Medium"), KeyboardButton(text="Large")],
            [KeyboardButton(text="↩ Назад"), KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def milk_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Yes"), KeyboardButton(text="No"), KeyboardButton(text="↩ Назад")],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def resume_or_cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Продолжить заказ"), KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def history_actions_kb(order_id: int, display_no: int | None = None) -> InlineKeyboardMarkup:
    tag = f"№{display_no}" if display_no is not None else f"#{order_id}"
    b1 = InlineKeyboardButton(text=f"🔁 Повторить {tag}", callback_data=f"repeat:{order_id}")
    b2 = InlineKeyboardButton(text=f"❌ Удалить {tag}",  callback_data=f"delete:{order_id}")
    return InlineKeyboardMarkup(inline_keyboard=[[b1, b2]])


def confirm_delete_kb(order_id: int, display_no: int) -> InlineKeyboardMarkup:
    yes = InlineKeyboardButton(
        text=f"✅ Да, удалить №{display_no}",
        callback_data=f"delete_confirm:{order_id}",
    )
    cancel = InlineKeyboardButton(
        text="↩️ Отмена",
        callback_data=f"delete_cancel:{order_id}",
    )
    return InlineKeyboardMarkup(inline_keyboard=[[yes], [cancel]])


def history_filter_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="☕ Все", callback_data="history_filter:all")]]
    codes = list(DRINKS.items())
    for i in range(0, len(codes), 2):
        chunk = codes[i:i + 2]
        rows.append([
            InlineKeyboardButton(text=label, callback_data=f"history_filter:{code}")
            for code, label in chunk
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def history_more_kb(*, drink: str, offset: int, remain: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"Показать ещё {remain}",
            callback_data=f"history_more:{drink}:{offset}",
        )
    ]])


def repeat_confirm_kb(order_id: int, display_no: int) -> InlineKeyboardMarkup:
    ok = InlineKeyboardButton(
        text=f"✅ Оформить как №{display_no}",
        callback_data=f"repeat_confirm:{order_id}",
    )
    cancel = InlineKeyboardButton(text="❌ Отмена", callback_data="repeat_cancel")
    return InlineKeyboardMarkup(inline_keyboard=[[ok], [cancel]])


def undo_delete_kb(order_id: int, *, seconds_left: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"↩️ Вернуть ({seconds_left})",
            callback_data=f"undo_delete:{order_id}",
        )
    ]])


def after_order_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="➕ Заказать ещё"), KeyboardButton(text="🏠 В меню")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def export_periods_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сегодня",   callback_data="exp:p:today")],
        [InlineKeyboardButton(text="Неделя",    callback_data="exp:p:week")],
        [InlineKeyboardButton(text="Месяц",     callback_data="exp:p:month")],
        [InlineKeyboardButton(text="Всё время", callback_data="exp:p:all")],
    ])


def export_drink_kb(period: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="☕ Все", callback_data=f"exp:d:{period}:all")]]
    codes = list(DRINKS.items())
    for i in range(0, len(codes), 2):
        chunk = codes[i:i + 2]
        rows.append([
            InlineKeyboardButton(text=label, callback_data=f"exp:d:{period}:{code}")
            for code, label in chunk
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def top_periods_kb(active: str = "30d") -> InlineKeyboardMarkup:
    def lbl(code: str, text: str) -> str:
        return f"• {text}" if code == active else text

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=lbl("week",  "Неделя"),   callback_data="top:p:week"),
            InlineKeyboardButton(text=lbl("month", "Месяц"),    callback_data="top:p:month"),
        ],
        [
            InlineKeyboardButton(text=lbl("30d",   "30 дней"),  callback_data="top:p:30d"),
            InlineKeyboardButton(text=lbl("all",   "Всё время"), callback_data="top:p:all"),
        ],
    ])
