"""
database.py — SQLite менеджер для финансового бота
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager

DB_PATH = "finance.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Создаёт таблицы при первом запуске."""
    with get_conn() as conn:
        conn.executescript("""
        -- Пользователи
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            balance     REAL    NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- Транзакции (доходы и расходы)
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(user_id),
            type        TEXT    NOT NULL CHECK(type IN ('income', 'expense')),
            category    TEXT    NOT NULL,
            amount      REAL    NOT NULL CHECK(amount > 0),
            month_key   TEXT    NOT NULL,   -- формат: '2025-05'
            note        TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- Долги
        CREATE TABLE IF NOT EXISTS debts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(user_id),
            direction   TEXT    NOT NULL CHECK(direction IN ('i_gave', 'owe_me')),
            person      TEXT    NOT NULL,
            amount      REAL    NOT NULL CHECK(amount > 0),
            remaining   REAL    NOT NULL,   -- остаток долга
            month_key   TEXT    NOT NULL,
            note        TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- Возвраты долгов
        CREATE TABLE IF NOT EXISTS debt_returns (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            debt_id     INTEGER NOT NULL REFERENCES debts(id),
            user_id     INTEGER NOT NULL REFERENCES users(user_id),
            direction   TEXT    NOT NULL CHECK(direction IN ('returned_to_me', 'i_returned')),
            amount      REAL    NOT NULL CHECK(amount > 0),
            month_key   TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_tx_user_month  ON transactions(user_id, month_key);
        CREATE INDEX IF NOT EXISTS idx_debt_user       ON debts(user_id);
        CREATE INDEX IF NOT EXISTS idx_ret_debt        ON debt_returns(debt_id);
        """)


# ─────────────────────────────────────────────
#  Вспомогательные функции
# ─────────────────────────────────────────────

def current_month() -> str:
    return datetime.now().strftime("%Y-%m")


def ensure_user(user_id: int, username: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(user_id, username) VALUES (?, ?)",
            (user_id, username)
        )


def purge_old_months(user_id: int, keep: int = 6):
    """Удаляет данные старше keep месяцев."""
    with get_conn() as conn:
        months = conn.execute(
            """SELECT DISTINCT month_key FROM transactions
               WHERE user_id = ?
               UNION
               SELECT DISTINCT month_key FROM debts WHERE user_id = ?
               ORDER BY month_key DESC""",
            (user_id, user_id)
        ).fetchall()

        old = [r["month_key"] for r in months[keep:]]
        if not old:
            return

        placeholders = ",".join("?" * len(old))
        conn.execute(
            f"DELETE FROM transactions WHERE user_id=? AND month_key IN ({placeholders})",
            [user_id] + old
        )
        # долги удаляем только если fully returned или старые
        conn.execute(
            f"DELETE FROM debts WHERE user_id=? AND month_key IN ({placeholders}) AND remaining<=0",
            [user_id] + old
        )


# ─────────────────────────────────────────────
#  Доходы / Расходы
# ─────────────────────────────────────────────

def add_income(user_id: int, category: str, amount: float, note: str = ""):
    month = current_month()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transactions(user_id,type,category,amount,month_key,note) VALUES(?,?,?,?,?,?)",
            (user_id, "income", category, amount, month, note)
        )
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
    purge_old_months(user_id)


def add_expense(user_id: int, category: str, amount: float, note: str = ""):
    month = current_month()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transactions(user_id,type,category,amount,month_key,note) VALUES(?,?,?,?,?,?)",
            (user_id, "expense", category, amount, month, note)
        )
        conn.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (amount, user_id)
        )
    purge_old_months(user_id)


# ─────────────────────────────────────────────
#  Долги
# ─────────────────────────────────────────────

def add_debt_i_gave(user_id: int, person: str, amount: float, note: str = "") -> int:
    """Я дал → баланс уменьшается, долг записывается."""
    month = current_month()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO debts(user_id,direction,person,amount,remaining,month_key,note) VALUES(?,?,?,?,?,?,?)",
            (user_id, "i_gave", person, amount, amount, month, note)
        )
        debt_id = cur.lastrowid
        conn.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (amount, user_id)
        )
    return debt_id


def add_debt_owe_me(user_id: int, person: str, amount: float, note: str = "") -> int:
    """Мне должны → баланс НЕ меняется, только запись."""
    month = current_month()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO debts(user_id,direction,person,amount,remaining,month_key,note) VALUES(?,?,?,?,?,?,?)",
            (user_id, "owe_me", person, amount, amount, month, note)
        )
    return cur.lastrowid


def return_debt(user_id: int, debt_id: int, direction: str, amount: float):
    """
    direction='returned_to_me' → мне вернули → баланс +
    direction='i_returned'     → я вернул    → баланс -
    """
    month = current_month()
    with get_conn() as conn:
        debt = conn.execute(
            "SELECT * FROM debts WHERE id=? AND user_id=?", (debt_id, user_id)
        ).fetchone()
        if not debt:
            raise ValueError("Долг не найден")

        actual = min(amount, debt["remaining"])

        conn.execute(
            "INSERT INTO debt_returns(debt_id,user_id,direction,amount,month_key) VALUES(?,?,?,?,?)",
            (debt_id, user_id, direction, actual, month)
        )
        conn.execute(
            "UPDATE debts SET remaining = remaining - ? WHERE id=?",
            (actual, debt_id)
        )
        if direction == "returned_to_me":
            conn.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id=?",
                (actual, user_id)
            )
        else:  # i_returned
            conn.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id=?",
                (actual, user_id)
            )


def get_active_debts(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM debts WHERE user_id=? AND remaining > 0 ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()


# ─────────────────────────────────────────────
#  Статистика
# ─────────────────────────────────────────────

def get_monthly_stats(user_id: int, month: str = None):
    if not month:
        month = current_month()
    with get_conn() as conn:
        income = conn.execute(
            "SELECT COALESCE(SUM(amount),0) as total FROM transactions WHERE user_id=? AND type='income' AND month_key=?",
            (user_id, month)
        ).fetchone()["total"]

        expense = conn.execute(
            "SELECT COALESCE(SUM(amount),0) as total FROM transactions WHERE user_id=? AND type='expense' AND month_key=?",
            (user_id, month)
        ).fetchone()["total"]

        balance = conn.execute(
            "SELECT balance FROM users WHERE user_id=?", (user_id,)
        ).fetchone()["balance"]

        # Активные долги
        debts = conn.execute(
            "SELECT direction, SUM(remaining) as total FROM debts WHERE user_id=? AND remaining>0 GROUP BY direction",
            (user_id,)
        ).fetchall()
        debt_map = {r["direction"]: r["total"] for r in debts}

        return {
            "month": month,
            "income": income,
            "expense": expense,
            "profit": income - expense,
            "balance": balance,
            "i_gave": debt_map.get("i_gave", 0),
            "owe_me": debt_map.get("owe_me", 0),
        }


def get_income_by_category(user_id: int, month: str = None):
    if not month:
        month = current_month()
    with get_conn() as conn:
        return conn.execute(
            "SELECT category, SUM(amount) as total FROM transactions WHERE user_id=? AND type='income' AND month_key=? GROUP BY category",
            (user_id, month)
        ).fetchall()


def get_expense_by_category(user_id: int, month: str = None):
    if not month:
        month = current_month()
    with get_conn() as conn:
        return conn.execute(
            "SELECT category, SUM(amount) as total FROM transactions WHERE user_id=? AND type='expense' AND month_key=? GROUP BY category",
            (user_id, month)
        ).fetchall()
