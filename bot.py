import os
import sqlite3
from datetime import datetime, date, timedelta
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не найден BOT_TOKEN")

DB_NAME = os.getenv("DB_NAME", "wishlist_bot.db")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
user_states = {}

WEEKDAY_NAMES = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}

DAY_BUTTONS = [
    ("Пн", 0),
    ("Вт", 1),
    ("Ср", 2),
    ("Чт", 3),
    ("Пт", 4),
    ("Сб", 5),
    ("Вс", 6),
]


# =========================
# БАЗА
# =========================
def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_text TEXT NOT NULL,
            task_date TEXT NOT NULL,
            is_done INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)

    # Повторяющиеся задачи по дням недели
    cur.execute("""
        CREATE TABLE IF NOT EXISTS weekly_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            weekday INTEGER NOT NULL,
            task_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Разовые задачи по дням недели
    # added_to_date = в какой день эта задача уже была перенесена в обычные задачи
    cur.execute("""
        CREATE TABLE IF NOT EXISTS weekday_once_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            weekday INTEGER NOT NULL,
            task_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            added_to_date TEXT
        )
    """)

    conn.commit()
    conn.close()


# =========================
# ОБЫЧНЫЕ ЗАДАЧИ
# =========================
def add_task(user_id: int, task_text: str, task_date: str | None = None):
    if task_date is None:
        task_date = date.today().strftime("%Y-%m-%d")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tasks (user_id, task_text, task_date, is_done, created_at, completed_at)
        VALUES (?, ?, ?, 0, ?, NULL)
    """, (
        user_id,
        task_text,
        task_date,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()


def get_tasks_by_date(user_id: int, task_date: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, task_text, is_done
        FROM tasks
        WHERE user_id = ? AND task_date = ?
        ORDER BY id ASC
    """, (user_id, task_date))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_today_tasks(user_id: int):
    return get_tasks_by_date(user_id, date.today().strftime("%Y-%m-%d"))


def get_last_days_with_tasks(user_id: int, limit: int = 7):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT task_date
        FROM tasks
        WHERE user_id = ?
        ORDER BY task_date DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]


def mark_task_done(user_id: int, task_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM tasks
        WHERE user_id = ? AND id = ?
    """, (user_id, task_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return False

    cur.execute("""
        UPDATE tasks
        SET is_done = 1,
            completed_at = ?
        WHERE user_id = ? AND id = ?
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user_id,
        task_id
    ))
    conn.commit()
    conn.close()
    return True


def delete_task(user_id: int, task_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM tasks
        WHERE user_id = ? AND id = ?
    """, (user_id, task_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return False

    cur.execute("""
        DELETE FROM tasks
        WHERE user_id = ? AND id = ?
    """, (user_id, task_id))
    conn.commit()
    conn.close()
    return True


# =========================
# ПОВТОРЯЮЩИЕСЯ ПО ДНЯМ НЕДЕЛИ
# =========================
def add_weekly_task(user_id: int, weekday: int, task_text: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO weekly_tasks (user_id, weekday, task_text, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        weekday,
        task_text,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()


def get_weekly_tasks(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, weekday, task_text
        FROM weekly_tasks
        WHERE user_id = ?
        ORDER BY weekday ASC, id ASC
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_weekly_tasks_for_day(user_id: int, weekday: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, weekday, task_text
        FROM weekly_tasks
        WHERE user_id = ? AND weekday = ?
        ORDER BY id ASC
    """, (user_id, weekday))
    rows = cur.fetchall()
    conn.close()
    return rows


def delete_weekly_task(user_id: int, weekly_task_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM weekly_tasks
        WHERE user_id = ? AND id = ?
    """, (user_id, weekly_task_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return False

    cur.execute("""
        DELETE FROM weekly_tasks
        WHERE user_id = ? AND id = ?
    """, (user_id, weekly_task_id))
    conn.commit()
    conn.close()
    return True


# =========================
# РАЗОВЫЕ ПО ДНЯМ НЕДЕЛИ
# =========================
def add_weekday_once_task(user_id: int, weekday: int, task_text: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO weekday_once_tasks (user_id, weekday, task_text, created_at, is_used, added_to_date)
        VALUES (?, ?, ?, ?, 0, NULL)
    """, (
        user_id,
        weekday,
        task_text,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()


def get_weekday_once_tasks(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, weekday, task_text, is_used, added_to_date
        FROM weekday_once_tasks
        WHERE user_id = ?
        ORDER BY is_used ASC, weekday ASC, id ASC
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_weekday_once_tasks_for_day(user_id: int, weekday: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, weekday, task_text
        FROM weekday_once_tasks
        WHERE user_id = ? AND weekday = ? AND is_used = 0
        ORDER BY id ASC
    """, (user_id, weekday))
    rows = cur.fetchall()
    conn.close()
    return rows


def mark_weekday_once_task_used(task_id: int, task_date: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE weekday_once_tasks
        SET is_used = 1,
            added_to_date = ?
        WHERE id = ?
    """, (task_date, task_id))
    conn.commit()
    conn.close()


def delete_weekday_once_task(user_id: int, task_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM weekday_once_tasks
        WHERE user_id = ? AND id = ?
    """, (user_id, task_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return False

    cur.execute("""
        DELETE FROM weekday_once_tasks
        WHERE user_id = ? AND id = ?
    """, (user_id, task_id))
    conn.commit()
    conn.close()
    return True


# =========================
# АВТОДОБАВЛЕНИЕ ДЕЛ ДНЯ
# =========================
def add_today_tasks_from_weekday(user_id: int) -> tuple[int, int]:
    today_weekday = date.today().weekday()
    today_str = date.today().strftime("%Y-%m-%d")

    today_existing = get_tasks_by_date(user_id, today_str)
    today_texts = {row[1].strip().lower() for row in today_existing}

    added_once = 0
    added_repeat = 0

    # Разовые задачи по дню недели
    once_rows = get_weekday_once_tasks_for_day(user_id, today_weekday)
    for task_id, _, task_text in once_rows:
        if task_text.strip().lower() not in today_texts:
            add_task(user_id, task_text, today_str)
            mark_weekday_once_task_used(task_id, today_str)
            today_texts.add(task_text.strip().lower())
            added_once += 1

    # Повторяющиеся задачи по дню недели
    weekly_rows = get_weekly_tasks_for_day(user_id, today_weekday)
    for _, _, task_text in weekly_rows:
        if task_text.strip().lower() not in today_texts:
            add_task(user_id, task_text, today_str)
            today_texts.add(task_text.strip().lower())
            added_repeat += 1

    return added_once, added_repeat


def get_unfinished_tasks_from_yesterday(user_id: int):
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT task_text
        FROM tasks
        WHERE user_id = ?
          AND task_date = ?
          AND is_done = 0
    """, (user_id, yesterday))
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]


def carry_unfinished_tasks(user_id: int) -> int:
    yesterday_tasks = get_unfinished_tasks_from_yesterday(user_id)
    if not yesterday_tasks:
        return 0

    today_str = date.today().strftime("%Y-%m-%d")
    today_existing = get_tasks_by_date(user_id, today_str)
    today_texts = {row[1].strip().lower() for row in today_existing}

    added_count = 0
    for task_text in yesterday_tasks:
        if task_text.strip().lower() not in today_texts:
            add_task(user_id, task_text, today_str)
            added_count += 1

    return added_count


# =========================
# СОСТОЯНИЯ
# =========================
def clear_state(user_id: int):
    user_states.pop(user_id, None)


def set_state(user_id: int, state):
    user_states[user_id] = state


def get_state(user_id: int):
    return user_states.get(user_id)


# =========================
# UI
# =========================
def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Добавить задачу", "📋 Сегодня")
    kb.row("✅ Выполнить", "🗑 Удалить")
    kb.row("📜 История", "🔁 Повторяющиеся")
    kb.row("📅 По дням недели", "📥 Добавить задачи дня")
    kb.row("🔄 Перенести невыполненные", "❌ Отмена")
    kb.row("ℹ️ Помощь")
    return kb


def add_task_type_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("📝 На сегодня", callback_data="add_type_once_today"))
    kb.row(types.InlineKeyboardButton("📅 По дням недели (один раз)", callback_data="add_type_weekday_once"))
    kb.row(types.InlineKeyboardButton("🔁 Повторяющаяся", callback_data="add_type_weekly"))
    return kb


def selected_days_keyboard(selected_days: set[int]):
    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = []

    for title, num in DAY_BUTTONS:
        mark = "✅ " if num in selected_days else ""
        buttons.append(
            types.InlineKeyboardButton(f"{mark}{title}", callback_data=f"toggle_day_{num}")
        )

    kb.add(*buttons)
    kb.row(
        types.InlineKeyboardButton("✔ Готово", callback_data="days_done"),
        types.InlineKeyboardButton("🧹 Очистить", callback_data="days_clear")
    )
    kb.row(types.InlineKeyboardButton("❌ Отмена", callback_data="days_cancel"))
    return kb


def today_done_keyboard(user_id: int):
    tasks = get_today_tasks(user_id)
    kb = types.InlineKeyboardMarkup()
    pending = [row for row in tasks if row[2] == 0]

    for task_id, task_text, _ in pending[:20]:
        short_text = task_text[:25] + ("..." if len(task_text) > 25 else "")
        kb.row(types.InlineKeyboardButton(f"✅ {task_id}. {short_text}", callback_data=f"done_{task_id}"))

    if not pending:
        kb.row(types.InlineKeyboardButton("Пусто", callback_data="noop"))

    return kb


def today_delete_keyboard(user_id: int):
    tasks = get_today_tasks(user_id)
    kb = types.InlineKeyboardMarkup()

    for task_id, task_text, _ in tasks[:20]:
        short_text = task_text[:25] + ("..." if len(task_text) > 25 else "")
        kb.row(types.InlineKeyboardButton(f"🗑 {task_id}. {short_text}", callback_data=f"delete_{task_id}"))

    if not tasks:
        kb.row(types.InlineKeyboardButton("Пусто", callback_data="noop"))

    return kb


def weekly_delete_keyboard(user_id: int):
    rows = get_weekly_tasks(user_id)
    kb = types.InlineKeyboardMarkup()

    for task_id, weekday, task_text in rows[:20]:
        short_text = task_text[:20] + ("..." if len(task_text) > 20 else "")
        kb.row(types.InlineKeyboardButton(
            f"🗑 🔁 {WEEKDAY_NAMES[weekday]}: {short_text}",
            callback_data=f"deleteweekly_{task_id}"
        ))

    if not rows:
        kb.row(types.InlineKeyboardButton("Пусто", callback_data="noop"))

    return kb


def weekday_once_delete_keyboard(user_id: int):
    rows = get_weekday_once_tasks(user_id)
    kb = types.InlineKeyboardMarkup()

    for task_id, weekday, task_text, is_used, added_to_date in rows[:20]:
        status = "✅" if is_used else "📅"
        short_text = task_text[:20] + ("..." if len(task_text) > 20 else "")
        kb.row(types.InlineKeyboardButton(
            f"🗑 {status} {WEEKDAY_NAMES[weekday]}: {short_text}",
            callback_data=f"deleteweekdayonce_{task_id}"
        ))

    if not rows:
        kb.row(types.InlineKeyboardButton("Пусто", callback_data="noop"))

    return kb


def format_tasks(task_rows, day_title: str) -> str:
    if not task_rows:
        return f"<b>{day_title}</b>\nСписок пуст."

    total = len(task_rows)
    done_count = sum(1 for row in task_rows if row[2] == 1)
    pending_count = total - done_count

    text = f"<b>{day_title}</b>\n"
    text += f"Всего: {total} | Выполнено: {done_count} | Осталось: {pending_count}\n\n"

    for task_id, task_text, is_done in task_rows:
        status = "✅" if is_done else "⬜"
        text += f"{status} <b>{task_id}</b>. {task_text}\n"

    return text


def format_history(user_id: int) -> str:
    days = get_last_days_with_tasks(user_id, limit=7)
    if not days:
        return "Истории пока нет."

    text = "<b>История за последние дни:</b>\n\n"

    for day_str in days:
        tasks = get_tasks_by_date(user_id, day_str)
        total = len(tasks)
        done_count = sum(1 for row in tasks if row[2] == 1)
        pending_count = total - done_count

        text += f"<b>{day_str}</b>\n"
        text += f"Всего: {total} | Выполнено: {done_count} | Осталось: {pending_count}\n\n"

    text += "Посмотреть конкретный день:\n<code>/day 2026-04-20</code>"
    return text


def format_weekly_tasks(user_id: int) -> str:
    rows = get_weekly_tasks(user_id)
    if not rows:
        return "Повторяющихся задач пока нет."

    text = "<b>🔁 Повторяющиеся задачи:</b>\n\n"
    current_day = None

    for task_id, weekday, task_text in rows:
        if weekday != current_day:
            current_day = weekday
            text += f"\n<b>{WEEKDAY_NAMES[weekday]}</b>\n"
        text += f"• <b>{task_id}</b>. {task_text}\n"

    return text


def format_weekday_once_tasks(user_id: int) -> str:
    rows = get_weekday_once_tasks(user_id)
    if not rows:
        return "Разовых задач по дням недели пока нет."

    text = "<b>📅 Разовые задачи по дням недели:</b>\n\n"
    active = [r for r in rows if r[3] == 0]
    used = [r for r in rows if r[3] == 1]

    if active:
        text += "<b>Активные:</b>\n"
        for task_id, weekday, task_text, _, _ in active:
            text += f"• <b>{task_id}</b>. {WEEKDAY_NAMES[weekday]} — {task_text}\n"

    if used:
        text += "\n<b>Уже использованные:</b>\n"
        for task_id, weekday, task_text, _, added_to_date in used:
            text += f"• <b>{task_id}</b>. {WEEKDAY_NAMES[weekday]} — {task_text} (добавлено {added_to_date})\n"

    return text


# =========================
# КОМАНДЫ
# =========================
@bot.message_handler(commands=["start"])
def start_handler(message):
    clear_state(message.from_user.id)
    text = (
        "Привет! Я бот для задач на день.\n\n"
        "У меня есть:\n"
        "• обычные задачи на сегодня\n"
        "• задачи по дням недели на один раз\n"
        "• повторяющиеся задачи по дням недели\n\n"
        "Лучше пользоваться кнопками снизу 👇"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())


@bot.message_handler(commands=["help"])
def help_handler(message):
    clear_state(message.from_user.id)
    text = (
        "<b>Что есть:</b>\n"
        "• На сегодня — обычная задача\n"
        "• По дням недели (один раз) — добавится в нужный день и больше не повторится\n"
        "• Повторяющаяся — будет доступна каждую неделю\n\n"
        "<b>Кнопки:</b>\n"
        "• Добавить задачу\n"
        "• Сегодня\n"
        "• Выполнить\n"
        "• Удалить\n"
        "• По дням недели\n"
        "• Повторяющиеся\n"
        "• Добавить задачи дня\n"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())


@bot.message_handler(commands=["history"])
def history_handler(message):
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, format_history(message.from_user.id), reply_markup=main_keyboard())


@bot.message_handler(commands=["today"])
def today_handler(message):
    clear_state(message.from_user.id)
    weekday_name = WEEKDAY_NAMES[date.today().weekday()]
    tasks = get_today_tasks(message.from_user.id)
    bot.send_message(
        message.chat.id,
        format_tasks(tasks, f"Дела на {date.today().strftime('%Y-%m-%d')} ({weekday_name})"),
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["day"])
def day_handler(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Напиши так: <code>/day 2026-04-20</code>")
        return

    day_str = parts[1].strip()
    try:
        dt = datetime.strptime(day_str, "%Y-%m-%d")
    except ValueError:
        bot.reply_to(message, "Дата должна быть в формате: <code>ГГГГ-ММ-ДД</code>")
        return

    tasks = get_tasks_by_date(message.from_user.id, day_str)
    bot.send_message(
        message.chat.id,
        format_tasks(tasks, f"Дела на {day_str} ({WEEKDAY_NAMES[dt.weekday()]})"),
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["todayauto"])
def todayauto_handler(message):
    clear_state(message.from_user.id)
    added_once, added_repeat = add_today_tasks_from_weekday(message.from_user.id)
    today_name = WEEKDAY_NAMES[date.today().weekday()]
    total = added_once + added_repeat

    if total == 0:
        bot.send_message(
            message.chat.id,
            f"На сегодня ({today_name}) новых задач по дню недели не добавлено.",
            reply_markup=main_keyboard()
        )
        return

    bot.send_message(
        message.chat.id,
        f"📥 На сегодня ({today_name}) добавлено задач: <b>{total}</b>\n"
        f"📅 Разовых: {added_once}\n"
        f"🔁 Повторяющихся: {added_repeat}",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["carry"])
def carry_handler(message):
    clear_state(message.from_user.id)
    count = carry_unfinished_tasks(message.from_user.id)

    if count == 0:
        bot.send_message(message.chat.id, "Со вчера нечего переносить.", reply_markup=main_keyboard())
        return

    bot.send_message(
        message.chat.id,
        f"🔄 Перенесено невыполненных дел: <b>{count}</b>",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["cancel"])
def cancel_handler(message):
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "Действие отменено.", reply_markup=main_keyboard())


# =========================
# КНОПКИ
# =========================
@bot.message_handler(func=lambda message: message.text == "➕ Добавить задачу")
def btn_add_task(message):
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "Какую задачу хочешь добавить?", reply_markup=main_keyboard())
    bot.send_message(message.chat.id, "Выбери тип:", reply_markup=add_task_type_keyboard())


@bot.message_handler(func=lambda message: message.text == "📋 Сегодня")
def btn_today(message):
    today_handler(message)


@bot.message_handler(func=lambda message: message.text == "📜 История")
def btn_history(message):
    history_handler(message)


@bot.message_handler(func=lambda message: message.text == "🔁 Повторяющиеся")
def btn_weekly(message):
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, format_weekly_tasks(message.from_user.id), reply_markup=main_keyboard())
    bot.send_message(
        message.chat.id,
        "Удалить повторяющуюся задачу:",
        reply_markup=weekly_delete_keyboard(message.from_user.id)
    )


@bot.message_handler(func=lambda message: message.text == "📅 По дням недели")
def btn_weekday_once(message):
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, format_weekday_once_tasks(message.from_user.id), reply_markup=main_keyboard())
    bot.send_message(
        message.chat.id,
        "Удалить разовую задачу по дням недели:",
        reply_markup=weekday_once_delete_keyboard(message.from_user.id)
    )


@bot.message_handler(func=lambda message: message.text == "📥 Добавить задачи дня")
def btn_todayauto(message):
    todayauto_handler(message)


@bot.message_handler(func=lambda message: message.text == "🔄 Перенести невыполненные")
def btn_carry(message):
    carry_handler(message)


@bot.message_handler(func=lambda message: message.text == "✅ Выполнить")
def btn_done(message):
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "Выбери задачу, которую нужно отметить выполненной:",
        reply_markup=today_done_keyboard(message.from_user.id)
    )


@bot.message_handler(func=lambda message: message.text == "🗑 Удалить")
def btn_delete(message):
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "Выбери задачу, которую нужно удалить:",
        reply_markup=today_delete_keyboard(message.from_user.id)
    )


@bot.message_handler(func=lambda message: message.text == "❌ Отмена")
def btn_cancel(message):
    cancel_handler(message)


@bot.message_handler(func=lambda message: message.text == "ℹ️ Помощь")
def btn_help(message):
    help_handler(message)


# =========================
# CALLBACKS
# =========================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    state = get_state(user_id)

    if call.data == "noop":
        bot.answer_callback_query(call.id)
        return

    if call.data == "add_type_once_today":
        clear_state(user_id)
        set_state(user_id, {"mode": "add_once_today"})
        bot.answer_callback_query(call.id, "Выбрана задача на сегодня")
        bot.send_message(call.message.chat.id, "Напиши текст задачи на сегодня.")
        return

    if call.data == "add_type_weekday_once":
        clear_state(user_id)
        set_state(user_id, {"mode": "select_days_once", "selected_days": []})
        bot.answer_callback_query(call.id, "Выбран режим: по дням недели один раз")
        bot.send_message(
            call.message.chat.id,
            "Выбери один или несколько дней недели:",
            reply_markup=selected_days_keyboard(set())
        )
        return

    if call.data == "add_type_weekly":
        clear_state(user_id)
        set_state(user_id, {"mode": "select_days_weekly", "selected_days": []})
        bot.answer_callback_query(call.id, "Выбран режим: повторяющаяся")
        bot.send_message(
            call.message.chat.id,
            "Выбери один или несколько дней недели:",
            reply_markup=selected_days_keyboard(set())
        )
        return

    if call.data == "days_cancel":
        clear_state(user_id)
        bot.answer_callback_query(call.id, "Отменено")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, "Добавление отменено.", reply_markup=main_keyboard())
        return

    if call.data == "days_clear":
        if isinstance(state, dict):
            state["selected_days"] = []
            set_state(user_id, state)
        bot.answer_callback_query(call.id, "Дни очищены")
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=selected_days_keyboard(set())
        )
        return

    if call.data.startswith("toggle_day_"):
        day_num = int(call.data.split("_")[2])
        if not isinstance(state, dict):
            bot.answer_callback_query(call.id, "Сессия сбилась")
            return

        selected = set(state.get("selected_days", []))
        if day_num in selected:
            selected.remove(day_num)
        else:
            selected.add(day_num)

        state["selected_days"] = sorted(selected)
        set_state(user_id, state)

        bot.answer_callback_query(call.id, "Выбор обновлён")
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=selected_days_keyboard(selected)
        )
        return

    if call.data == "days_done":
        if not isinstance(state, dict):
            bot.answer_callback_query(call.id, "Сессия сбилась")
            return

        selected = state.get("selected_days", [])
        if not selected:
            bot.answer_callback_query(call.id, "Сначала выбери хотя бы один день")
            return

        mode = state.get("mode")
        if mode == "select_days_once":
            set_state(user_id, {"mode": "add_weekday_once_text", "selected_days": selected})
            bot.answer_callback_query(call.id, "Дни выбраны")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            days_text = ", ".join(WEEKDAY_NAMES[d] for d in selected)
            bot.send_message(call.message.chat.id, f"Выбраны дни: <b>{days_text}</b>\nТеперь напиши текст задачи.")
            return

        if mode == "select_days_weekly":
            set_state(user_id, {"mode": "add_weekly_text", "selected_days": selected})
            bot.answer_callback_query(call.id, "Дни выбраны")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            days_text = ", ".join(WEEKDAY_NAMES[d] for d in selected)
            bot.send_message(call.message.chat.id, f"Выбраны дни: <b>{days_text}</b>\nТеперь напиши текст повторяющейся задачи.")
            return

    if call.data.startswith("done_"):
        task_id = int(call.data.split("_")[1])
        ok = mark_task_done(user_id, task_id)
        if ok:
            bot.answer_callback_query(call.id, "Задача выполнена")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, "✅ Задача отмечена выполненной.", reply_markup=main_keyboard())
        else:
            bot.answer_callback_query(call.id, "Не найдено")
        return

    if call.data.startswith("delete_"):
        task_id = int(call.data.split("_")[1])
        ok = delete_task(user_id, task_id)
        if ok:
            bot.answer_callback_query(call.id, "Задача удалена")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, "🗑 Задача удалена.", reply_markup=main_keyboard())
        else:
            bot.answer_callback_query(call.id, "Не найдено")
        return

    if call.data.startswith("deleteweekly_"):
        task_id = int(call.data.split("_")[1])
        ok = delete_weekly_task(user_id, task_id)
        if ok:
            bot.answer_callback_query(call.id, "Повторяющаяся задача удалена")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, "🗑 Повторяющаяся задача удалена.", reply_markup=main_keyboard())
        else:
            bot.answer_callback_query(call.id, "Не найдено")
        return

    if call.data.startswith("deleteweekdayonce_"):
        task_id = int(call.data.split("_")[1])
        ok = delete_weekday_once_task(user_id, task_id)
        if ok:
            bot.answer_callback_query(call.id, "Разовая задача по дням недели удалена")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, "🗑 Разовая задача по дням недели удалена.", reply_markup=main_keyboard())
        else:
            bot.answer_callback_query(call.id, "Не найдено")
        return


# =========================
# СВОБОДНЫЙ ВВОД
# =========================
@bot.message_handler(func=lambda message: True, content_types=["text"])
def free_text_handler(message):
    user_id = message.from_user.id
    text = message.text.strip()
    state = get_state(user_id)

    if isinstance(state, dict):
        mode = state.get("mode")

        if mode == "add_once_today":
            if not text:
                bot.reply_to(message, "Текст задачи не должен быть пустым.")
                return

            add_task(user_id, text)
            clear_state(user_id)
            bot.send_message(
                message.chat.id,
                f"📝 Задача на сегодня добавлена:\n<b>{text}</b>",
                reply_markup=main_keyboard()
            )
            return

        if mode == "add_weekday_once_text":
            selected_days = state.get("selected_days", [])
            if not selected_days:
                clear_state(user_id)
                bot.reply_to(message, "Что-то сбилось. Попробуй ещё раз.")
                return

            if not text:
                bot.reply_to(message, "Текст задачи не должен быть пустым.")
                return

            for weekday in selected_days:
                add_weekday_once_task(user_id, weekday, text)

            days_text = ", ".join(WEEKDAY_NAMES[d] for d in selected_days)
            clear_state(user_id)
            bot.send_message(
                message.chat.id,
                f"📅 Разовая задача по дням недели добавлена:\n"
                f"<b>{days_text}</b>\n{text}",
                reply_markup=main_keyboard()
            )
            return

        if mode == "add_weekly_text":
            selected_days = state.get("selected_days", [])
            if not selected_days:
                clear_state(user_id)
                bot.reply_to(message, "Что-то сбилось. Попробуй ещё раз.")
                return

            if not text:
                bot.reply_to(message, "Текст задачи не должен быть пустым.")
                return

            for weekday in selected_days:
                add_weekly_task(user_id, weekday, text)

            days_text = ", ".join(WEEKDAY_NAMES[d] for d in selected_days)
            clear_state(user_id)
            bot.send_message(
                message.chat.id,
                f"🔁 Повторяющаяся задача добавлена:\n"
                f"<b>{days_text}</b>\n{text}",
                reply_markup=main_keyboard()
            )
            return

    bot.reply_to(
        message,
        "Не поняла сообщение.\nИспользуй кнопки снизу.",
        reply_markup=main_keyboard()
    )


if __name__ == "__main__":
    init_db()
    print("Бот запущен...")
    bot.remove_webhook()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
