import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List


class Storage:
    def __init__(self, path: str = "bot.db"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        cur = self.conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            chat_id INTEGER PRIMARY KEY,
            paused INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            details TEXT NOT NULL,
            slot TEXT NOT NULL,
            kind TEXT NOT NULL,        -- base/followup/pill
            chain INTEGER NOT NULL DEFAULT 0,
            scheduled_for TEXT NOT NULL,
            deadline_at TEXT NOT NULL,
            parent_task_id INTEGER,
            status TEXT NOT NULL DEFAULT 'pending', -- pending/done/skipped
            created_at TEXT NOT NULL,
            done_at TEXT
        );
        """)
        self.conn.commit()

    # Users
    def upsert_user(self, chat_id: int):
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO users(chat_id) VALUES(?)", (chat_id,))
        self.conn.commit()

    def set_paused(self, chat_id: int, paused: bool):
        cur = self.conn.cursor()
        cur.execute("UPDATE users SET paused=? WHERE chat_id=?", (1 if paused else 0, chat_id))
        self.conn.commit()

    def is_paused(self, chat_id: int) -> bool:
        cur = self.conn.cursor()
        r = cur.execute("SELECT paused FROM users WHERE chat_id=?", (chat_id,)).fetchone()
        return bool(r["paused"]) if r else False

    def get_users(self) -> List[int]:
        cur = self.conn.cursor()
        rows = cur.execute("SELECT chat_id FROM users").fetchall()
        return [r["chat_id"] for r in rows]

    # Tasks
    def create_task(
        self,
        chat_id: int,
        title: str,
        details: str,
        slot: str,
        kind: str,
        chain: bool,
        scheduled_for: datetime,
        deadline_at: datetime,
        parent_task_id: Optional[int] = None,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO tasks(chat_id,title,details,slot,kind,chain,scheduled_for,deadline_at,parent_task_id,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            chat_id, title, details, slot, kind, 1 if chain else 0,
            scheduled_for.isoformat(), deadline_at.isoformat(), parent_task_id,
            datetime.now().isoformat()
        ))
        self.conn.commit()
        return int(cur.lastrowid)

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        r = cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(r) if r else None

    def mark_done(self, task_id: int, done_at: datetime):
        cur = self.conn.cursor()
        cur.execute("UPDATE tasks SET status='done', done_at=? WHERE id=?", (done_at.isoformat(), task_id))
        self.conn.commit()

    def mark_skipped(self, task_id: int, done_at: datetime):
        cur = self.conn.cursor()
        cur.execute("UPDATE tasks SET status='skipped', done_at=? WHERE id=?", (done_at.isoformat(), task_id))
        self.conn.commit()

    def snooze(self, task_id: int, new_time: datetime):
        cur = self.conn.cursor()
        cur.execute("UPDATE tasks SET scheduled_for=? WHERE id=?", (new_time.isoformat(), task_id))
        self.conn.commit()

    def list_day(self, chat_id: int, day_iso: str) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        rows = cur.execute("""
            SELECT * FROM tasks
            WHERE chat_id=? AND substr(scheduled_for,1,10)=?
            ORDER BY scheduled_for
        """, (chat_id, day_iso)).fetchall()
        return [dict(r) for r in rows]

    def stats(self, chat_id: int) -> Dict[str, int]:
        cur = self.conn.cursor()
        rows = cur.execute("""
            SELECT status, count(*) as c
            FROM tasks
            WHERE chat_id=?
            GROUP BY status
        """, (chat_id,)).fetchall()
        return {r["status"]: int(r["c"]) for r in rows}

    # Rendering (новый стиль: коротко, без времени/дедлайнов)
    def render_task(self, task: Dict[str, Any]) -> str:
        if not task:
            return "Задача не найдена"
        title = (task.get("title") or "").strip()
        details = (task.get("details") or "").strip()
        if details:
            return f"{title}\n{details}".strip()
        return title
