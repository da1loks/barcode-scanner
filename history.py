import json
import os
import sqlite3
import threading
import time
from typing import Optional

DB_PATH = os.getenv("HISTORY_DB", "history.db")
_local = threading.local()


def _conn() -> sqlite3.Connection:
    if not getattr(_local, "conn", None):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


def init_db(path: str = DB_PATH):
    global DB_PATH
    DB_PATH = path
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            event TEXT NOT NULL,
            task_id TEXT,
            manipulator_id TEXT,
            code TEXT,
            priority INTEGER,
            status TEXT,
            center_x REAL,
            center_y REAL,
            robot_x REAL,
            robot_y REAL,
            payload TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_history_ts ON history(ts DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_history_code ON history(code)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_manip ON history(manipulator_id)"
    )
    conn.commit()
    conn.close()
    _local.conn = None


def log_event(
    event: str,
    *,
    task: Optional[dict] = None,
    detection: Optional[dict] = None,
    extra: Optional[dict] = None,
):
    task = task or {}
    detection = detection or {}
    result = task.get("result") or detection or {}
    center = result.get("center") or {}
    robot = result.get("robot_mm") or {}
    payload = {
        "task": {
            "task_id": task.get("task_id"),
            "code": task.get("code"),
            "manipulator_id": task.get("manipulator_id"),
            "priority": task.get("priority"),
            "status": task.get("status"),
        }
        if task
        else None,
        "result": result or None,
        "extra": extra,
    }
    conn = _conn()
    conn.execute(
        """
        INSERT INTO history (
            ts, event, task_id, manipulator_id, code, priority, status,
            center_x, center_y, robot_x, robot_y, payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            time.time(),
            event,
            task.get("task_id"),
            task.get("manipulator_id"),
            task.get("code") or result.get("code"),
            task.get("priority"),
            task.get("status"),
            center.get("x"),
            center.get("y"),
            robot.get("x"),
            robot.get("y"),
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    conn.commit()


def query_history(
    *,
    limit: int = 50,
    manipulator_id: Optional[str] = None,
    code: Optional[str] = None,
    event: Optional[str] = None,
) -> list[dict]:
    sql = "SELECT * FROM history WHERE 1=1"
    args: list = []
    if manipulator_id:
        sql += " AND manipulator_id = ?"
        args.append(manipulator_id)
    if code:
        sql += " AND code = ?"
        args.append(code)
    if event:
        sql += " AND event = ?"
        args.append(event)
    sql += " ORDER BY ts DESC LIMIT ?"
    args.append(limit)

    conn = _conn()
    rows = conn.execute(sql, args).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        if item.get("payload"):
            try:
                item["payload"] = json.loads(item["payload"])
            except json.JSONDecodeError:
                pass
        out.append(item)
    return out
