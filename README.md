# 💰 Финансовый Telegram-бот

Бот для учёта личных финансов на **aiogram 3** + **SQLite**.

---

## Структура проекта

```
finance_bot/
├── main.py          # Точка входа, запуск polling
├── database.py      # Вся работа с SQLite
├── handlers.py      # Обработчики сообщений и кнопок
├── keyboards.py     # Все клавиатуры
├── states.py        # FSM-состояния
├── requirements.txt
└── finance.db       # Создаётся автоматически
```

---

## Архитектура БД

```sql
users
  user_id     PK
  username
  balance         ← текущий баланс (изменяется при каждой операции)
  created_at

transactions
  id          PK
  user_id     FK → users
  type        'income' | 'expense'
  category    'salary' | 'bonus' | 'advance' | 'food' | 'other'
  amount
  month_key   '2025-05'
  note
  created_at

debts
  id          PK
  user_id     FK → users
  direction   'i_gave' | 'owe_me'
  person      имя контрагента
  amount      исходная сумма
  remaining   остаток (уменьшается при возвратах)
  month_key
  note
  created_at

debt_returns
  id          PK
  debt_id     FK → debts
  user_id     FK → users
  direction   'returned_to_me' | 'i_returned'
  amount
  month_key
  created_at
```

---

## Логика баланса

| Операция         | Баланс   | Запись в          |
|------------------|----------|-------------------|
| Доход            | +сумма   | transactions      |
| Расход           | -сумма   | transactions      |
| Я дал (долг)     | -сумма   | debts (i_gave)    |
| Мне должны       | без изм. | debts (owe_me)    |
| Вернули мне      | +сумма   | debt_returns      |
| Я вернул         | -сумма   | debt_returns      |

---

## FSM-диаграмма

```
/start → главное меню (Reply-кнопки)

[💰 Доходы]
  → inline: выбор категории
  → ввод суммы → сохранение → главное меню

[💸 Расходы]
  → inline: выбор категории
  → ввод суммы → сохранение → главное меню

[🤝 Долги]
  Я дал / Мне должны:
    → ввод имени → ввод суммы → сохранение

  Вернули мне / Я вернул:
    → список активных долгов (inline)
    → выбор долга → ввод суммы → сохранение

[📊 Статистика]
  → сводка: доходы/расходы/прибыль/баланс/долги
```

---

## Запуск

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Задать токен
export BOT_TOKEN="ваш_токен_от_BotFather"

# 3. Запустить
python main.py
```

---

## Хранение данных

- Последние **6 месяцев** — автоочистка при каждой записи
- Активные долги (remaining > 0) **не удаляются** даже если старые
- Баланс хранится накопительно в `users.balance`
