import os
from datetime import time
import pytz

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
TZ = pytz.timezone("Europe/Moscow")

SLOTS = ["07:30", "11:30", "15:30", "19:30", "23:30"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я бот-напоминатель 💊\n"
        "Я на сервере и буду присылать напоминания.\n"
        "Пока тестовый режим.\n"
        "Команды: /ping"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я жив ✅")

def keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Сделано", callback_data="done"),
        InlineKeyboardButton("⏰ +10 минут", callback_data="delay")
    ]])

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    text = context.job.data["text"]
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "done":
        await q.edit_message_text("Отмечено ✅")
    elif q.data == "delay":
        # повтор через 10 минут
        context.job_queue.run_once(
            send_reminder,
            when=10 * 60,
            chat_id=q.message.chat_id,
            data={"text": "⏰ Напоминание (отложено на 10 минут) — проверь лекарства."},
        )
        await q.edit_message_text("Ок, напомню через 10 минут ⏰")

def schedule_for_chat(app: Application, chat_id: int):
    for slot in SLOTS:
        hh, mm = map(int, slot.split(":"))
        app.job_queue.run_daily(
            send_reminder,
            time=time(hour=hh, minute=mm, tzinfo=TZ),
            chat_id=chat_id,
            data={"text": f"🕒 {slot} (Мск)\nНапоминание — проверь лекарства."},
            name=f"reminder-{chat_id}-{slot}",
        )

async def on_post_init(app: Application):
    # ВАЖНО: расписание запускается только после /start (когда мы узнаем chat_id).
    pass

async def on_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # не плодим дубликаты — удаляем старые джобы этого чата
    for job in context.job_queue.jobs():
        if job.name and job.name.startswith(f"reminder-{chat_id}-"):
            job.schedule_removal()
    schedule_for_chat(context.application, chat_id)
    await update.message.reply_text("Супер! Я поставил расписание для этого чата ✅")

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN env var is missing")

    app = Application.builder().token(TOKEN).post_init(on_post_init).build()

    app.add_handler(CommandHandler("start", on_start_command))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CallbackQueryHandler(button))

    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
