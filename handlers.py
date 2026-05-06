"""
handlers.py — все обработчики бота
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

import database as db
import keyboards as kb
from states import IncomeState, ExpenseState, DebtState

router = Router()

# ═══════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    db.ensure_user(msg.from_user.id, msg.from_user.username or "")
    await msg.answer(
        "👋 Привет! Я помогу вести личные финансы.\n"
        "Выбери раздел 👇",
        reply_markup=kb.main_menu()
    )


# ═══════════════════════════════════════════════
#  Главное меню (Reply-кнопки)
# ═══════════════════════════════════════════════

@router.message(F.text == "💰 Доходы")
async def menu_income(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Выбери категорию дохода:", reply_markup=kb.income_categories())


@router.message(F.text == "💸 Расходы")
async def menu_expense(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Выбери категорию расхода:", reply_markup=kb.expense_categories())


@router.message(F.text == "🤝 Долги")
async def menu_debt(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Раздел долгов:", reply_markup=kb.debt_menu())


@router.message(F.text == "📊 Статистика")
async def menu_stats(msg: Message, state: FSMContext):
    await state.clear()
    await show_stats(msg)


# ═══════════════════════════════════════════════
#  Универсальная кнопка «Назад»
# ═══════════════════════════════════════════════

@router.callback_query(F.data == "back:main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Выбери раздел:")
    await call.message.answer("👇", reply_markup=kb.main_menu())
    await call.answer()


@router.callback_query(F.data == "back:debt")
async def back_debt(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Раздел долгов:", reply_markup=kb.debt_menu())
    await call.answer()


# ═══════════════════════════════════════════════
#  ДОХОДЫ
# ═══════════════════════════════════════════════

INCOME_LABELS = {
    "Зарплата":  "💼 Зарплата",
    "Премия":   "🎁 Премия",
    "Аванс": "💳 Аванс",
}

@router.callback_query(F.data.startswith("income:"))
async def income_category_chosen(call: CallbackQuery, state: FSMContext):
    category = call.data.split(":")[1]
    await state.set_state(IncomeState.waiting_amount)
    await state.update_data(category=category)
    label = INCOME_LABELS.get(category, category)
    await call.message.edit_text(
        f"📥 {label}\n\nВведи сумму (сум):",
        reply_markup=kb.cancel_kb()
    )
    await call.answer()


@router.message(IncomeState.waiting_amount)
async def income_amount_entered(msg: Message, state: FSMContext):
    amount = parse_amount(msg.text)
    if amount is None:
        await msg.answer("❗ Введи корректную сумму, например: 500000")
        return

    data = await state.get_data()
    category = data["category"]
    db.add_income(msg.from_user.id, category, amount)

    label = INCOME_LABELS.get(category, category)
    stats = db.get_monthly_stats(msg.from_user.id)
    await state.clear()
    await msg.answer(
        f"✅ Доход добавлен!\n"
        f"📌 {label}: +{fmt(amount)} сум\n"
        f"💰 Баланс: {fmt(stats['balance'])} сум",
        reply_markup=kb.main_menu()
    )


# ═══════════════════════════════════════════════
#  РАСХОДЫ
# ═══════════════════════════════════════════════

EXPENSE_LABELS = {
    "food":  "🍕 Еда",
    "other": "📦 Прочее",
}

@router.callback_query(F.data.startswith("expense:"))
async def expense_category_chosen(call: CallbackQuery, state: FSMContext):
    category = call.data.split(":")[1]
    await state.set_state(ExpenseState.waiting_amount)
    await state.update_data(category=category)
    label = EXPENSE_LABELS.get(category, category)
    await call.message.edit_text(
        f"📤 {label}\n\nВведи сумму (сум):",
        reply_markup=kb.cancel_kb()
    )
    await call.answer()


@router.message(ExpenseState.waiting_amount)
async def expense_amount_entered(msg: Message, state: FSMContext):
    amount = parse_amount(msg.text)
    if amount is None:
        await msg.answer("❗ Введи корректную сумму, например: 150000")
        return

    data = await state.get_data()
    category = data["category"]
    db.add_expense(msg.from_user.id, category, amount)

    label = EXPENSE_LABELS.get(category, category)
    stats = db.get_monthly_stats(msg.from_user.id)
    await state.clear()
    await msg.answer(
        f"✅ Расход записан!\n"
        f"📌 {label}: -{fmt(amount)} сум\n"
        f"💰 Баланс: {fmt(stats['balance'])} сум",
        reply_markup=kb.main_menu()
    )


# ═══════════════════════════════════════════════
#  ДОЛГИ — Я дал / Мне должны
# ═══════════════════════════════════════════════

DEBT_LABELS = {
    "i_gave":  "➡️ Я дал",
    "owe_me":  "⬅️ Мне должны",
}

@router.callback_query(F.data.in_({"debt:i_gave", "debt:owe_me"}))
async def debt_new_start(call: CallbackQuery, state: FSMContext):
    direction = call.data.split(":")[1]
    await state.set_state(DebtState.waiting_person)
    await state.update_data(direction=direction)
    label = DEBT_LABELS[direction]
    await call.message.edit_text(
        f"{label}\n\nВведи имя человека:",
        reply_markup=kb.cancel_kb()
    )
    await call.answer()


@router.message(DebtState.waiting_person)
async def debt_person_entered(msg: Message, state: FSMContext):
    await state.update_data(person=msg.text.strip())
    await state.set_state(DebtState.waiting_amount)
    await msg.answer("Введи сумму (сум):", reply_markup=kb.cancel_kb())


@router.message(DebtState.waiting_amount)
async def debt_amount_entered(msg: Message, state: FSMContext):
    amount = parse_amount(msg.text)
    if amount is None:
        await msg.answer("❗ Введи корректную сумму")
        return

    data = await state.get_data()
    uid = msg.from_user.id
    direction = data["direction"]
    person = data["person"]

    if direction == "i_gave":
        db.add_debt_i_gave(uid, person, amount)
        stats = db.get_monthly_stats(uid)
        text = (
            f"✅ Долг записан!\n"
            f"➡️ Дал {person}: {fmt(amount)} сум\n"
            f"💰 Баланс: {fmt(stats['balance'])} сум"
        )
    else:
        db.add_debt_owe_me(uid, person, amount)
        text = (
            f"✅ Долг записан!\n"
            f"⬅️ {person} должен тебе: {fmt(amount)} сум\n"
            f"(Баланс не изменён)"
        )

    await state.clear()
    await msg.answer(text, reply_markup=kb.main_menu())


# ═══════════════════════════════════════════════
#  ДОЛГИ — Возвраты
# ═══════════════════════════════════════════════

RETURN_LABELS = {
    "returned_to_me": "✅ Вернули мне",
    "i_returned":     "🔄 Я вернул",
}

@router.callback_query(F.data.in_({"debt:returned_to_me", "debt:i_returned"}))
async def debt_return_list(call: CallbackQuery, state: FSMContext):
    action = call.data.split(":")[1]   # returned_to_me / i_returned
    uid = call.from_user.id

    # Фильтруем долги по направлению
    all_debts = db.get_active_debts(uid)
    if action == "returned_to_me":
        debts = [d for d in all_debts if d["direction"] == "owe_me"]
    else:
        debts = [d for d in all_debts if d["direction"] == "i_gave"]

    if not debts:
        await call.answer("Нет активных долгов в этой категории", show_alert=True)
        return

    label = RETURN_LABELS[action]
    await state.update_data(return_action=action)
    await call.message.edit_text(
        f"{label}\n\nВыбери долг:",
        reply_markup=kb.debt_list_keyboard(debts, action)
    )
    await call.answer()


@router.callback_query(F.data.startswith("return:"))
async def debt_return_chosen(call: CallbackQuery, state: FSMContext):
    # return:<action>:<debt_id>
    parts = call.data.split(":")
    action  = parts[1]
    debt_id = int(parts[2])
    await state.set_state(DebtState.waiting_return_amount)
    await state.update_data(return_action=action, debt_id=debt_id)
    await call.message.edit_text(
        "Введи возвращаемую сумму (сум):",
        reply_markup=kb.cancel_kb()
    )
    await call.answer()


@router.message(DebtState.waiting_return_amount)
async def debt_return_amount(msg: Message, state: FSMContext):
    amount = parse_amount(msg.text)
    if amount is None:
        await msg.answer("❗ Введи корректную сумму")
        return

    data = await state.get_data()
    uid     = msg.from_user.id
    action  = data["return_action"]
    debt_id = data["debt_id"]

    db.return_debt(uid, debt_id, action, amount)
    stats = db.get_monthly_stats(uid)
    label = RETURN_LABELS[action]
    await state.clear()
    await msg.answer(
        f"✅ Возврат записан!\n"
        f"{label}: {fmt(amount)} сум\n"
        f"💰 Баланс: {fmt(stats['balance'])} сум",
        reply_markup=kb.main_menu()
    )


# ═══════════════════════════════════════════════
#  СТАТИСТИКА
# ═══════════════════════════════════════════════

async def show_stats(msg: Message):
    uid   = msg.from_user.id
    stats = db.get_monthly_stats(uid)
    inc_cat  = db.get_income_by_category(uid)
    exp_cat  = db.get_expense_by_category(uid)

    month_display = stats["month"]   # 2025-05

    # Доходы по категориям
    inc_lines = "\n".join(
        f"  • {r['category']}: {fmt(r['total'])} сум" for r in inc_cat
    ) or "  нет данных"

    # Расходы по категориям
    exp_lines = "\n".join(
        f"  • {r['category']}: {fmt(r['total'])} сум" for r in exp_cat
    ) or "  нет данных"

    profit_sign = "+" if stats["profit"] >= 0 else ""

    text = (
        f"📊 *Статистика за {month_display}*\n\n"
        f"💰 *Доходы:* {fmt(stats['income'])} сум\n{inc_lines}\n\n"
        f"💸 *Расходы:* {fmt(stats['expense'])} сум\n{exp_lines}\n\n"
        f"📈 *Прибыль:* {profit_sign}{fmt(stats['profit'])} сум\n"
        f"🏦 *Текущий баланс:* {fmt(stats['balance'])} сум\n\n"
        f"🤝 *Активные долги:*\n"
        f"  ➡️ Я дал: {fmt(stats['i_gave'])} сум\n"
        f"  ⬅️ Мне должны: {fmt(stats['owe_me'])} сум"
    )
    await msg.answer(text, parse_mode="Markdown", reply_markup=kb.main_menu())


# ═══════════════════════════════════════════════
#  Утилиты
# ═══════════════════════════════════════════════

def parse_amount(text: str):
    """Парсит сумму из строки. Возвращает float или None."""
    try:
        cleaned = text.replace(" ", "").replace(",", "").replace("_", "")
        value = float(cleaned)
        return value if value > 0 else None
    except (ValueError, AttributeError):
        return None


def fmt(amount: float) -> str:
    """Форматирует число с разделителями тысяч."""
    return f"{amount:,.0f}".replace(",", " ")
