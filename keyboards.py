"""
keyboards.py — все клавиатуры бота
"""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


# ─────────────────────────────────────────────
#  Reply-клавиатуры (постоянные снизу экрана)
# ─────────────────────────────────────────────

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Доходы"),   KeyboardButton(text="💸 Расходы")],
            [KeyboardButton(text="🤝 Долги"),     KeyboardButton(text="📊 Статистика")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел"
    )


# ─────────────────────────────────────────────
#  Inline-клавиатуры
# ─────────────────────────────────────────────

def income_categories() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 Зарплата", callback_data="income:salary")],
        [InlineKeyboardButton(text="🎁 Премия",   callback_data="income:bonus")],
        [InlineKeyboardButton(text="💳 Аванс",    callback_data="income:advance")],
        [InlineKeyboardButton(text="◀️ Назад",    callback_data="back:main")],
    ])


def expense_categories() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍕 Еда",    callback_data="expense:food")],
        [InlineKeyboardButton(text="📦 Прочее", callback_data="expense:other")],
        [InlineKeyboardButton(text="◀️ Назад",  callback_data="back:main")],
    ])


def debt_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Я дал",       callback_data="debt:i_gave")],
        [InlineKeyboardButton(text="⬅️ Мне должны",  callback_data="debt:owe_me")],
        [InlineKeyboardButton(text="✅ Вернули мне",  callback_data="debt:returned_to_me")],
        [InlineKeyboardButton(text="🔄 Я вернул",    callback_data="debt:i_returned")],
        [InlineKeyboardButton(text="◀️ Назад",       callback_data="back:main")],
    ])


def debt_list_keyboard(debts, action: str) -> InlineKeyboardMarkup:
    """Список активных долгов для выбора при возврате."""
    buttons = []
    for d in debts:
        label = f"{d['person']} — {d['remaining']:,.0f} сум"
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=f"return:{action}:{d['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back:debt")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back:main")]
    ])
