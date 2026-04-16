import sqlite3
from datetime import datetime

DB_FILE = "reminders.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                is_sent INTEGER NOT NULL DEFAULT 0
            )
        """)

def add_reminder(chat_id: int, message: str, remind_at: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO reminders (chat_id, message, remind_at) VALUES (?, ?, ?)",
            (chat_id, message, remind_at)
        )
        return cursor.lastrowid

def get_pending_reminders() -> list:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM reminders WHERE is_sent = 0 AND remind_at <= ?",
            (now,)
        )
        return cursor.fetchall()

def get_user_reminders(chat_id: int) -> list:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM reminders WHERE chat_id = ? AND is_sent = 0 ORDER BY remind_at ASC",
            (chat_id,)
        )
        return cursor.fetchall()

def mark_as_sent(reminder_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE reminders SET is_sent = 1 WHERE id = ?", (reminder_id,))

def delete_reminder(reminder_id: int, chat_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM reminders WHERE id = ? AND chat_id = ? AND is_sent = 0",
            (reminder_id, chat_id)
        )
        return cursor.rowcount > 0