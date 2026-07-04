from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.data import TRADE_COLUMNS, load_trades as load_csv_trades, save_trades as save_csv_trades
from src.data import trade_account_mode_name
from src.portfolio import calculate_trade_fees
from backend.storage import sqlite_store
from backend.storage.csv_adapter import (
    api_trade_id,
    api_trades_for_sqlite,
    ensure_trade_frame,
    trades_to_api,
)


def _trade_frame_from_api(api_trades: list[dict[str, Any]], mode_name: str | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trade in api_trades:
        side = "卖出" if trade.get("type") == "SELL" else "买入"
        snapshot = trade.get("snapshot", {})
        rows.append(
            {
                "账户模式": mode_name or trade_account_mode_name(trade.get("accountMode")),
                "代码": trade.get("code", ""),
                "名称": trade.get("name", ""),
                "类型": side,
                "日期": trade.get("date", ""),
                "时间": trade.get("time", ""),
                "价格": trade.get("price", 0),
                "数量": trade.get("quantity", 0),
                "金额": trade.get("amount", 0),
                "手续费": trade.get("commission", 0),
                "印花税": trade.get("stampDuty", 0),
                "过户费": trade.get("transferFee", 0),
                "总费用": trade.get("totalFee", 0),
                "原因": trade.get("reason", ""),
                "备注": trade.get("remark", ""),
                "规则快照": json.dumps(snapshot, ensure_ascii=False),
                "规则结论": trade.get("rulesConclusion", ""),
                "违规标签": json.dumps(trade.get("violationTags", []), ensure_ascii=False),
            }
        )
    return ensure_trade_frame(pd.DataFrame(rows, columns=TRADE_COLUMNS))


def _bootstrap_mode_from_csv(mode_name: str, sqlite_mode: str) -> list[dict[str, Any]]:
    csv_frame = ensure_trade_frame(load_csv_trades())
    mode_frame = csv_frame[csv_frame["账户模式"].map(trade_account_mode_name) == mode_name].reset_index(drop=True)
    api_trades = trades_to_api(mode_frame)
    if api_trades:
        sqlite_store.replace_trades(sqlite_mode, api_trades_for_sqlite(api_trades))
    return api_trades


def ensure_mode_loaded(mode: str, mode_name: str) -> None:
    if not sqlite_store.has_trades(mode):
        _bootstrap_mode_from_csv(mode_name, mode)


def list_api_trades(mode: str, mode_name: str) -> list[dict[str, Any]]:
    if not sqlite_store.has_trades(mode):
        return _bootstrap_mode_from_csv(mode_name, mode)
    return sqlite_store.list_trades(mode)


def load_trade_frame(mode: str, mode_name: str) -> pd.DataFrame:
    return _trade_frame_from_api(list_api_trades(mode, mode_name), mode_name)


def next_trade_id(mode: str, mode_name: str) -> str:
    ensure_mode_loaded(mode, mode_name)
    return sqlite_store.next_trade_id(mode)


def save_api_trades(mode: str, mode_name: str, api_trades: list[dict[str, Any]]) -> None:
    sqlite_store.replace_trades(mode, api_trades_for_sqlite(api_trades))
    sync_csv_mode(mode, mode_name)


def append_api_trade(mode: str, mode_name: str, api_trade: dict[str, Any]) -> None:
    ensure_mode_loaded(mode, mode_name)
    sqlite_row = api_trades_for_sqlite([api_trade])[0]
    sqlite_store.upsert_trade(mode, sqlite_row)
    sync_csv_mode(mode, mode_name)


def delete_api_trade(mode: str, mode_name: str, trade_id: str) -> None:
    ensure_mode_loaded(mode, mode_name)
    remaining: list[dict[str, Any]] = []
    deleted = False
    for trade in sqlite_store.list_trades(mode):
        if trade.get("id") == trade_id:
            deleted = True
            continue
        remaining.append(trade)
    if not deleted:
        return
    for index, trade in enumerate(remaining):
        trade["id"] = api_trade_id(index)
    save_api_trades(mode, mode_name, remaining)


def delete_all_api_trades(mode: str, mode_name: str) -> None:
    ensure_mode_loaded(mode, mode_name)
    sqlite_store.delete_trades(mode)
    sync_csv_mode(mode, mode_name)


def recalculate_api_trade_fees(mode: str, mode_name: str, fee_settings: dict[str, Any]) -> list[dict[str, Any]]:
    frame = load_trade_frame(mode, mode_name).reset_index(drop=True)
    if frame.empty:
        save_api_trades(mode, mode_name, [])
        return []
    for index, row in frame.iterrows():
        fees = calculate_trade_fees(row.get("类型"), row.get("价格"), row.get("数量"), fee_settings)
        frame.loc[index, "金额"] = fees["amount"]
        frame.loc[index, "手续费"] = fees["commission"]
        frame.loc[index, "印花税"] = fees["stamp_tax"]
        frame.loc[index, "过户费"] = fees["transfer_fee"]
        frame.loc[index, "总费用"] = fees["total_fee"]
    api_trades = trades_to_api(frame)
    for item_index, item in enumerate(api_trades):
        item["id"] = api_trade_id(item_index)
    save_api_trades(mode, mode_name, api_trades)
    return api_trades


def sync_csv_mode(mode: str, mode_name: str) -> None:
    current = ensure_trade_frame(load_csv_trades())
    other_modes = current[current["账户模式"].map(trade_account_mode_name) != mode_name].reset_index(drop=True)
    mode_frame = _trade_frame_from_api(sqlite_store.list_trades(mode), mode_name)
    combined = pd.concat([other_modes, mode_frame], ignore_index=True)
    save_csv_trades(combined)
