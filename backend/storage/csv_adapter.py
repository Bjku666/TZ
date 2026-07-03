from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd

from src.data import TRADE_COLUMNS, WATCHLIST_COLUMNS
from src.rules import clean_code, evaluate_stock, stage_to_group
from src.storage import load_last_refresh

FRONTEND_GROUP_TO_STAGE = {
    "初筛": "初筛通过",
    "观察": "等回踩",
    "待买": "接近买点",
    "持仓": "等回踩",
}


def clean_value(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def number(value: Any, default: float = 0.0) -> float:
    numeric = pd.to_numeric(value, errors="coerce")
    return float(numeric) if pd.notna(numeric) else default


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "是", "yes", "y"}


def records_from_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        rows.append({key: clean_value(value, "") for key, value in row.items()})
    return rows


def watchlist_to_api(frame: pd.DataFrame) -> list[dict[str, Any]]:
    last_refresh = load_last_refresh()
    last_updated = str(last_refresh.get("更新时间", ""))
    result: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        evaluation = evaluate_stock(row.to_dict())
        stage = str(evaluation.get("stage") or row.get("流程阶段") or row.get("状态") or "初筛通过")
        group = str(row.get("分组") or stage_to_group(stage))
        group = str(evaluation.get("group") or stage_to_group(stage))
        risk = evaluation.get("risk_level", "normal")
        result.append(
            {
                "code": clean_code(row.get("代码")),
                "name": str(clean_value(row.get("名称"), "")),
                "price": number(row.get("现价")),
                "pct": number(row.get("涨跌幅%")),
                "volume": number(row.get("成交额")),
                "rank": int(number(row.get("成交额排名"), 0)),
                "ma5": number(row.get("MA5")),
                "ma10": number(row.get("MA10")),
                "ma20": number(row.get("MA20")),
                "deviation5": number(row.get("MA5偏离率%")),
                "bigCandlePct": number(row.get("最近大阳线%")),
                "ma5Upward": bool_value(row.get("MA5向上")),
                "canBuy": bool(evaluation.get("can_buy")),
                "group": group,
                "stage": stage,
                "riskLevel": risk,
                "reason": str(evaluation.get("reason") or clean_value(row.get("筛选原因"), "")),
                "reminder": str(evaluation.get("reminder") or clean_value(row.get("提醒"), "")),
                "historyStatus": str(clean_value(row.get("history_status"), "缺少历史K线")),
                "lastUpdated": last_updated,
                "remark": str(clean_value(row.get("备注"), "")),
            }
        )
    return result


def frontend_settings(settings: dict[str, Any]) -> dict[str, Any]:
    account_mode = settings.get("account_mode", "模拟训练")
    return {
        **settings,
        "initialCash": number(settings.get("simulation_capital"), 10000),
        "realInitialCash": number(settings.get("live_capital"), 5000),
        "currentMode": "real" if account_mode == "实盘记录" else "simulation",
        "commissionRate": number(settings.get("commission_rate"), 0.00025),
        "minCommission": number(settings.get("min_commission"), 5.0),
        "stampDutyRate": number(settings.get("stamp_tax_rate"), 0.0005),
        "transferFeeRate": number(settings.get("transfer_fee_rate"), 0.00001),
    }


def settings_from_frontend(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    out = {**current, **updates}
    if "currentMode" in updates:
        out["account_mode"] = "实盘记录" if updates["currentMode"] == "real" else "模拟训练"
    if "initialCash" in updates:
        out["simulation_capital"] = number(updates["initialCash"], number(current.get("simulation_capital"), 10000))
    if "realInitialCash" in updates:
        out["live_capital"] = number(updates["realInitialCash"], number(current.get("live_capital"), 5000))
    if "commissionRate" in updates:
        out["commission_rate"] = number(updates["commissionRate"], number(current.get("commission_rate"), 0.00025))
    if "minCommission" in updates:
        out["min_commission"] = number(updates["minCommission"], number(current.get("min_commission"), 5.0))
    if "stampDutyRate" in updates:
        out["stamp_tax_rate"] = number(updates["stampDutyRate"], number(current.get("stamp_tax_rate"), 0.0005))
    if "transferFeeRate" in updates:
        out["transfer_fee_rate"] = number(updates["transferFeeRate"], number(current.get("transfer_fee_rate"), 0.00001))
    return out


def api_trade_id(index: int) -> str:
    return f"T{index + 1:06d}"


def trade_index_from_id(trade_id: str) -> int | None:
    text = str(trade_id or "").strip()
    if text.startswith("T") and text[1:].isdigit():
        return int(text[1:]) - 1
    if text.isdigit():
        return int(text)
    return None


def parse_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return [part.strip() for part in text.replace("，", ",").split(",") if part.strip()]


def trades_to_api(frame: pd.DataFrame) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, row in frame.reset_index(drop=True).iterrows():
        side = str(row.get("类型") or "买入")
        snapshot_raw = str(clean_value(row.get("规则快照"), "{}"))
        try:
            snapshot = json.loads(snapshot_raw) if snapshot_raw else {}
        except json.JSONDecodeError:
            snapshot = {}
        result.append(
            {
                "id": api_trade_id(index),
                "code": clean_code(row.get("代码")),
                "name": str(clean_value(row.get("名称"), "")),
                "type": "SELL" if side == "卖出" else "BUY",
                "date": str(clean_value(row.get("日期"), date.today().isoformat()))[:10],
                "time": str(clean_value(row.get("时间"), "")),
                "price": number(row.get("价格")),
                "quantity": number(row.get("数量")),
                "amount": number(row.get("金额")),
                "commission": number(row.get("手续费")),
                "stampDuty": number(row.get("印花税")),
                "transferFee": number(row.get("过户费")),
                "totalFee": number(row.get("总费用")),
                "reason": str(clean_value(row.get("原因"), "")),
                "remark": str(clean_value(row.get("备注"), "")),
                "snapshot": {
                    "group": snapshot.get("group", "初筛"),
                    "stage": snapshot.get("stage", "初筛通过"),
                    "ma5": number(snapshot.get("ma5")),
                    "deviation5": number(snapshot.get("deviation5")),
                    "bigCandlePct": number(snapshot.get("bigCandlePct")),
                    "ma5Upward": bool_value(snapshot.get("ma5Upward")),
                    "cashSufficient": bool_value(snapshot.get("cashSufficient")),
                    "inTradingTime": bool_value(snapshot.get("inTradingTime")),
                },
                "rulesConclusion": str(clean_value(row.get("规则结论"), "") or "其他"),
                "violationTags": parse_tags(row.get("违规标签")),
            }
        )
    return result


def api_trades_for_sqlite(api_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in api_trades:
        rows.append(
            {
                "id": trade["id"],
                "code": trade["code"],
                "name": trade["name"],
                "side": "卖出" if trade["type"] == "SELL" else "买入",
                "trade_date": trade["date"],
                "trade_time": trade.get("time", ""),
                "price": trade.get("price", 0),
                "quantity": trade.get("quantity", 0),
                "amount": trade.get("amount", 0),
                "commission": trade.get("commission", 0),
                "stamp_tax": trade.get("stampDuty", 0),
                "transfer_fee": trade.get("transferFee", 0),
                "total_fee": trade.get("totalFee", 0),
                "reason": trade.get("reason", ""),
                "remark": trade.get("remark", ""),
                "rule_snapshot": json.dumps(trade.get("snapshot", {}), ensure_ascii=False),
                "rule_conclusion": trade.get("rulesConclusion", ""),
                "violation_tags": json.dumps(trade.get("violationTags", []), ensure_ascii=False),
            }
        )
    return rows


def ensure_trade_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in TRADE_COLUMNS:
        if column not in out:
            out[column] = 0 if column in {"手续费", "印花税", "过户费", "总费用"} else ""
    return out[TRADE_COLUMNS]


def ensure_watchlist_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in WATCHLIST_COLUMNS:
        if column not in out:
            out[column] = False if column in {"MA5向上", "放量跌破MA5"} else pd.NA
    return out[WATCHLIST_COLUMNS]
