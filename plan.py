from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict
import pytz

TZ = pytz.timezone("Europe/Moscow")

# Плановые слоты по Мск
SLOTS = ["07:30", "11:30", "15:30", "19:30", "23:30"]

# Таблетки 1 раз/день (можно поменять)
DAILY_PILLS_TIME = "08:30"

DAILY_PILLS = [
    "Витамины группы B",
    "Витамин D",
    "Йодомарин",
    "Фолиевая кислота",
]

# Интервалы по листочку
KORN_OFFSET_MIN = 5
FLOX_OFFSET_MIN = 10

# Дедлайны (для трекера, в тексте не показываем)
EYE_BASE_DEADLINE_MIN = 60
KORN_DEADLINE_MIN = 15
FLOX_DEADLINE_MIN = 20
PILLS_DEADLINE_HOURS = 3

# Нумерация приёмов (как ты просила: первый/второй/пятый)
# Для краткости в тексте показываем #n/N.
KOMVEO_LEFT_N = {"07:30": 1, "11:30": 2, "15:30": 3, "19:30": 4, "23:30": 5}
KOMVEO_RIGHT_N = {"07:30": 1, "15:30": 2, "23:30": 3}

OFTALMOFERON_N = {"07:30": 1, "19:30": 2}

KORN_LEFT_N = {"07:30": 1, "11:30": 2, "15:30": 3, "19:30": 4, "23:30": 5}
KORN_RIGHT_N = {"07:30": 1, "15:30": 2, "23:30": 3}

@dataclass
class TaskSpec:
    title: str
    details: str
    kind: str          # base / followup / pill
    slot: str
    scheduled_for: datetime
    deadline_at: datetime
    chain: bool = False

def _today_at(hhmm: str) -> datetime:
    now = datetime.now(TZ)
    hh, mm = map(int, hhmm.split(":"))
    return now.replace(hour=hh, minute=mm, second=0, microsecond=0)

def build_tasks_for_slot(slot: str) -> List[TaskSpec]:
    t = _today_at(slot)
    out: List[TaskSpec] = []

    # --- ГЛАЗА: базовые шаги (капли), которые запускают цепочки ---
    if slot == "07:30":
        # Комвео: оба (левый 1/5 + правый 1/3, но в тексте показываем #1/5)
        n = KOMVEO_LEFT_N[slot]
        out.append(TaskSpec(
            title=f"#{n}/5 Комвео + Офтальмоферон — оба",
            details=f"⏱ через {KORN_OFFSET_MIN} мин: Корнерегель",
            kind="base",
            slot=slot,
            scheduled_for=t,
            deadline_at=t + timedelta(minutes=EYE_BASE_DEADLINE_MIN),
            chain=True
        ))

    elif slot == "11:30":
        n = KOMVEO_LEFT_N[slot]
        out.append(TaskSpec(
            title=f"#{n}/5 Комвео — левый",
            details=f"⏱ через {KORN_OFFSET_MIN} мин: Корнерегель",
            kind="base",
            slot=slot,
            scheduled_for=t,
            deadline_at=t + timedelta(minutes=EYE_BASE_DEADLINE_MIN),
            chain=True
        ))

    elif slot == "15:30":
        n = KOMVEO_LEFT_N[slot]
        out.append(TaskSpec(
            title=f"#{n}/5 Комвео — оба",
            details=f"⏱ через {KORN_OFFSET_MIN} мин: Корнерегель",
            kind="base",
            slot=slot,
            scheduled_for=t,
            deadline_at=t + timedelta(minutes=EYE_BASE_DEADLINE_MIN),
            chain=True
        ))

    elif slot == "19:30":
        n = KOMVEO_LEFT_N[slot]
        out.append(TaskSpec(
            title=f"#{n}/5 Комвео + Офтальмоферон — левый/оба",
            details=f"⏱ через {KORN_OFFSET_MIN} мин: Корнерегель",
            kind="base",
            slot=slot,
            scheduled_for=t,
            deadline_at=t + timedelta(minutes=EYE_BASE_DEADLINE_MIN),
            chain=True
        ))

    elif slot == "23:30":
        n = KOMVEO_LEFT_N[slot]
        out.append(TaskSpec(
            title=f"#{n}/5 Комвео — оба",
            details=f"⏱ через {KORN_OFFSET_MIN} мин: Корнерегель • через {FLOX_OFFSET_MIN} мин: Флоксал мазь",
            kind="base",
            slot=slot,
            scheduled_for=t,
            deadline_at=t + timedelta(minutes=EYE_BASE_DEADLINE_MIN),
            chain=True
        ))

    # --- Таблетки: один блок 1 раз в день ---
    if slot == "07:30":
        pills_dt = _today_at(DAILY_PILLS_TIME)
        out.append(TaskSpec(
            title="💊 Таблетки (1×/день)",
            details="\n".join(DAILY_PILLS) + "\n\nПосле еды.",
            kind="pill",
            slot=DAILY_PILLS_TIME,
            scheduled_for=pills_dt,
            deadline_at=pills_dt + timedelta(hours=PILLS_DEADLINE_HOURS),
            chain=False
        ))

    return out

def followups_for_base(slot: str) -> List[Dict]:
    """
    Возвращает список follow-up шагов, которые нужно запланировать
    ПОСЛЕ того, как ты нажала ✅ на базовом шаге (капли).
    """
    items = []

    # Корнерегель
    if slot in ("07:30", "15:30", "23:30"):
        n = KORN_LEFT_N[slot]
        items.append({
            "title": f"#{n}/5 Корнерегель — оба",
            "details": "✔ Готово. Ждём следующий приём по расписанию.",
            "offset_min": KORN_OFFSET_MIN,
            "deadline_min": KORN_DEADLINE_MIN,
        })
    elif slot in ("11:30", "19:30"):
        n = KORN_LEFT_N[slot]
        items.append({
            "title": f"#{n}/5 Корнерегель — левый",
            "details": "✔ Готово. Ждём следующий приём по расписанию.",
            "offset_min": KORN_OFFSET_MIN,
            "deadline_min": KORN_DEADLINE_MIN,
        })

    # Флоксал — только на ночь, отдельным сообщением
    if slot == "23:30":
        items.append({
            "title": "Флоксал мазь — левый",
            "details": "✔ Готово. Ждём следующий приём по расписанию.",
            "offset_min": FLOX_OFFSET_MIN,
            "deadline_min": FLOX_DEADLINE_MIN,
        })

    return items
