import sqlite3
import datetime
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent / "tickets.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_no       TEXT    NOT NULL UNIQUE,
            creator         TEXT    NOT NULL DEFAULT '匿名用户',
            department      TEXT    NOT NULL DEFAULT '未指定部门',
            description     TEXT    NOT NULL,
            category        TEXT    NOT NULL,
            risk_level      TEXT    NOT NULL DEFAULT '中',
            status          TEXT    NOT NULL DEFAULT '待分配',
            assignee        TEXT    DEFAULT NULL,
            resolution      TEXT    DEFAULT NULL,
            review_comment  TEXT    DEFAULT NULL,
            rating          INTEGER DEFAULT NULL,
            feedback        TEXT    DEFAULT NULL,
            persona         TEXT    DEFAULT NULL,
            points_earned   INTEGER DEFAULT 0,
            created_at      TEXT    NOT NULL,
            assigned_at     TEXT    DEFAULT NULL,
            resolved_at     TEXT    DEFAULT NULL,
            reviewed_at     TEXT    DEFAULT NULL,
            closed_at       TEXT    DEFAULT NULL
        )
    """)
    # Migrations for existing columns
    columns = [row[1] for row in conn.execute("PRAGMA table_info(tickets)").fetchall()]
    migrations = [
        ("ticket_no",       "TEXT NOT NULL DEFAULT ''"),
        ("creator",         "TEXT NOT NULL DEFAULT '匿名用户'"),
        ("department",      "TEXT NOT NULL DEFAULT '未指定部门'"),
        ("assignee",        "TEXT DEFAULT NULL"),
        ("resolution",      "TEXT DEFAULT NULL"),
        ("review_comment",  "TEXT DEFAULT NULL"),
        ("rating",          "INTEGER DEFAULT NULL"),
        ("feedback",        "TEXT DEFAULT NULL"),
        ("persona",         "TEXT DEFAULT NULL"),
        ("points_earned",   "INTEGER DEFAULT 0"),
        ("assigned_at",     "TEXT DEFAULT NULL"),
        ("resolved_at",     "TEXT DEFAULT NULL"),
        ("reviewed_at",     "TEXT DEFAULT NULL"),
        ("closed_at",       "TEXT DEFAULT NULL"),
    ]
    for col_name, col_def in migrations:
        if col_name not in columns:
            conn.execute(f"ALTER TABLE tickets ADD COLUMN {col_name} {col_def}")
    conn.commit()
    conn.close()


def _now() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _generate_ticket_no(ticket_id: int) -> str:
    today = datetime.datetime.utcnow().strftime("%Y%m%d")
    return f"TK-{today}-{ticket_id:04d}"


def add_ticket(description: str, category: str, risk_level: str = "中",
               creator: str = "匿名用户", department: str = "未指定部门") -> int:
    created_at = _now()
    conn = get_db_connection()
    cursor = conn.execute(
        """INSERT INTO tickets
           (ticket_no, creator, department, description, category, risk_level, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, '待分配', ?)""",
        ("", creator, department, description, category, risk_level, created_at),
    )
    ticket_id = cursor.lastrowid
    ticket_no = _generate_ticket_no(ticket_id)
    conn.execute("UPDATE tickets SET ticket_no = ? WHERE id = ?", (ticket_no, ticket_id))
    conn.commit()
    conn.close()
    return ticket_id


def get_all_tickets(status_filter: str = "all", category_filter: str = "all") -> List[sqlite3.Row]:
    conn = get_db_connection()
    query = "SELECT * FROM tickets WHERE 1=1"
    params: list = []
    if status_filter != "all":
        query += " AND status = ?"
        params.append(status_filter)
    if category_filter != "all":
        query += " AND category = ?"
        params.append(category_filter)
    rows = conn.execute(query + " ORDER BY id DESC", params).fetchall()
    conn.close()
    return rows


def get_ticket(ticket_id: int):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.close()
    return row


def update_ticket(ticket_id: int, **kwargs) -> None:
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [ticket_id]
    conn = get_db_connection()
    conn.execute(f"UPDATE tickets SET {sets} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_ticket_stats():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT category, status, risk_level, COUNT(*) AS count FROM tickets GROUP BY category, status"
    ).fetchall()
    conn.close()
    return rows


def get_leaderboard(limit: int = 10):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT assignee, SUM(points_earned) AS total_points, COUNT(*) AS total_tickets, "
        "AVG(rating) AS avg_rating "
        "FROM tickets WHERE assignee IS NOT NULL AND points_earned > 0 "
        "GROUP BY assignee ORDER BY total_points DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        if d["avg_rating"] is not None:
            d["avg_rating"] = round(d["avg_rating"], 1)
        result.append(d)
    return result


def get_analytics():
    conn = get_db_connection()
    total = conn.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()["c"]
    by_status = {
        row["status"]: row["count"]
        for row in conn.execute("SELECT status, COUNT(*) AS count FROM tickets GROUP BY status").fetchall()
    }
    by_category = {
        row["category"]: row["count"]
        for row in conn.execute("SELECT category, COUNT(*) AS count FROM tickets GROUP BY category").fetchall()
    }
    avg_rating_row = conn.execute("SELECT AVG(rating) AS avg_r FROM tickets WHERE rating IS NOT NULL").fetchone()
    avg_rating = round(avg_rating_row["avg_r"], 1) if avg_rating_row["avg_r"] else 0
    conn.close()
    return {
        "total": total,
        "by_status": by_status,
        "by_category": by_category,
        "avg_rating": avg_rating,
    }
