import os
from datetime import datetime, timedelta, time as dtime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from storage import Storage
from plan import TZ, SLOTS, build_tasks_for_slot, followups_for_base

TOKEN = os.getenv("BOT_TOKEN")
storage = Storage("bot.db")


def now_msk() -> datetime:
    return datetime.now(TZ)


def kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Сделано", callback_data=f"done:{task_id}"),
            InlineKeyboardButton("⏰ +10 минут", callback_data=f"snooze10:{task_id}")
        ],
        [InlineKeyboardButton("❌ Пропустить", callback_data=f"skip:{task_id}")]
    ])


async def send_task(context: ContextTypes.DEFAULT_TYPE, task_id: int):
    task = storage.get_task(task_id)
    if not task:
        return
    await context.bot.send_message(
        chat_id=task["chat_id"],
        text=storage.render_task(task),
        reply_markup=kb(task_id)
    )


async def trigger_slot(app: Application, slot: str):
    """Создаёт задачи на слот и отправляет их пользователям."""
    for chat_id in storage.get_users():
        if storage.is_paused(chat_id):
            continue

        for spec in build_tasks_for_slot(slot):
            task_id = storage.create_task(
                chat_id=chat_id,
                title=spec.title,
                details=spec.details,
                slot=spec.slot,
                kind=spec.kind,
                chain=spec.chain,
                scheduled_for=spec.scheduled_for,
                deadline_at=spec.deadline_at
            )

            # Таблетки (например 08:30) создаём на 07:30, но отправляем в своё время
            if spec.kind == "pill" and spec.scheduled_for > now_msk():
                delay = (spec.scheduled_for - now_msk()).total_seconds()
                app.job_queue.run_once(
                    one_off_send_task,
                    when=delay,
                    chat_id=chat_id,
                    data={"task_id": task_id},
                    name=f"task:{task_id}",
                )
            else:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=storage.render_task(storage.get_task(task_id)),
                    reply_markup=kb(task_id)
                )


# ---------------- JOB HANDLERS (без lambda — стабильнее) ----------------

async def slot_job(context: ContextTypes.DEFAULT_TYPE):
    slot = context.job.data["slot"]
    await trigger_slot(context.application, slot)


async def one_off_send_task(context: ContextTypes.DEFAULT_TYPE):
    task_id = context.job.data["task_id"]
    await send_task(context, task_id)


# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    storage.upsert_user(chat_id)
    await update.message.reply_text(
        "Я включён ✅\n"
        "Команды:\n"
        "/next — следующий приём\n"
        "/plan — план на сегодня\n"
        "/today — что уже создано/отмечено сегодня\n"
        "/stats — статистика\n"
        "/pause — пауза\n"
        "/resume — продолжить\n"
        "/ping — проверка"
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я жив ✅")


def _format_in(diff: timedelta) -> str:
    total_seconds = int(diff.total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours > 0:
        return f"{hours}ч {minutes}м"
    return f"{minutes}м"


def _next_slot_dt(now: datetime):
    upcoming = []
    for slot in SLOTS:
        hh, mm = map(int, slot.split(":"))
        dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if dt <= now:
            dt = dt + timedelta(days=1)
        upcoming.append((dt, slot))
    return min(upcoming, key=lambda x: x[0])  # (datetime, "HH:MM")


async def next_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = now_msk()
    next_time, slot = _next_slot_dt(now)
    diff = next_time - now

    # Показываем "что будет" по расписанию (первую задачу слота; таблетки не дублируем тут отдельно)
    specs = build_tasks_for_slot(slot)
    if specs:
        preview = f"{specs[0].title}\n{specs[0].details}".strip()
    else:
        preview = "Следующий приём по расписанию."

    await update.message.reply_text(
        f"Следующий приём\n\n{preview}\n\nчерез {_format_in(diff)}"
    )


async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает план оставшихся слотов на сегодня (по расписанию),
    без привязки к тому, созданы ли уже задачи в БД.
    """
    now = now_msk()
    today = now.date()
    lines = []

    # оставшиеся слоты сегодня
    for slot in SLOTS:
        hh, mm = map(int, slot.split(":"))
        dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if dt.date() != today:
            continue
        if dt <= now:
            continue

        specs = build_tasks_for_slot(slot)
        if specs:
            # обычно первый spec — глазной базовый шаг (то, что нужно видеть)
            lines.append(f"• {specs[0].title}")

    # таблеточный блок (если он у тебя отдельным временем — показываем один раз, если ещё впереди)
    # Он создаётся внутри build_tasks_for_slot("07:30"), но для плана покажем отдельно:
    # Берём его из build_tasks_for_slot("07:30") и проверяем время относительно now.
    pill_specs = [s for s in build_tasks_for_slot("07:30") if s.kind == "pill"]
    if pill_specs:
        ps = pill_specs[0]
        if ps.scheduled_for.date() == today and ps.scheduled_for > now:
            lines.insert(0, f"• {ps.title}")

    if not lines:
        await update.message.reply_text("На сегодня по расписанию больше ничего нет. Ждём следующий приём завтра ✅")
        return

    await update.message.reply_text("План на сегодня (оставшиеся приёмы):\n" + "\n".join(lines))


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает то, что уже было СОЗДАНО сегодня (и статус).
    Полезно для трекера, но помни: задачи появляются только когда наступает слот.
    """
    chat_id = update.effective_chat.id
    day_iso = now_msk().date().isoformat()
    items = storage.list_day(chat_id, day_iso)
    if not items:
        await update.message.reply_text("На сегодня пока нет созданных задач (они появятся по расписанию).")
        return

    lines = []
    for t in items:
        status = "⏳" if t["status"] == "pending" else ("✅" if t["status"] == "done" else "❌")
        lines.append(f"{status} {t['title']}")

    await update.message.reply_text("Сегодня (созданные задачи):\n" + "\n".join(lines))


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    s = storage.stats(chat_id)
    await update.message.reply_text(
        "Статистика:\n"
        f"✅ выполнено: {s.get('done', 0)}\n"
        f"⏳ ожидает: {s.get('pending', 0)}\n"
        f"❌ пропущено: {s.get('skipped', 0)}"
    )


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.set_paused(update.effective_chat.id, True)
    await update.message.reply_text("Ок, пауза. /resume чтобы включить снова.")


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.set_paused(update.effective_chat.id, False)
    await update.message.reply_text("Вернула напоминания ✅")


# ---------------- BUTTONS ----------------

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat.id

    action, task_id_s = q.data.split(":")
    task_id = int(task_id_s)

    if storage.is_paused(chat_id):
        await q.edit_message_text("Сейчас пауза. /resume чтобы включить.")
        return

    if action == "done":
        storage.mark_done(task_id, now_msk())
        task = storage.get_task(task_id)

        # Цепочки от факта выполнения (капли -> +5/+10)
        if task and task["kind"] == "base" and int(task["chain"]) == 1:
            done_at = datetime.fromisoformat(task["done_at"])
            for fu in followups_for_base(task["slot"]):
                scheduled_for = done_at + timedelta(minutes=fu["offset_min"])
                deadline_at = done_at + timedelta(minutes=fu["deadline_min"])

                fu_id = storage.create_task(
                    chat_id=chat_id,
                    title=fu["title"],
                    details=fu["details"],
                    slot=task["slot"],
                    kind="followup",
                    chain=False,
                    scheduled_for=scheduled_for,
                    deadline_at=deadline_at,
                    parent_task_id=task_id
                )

                delay = (scheduled_for - now_msk()).total_seconds()
                if delay < 0:
                    delay = 0

                context.job_queue.run_once(
                    one_off_send_task,
                    when=delay,
                    chat_id=chat_id,
                    data={"task_id": fu_id},
                    name=f"task:{fu_id}",
                )

        await q.edit_message_text(storage.render_task(storage.get_task(task_id)) + "\n\n✅ Отмечено")

    elif action == "skip":
        storage.mark_skipped(task_id, now_msk())
        await q.edit_message_text(storage.render_task(storage.get_task(task_id)) + "\n\n❌ Пропущено")

    elif action == "snooze10":
        new_time = now_msk() + timedelta(minutes=10)
        storage.snooze(task_id, new_time)

        context.job_queue.run_once(
            one_off_send_task,
            when=10 * 60,
            chat_id=chat_id,
            data={"task_id": task_id},
            name=f"task:{task_id}"
        )

        await q.edit_message_text(storage.render_task(storage.get_task(task_id)) + "\n\n⏰ Отложено на 10 минут")


# ---------------- SCHEDULER ----------------

def schedule_slots(app: Application):
    for slot in SLOTS:
        hh, mm = map(int, slot.split(":"))
        app.job_queue.run_daily(
            slot_job,
            time=dtime(hour=hh, minute=mm, tzinfo=TZ),
            data={"slot": slot},
            name=f"slot:{slot}",
        )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("next", next_slot))
    app.add_handler(CommandHandler("plan", plan))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CallbackQueryHandler(on_button))

    schedule_slots(app)
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
