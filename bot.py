import os
import sqlite3
from datetime import datetime, date, timedelta
import telebot
from telebot import types

# =========================
# НАСТРОЙКИ
# =========================
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не найден BOT_TOKEN")

DB_NAME = os.getenv("DB_NAME", "wishlist_bot.db")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
user_states = {}

WEEKDAY_MAP = {
    "пн": 0,
    "понедельник": 0,
    "вт": 1,
    "вторник": 1,
    "ср": 2,
    "среда": 2,
    "чт": 3,
    "четверг": 3,
    "пт": 4,
    "пятница": 4,
    "сб": 5,
    "суббота": 5,
    "вс": 6,
    "воскресенье": 6,
}

WEEKDAY_NAMES = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}


# =========================
# БАЗА ДАННЫХ
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS weekly_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            weekday INTEGER NOT NULL,
            task_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


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
        SELECT id, task_text, is_done, created_at, completed_at
        FROM tasks
        WHERE user_id = ? AND task_date = ?
        ORDER BY id ASC
    """, (user_id, task_date))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_today_tasks(user_id: int):
    return get_tasks_by_date(user_id, date.today().strftime("%Y-%m-%d"))


def mark_task_done(user_id: int, task_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, is_done
        FROM tasks
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
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, task_id))

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


def add_today_tasks_from_weekday(user_id: int) -> int:
    today_weekday = date.today().weekday()
    weekly_rows = get_weekly_tasks_for_day(user_id, today_weekday)
    today_str = date.today().strftime("%Y-%m-%d")
    today_existing = get_tasks_by_date(user_id, today_str)
    today_texts = {row[1].strip().lower() for row in today_existing}

    added_count = 0
    for _, _, task_text in weekly_rows:
        if task_text.strip().lower() not in today_texts:
            add_task(user_id, task_text, today_str)
            added_count += 1

    return added_count


# =========================
# СОСТОЯНИЯ
# =========================
def clear_state(user_id: int):
    user_states.pop(user_id, None)


def set_state(user_id: int, state: str):
    user_states[user_id] = state


def get_state(user_id: int):
    return user_states.get(user_id)


# =========================
# UI
# =========================
def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Добавить дело", "📋 Сегодня")
    kb.row("✅ Выполнить дело", "📜 История")
    kb.row("📅 Дела по дням", "📥 Добавить дела дня")
    kb.row("🔄 Перенести невыполненные", "❌ Отмена")
    kb.row("ℹ️ Помощь")
    return kb


def format_tasks(task_rows, day_title: str) -> str:
    if not task_rows:
        return f"<b>{day_title}</b>\nСписок пуст."

    total = len(task_rows)
    done_count = sum(1 for row in task_rows if row[2] == 1)
    pending_count = total - done_count

    text = f"<b>{day_title}</b>\n"
    text += f"Всего: {total} | Выполнено: {done_count} | Осталось: {pending_count}\n\n"

    for task_id, task_text, is_done, created_at, completed_at in task_rows:
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

        text += (
            f"<b>{day_str}</b>\n"
            f"Всего: {total} | Выполнено: {done_count} | Осталось: {pending_count}\n\n"
        )

    text += "Чтобы посмотреть конкретный день:\n<code>/day 2026-04-20</code>"
    return text


def format_weekly_tasks(user_id: int) -> str:
    rows = get_weekly_tasks(user_id)
    if not rows:
        return (
            "Шаблонных задач по дням недели пока нет.\n\n"
            "Пример:\n<code>/addweekly сб Сохранить открытые уроки</code>"
        )

    text = "<b>Задачи по дням недели:</b>\n\n"
    current_day = None

    for task_id, weekday, task_text in rows:
        if weekday != current_day:
            current_day = weekday
            text += f"\n<b>{WEEKDAY_NAMES[weekday]}</b>\n"

        text += f"• <b>{task_id}</b>. {task_text}\n"

    text += (
        "\n\nДобавить:\n"
        "<code>/addweekly сб Сохранить открытые уроки</code>\n\n"
        "Удалить:\n"
        "<code>/deleteweekly 3</code>"
    )
    return text


# =========================
# КОМАНДЫ
# =========================
@bot.message_handler(commands=["start"])
def start_handler(message):
    clear_state(message.from_user.id)
    text = (
        "Привет! Я бот для списка дел на день.\n\n"
        "Я умею:\n"
        "• сохранять дела на сегодня\n"
        "• отмечать выполненные\n"
        "• показывать историю прошлых дней\n"
        "• переносить невыполненные дела со вчера\n"
        "• хранить шаблонные дела по дням недели\n\n"
        "<b>Примеры:</b>\n"
        "• <code>/add Купить молоко</code>\n"
        "• <code>/today</code>\n"
        "• <code>/done 3</code>\n"
        "• <code>/history</code>\n"
        "• <code>/addweekly сб Сохранить открытые уроки</code>\n"
        "• <code>/todayauto</code>"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())


@bot.message_handler(commands=["help"])
def help_handler(message):
    clear_state(message.from_user.id)
    text = (
        "<b>Команды:</b>\n"
        "• <code>/add Текст дела</code> — добавить дело на сегодня\n"
        "• <code>/today</code> — список дел на сегодня\n"
        "• <code>/done 5</code> — отметить дело выполненным\n"
        "• <code>/delete 5</code> — удалить дело\n"
        "• <code>/history</code> — история последних дней\n"
        "• <code>/day 2026-04-20</code> — показать дела за дату\n"
        "• <code>/carry</code> — перенести невыполненные дела со вчера\n"
        "• <code>/addweekly сб Текст</code> — добавить дело на день недели\n"
        "• <code>/weekly</code> — показать дела по дням недели\n"
        "• <code>/todayauto</code> — добавить на сегодня шаблонные дела текущего дня\n"
        "• <code>/deleteweekly 3</code> — удалить шаблонное дело\n"
        "• <code>/cancel</code> — отменить текущий ввод\n"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())


@bot.message_handler(commands=["cancel"])
def cancel_handler(message):
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "Действие отменено.", reply_markup=main_keyboard())


@bot.message_handler(commands=["add"])
def add_handler(message):
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        set_state(message.from_user.id, "add_task")
        bot.send_message(
            message.chat.id,
            "Напиши текст дела.\nНапример:\n<code>Купить молоко</code>",
            reply_markup=main_keyboard()
        )
        return

    task_text = parts[1].strip()
    if not task_text:
        bot.reply_to(message, "Текст дела не должен быть пустым.")
        return

    add_task(message.from_user.id, task_text)
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"➕ Дело добавлено:\n<b>{task_text}</b>",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["today"])
def today_handler(message):
    clear_state(message.from_user.id)
    tasks = get_today_tasks(message.from_user.id)
    weekday_name = WEEKDAY_NAMES[date.today().weekday()]
    bot.send_message(
        message.chat.id,
        format_tasks(tasks, f"Дела на {date.today().strftime('%Y-%m-%d')} ({weekday_name})"),
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["done"])
def done_handler(message):
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        set_state(message.from_user.id, "done_task")
        bot.send_message(
            message.chat.id,
            "Введи ID дела, которое нужно отметить выполненным.\nНапример: <code>3</code>",
            reply_markup=main_keyboard()
        )
        return

    try:
        task_id = int(parts[1])
    except ValueError:
        bot.reply_to(message, "ID должен быть числом. Например: <code>/done 3</code>")
        return

    ok = mark_task_done(message.from_user.id, task_id)
    if not ok:
        bot.reply_to(message, "Дело с таким ID не найдено.")
        return

    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "✅ Дело отмечено выполненным.", reply_markup=main_keyboard())


@bot.message_handler(commands=["delete"])
def delete_handler(message):
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        set_state(message.from_user.id, "delete_task")
        bot.send_message(
            message.chat.id,
            "Введи ID дела, которое нужно удалить.\nНапример: <code>3</code>",
            reply_markup=main_keyboard()
        )
        return

    try:
        task_id = int(parts[1])
    except ValueError:
        bot.reply_to(message, "ID должен быть числом. Например: <code>/delete 3</code>")
        return

    ok = delete_task(message.from_user.id, task_id)
    if not ok:
        bot.reply_to(message, "Дело с таким ID не найдено.")
        return

    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, "🗑 Дело удалено.", reply_markup=main_keyboard())


@bot.message_handler(commands=["history"])
def history_handler(message):
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        format_history(message.from_user.id),
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
    weekday_name = WEEKDAY_NAMES[dt.weekday()]
    bot.send_message(
        message.chat.id,
        format_tasks(tasks, f"Дела на {day_str} ({weekday_name})"),
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["carry"])
def carry_handler(message):
    clear_state(message.from_user.id)
    count = carry_unfinished_tasks(message.from_user.id)

    if count == 0:
        bot.send_message(
            message.chat.id,
            "Со вчера нечего переносить.",
            reply_markup=main_keyboard()
        )
        return

    bot.send_message(
        message.chat.id,
        f"🔄 Перенесено невыполненных дел: <b>{count}</b>",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["addweekly"])
def addweekly_handler(message):
    parts = message.text.split(maxsplit=2)

    if len(parts) < 3:
        bot.send_message(
            message.chat.id,
            "Напиши так:\n<code>/addweekly сб Сохранить открытые уроки</code>\n"
            "или\n<code>/addweekly суббота Сохранить открытые уроки</code>",
            reply_markup=main_keyboard()
        )
        return

    weekday_raw = parts[1].strip().lower()
    task_text = parts[2].strip()

    if weekday_raw not in WEEKDAY_MAP:
        bot.reply_to(
            message,
            "Не поняла день недели.\nИспользуй: пн, вт, ср, чт, пт, сб, вс"
        )
        return

    if not task_text:
        bot.reply_to(message, "Текст задачи не должен быть пустым.")
        return

    weekday = WEEKDAY_MAP[weekday_raw]
    add_weekly_task(message.from_user.id, weekday, task_text)

    bot.send_message(
        message.chat.id,
        f"📅 Добавлена повторяющаяся задача:\n<b>{WEEKDAY_NAMES[weekday]}</b> — {task_text}",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["weekly"])
def weekly_handler(message):
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        format_weekly_tasks(message.from_user.id),
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["todayauto"])
def todayauto_handler(message):
    clear_state(message.from_user.id)
    added_count = add_today_tasks_from_weekday(message.from_user.id)
    today_name = WEEKDAY_NAMES[date.today().weekday()]

    if added_count == 0:
        bot.send_message(
            message.chat.id,
            f"На сегодня ({today_name}) новых шаблонных задач не добавлено.",
            reply_markup=main_keyboard()
        )
        return

    bot.send_message(
        message.chat.id,
        f"📥 На сегодня ({today_name}) добавлено задач: <b>{added_count}</b>",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["deleteweekly"])
def deleteweekly_handler(message):
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        bot.send_message(
            message.chat.id,
            "Напиши так:\n<code>/deleteweekly 3</code>",
            reply_markup=main_keyboard()
        )
        return

    try:
        weekly_task_id = int(parts[1])
    except ValueError:
        bot.reply_to(message, "ID должен быть числом.")
        return

    ok = delete_weekly_task(message.from_user.id, weekly_task_id)
    if not ok:
        bot.reply_to(message, "Шаблонная задача с таким ID не найдена.")
        return

    bot.send_message(
        message.chat.id,
        "🗑 Шаблонная задача удалена.",
        reply_markup=main_keyboard()
    )


# =========================
# КНОПКИ
# =========================
@bot.message_handler(func=lambda message: message.text == "➕ Добавить дело")
def btn_add(message):
    set_state(message.from_user.id, "add_task")
    bot.send_message(
        message.chat.id,
        "Напиши новое дело для сегодняшнего списка.",
        reply_markup=main_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "📋 Сегодня")
def btn_today(message):
    today_handler(message)


@bot.message_handler(func=lambda message: message.text == "✅ Выполнить дело")
def btn_done(message):
    set_state(message.from_user.id, "done_task")
    bot.send_message(
        message.chat.id,
        "Введи ID выполненного дела.\nНапример: <code>3</code>",
        reply_markup=main_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "📜 История")
def btn_history(message):
    history_handler(message)


@bot.message_handler(func=lambda message: message.text == "📅 Дела по дням")
def btn_weekly(message):
    weekly_handler(message)


@bot.message_handler(func=lambda message: message.text == "📥 Добавить дела дня")
def btn_todayauto(message):
    todayauto_handler(message)


@bot.message_handler(func=lambda message: message.text == "🔄 Перенести невыполненные")
def btn_carry(message):
    carry_handler(message)


@bot.message_handler(func=lambda message: message.text == "❌ Отмена")
def btn_cancel(message):
    cancel_handler(message)


@bot.message_handler(func=lambda message: message.text == "ℹ️ Помощь")
def btn_help(message):
    help_handler(message)


# =========================
# СВОБОДНЫЙ ВВОД
# =========================
@bot.message_handler(func=lambda message: True, content_types=["text"])
def free_text_handler(message):
    user_id = message.from_user.id
    text = message.text.strip()
    state = get_state(user_id)

    if state == "add_task":
        if not text:
            bot.reply_to(message, "Текст дела не должен быть пустым.")
            return

        add_task(user_id, text)
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            f"➕ Дело добавлено:\n<b>{text}</b>",
            reply_markup=main_keyboard()
        )
        return

    if state == "done_task":
        if not text.isdigit():
            bot.reply_to(message, "Нужно ввести ID числом. Например: <code>3</code>")
            return

        task_id = int(text)
        ok = mark_task_done(user_id, task_id)
        if not ok:
            bot.reply_to(message, "Дело с таким ID не найдено.")
            return

        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "✅ Дело отмечено выполненным.",
            reply_markup=main_keyboard()
        )
        return

    if state == "delete_task":
        if not text.isdigit():
            bot.reply_to(message, "Нужно ввести ID числом. Например: <code>3</code>")
            return

        task_id = int(text)
        ok = delete_task(user_id, task_id)
        if not ok:
            bot.reply_to(message, "Дело с таким ID не найдено.")
            return

        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "🗑 Дело удалено.",
            reply_markup=main_keyboard()
        )
        return

    bot.reply_to(
        message,
        "Не поняла сообщение.\n\n"
        "Попробуй:\n"
        "<code>/add Купить молоко</code>\n"
        "<code>/today</code>\n"
        "<code>/addweekly сб Сохранить открытые уроки</code>\n"
        "<code>/todayauto</code>",
        reply_markup=main_keyboard()
    )


if __name__ == "__main__":
    init_db()
    print("Бот запущен...")
    bot.remove_webhook()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
