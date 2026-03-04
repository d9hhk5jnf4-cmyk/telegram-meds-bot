import os
import asyncio
from datetime import datetime, timedelta
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

TOKEN = os.getenv("BOT_TOKEN")
TZ = pytz.timezone("Europe/Moscow")

slots = ["07:30","11:30","15:30","19:30","23:30"]

async def start(update, context):
    await update.message.reply_text(
        "Я бот-напоминатель 💊\n"
        "Буду напоминать про капли и витамины."
    )

async def remind(context):
    chat_id = context.job.chat_id
    text = context.job.data

    keyboard = [[
        InlineKeyboardButton("✅ Сделано", callback_data="done"),
        InlineKeyboardButton("⏰ +10 минут", callback_data="delay")
    ]]

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "done":
        await query.edit_message_text("Отмечено ✅")
    else:
        await query.edit_message_text("Напомню через 10 минут ⏰")

async def schedule(application, chat_id):

    for slot in slots:
        hour, minute = map(int, slot.split(":"))
        application.job_queue.run_daily(
            remind,
            time=datetime.strptime(slot,"%H:%M").time(),
            data=f"Напоминание {slot}\nПроверь лекарства.",
            chat_id=chat_id
        )

async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    await app.initialize()
    await app.start()

    print("Bot started")

    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
