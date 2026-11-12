"""SQLite storage for box types and freight plans.

A single file ``data/planner.db`` is created on first use and seeded with a
small demo catalog so the UI works out of the box.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

DB_PATH = os.environ.get(
    "PLANNER_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "planner.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS box_types (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL DEFAULT '',
    inner_l      INTEGER NOT NULL,
    inner_w      INTEGER NOT NULL,
    inner_h      INTEGER NOT NULL,
    outer_l      INTEGER NOT NULL,
    outer_w      INTEGER NOT NULL,
    outer_h      INTEGER NOT NULL,
    box_weight_g INTEGER NOT NULL,
    box_fee      REAL NOT NULL,
    max_gross_g  INTEGER NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS freight_plans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL DEFAULT '',
    vol_divisor     INTEGER NOT NULL,
    unit            TEXT NOT NULL DEFAULT 'g',
    billing_step_g  INTEGER NOT NULL,
    price_per_step  REAL NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS solve_runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    request    TEXT NOT NULL,
    response   TEXT NOT NULL,
    ok         INTEGER NOT NULL
);
"""

SEED_BOXES = [
    # code, name, inner (l,w,h), outer (l,w,h), box weight g, box fee, max gross g
    ("B1", "小号箱", 200, 150, 120, 210, 160, 130, 180, 1.2, 3000),
    ("B2", "中号箱", 300, 220, 200, 312, 232, 212, 320, 2.0, 8000),
    ("B3", "大号箱", 400, 300, 280, 414, 314, 294, 520, 3.2, 15000),
    ("B4", "特大箱", 550, 400, 380, 566, 416, 396, 780, 4.8, 25000),
]

SEED_PLANS = [
    # code, name, vol divisor mm3/g, unit, step g, price per step
    # 6000 cm3/kg -> 6000 mm3/g ; 5000 -> common express divisors
    ("STD", "标准快递 (÷6000)", 6000, "g", 1000, 8.0),
    ("ECON", "经济快递 (÷8000)", 8000, "g", 1000, 6.0),
    ("AIR", "航空快运 (÷5000)", 5000, "g", 500, 5.0),
]


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        n = conn.execute("SELECT COUNT(*) FROM box_types").fetchone()[0]
        if n == 0:
            conn.executemany(
                """INSERT INTO box_types
                   (code,name,inner_l,inner_w,inner_h,outer_l,outer_w,outer_h,
                    box_weight_g,box_fee,max_gross_g,active)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
                SEED_BOXES,
            )
        n = conn.execute("SELECT COUNT(*) FROM freight_plans").fetchone()[0]
        if n == 0:
            conn.executemany(
                """INSERT INTO freight_plans
                   (code,name,vol_divisor,unit,billing_step_g,price_per_step,active)
                   VALUES (?,?,?,?,?,?,1)""",
                SEED_PLANS,
            )


# ---------------------------------------------------------------------------
# Row -> dict helpers
# ---------------------------------------------------------------------------

def _box_row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["active"] = bool(d["active"])
    return d


def _plan_row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["active"] = bool(d["active"])
    return d


def list_boxes(active_only: bool = True) -> list[dict]:
    with get_conn() as conn:
        sql = "SELECT * FROM box_types"
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY id"
        return [_box_row(r) for r in conn.execute(sql)]


def list_plans(active_only: bool = True) -> list[dict]:
    with get_conn() as conn:
        sql = "SELECT * FROM freight_plans"
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY id"
        return [_plan_row(r) for r in conn.execute(sql)]


def get_boxes(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    q = ",".join("?" * len(ids))
    with get_conn() as conn:
        return [
            _box_row(r)
            for r in conn.execute(
                f"SELECT * FROM box_types WHERE id IN ({q}) ORDER BY id", ids
            )
        ]


def get_plans(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    q = ",".join("?" * len(ids))
    with get_conn() as conn:
        return [
            _plan_row(r)
            for r in conn.execute(
                f"SELECT * FROM freight_plans WHERE id IN ({q}) ORDER BY id", ids
            )
        ]


def insert_box(data: dict) -> dict:
    cols = (
        "code,name,inner_l,inner_w,inner_h,outer_l,outer_w,outer_h,"
        "box_weight_g,box_fee,max_gross_g,active"
    )
    vals = (
        data["code"], data.get("name", ""), data["inner_l"], data["inner_w"],
        data["inner_h"], data["outer_l"], data["outer_w"], data["outer_h"],
        data["box_weight_g"], data["box_fee"], data["max_gross_g"],
        1 if data.get("active", True) else 0,
    )
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO box_types ({cols}) VALUES ({','.join('?' * len(vals))})", vals
        )
        row = conn.execute("SELECT * FROM box_types WHERE id=?", (cur.lastrowid,)).fetchone()
        return _box_row(row)


def insert_plan(data: dict) -> dict:
    cols = "code,name,vol_divisor,unit,billing_step_g,price_per_step,active"
    vals = (
        data["code"], data.get("name", ""), data["vol_divisor"], data.get("unit", "g"),
        data["billing_step_g"], data["price_per_step"],
        1 if data.get("active", True) else 0,
    )
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO freight_plans ({cols}) VALUES ({','.join('?' * len(vals))})", vals
        )
        row = conn.execute(
            "SELECT * FROM freight_plans WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return _plan_row(row)


def save_run(request_json: str, response_json: str, ok: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO solve_runs (request,response,ok) VALUES (?,?,?)",
            (request_json, response_json, 1 if ok else 0),
        )
