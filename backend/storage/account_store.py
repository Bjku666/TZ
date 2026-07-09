from __future__ import annotations

import json
import os
import sqlite3
import csv
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from backend.services.strategy_rules import DEFAULT_STRATEGY_ID, validate_strategy

MODES = {"simulation", "real"}
DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    "simulation": {
        "initialCash": 200000.0,
        "accountDesc": "五日线回踩模拟训练账户",
        "enableReconciliation": False,
        "defaultRemark": "记录依据与执行纪律",
        "commissionRate": 0.0003,
        "minCommission": 5.0,
        "enableMinCommission": True,
        "stampDutyRate": 0.0005,
        "transferFeeRate": 0.00001,
        "reconciliation": {
            "enabled": False,
            "totalAssets": 200000.0,
            "availableCash": 200000.0,
            "holdingValue": 0.0,
            "holdingPnL": 0.0,
            "todayPnL": 0.0,
            "updatedAt": "",
            "remark": "模拟账户无需券商对账",
        },
    },
    "real": {
        "initialCash": 5000.0,
        "accountDesc": "实盘交易记录账户",
        "enableReconciliation": True,
        "defaultRemark": "实盘记录，纪律优先",
        "commissionRate": 0.0002,
        "minCommission": 5.0,
        "enableMinCommission": True,
        "stampDutyRate": 0.0005,
        "transferFeeRate": 0.00001,
        "reconciliation": {
            "enabled": False,
            "totalAssets": 5000.0,
            "availableCash": 5000.0,
            "holdingValue": 0.0,
            "holdingPnL": 0.0,
            "todayPnL": 0.0,
            "updatedAt": "",
            "remark": "手工录入同花顺期末数后，仅用于对账展示",
        },
    },
}


def validate_mode(mode: str) -> str:
    if mode not in MODES:
        raise ValueError("mode 必须是 simulation 或 real")
    return mode


def _data_dir() -> Path:
    path = Path(os.getenv("TZ_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return _data_dir() / "tz_workspace.sqlite3"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def utc_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def init_account_storage() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS account_settings (
                mode TEXT PRIMARY KEY CHECK(mode IN ('simulation','real')),
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trades (
                id TEXT NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('simulation','real')),
                strategy_id TEXT NOT NULL DEFAULT 'ma5_pullback',
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
                trade_date TEXT NOT NULL,
                trade_time TEXT NOT NULL,
                price REAL NOT NULL CHECK(price > 0),
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                amount REAL NOT NULL,
                commission REAL NOT NULL DEFAULT 0,
                stamp_duty REAL NOT NULL DEFAULT 0,
                transfer_fee REAL NOT NULL DEFAULT 0,
                total_fee REAL NOT NULL DEFAULT 0,
                reason TEXT NOT NULL DEFAULT '',
                remark TEXT NOT NULL DEFAULT '',
                rules_conclusion TEXT NOT NULL DEFAULT '无法判断',
                violation_tags_json TEXT NOT NULL DEFAULT '[]',
                historical_backfill INTEGER NOT NULL DEFAULT 0,
                manual_fee_override INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(id, mode, strategy_id)
            );

            CREATE TABLE IF NOT EXISTS position_state (
                mode TEXT NOT NULL CHECK(mode IN ('simulation','real')),
                strategy_id TEXT NOT NULL DEFAULT 'ma5_pullback',
                code TEXT NOT NULL,
                buy_date TEXT NOT NULL DEFAULT '',
                deferred INTEGER NOT NULL DEFAULT 0,
                defer_reason TEXT NOT NULL DEFAULT '',
                notes_json TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(mode, strategy_id, code)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('simulation','real')),
                strategy_id TEXT NOT NULL DEFAULT 'ma5_pullback',
                review_type TEXT NOT NULL DEFAULT 'daily',
                review_date TEXT NOT NULL,
                plan_and_basis TEXT NOT NULL DEFAULT '',
                execution_and_deviation TEXT NOT NULL DEFAULT '',
                result_and_emotion TEXT NOT NULL DEFAULT '',
                improvement_and_next_plan TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(id, mode, strategy_id),
                UNIQUE(mode, strategy_id, review_type, review_date)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('simulation','real')),
                strategy_id TEXT NOT NULL DEFAULT 'ma5_pullback',
                level TEXT NOT NULL DEFAULT 'INFO',
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                code TEXT,
                created_at TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(id, mode, strategy_id)
            );
            """
        )
        _migrate_strategy_scope(conn)
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_trades_mode_strategy_time
                ON trades(mode, strategy_id, trade_date DESC, trade_time DESC, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_notifications_mode_strategy_time
                ON notifications(mode, strategy_id, created_at DESC);
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(4, ?)",
            (utc_now(),),
        )
        for mode, settings in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO account_settings(mode, payload_json, updated_at) VALUES(?,?,?)",
                (mode, json.dumps(settings, ensure_ascii=False), utc_now()),
            )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _pk_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row["name"] for row in sorted((row for row in rows if row["pk"]), key=lambda row: row["pk"])]


def _migrate_strategy_scope(conn: sqlite3.Connection) -> None:
    trade_columns = _columns(conn, "trades")
    if "strategy_id" not in trade_columns or _pk_columns(conn, "trades") != ["id", "mode", "strategy_id"]:
        strategy_expr = "COALESCE(strategy_id,'ma5_pullback')" if "strategy_id" in trade_columns else "'ma5_pullback'"
        conn.executescript(
            f"""
            ALTER TABLE trades RENAME TO trades_legacy_strategy_migration;
            CREATE TABLE trades (
                id TEXT NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('simulation','real')),
                strategy_id TEXT NOT NULL DEFAULT 'ma5_pullback',
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
                trade_date TEXT NOT NULL,
                trade_time TEXT NOT NULL,
                price REAL NOT NULL CHECK(price > 0),
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                amount REAL NOT NULL,
                commission REAL NOT NULL DEFAULT 0,
                stamp_duty REAL NOT NULL DEFAULT 0,
                transfer_fee REAL NOT NULL DEFAULT 0,
                total_fee REAL NOT NULL DEFAULT 0,
                reason TEXT NOT NULL DEFAULT '',
                remark TEXT NOT NULL DEFAULT '',
                rules_conclusion TEXT NOT NULL DEFAULT '无法判断',
                violation_tags_json TEXT NOT NULL DEFAULT '[]',
                historical_backfill INTEGER NOT NULL DEFAULT 0,
                manual_fee_override INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(id, mode, strategy_id)
            );
            INSERT OR IGNORE INTO trades(
                id,mode,strategy_id,code,name,side,trade_date,trade_time,price,quantity,amount,
                commission,stamp_duty,transfer_fee,total_fee,reason,remark,rules_conclusion,
                violation_tags_json,historical_backfill,manual_fee_override,created_at,updated_at
            )
            SELECT
                id,mode,{strategy_expr},code,name,side,trade_date,trade_time,price,quantity,amount,
                commission,stamp_duty,transfer_fee,total_fee,reason,remark,rules_conclusion,
                violation_tags_json,historical_backfill,manual_fee_override,created_at,updated_at
            FROM trades_legacy_strategy_migration;
            DROP TABLE trades_legacy_strategy_migration;
            """
        )

    position_columns = _columns(conn, "position_state")
    if "strategy_id" not in position_columns or _pk_columns(conn, "position_state") != ["mode", "strategy_id", "code"]:
        strategy_expr = "COALESCE(strategy_id,'ma5_pullback')" if "strategy_id" in position_columns else "'ma5_pullback'"
        conn.executescript(
            f"""
            ALTER TABLE position_state RENAME TO position_state_legacy_strategy_migration;
            CREATE TABLE position_state (
                mode TEXT NOT NULL CHECK(mode IN ('simulation','real')),
                strategy_id TEXT NOT NULL DEFAULT 'ma5_pullback',
                code TEXT NOT NULL,
                buy_date TEXT NOT NULL DEFAULT '',
                deferred INTEGER NOT NULL DEFAULT 0,
                defer_reason TEXT NOT NULL DEFAULT '',
                notes_json TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(mode, strategy_id, code)
            );
            INSERT OR IGNORE INTO position_state(mode,strategy_id,code,buy_date,deferred,defer_reason,notes_json,updated_at)
            SELECT mode,{strategy_expr},code,buy_date,deferred,defer_reason,notes_json,updated_at
            FROM position_state_legacy_strategy_migration;
            DROP TABLE position_state_legacy_strategy_migration;
            """
        )

    review_columns = _columns(conn, "reviews")
    if "strategy_id" not in review_columns or _pk_columns(conn, "reviews") != ["id", "mode", "strategy_id"]:
        strategy_expr = "COALESCE(strategy_id,'ma5_pullback')" if "strategy_id" in review_columns else "'ma5_pullback'"
        conn.executescript(
            f"""
            ALTER TABLE reviews RENAME TO reviews_legacy_strategy_migration;
            CREATE TABLE reviews (
                id TEXT NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('simulation','real')),
                strategy_id TEXT NOT NULL DEFAULT 'ma5_pullback',
                review_type TEXT NOT NULL DEFAULT 'daily',
                review_date TEXT NOT NULL,
                plan_and_basis TEXT NOT NULL DEFAULT '',
                execution_and_deviation TEXT NOT NULL DEFAULT '',
                result_and_emotion TEXT NOT NULL DEFAULT '',
                improvement_and_next_plan TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(id, mode, strategy_id),
                UNIQUE(mode, strategy_id, review_type, review_date)
            );
            INSERT OR IGNORE INTO reviews(
                id,mode,strategy_id,review_type,review_date,plan_and_basis,execution_and_deviation,
                result_and_emotion,improvement_and_next_plan,created_at,updated_at
            )
            SELECT
                id,mode,{strategy_expr},review_type,review_date,plan_and_basis,execution_and_deviation,
                result_and_emotion,improvement_and_next_plan,created_at,updated_at
            FROM reviews_legacy_strategy_migration;
            DROP TABLE reviews_legacy_strategy_migration;
            """
        )

    notification_columns = _columns(conn, "notifications")
    if "strategy_id" not in notification_columns or _pk_columns(conn, "notifications") != ["id", "mode", "strategy_id"]:
        strategy_expr = "COALESCE(strategy_id,'ma5_pullback')" if "strategy_id" in notification_columns else "'ma5_pullback'"
        conn.executescript(
            f"""
            ALTER TABLE notifications RENAME TO notifications_legacy_strategy_migration;
            CREATE TABLE notifications (
                id TEXT NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('simulation','real')),
                strategy_id TEXT NOT NULL DEFAULT 'ma5_pullback',
                level TEXT NOT NULL DEFAULT 'INFO',
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                code TEXT,
                created_at TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(id, mode, strategy_id)
            );
            INSERT OR IGNORE INTO notifications(id,mode,strategy_id,level,title,message,code,created_at,is_read)
            SELECT id,mode,{strategy_expr},level,title,message,code,created_at,is_read
            FROM notifications_legacy_strategy_migration;
            DROP TABLE notifications_legacy_strategy_migration;
            """
        )


def get_settings(mode: str) -> dict[str, Any]:
    validate_mode(mode)
    with connect() as conn:
        row = conn.execute("SELECT payload_json FROM account_settings WHERE mode=?", (mode,)).fetchone()
    return json.loads(row["payload_json"]) if row else json.loads(json.dumps(DEFAULT_SETTINGS[mode]))


def save_settings(mode: str, payload: dict[str, Any]) -> dict[str, Any]:
    validate_mode(mode)
    merged = {**get_settings(mode), **payload}
    if "reconciliation" in payload:
        merged["reconciliation"] = {**get_settings(mode).get("reconciliation", {}), **payload["reconciliation"]}
    with connect() as conn:
        conn.execute(
            "INSERT INTO account_settings(mode,payload_json,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(mode) DO UPDATE SET payload_json=excluded.payload_json, updated_at=excluded.updated_at",
            (mode, json.dumps(merged, ensure_ascii=False), utc_now()),
        )
    return merged


def list_trades(mode: str, strategy_id: str | None = None) -> list[dict[str, Any]]:
    validate_mode(mode)
    strategy_id = validate_strategy(strategy_id)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE mode=? AND strategy_id=? ORDER BY trade_date DESC, trade_time DESC, created_at DESC",
            (mode, strategy_id),
        ).fetchall()
    return [_trade_row(row) for row in rows]


def get_trade(mode: str, trade_id: str, strategy_id: str | None = None) -> dict[str, Any] | None:
    strategy_id = validate_strategy(strategy_id)
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM trades WHERE mode=? AND strategy_id=? AND id=?",
            (validate_mode(mode), strategy_id, trade_id),
        ).fetchone()
    return _trade_row(row) if row else None


def upsert_trade(mode: str, trade: dict[str, Any], strategy_id: str | None = None) -> dict[str, Any]:
    validate_mode(mode)
    strategy_id = validate_strategy(strategy_id or trade.get("strategyId"))
    now = utc_now()
    existing = get_trade(mode, str(trade["id"]), strategy_id)
    created_at = existing.get("createdAt", now) if existing else now
    values = (
        str(trade["id"]), mode, strategy_id, str(trade["code"]), str(trade["name"]), str(trade["type"]),
        str(trade["date"]), str(trade["time"]), float(trade["price"]), int(trade["quantity"]),
        float(trade["amount"]), float(trade.get("commission", 0)), float(trade.get("stampDuty", 0)),
        float(trade.get("transferFee", 0)), float(trade.get("totalFee", 0)), str(trade.get("reason", "")),
        str(trade.get("remark", "")), str(trade.get("rulesConclusion", "无法判断")),
        json.dumps(trade.get("violationTags", []), ensure_ascii=False), int(bool(trade.get("historicalBackfill"))),
        int(bool(trade.get("manualFeeOverride"))), created_at, now,
    )
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO trades(
                id,mode,strategy_id,code,name,side,trade_date,trade_time,price,quantity,amount,
                commission,stamp_duty,transfer_fee,total_fee,reason,remark,rules_conclusion,
                violation_tags_json,historical_backfill,manual_fee_override,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id,mode,strategy_id) DO UPDATE SET
                code=excluded.code,name=excluded.name,side=excluded.side,trade_date=excluded.trade_date,
                trade_time=excluded.trade_time,price=excluded.price,quantity=excluded.quantity,amount=excluded.amount,
                commission=excluded.commission,stamp_duty=excluded.stamp_duty,transfer_fee=excluded.transfer_fee,
                total_fee=excluded.total_fee,reason=excluded.reason,remark=excluded.remark,
                rules_conclusion=excluded.rules_conclusion,violation_tags_json=excluded.violation_tags_json,
                historical_backfill=excluded.historical_backfill,manual_fee_override=excluded.manual_fee_override,
                updated_at=excluded.updated_at
            """,
            values,
        )
    return get_trade(mode, str(trade["id"]), strategy_id) or {**trade, "strategyId": strategy_id}


def delete_trade(mode: str, trade_id: str, strategy_id: str | None = None) -> bool:
    strategy_id = validate_strategy(strategy_id)
    with connect() as conn:
        cursor = conn.execute(
            "DELETE FROM trades WHERE mode=? AND strategy_id=? AND id=?",
            (validate_mode(mode), strategy_id, trade_id),
        )
    return cursor.rowcount > 0


def get_position_state(mode: str, code: str, strategy_id: str | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id)
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM position_state WHERE mode=? AND strategy_id=? AND code=?",
            (validate_mode(mode), strategy_id, code),
        ).fetchone()
    if not row:
        return {"deferred": False, "deferReason": "", "notes": [], "buyDate": ""}
    return {
        "deferred": bool(row["deferred"]),
        "deferReason": row["defer_reason"],
        "notes": json.loads(row["notes_json"] or "[]"),
        "buyDate": row["buy_date"],
    }


def save_position_state(mode: str, code: str, *, strategy_id: str | None = None, buy_date: str = "", deferred: bool | None = None,
                        defer_reason: str | None = None, notes: list[str] | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id)
    current = get_position_state(mode, code, strategy_id)
    payload = {
        "buyDate": buy_date or current.get("buyDate", ""),
        "deferred": current.get("deferred", False) if deferred is None else deferred,
        "deferReason": current.get("deferReason", "") if defer_reason is None else defer_reason,
        "notes": current.get("notes", []) if notes is None else notes,
    }
    with connect() as conn:
        conn.execute(
            """INSERT INTO position_state(mode,strategy_id,code,buy_date,deferred,defer_reason,notes_json,updated_at)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(mode,strategy_id,code) DO UPDATE SET buy_date=excluded.buy_date,deferred=excluded.deferred,
               defer_reason=excluded.defer_reason,notes_json=excluded.notes_json,updated_at=excluded.updated_at""",
            (validate_mode(mode), strategy_id, code, payload["buyDate"], int(payload["deferred"]), payload["deferReason"],
             json.dumps(payload["notes"], ensure_ascii=False), utc_now()),
        )
    return payload


def list_reviews(mode: str, strategy_id: str | None = None) -> list[dict[str, Any]]:
    strategy_id = validate_strategy(strategy_id)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM reviews WHERE mode=? AND strategy_id=? ORDER BY review_date DESC, updated_at DESC",
            (validate_mode(mode), strategy_id),
        ).fetchall()
    return [_review_row(row) for row in rows]


def save_review(mode: str, review: dict[str, Any], strategy_id: str | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id or review.get("strategyId"))
    now = utc_now()
    review_id = str(review.get("id") or f"{review.get('type','daily')}-{review['date']}")
    with connect() as conn:
        conn.execute(
            """INSERT INTO reviews(id,mode,strategy_id,review_type,review_date,plan_and_basis,execution_and_deviation,
               result_and_emotion,improvement_and_next_plan,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(mode,strategy_id,review_type,review_date) DO UPDATE SET
               plan_and_basis=excluded.plan_and_basis,execution_and_deviation=excluded.execution_and_deviation,
               result_and_emotion=excluded.result_and_emotion,improvement_and_next_plan=excluded.improvement_and_next_plan,
               updated_at=excluded.updated_at""",
            (review_id, validate_mode(mode), strategy_id, review.get("type", "daily"), review["date"],
             review.get("planAndBasis", ""), review.get("executionAndDeviation", ""),
             review.get("resultAndEmotion", ""), review.get("improvementAndNextPlan", ""), now, now),
        )
    return next(item for item in list_reviews(mode, strategy_id) if item["date"] == review["date"] and item["type"] == review.get("type", "daily"))


def list_notifications(mode: str, strategy_id: str | None = None) -> list[dict[str, Any]]:
    strategy_id = validate_strategy(strategy_id)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE mode=? AND strategy_id=? ORDER BY created_at DESC",
            (validate_mode(mode), strategy_id),
        ).fetchall()
    return [_notification_row(row) for row in rows]


def add_notification(mode: str, level: str, title: str, message: str, code: str | None = None,
                     strategy_id: str | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id)
    now = utc_now()
    notification_id = f"notification-{int(datetime.now().timestamp() * 1000000)}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO notifications(id,mode,strategy_id,level,title,message,code,created_at,is_read) VALUES(?,?,?,?,?,?,?,?,0)",
            (notification_id, validate_mode(mode), strategy_id, level, title, message, code, now),
        )
    return list_notifications(mode, strategy_id)[0]


def mark_notification(mode: str, notification_id: str, strategy_id: str | None = None) -> None:
    strategy_id = validate_strategy(strategy_id)
    with connect() as conn:
        conn.execute(
            "UPDATE notifications SET is_read=1 WHERE mode=? AND strategy_id=? AND id=?",
            (validate_mode(mode), strategy_id, notification_id),
        )


def mark_all_notifications(mode: str, strategy_id: str | None = None) -> None:
    strategy_id = validate_strategy(strategy_id)
    with connect() as conn:
        conn.execute("UPDATE notifications SET is_read=1 WHERE mode=? AND strategy_id=?", (validate_mode(mode), strategy_id))


def clear_notifications(mode: str, strategy_id: str | None = None) -> None:
    strategy_id = validate_strategy(strategy_id)
    with connect() as conn:
        conn.execute("DELETE FROM notifications WHERE mode=? AND strategy_id=?", (validate_mode(mode), strategy_id))


def lookup_security_name(mode: str, code: str, strategy_id: str | None = None) -> dict[str, Any]:
    mode = validate_mode(mode)
    strategy_id = validate_strategy(strategy_id)
    normalized = str(code or "").strip()
    if not normalized:
        return {"code": normalized, "name": "", "found": False, "source": ""}

    for trade in list_trades(mode, strategy_id):
        if trade["code"] == normalized and trade.get("name"):
            return {"code": normalized, "name": trade["name"], "found": True, "source": "历史交易"}

    for filename, source in (("holdings.csv", "当前持仓"), ("watchlist.csv", "自选池")):
        path = _data_dir() / filename
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    row_code = str(row.get("代码") or row.get("code") or row.get("证券代码") or "").strip()
                    row_name = str(row.get("名称") or row.get("name") or row.get("证券名称") or "").strip()
                    if row_code == normalized and row_name:
                        return {"code": normalized, "name": row_name, "found": True, "source": source}
        except OSError:
            continue

    return {"code": normalized, "name": "", "found": False, "source": ""}


def _trade_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "accountMode": row["mode"], "strategyId": row["strategy_id"], "code": row["code"], "name": row["name"],
        "type": row["side"], "date": row["trade_date"], "time": row["trade_time"], "price": row["price"],
        "quantity": row["quantity"], "amount": row["amount"], "commission": row["commission"],
        "stampDuty": row["stamp_duty"], "transferFee": row["transfer_fee"], "totalFee": row["total_fee"],
        "reason": row["reason"], "remark": row["remark"], "rulesConclusion": row["rules_conclusion"],
        "violationTags": json.loads(row["violation_tags_json"] or "[]"),
        "historicalBackfill": bool(row["historical_backfill"]), "manualFeeOverride": bool(row["manual_fee_override"]),
        "createdAt": row["created_at"], "updatedAt": row["updated_at"],
    }


def _review_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "accountMode": row["mode"], "strategyId": row["strategy_id"], "type": row["review_type"], "date": row["review_date"],
        "planAndBasis": row["plan_and_basis"], "executionAndDeviation": row["execution_and_deviation"],
        "resultAndEmotion": row["result_and_emotion"], "improvementAndNextPlan": row["improvement_and_next_plan"],
        "saved": True, "createdAt": row["created_at"], "updatedAt": row["updated_at"],
    }


def _notification_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "timestamp": row["created_at"], "accountMode": row["mode"], "strategyId": row["strategy_id"], "type": row["level"],
        "title": row["title"], "message": row["message"], "relatedCode": row["code"], "read": bool(row["is_read"]),
    }
