"""
states.py — FSM-состояния (aiogram 3.x)
"""

from aiogram.fsm.state import State, StatesGroup


class IncomeState(StatesGroup):
    waiting_amount = State()      # ждём сумму
    # category хранится в data


class ExpenseState(StatesGroup):
    waiting_amount = State()


class DebtState(StatesGroup):
    waiting_person  = State()     # имя контрагента
    waiting_amount  = State()     # сумма долга
    waiting_return_amount = State()  # сумма возврата
