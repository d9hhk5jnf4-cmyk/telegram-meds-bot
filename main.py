import logging
import os
import random
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes, Defaults

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
DB_PATH = os.getenv("DB_PATH", "bot.db")
TREATMENT_START = os.getenv("TREATMENT_START", "2026-04-10")

if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN")

TZ = ZoneInfo(TIMEZONE)
START_DATE = date.fromisoformat(TREATMENT_START)


@dataclass(frozen=True)
class PlanItem:
    key: str
    hh: int
    mm: int
    title: str
    details: str
    duration_days: int | None = None
    is_quote: bool = False

    @property
    def at(self) -> time:
        return time(self.hh, self.mm, tzinfo=TZ)

    @property
    def time_str(self) -> str:
        return f"{self.hh:02d}:{self.mm:02d}"


PLAN: list[PlanItem] = [
    PlanItem(
        key="thermometry_08_00",
        hh=8,
        mm=0,
        title="Термометрия",
        details=(
            "Измерить температуру. При t > 37,0°C: Парацетамол 500 мг "
            "или Ибупрофен 200 мг."
        ),
    ),
    PlanItem(
        key="nose_rinse_1",
        hh=8,
        mm=10,
        title="Промывание носа",
        details="Аквалор / Аквамарис.",
        duration_days=7,
    ),
    PlanItem(
        key="nose_spray_1",
        hh=8,
        mm=15,
        title="Спрей для носа",
        details="Синусэфрин / Полидекса.",
        duration_days=7,
    ),
    PlanItem(
        key="vitamin_c",
        hh=8,
        mm=30,
        title="Витамин C",
        details="Витамин C 1000 мг/день. Лучше после еды.",
        duration_days=10,
    ),
    PlanItem(
        key="vitamin_d3",
        hh=8,
        mm=35,
        title="Витамин D3",
        details="Витамин D3 (Аквадетрим) 2000 Ед/день. Лучше после еды.",
        duration_days=30,
    ),
    PlanItem(
        key="inhalation_1",
        hh=9,
        mm=0,
        title="Ингаляция (небулайзер)",
        details=(
            "Пульмикорт 0.5: 1 фл + Беродуал 20 капель + 5 мл физраствора. "
            "После ингаляции промыть рот водой."
        ),
        duration_days=6,
    ),
    PlanItem(
        key="acc",
        hh=10,
        mm=0,
        title="АЦЦ-Лонг / Флуимуцил / Флуифорт",
        details="600 мг, 1 раз в день, в первой половине дня.",
        duration_days=5,
    ),
    PlanItem(
        key="thermometry_12_00",
        hh=12,
        mm=0,
        title="Термометрия",
        details=(
            "Измерить температуру. При t > 37,0°C: Парацетамол 500 мг "
            "или Ибупрофен 200 мг."
        ),
    ),
    PlanItem(
        key="nose_rinse_2",
        hh=12,
        mm=30,
        title="Промывание носа",
        details="Аквалор / Аквамарис.",
        duration_days=7,
    ),
    PlanItem(
        key="nose_spray_2",
        hh=12,
        mm=35,
        title="Спрей для носа",
        details="Синусэфрин / Полидекса.",
        duration_days=7,
    ),
    PlanItem(
        key="gargle_lunch",
        hh=13,
        mm=30,
        title="Полоскание",
        details=(
            "Фурацилин: 1 таб + 100 мл воды. "
            "ОКИ: 10 мл раствора + 100 мл воды."
        ),
        duration_days=5,
    ),
    PlanItem(
        key="azithromycin",
        hh=14,
        mm=0,
        title="Азитромицин (Сумамед)",
        details="500 мг, 1 таблетка 1 раз в сутки.",
        duration_days=6,
    ),
    PlanItem(
        key="thermometry_16_00",
        hh=16,
        mm=0,
        title="Термометрия",
        details=(
            "Измерить температуру. При t > 37,0°C: Парацетамол 500 мг "
            "или Ибупрофен 200 мг."
        ),
    ),
    PlanItem(
        key="probiotic",
        hh=17,
        mm=0,
        title="Пробиотик",
        details=(
            "Линекс / Аципол / Бифиформ / Максилак / Пробиолог, "
            "по 1 капсуле 1 раз в день, через 3 часа после антибиотика."
        ),
        duration_days=10,
    ),
    PlanItem(
        key="gargle_evening_1",
        hh=17,
        mm=30,
        title="Полоскание",
        details=(
            "Фурацилин: 1 таб + 100 мл воды. "
            "ОКИ: 10 мл раствора + 100 мл воды."
        ),
        duration_days=5,
    ),
    PlanItem(
        key="nose_rinse_3",
        hh=18,
        mm=30,
        title="Промывание носа",
        details="Аквалор / Аквамарис.",
        duration_days=7,
    ),
    PlanItem(
        key="nose_spray_3",
        hh=18,
        mm=35,
        title="Спрей для носа",
        details="Синусэфрин / Полидекса.",
        duration_days=7,
    ),
    PlanItem(
        key="inhalation_2",
        hh=20,
        mm=0,
        title="Ингаляция (небулайзер)",
        details=(
            "Пульмикорт 0.5: 1 фл + Беродуал 20 капель + 5 мл физраствора. "
            "После ингаляции промыть рот водой."
        ),
        duration_days=6,
    ),
    PlanItem(
        key="thermometry_20_00",
        hh=20,
        mm=5,
        title="Термометрия",
        details=(
            "Измерить температуру. При t > 37,0°C: Парацетамол 500 мг "
            "или Ибупрофен 200 мг."
        ),
    ),
    PlanItem(
        key="gargle_evening_2",
        hh=21,
        mm=0,
        title="Полоскание",
        details=(
            "Фурацилин: 1 таб + 100 мл воды. "
            "ОКИ: 10 мл раствора + 100 мл воды."
        ),
        duration_days=5,
    ),
    PlanItem(
        key="quote",
        hh=21,
        mm=30,
        title="Вечерняя поддержка",
        details="Поддерживающая цитата.",
        is_quote=True,
    ),
]

QUOTES = [
    "Успех — это сумма маленьких усилий, повторяемых изо дня в день. — Роберт Колльер",
    "Сила не в том, чтобы никогда не падать, а в том, чтобы подниматься каждый раз. — Конфуций",
    "Терпение, настойчивость и труд создают непобедимое сочетание. — Наполеон Хилл",
    "Сделанное сегодня меняет завтра. — Джеймс Клир",
    "Мужество — это идти вперёд, даже когда трудно. — Теодор Рузвельт",
    "Великие дела состоят из маленьких дел, доведённых до конца. — Винсент Ван Гог",
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def add_subscriber(chat_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO subscribers (chat_id, created_at)
            VALUES (?, ?)
            """,
            (chat_id, datetime.now(TZ).isoformat()),
        )
        conn.commit()


def remove_subscriber(chat_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM subscribers WHERE chat_id = ?", (chat_id,))
        conn.commit()


def get_subscribers() -> list[int]:
    with get_connection() as conn:
        rows = conn.execute("SELECT chat_id FROM subscribers").fetchall()
    return [int(row["chat_id"]) for row in rows]


def now_local() -> datetime:
    return datetime.now(TZ)


def treatment_day(target_date: date | None = None) -> int:
    current = target_date or now_local().date()
    return (current - START_DATE).days + 1


def is_item_active(item: PlanItem, target_date: date | None = None) -> bool:
    current = target_date or now_local().date()

    if current < START_DATE:
        return False

    if item.is_quote:
        return True

    if item.duration_days is None:
        return True

    day_number = treatment_day(current)
    return 1 <= day_number <= item.duration_days


def get_active_items_for_date(target_date: date | None = None) -> list[PlanItem]:
    current = target_date or now_local().date()
    items = [item for item in PLAN if is_item_active(item, current) and not item.is_quote]
    return sorted(items, key=lambda x: (x.hh, x.mm, x.key))


def get_next_active_item(now_dt: datetime | None = None) -> PlanItem | None:
    now_dt = now_dt or now_local()
    active_items = get_active_items_for_date(now_dt.date())
    current_minutes = now_dt.hour * 60 + now_dt.minute

    for item in active_items:
        item_minutes = item.hh * 60 + item.mm
        if item_minutes >= current_minutes:
            return item
    return None


def get_following_active_item(item_key: str, target_date: date | None = None) -> PlanItem | None:
    active_items = get_active_items_for_date(target_date)
    for idx, item in enumerate(active_items):
        if item.key == item_key and idx + 1 < len(active_items):
            return active_items[idx + 1]
    return None


def format_plan_for_today() -> str:
    today = now_local().date()

    if today < START_DATE:
        return f"Лечение ещё не началось. Старт: {START_DATE.isoformat()}"

    active_items = get_active_items_for_date(today)
    day_num = treatment_day(today)

    if not active_items:
        return "На сегодня активных назначений по плану уже нет."

    lines = [f"🩺 План на сегодня (день {day_num}):"]
    for item in active_items:
        lines.append(f"{item.time_str} — {item.title}")
        lines.append(f"    {item.details}")
    return "\n".join(lines)


def format_next() -> str:
    now_dt = now_local()
    today = now_dt.date()

    if today < START_DATE:
        return f"Лечение ещё не началось. Старт: {START_DATE.isoformat()}"

    next_item = get_next_active_item(now_dt)
    if next_item is None:
        return "На сегодня больше нет активных пунктов плана."

    following = get_following_active_item(next_item.key, today)
    lines = [
        f"⏭ Следующее по плану: {next_item.time_str} — {next_item.title}",
        next_item.details,
    ]
    if following:
        lines.append(f"\nПотом: {following.time_str} — {following.title}")
    return "\n".join(lines)


async def send_to_all_subscribers(application: Application, text: str) -> None:
    subscribers = get_subscribers()
    if not subscribers:
        return

    for chat_id in subscribers:
        try:
            await application.bot.send_message(chat_id=chat_id, text=text)
        except Exception as exc:
            logger.warning("Не удалось отправить сообщение chat_id=%s: %s", chat_id, exc)


async def reminder_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    item_key = context.job.data["item_key"]
    item = next((i for i in PLAN if i.key == item_key), None)
    if item is None:
        return

    today = now_local().date()
    if not is_item_active(item, today):
        return

    following = get_following_active_item(item.key, today)
    lines = [
        f"⏰ {item.time_str} — {item.title}",
        item.details,
    ]
    if following:
        lines.append(f"\nДальше по плану: {following.time_str} — {following.title}")

    await send_to_all_subscribers(context.application, "\n".join(lines))


async def evening_quote_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    today = now_local().date()
    if today < START_DATE:
        return

    text = (
        "🌟 Ты молодец. Сегодня ты справилась со всем, что было нужно, "
        "и делаешь ещё один шаг к восстановлению.\n\n"
        f"«{random.choice(QUOTES)}»"
    )
    await send_to_all_subscribers(context.application, text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.message is None:
        return

    add_subscriber(update.effective_chat.id)

    text = (
        "Привет! Я бот-напоминалка по твоему плану лечения 💛\n\n"
        f"Старт лечения: {START_DATE.isoformat()}\n\n"
        "Команды:\n"
        "/today — показать актуальный план на сегодня\n"
        "/next — показать ближайший следующий пункт\n"
        "/quote — прислать вечернюю цитату сейчас\n"
        "/stop — отключить напоминания"
    )
    await update.message.reply_text(text)
    await update.message.reply_text(format_plan_for_today())


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(format_plan_for_today())


async def next_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(format_next())


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "🌟 Ты молодец. Ты лечишься, выдерживаешь режим и становишься здоровее.\n\n"
            f"«{random.choice(QUOTES)}»"
        )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.message is None:
        return

    remove_subscriber(update.effective_chat.id)
    await update.message.reply_text(
        "Ок, напоминания отключены. Чтобы включить снова, нажми /start"
    )


async def set_bot_commands(app: Application) -> None:
    await app.bot.set_my_commands(
        [
            BotCommand("start", "включить напоминания"),
            BotCommand("today", "актуальный план на сегодня"),
            BotCommand("next", "что дальше по плану"),
            BotCommand("quote", "получить поддержку"),
            BotCommand("stop", "выключить напоминания"),
        ]
    )


def schedule_jobs(application: Application) -> None:
    jq = application.job_queue

    for item in PLAN:
        if item.is_quote:
            continue

        jq.run_daily(
            callback=reminder_callback,
            time=item.at,
            data={"item_key": item.key},
            name=f"reminder_{item.key}",
        )

    jq.run_daily(
        callback=evening_quote_callback,
        time=time(21, 30, tzinfo=TZ),
        name="evening_quote",
    )


async def post_init(app: Application) -> None:
    await set_bot_commands(app)
    schedule_jobs(app)
    logger.info("Бот инициализирован")


def main() -> None:
    init_db()

    defaults = Defaults(tzinfo=TZ)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .defaults(defaults)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("next", next_step))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("stop", stop))

    logger.info("Запуск бота")
    app.run_polling()


if __name__ == "__main__":
    main()
