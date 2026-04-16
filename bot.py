import os
import threading
import time
import logging
from datetime import datetime

import telebot
import schedule
import database as db

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = os.environ.get("OWNER_ID")

if not BOT_TOKEN or not OWNER_ID:
    raise ValueError("BOT_TOKEN and OWNER_ID must be set in environment variables.")

try:
    OWNER_ID = int(OWNER_ID)
except ValueError:
    raise ValueError("OWNER_ID must be a valid integer.")

bot = telebot.TeleBot(BOT_TOKEN)
user_state = {}

def is_owner(message):
    if message.chat.id != OWNER_ID:
        logger.warning(f"Unauthorized access attempt from user ID: {message.from_user.id}")
        return False
    return True

def parse_datetime(text: str) -> str | None:
    text = text.strip()
    formats = [
        ("%d/%m/%Y %H:%M", text),
        ("%Y-%m-%d %H:%M", text),
        ("%H:%M", datetime.now().strftime("%Y-%m-%d ") + text),
    ]

    for fmt, value in formats:
        try:
            dt = datetime.strptime(value, fmt)
            if dt < datetime.now():
                return None
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    return None

def format_reminders(reminders) -> str:
    if not reminders:
        return "No active reminders."

    lines = ["*Active Reminders:*\n"]
    for r in reminders:
        dt = datetime.strptime(r["remind_at"], "%Y-%m-%d %H:%M")
        formatted_time = dt.strftime("%A, %d %b %Y at %H:%M")
        lines.append(f"*[ID: {r['id']}]* {r['message']}\n {formatted_time}")

    lines.append("\nDelete reminder using: `/delete [ID]`")
    return "\n".join(lines)

@bot.message_handler(commands=["start", "help"], func=is_owner)
def cmd_help(message):
    text = (
        "*Personal Reminder Bot*\n\n"
        "`/add` — Add new reminder\n"
        "`/list` — View active reminders\n"
        "`/delete [ID]` — Delete a reminder\n\n"
        "*Time Formats:*\n"
        "• `14:30` (Today)\n"
        "• `25/12/2024 09:00`\n"
        "• `2024-12-25 09:00`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["add"], func=is_owner)
def cmd_add(message):
    user_state[message.chat.id] = {"step": "waiting_message"}
    bot.send_message(message.chat.id, "Enter your reminder message:")

@bot.message_handler(commands=["list"], func=is_owner)
def cmd_list(message):
    reminders = db.get_user_reminders(message.chat.id)
    bot.send_message(message.chat.id, format_reminders(reminders), parse_mode="Markdown")

@bot.message_handler(commands=["delete"], func=is_owner)
def cmd_delete(message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        bot.send_message(message.chat.id, "Usage: `/delete [ID]`", parse_mode="Markdown")
        return

    reminder_id = int(parts[1])
    if db.delete_reminder(reminder_id, message.chat.id):
        bot.send_message(message.chat.id, f"Reminder *{reminder_id}* deleted.", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, f"Reminder *{reminder_id}* not found.", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: is_owner(msg) and msg.chat.id in user_state)
def handle_add_flow(message):
    chat_id = message.chat.id
    state = user_state[chat_id]
    step = state.get("step")

    if step == "waiting_message":
        text = message.text.strip()
        if not text:
            bot.send_message(chat_id, "Message cannot be empty.")
            return

        user_state[chat_id] = {"step": "waiting_time", "message": text}
        bot.send_message(chat_id, "Enter the reminder time (e.g., `14:30` or `25/12/2024 09:00`):", parse_mode="Markdown")

    elif step == "waiting_time":
        remind_at = parse_datetime(message.text)
        if not remind_at:
            bot.send_message(chat_id, "Invalid format or time is in the past. Try again:")
            return

        reminder_msg = state["message"]
        db.add_reminder(chat_id, reminder_msg, remind_at)
        del user_state[chat_id]

        bot.send_message(chat_id, f"Reminder set for {remind_at}!\n {reminder_msg}")

def check_and_send_reminders():
    pending = db.get_pending_reminders()
    for reminder in pending:
        try:
            bot.send_message(reminder["chat_id"], f"*REMINDER*\n\n{reminder['message']}", parse_mode="Markdown")
            db.mark_as_sent(reminder["id"])
            logger.info(f"Reminder ID {reminder['id']} sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send reminder ID {reminder['id']}: {e}")

def run_scheduler():
    schedule.every(1).minutes.do(check_and_send_reminders)
    logger.info("Scheduler started.")
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    db.init_db()
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    logger.info("Bot is polling...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)