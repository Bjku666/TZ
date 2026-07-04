from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.data import DATA_DIR, ensure_data_dir
from src.rule_models import CandidateState

DB_PATH = DATA_DIR / "app.db"


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False


def connect() -> sqlite3.Connection:
    ensure_data_dir()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
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
            CREATE TABLE IF NOT EXISTS selection_batches (
                id TEXT PRIMARY KEY,
                selection_date TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                data_as_of TEXT,
                source TEXT NOT NULL,
                is_official INTEGER NOT NULL DEFAULT 0,
                raw_top_n INTEGER NOT NULL DEFAULT 20,
                status TEXT NOT NULL DEFAULT 'active',
                source_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS selection_items (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                raw_rank INTEGER,
                turnover REAL,
                close_price REAL,
                ma5_close REAL,
                market_allowed INTEGER NOT NULL DEFAULT 0,
                exclusion_reason TEXT,
                above_ma5 INTEGER NOT NULL DEFAULT 0,
                candidate_created INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(batch_id, code),
                FOREIGN KEY(batch_id) REFERENCES selection_batches(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_cycles (
                id TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT,
                source_batch_id TEXT NOT NULL,
                selection_date TEXT NOT NULL,
                eligible_from TEXT NOT NULL,
                state TEXT NOT NULL,
                waiting_trade_days INTEGER NOT NULL DEFAULT 0,
                last_close REAL,
                last_ma5_close REAL,
                last_live_price REAL,
                last_ma5_live REAL,
                last_deviation REAL,
                touch_started_at TEXT,
                touch_detected_at TEXT,
                bought_trade_id TEXT,
                invalidated_at TEXT,
                invalidated_reason TEXT,
                closed_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(source_batch_id) REFERENCES selection_batches(id)
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_candidate_active_code
            ON candidate_cycles(code)
            WHERE state NOT IN ('BOUGHT', 'CLOSED', 'INVALIDATED', 'CANCELLED')
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_time TEXT NOT NULL,
                trade_date TEXT,
                price REAL,
                ma5 REAL,
                deviation REAL,
                quote_time TEXT,
                quote_age_seconds REAL,
                source TEXT,
                reason TEXT,
                payload_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(candidate_id) REFERENCES candidate_cycles(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT,
                code TEXT NOT NULL,
                event_time TEXT NOT NULL,
                trade_date TEXT,
                signal_type TEXT NOT NULL,
                signal_qualified INTEGER NOT NULL DEFAULT 0,
                execution_allowed INTEGER NOT NULL DEFAULT 0,
                execution_block_reasons TEXT,
                price REAL,
                ma5 REAL,
                deviation REAL,
                quote_time TEXT,
                quote_age_seconds REAL,
                payload_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(candidate_id) REFERENCES candidate_cycles(id)
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations(version)
            VALUES ('video_original_v1')
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


def _trade_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "accountMode": row["mode"],
        "code": row["code"],
        "name": row["name"],
        "type": "SELL" if row["side"] == "卖出" else "BUY",
        "date": row["trade_date"],
        "time": row["trade_time"] or "",
        "price": float(row["price"] or 0),
        "quantity": float(row["quantity"] or 0),
        "amount": float(row["amount"] or 0),
        "commission": float(row["commission"] or 0),
        "stampDuty": float(row["stamp_tax"] or 0),
        "transferFee": float(row["transfer_fee"] or 0),
        "totalFee": float(row["total_fee"] or 0),
        "reason": row["reason"] or "",
        "remark": row["remark"] or "",
        "snapshot": _json_value(row["rule_snapshot"], {}),
        "rulesConclusion": row["rule_conclusion"] or "",
        "violationTags": _json_value(row["violation_tags"], []),
    }


def _json_value(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        return default


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def upsert_selection_batch(batch: dict[str, Any]) -> str:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO selection_batches(
                id, selection_date, generated_at, data_as_of, source, is_official,
                raw_top_n, status, source_message, created_at, updated_at
            )
            VALUES (
                :id, :selection_date, :generated_at, :data_as_of, :source, :is_official,
                :raw_top_n, :status, :source_message, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT(id) DO UPDATE SET
                selection_date = excluded.selection_date,
                generated_at = excluded.generated_at,
                data_as_of = excluded.data_as_of,
                source = excluded.source,
                is_official = excluded.is_official,
                raw_top_n = excluded.raw_top_n,
                status = excluded.status,
                source_message = excluded.source_message,
                updated_at = CURRENT_TIMESTAMP
            """,
            batch,
        )
    return str(batch["id"])


def upsert_selection_item(item: dict[str, Any]) -> str:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO selection_items(
                id, batch_id, code, name, raw_rank, turnover, close_price, ma5_close,
                market_allowed, exclusion_reason, above_ma5, candidate_created, created_at
            )
            VALUES (
                :id, :batch_id, :code, :name, :raw_rank, :turnover, :close_price, :ma5_close,
                :market_allowed, :exclusion_reason, :above_ma5, :candidate_created, CURRENT_TIMESTAMP
            )
            ON CONFLICT(batch_id, code) DO UPDATE SET
                name = excluded.name,
                raw_rank = excluded.raw_rank,
                turnover = excluded.turnover,
                close_price = excluded.close_price,
                ma5_close = excluded.ma5_close,
                market_allowed = excluded.market_allowed,
                exclusion_reason = excluded.exclusion_reason,
                above_ma5 = excluded.above_ma5,
                candidate_created = excluded.candidate_created
            """,
            item,
        )
    return str(item["id"])


def active_candidate_for_code(code: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM candidate_cycles
            WHERE code = ?
              AND state NOT IN ('BOUGHT', 'CLOSED', 'INVALIDATED', 'CANCELLED')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (code,),
        ).fetchone()
    return _row_dict(row)


def create_candidate_cycle(candidate: dict[str, Any]) -> tuple[str, bool]:
    init_db()
    existing = active_candidate_for_code(str(candidate["code"]))
    if existing:
        return str(existing["id"]), False
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO candidate_cycles(
                id, code, name, source_batch_id, selection_date, eligible_from, state,
                waiting_trade_days, last_close, last_ma5_close, created_at, updated_at
            )
            VALUES (
                :id, :code, :name, :source_batch_id, :selection_date, :eligible_from, :state,
                :waiting_trade_days, :last_close, :last_ma5_close, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            candidate,
        )
    add_candidate_event(
        str(candidate["id"]),
        "CANDIDATE_CREATED",
        event_time=str(candidate.get("created_at") or candidate.get("event_time") or candidate.get("generated_at") or ""),
        trade_date=str(candidate.get("selection_date") or ""),
        price=candidate.get("last_close"),
        ma5=candidate.get("last_ma5_close"),
        reason="正式初筛通过，入选日收盘站上MA5",
        payload=candidate,
    )
    return str(candidate["id"]), True


def update_candidate_cycle(candidate_id: str, updates: dict[str, Any]) -> None:
    if not updates:
        return
    allowed = {
        "state",
        "waiting_trade_days",
        "last_close",
        "last_ma5_close",
        "last_live_price",
        "last_ma5_live",
        "last_deviation",
        "touch_started_at",
        "touch_detected_at",
        "bought_trade_id",
        "invalidated_at",
        "invalidated_reason",
        "closed_at",
    }
    pairs = [(key, value) for key, value in updates.items() if key in allowed]
    if not pairs:
        return
    assignments = ", ".join(f"{key} = ?" for key, _ in pairs) + ", updated_at = CURRENT_TIMESTAMP"
    values = [value for _, value in pairs] + [candidate_id]
    with connect() as conn:
        conn.execute(f"UPDATE candidate_cycles SET {assignments} WHERE id = ?", values)


def add_candidate_event(
    candidate_id: str,
    event_type: str,
    *,
    event_time: str,
    trade_date: str = "",
    price: Any = None,
    ma5: Any = None,
    deviation: Any = None,
    quote_time: str = "",
    quote_age_seconds: Any = None,
    source: str = "",
    reason: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO candidate_events(
                candidate_id, event_type, event_time, trade_date, price, ma5,
                deviation, quote_time, quote_age_seconds, source, reason, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                event_type,
                event_time,
                trade_date,
                price,
                ma5,
                deviation,
                quote_time,
                quote_age_seconds,
                source,
                reason,
                json.dumps(payload or {}, ensure_ascii=False),
            ),
        )


def add_signal_event(event: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO signal_events(
                candidate_id, code, event_time, trade_date, signal_type,
                signal_qualified, execution_allowed, execution_block_reasons,
                price, ma5, deviation, quote_time, quote_age_seconds, payload_json
            )
            VALUES (
                :candidate_id, :code, :event_time, :trade_date, :signal_type,
                :signal_qualified, :execution_allowed, :execution_block_reasons,
                :price, :ma5, :deviation, :quote_time, :quote_age_seconds, :payload_json
            )
            """,
            {
                **event,
                "execution_block_reasons": json.dumps(event.get("execution_block_reasons") or [], ensure_ascii=False),
                "payload_json": json.dumps(event.get("payload") or {}, ensure_ascii=False),
            },
        )


def latest_official_batch() -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM selection_batches
            WHERE is_official = 1
            ORDER BY selection_date DESC, generated_at DESC
            LIMIT 1
            """
        ).fetchone()
    return _row_dict(row)


def selection_items_for_batch(batch_id: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM selection_items WHERE batch_id = ? ORDER BY raw_rank",
            (batch_id,),
        ).fetchall()
    return [_row_dict(row) or {} for row in rows]


def candidate_cycles(active_only: bool = True) -> list[dict[str, Any]]:
    init_db()
    where = "WHERE state NOT IN ('BOUGHT', 'CLOSED', 'INVALIDATED', 'CANCELLED')" if active_only else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM candidate_cycles {where} ORDER BY selection_date, created_at"
        ).fetchall()
    return [_row_dict(row) or {} for row in rows]


def candidate_events(candidate_id: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM candidate_events
            WHERE candidate_id = ?
            ORDER BY event_time, id
            """,
            (candidate_id,),
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = _row_dict(row) or {}
        item["payload"] = _json_value(item.pop("payload_json", "{}"), {})
        result.append(item)
    return result


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


def list_trades(mode: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM trades
            WHERE mode = ?
            ORDER BY trade_date, COALESCE(trade_time, ''), rowid
            """,
            (mode,),
        ).fetchall()
    return [_trade_row(row) for row in rows]


def has_trades(mode: str) -> bool:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM trades WHERE mode = ? LIMIT 1", (mode,)).fetchone()
    return row is not None


def next_trade_id(mode: str) -> str:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM trades WHERE mode = ?", (mode,)).fetchone()
    return f"T{int(row['count']) + 1:06d}"


def upsert_trade(mode: str, trade: dict[str, Any]) -> None:
    init_db()
    row = {**trade, "mode": mode}
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO trades(
                id, mode, code, name, side, trade_date, trade_time, price, quantity,
                amount, commission, stamp_tax, transfer_fee, total_fee, reason,
                remark, rule_snapshot, rule_conclusion, violation_tags, updated_at
            )
            VALUES (
                :id, :mode, :code, :name, :side, :trade_date, :trade_time, :price,
                :quantity, :amount, :commission, :stamp_tax, :transfer_fee,
                :total_fee, :reason, :remark, :rule_snapshot, :rule_conclusion,
                :violation_tags, CURRENT_TIMESTAMP
            )
            ON CONFLICT(id, mode) DO UPDATE SET
                code = excluded.code,
                name = excluded.name,
                side = excluded.side,
                trade_date = excluded.trade_date,
                trade_time = excluded.trade_time,
                price = excluded.price,
                quantity = excluded.quantity,
                amount = excluded.amount,
                commission = excluded.commission,
                stamp_tax = excluded.stamp_tax,
                transfer_fee = excluded.transfer_fee,
                total_fee = excluded.total_fee,
                reason = excluded.reason,
                remark = excluded.remark,
                rule_snapshot = excluded.rule_snapshot,
                rule_conclusion = excluded.rule_conclusion,
                violation_tags = excluded.violation_tags,
                updated_at = CURRENT_TIMESTAMP
            """,
            row,
        )


def delete_trade(mode: str, trade_id: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM trades WHERE mode = ? AND id = ?", (mode, trade_id))


def delete_trades(mode: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM trades WHERE mode = ?", (mode,))


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
