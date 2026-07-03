from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.data import DATA_DIR, ensure_data_dir

DB_PATH = DATA_DIR / "app.db"


def connect() -> sqlite3.Connection:
    ensure_data_dir()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT NOT NULL,
                mode TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                side TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                trade_time TEXT,
                price REAL NOT NULL DEFAULT 0,
                quantity REAL NOT NULL DEFAULT 0,
                amount REAL NOT NULL DEFAULT 0,
                commission REAL NOT NULL DEFAULT 0,
                stamp_tax REAL NOT NULL DEFAULT 0,
                transfer_fee REAL NOT NULL DEFAULT 0,
                total_fee REAL NOT NULL DEFAULT 0,
                reason TEXT,
                remark TEXT,
                rule_snapshot TEXT,
                rule_conclusion TEXT,
                violation_tags TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id, mode)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                report_type TEXT NOT NULL,
                report_date TEXT NOT NULL,
                json_path TEXT,
                md_path TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def save_kv(key: str, value: Any) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO kv(key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, json.dumps(value, ensure_ascii=False)),
        )


def load_kv(key: str, default: Any = None) -> Any:
    with connect() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return default


def replace_trades(mode: str, trades: list[dict[str, Any]]) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM trades WHERE mode = ?", (mode,))
        conn.executemany(
            """
            INSERT INTO trades(
                id, mode, code, name, side, trade_date, trade_time, price, quantity,
                amount, commission, stamp_tax, transfer_fee, total_fee, reason,
                remark, rule_snapshot, rule_conclusion, violation_tags
            )
            VALUES (
                :id, :mode, :code, :name, :side, :trade_date, :trade_time, :price,
                :quantity, :amount, :commission, :stamp_tax, :transfer_fee,
                :total_fee, :reason, :remark, :rule_snapshot, :rule_conclusion,
                :violation_tags
            )
            """,
            [{**trade, "mode": mode} for trade in trades],
        )


def register_report(report_id: str, report_type: str, report_date: str, json_path: Path, md_path: Path) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO reports(id, report_type, report_date, json_path, md_path, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                report_type = excluded.report_type,
                report_date = excluded.report_date,
                json_path = excluded.json_path,
                md_path = excluded.md_path,
                updated_at = CURRENT_TIMESTAMP
            """,
            (report_id, report_type, report_date, str(json_path), str(md_path)),
        )

