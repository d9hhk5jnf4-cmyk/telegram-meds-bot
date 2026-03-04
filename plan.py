from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import List, Dict, Optional
import pytz

TZ = pytz.timezone("Europe/Moscow")

# Плановые слоты по Мск
SLOTS = ["07:30", "11:30", "15:30", "19:30", "23:30"]

# Таблетки 1 раз/день — поставила на 08:30 (можно поменять)
DAILY_PILLS_TIME = "08:30"

DAILY_PILLS = [
    ("Витамины группы B", "1 раз/день (обычно с едой, если твой препарат не говорит иначе)"),
    ("Витамин D", "1 раз/день, лучше с едой"),
    ("Йодомарин", "1 раз/день, обычно после еды, запить водой"),
    ("Фолиевая кислота", "1 раз/день, часто с едой/как удобно"),
]

# Дедлайны-окна
EYE_BASE_DEADLINE_MIN = 60          # на "базовый" слот даём час
KORN_OFFSET_MIN = 5                 # строго через 5 мин после капель
KORN_DEADLINE_MIN = 15              # окно: желательно до +15
FLOX_OFFSET_MIN = 10                # мазь через 10 мин после капель
FLOX_DEADLINE_MIN = 20              # окно: желательно до +20
PILLS_DEADLINE_HOURS = 3            # окно на таблетки

@dataclass
class TaskSpec:
    title: str
    details: str
    kind: str          # base / followup / pill
    slot: str
    scheduled_for: datetime
    deadline_at: datetime
    chain: bool = False  # если True — по done создаём followups

def _today_at(hhmm: str) -> datetime:
    now = datetime.now(TZ)
    hh, mm = map(int, hhmm.split(":"))
    return now.replace(hour=hh, minute=mm, second=0, microsecond=0)

def build_tasks_for_slot(slot: str) -> List[TaskSpec]:
    t = _today_at(slot)
    out: List[TaskSpec] = []

    # БАЗОВЫЕ (капли) — запускают цепочки
    if slot == "07:30":
        out.append(TaskSpec(
            title="Капли (утро): Комвео + Офтальмоферон",
            details=(
                "Комвео: 1 кап — ЛЕВЫЙ + ПРАВЫЙ.\n"
                "Офтальмоферон: 1 кап — ОБА глаза.\n\n"
                "После подтверждения я сам пришлю Корнерегель через 5 минут."
            ),
            kind="base",
            slot=slot,
            scheduled_for=t,
            deadline_at=t + timedelta(minutes=EYE_BASE_DEADLINE_MIN),
            chain=True
        ))
    elif slot == "11:30":
        out.append(TaskSpec(
            title="Капли: Комвео",
            details="Комвео: 1 кап — ЛЕВЫЙ.\n\nПосле подтверждения — Корнерегель через 5 минут.",
            kind="base",
            slot=slot,
            scheduled_for=t,
            deadline_at=t + timedelta(minutes=EYE_BASE_DEADLINE_MIN),
            chain=True
        ))
    elif slot == "15:30":
        out.append(TaskSpec(
            title="Капли: Комвео",
            details="Комвео: 1 кап — ЛЕВЫЙ + ПРАВЫЙ.\n\nПосле подтверждения — Корнерегель через 5 минут.",
            kind="base",
            slot=slot,
            scheduled_for=t,
            deadline_at=t + timedelta(minutes=EYE_BASE_DEADLINE_MIN),
            chain=True
        ))
    elif slot == "19:30":
        out.append(TaskSpec(
            title="Капли (вечер): Комвео + Офтальмоферон",
            details=(
                "Комвео: 1 кап — ЛЕВЫЙ.\n"
                "Офтальмоферон: 1 кап — ОБА глаза.\n\n"
                "После подтверждения — Корнерегель через 5 минут."
            ),
            kind="base",
            slot=slot,
            scheduled_for=t,
            deadline_at=t + timedelta(minutes=EYE_BASE_DEADLINE_MIN),
            chain=True
        ))
    elif slot == "23:30":
        out.append(TaskSpec(
            title="Капли (ночь): Комвео",
            details=(
                "Комвео: 1 кап — ЛЕВЫЙ + ПРАВЫЙ.\n\n"
                "После подтверждения:\n"
                f"• Корнерегель через {KORN_OFFSET_MIN} минут\n"
                f"• Флоксал мазь через {FLOX_OFFSET_MIN} минут (ЛЕВЫЙ)"
            ),
            kind="base",
            slot=slot,
            scheduled_for=t,
            deadline_at=t + timedelta(minutes=EYE_BASE_DEADLINE_MIN),
            chain=True
        ))

    # ТАБЛЕТКИ — одним блоком, 1 раз в день
    if slot == "07:30":
        pills_dt = _today_at(DAILY_PILLS_TIME)
        out.append(TaskSpec(
            title="Таблетки/витамины (1 раз/день)",
            details="\n".join([f"• {name}: {note}" for name, note in DAILY_PILLS]),
            kind="pill",
            slot=DAILY_PILLS_TIME,
            scheduled_for=pills_dt,
            deadline_at=pills_dt + timedelta(hours=PILLS_DEADLINE_HOURS),
            chain=False
        ))

    return out

def followups_for_base(slot: str) -> List[Dict]:
    # что именно должно прийти после done на базовой задаче
    items = []

    # Корнерегель
    if slot in ("07:30", "15:30", "23:30"):
        items.append({
            "title": "Корнерегель",
            "details": "Корнерегель: ЛЕВЫЙ + ПРАВЫЙ (строго после капель).",
            "offset_min": KORN_OFFSET_MIN,
            "deadline_min": KORN_DEADLINE_MIN,
        })
    elif slot in ("11:30", "19:30"):
        items.append({
            "title": "Корнерегель",
            "details": "Корнерегель: ЛЕВЫЙ (строго после капель).",
            "offset_min": KORN_OFFSET_MIN,
            "deadline_min": KORN_DEADLINE_MIN,
        })

    # Флоксал только на ночь
    if slot == "23:30":
        items.append({
            "title": "Флоксал мазь",
            "details": "Флоксал мазь: ЛЕВЫЙ, полоска ~1 см, за нижнее веко (через 10 минут после капель).",
            "offset_min": FLOX_OFFSET_MIN,
            "deadline_min": FLOX_DEADLINE_MIN,
        })

    return items
