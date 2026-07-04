from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd

from src.data import TRADE_COLUMNS, WATCHLIST_COLUMNS
from src.rules import clean_code, evaluate_stock, normalize_stage, stage_to_group
from src.settings import (
    FEE_API_ALIASES,
    FEE_DEFAULTS,
    FEE_PROFILE_CUSTOM,
    FEE_PROFILE_REAL_A_SHARE,
    FEE_PROFILE_THS_SIMULATION,
    account_mode_from_api,
    api_mode_from_account_mode,
    fee_prefix_for_mode,
    fee_defaults_for_profile,
    mode_fee_settings,
    normalize_fee_profile,
    profile_from_fee_values,
)
from src.storage import load_last_refresh

FRONTEND_GROUP_TO_STAGE = {
    "初筛": "初筛通过",
    "观察": "继续观察",
    "待买": "待买观察",
    "持仓": "继续观察",
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
        stage = normalize_stage(evaluation.get("stage") or row.get("流程阶段") or row.get("状态") or "初筛通过")
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
                "poolBatchId": str(clean_value(row.get("pool_batch_id"), "")),
                "poolSource": str(clean_value(row.get("pool_source"), "")),
                "poolGeneratedAt": str(clean_value(row.get("pool_generated_at"), "")),
                "poolRankAtGeneration": int(number(row.get("pool_rank_at_generation"), number(row.get("成交额排名"), 0))),
                "isPoolLocked": bool_value(row.get("is_pool_locked")),
                "isPinned": bool_value(row.get("is_pinned")),
                "ma5": number(row.get("MA5")),
                "ma10": number(row.get("MA10")),
                "ma20": number(row.get("MA20")),
                "deviation5": number(row.get("MA5偏离率%")),
                "bigCandlePct": number(row.get("最近大阳线%")),
                "ma5Upward": bool_value(row.get("MA5向上")),
                "canBuy": bool(evaluation.get("signal_qualified", evaluation.get("can_buy"))),
                "signalQualified": bool(evaluation.get("signal_qualified", evaluation.get("can_buy"))),
                "signalReason": str(evaluation.get("signal_reason") or ""),
                "executionAllowed": bool(evaluation.get("execution_allowed")),
                "executionBlockReasons": list(evaluation.get("execution_block_reasons") or []),
                "manualConfirmationRequired": bool(evaluation.get("manual_confirmation_required", True)),
                "maxBuyableLotQuantity": int(number(evaluation.get("max_lot_quantity"), 0)),
                "lotCost": number(evaluation.get("lot_cost"), number(row.get("一手金额"))),
                "stopPrice": number(evaluation.get("stop_price"), number(row.get("预估止损价"))),
                "riskAmount": number(evaluation.get("risk_amount"), number(row.get("预估亏损金额"))),
                "maxRiskAmount": number(evaluation.get("max_risk_amount"), number(row.get("最大允许亏损"))),
                "riskPct": number(row.get("单笔风险%")),
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
    current_mode = api_mode_from_account_mode(account_mode)
    active_fees = mode_fee_settings(settings, current_mode)
    simulation_fees = mode_fee_settings(settings, "simulation")
    real_fees = mode_fee_settings(settings, "real")
    simulation_reconciliation = _reconciliation_from_settings(settings, "simulation")
    real_reconciliation = _reconciliation_from_settings(settings, "real")
    return {
        **settings,
        "initialCash": number(settings.get("simulation_capital"), 10000),
        "realInitialCash": number(settings.get("live_capital"), 5000),
        "activeInitialCash": number(
            settings.get("live_capital") if current_mode == "real" else settings.get("simulation_capital"),
            5000 if current_mode == "real" else 10000,
        ),
        "currentMode": current_mode,
        "feeProfile": active_fees["fee_profile"],
        "commissionRate": active_fees["commission_rate"],
        "minCommission": active_fees["min_commission"],
        "stampDutyRate": active_fees["stamp_tax_rate"],
        "transferFeeRate": active_fees["transfer_fee_rate"],
        "simulationFees": {
            "feeProfile": simulation_fees["fee_profile"],
            "commissionRate": simulation_fees["commission_rate"],
            "minCommission": simulation_fees["min_commission"],
            "stampDutyRate": simulation_fees["stamp_tax_rate"],
            "transferFeeRate": simulation_fees["transfer_fee_rate"],
        },
        "realFees": {
            "feeProfile": real_fees["fee_profile"],
            "commissionRate": real_fees["commission_rate"],
            "minCommission": real_fees["min_commission"],
            "stampDutyRate": real_fees["stamp_tax_rate"],
            "transferFeeRate": real_fees["transfer_fee_rate"],
        },
        "thsReconciliation": real_reconciliation if current_mode == "real" else simulation_reconciliation,
        "simulationThsReconciliation": simulation_reconciliation,
        "realThsReconciliation": real_reconciliation,
    }


def _reconciliation_from_settings(settings: dict[str, Any], mode: str) -> dict[str, Any]:
    is_real = mode == "real"
    prefix = "live_ths" if is_real else "ths"
    default_capital = number(settings.get("live_capital"), 5000) if is_real else 200000
    return {
        "enabled": bool(settings.get(f"{prefix}_reconciliation_enabled", False)),
        "accountCapital": number(settings.get(f"{prefix}_account_capital"), default_capital),
        "totalAssets": number(settings.get(f"{prefix}_total_assets"), default_capital),
        "availableCash": number(settings.get(f"{prefix}_available_cash"), default_capital),
        "holdingValue": number(settings.get(f"{prefix}_holding_value"), 0 if is_real else 7090),
        "holdingPnL": number(settings.get(f"{prefix}_holding_pnl"), 0 if is_real else -57.28),
        "todayPnL": number(settings.get(f"{prefix}_today_pnl"), 0 if is_real else -242.27),
    }


def settings_from_frontend(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    out = {**current, **updates}
    if "currentMode" in updates:
        out["account_mode"] = account_mode_from_api(updates["currentMode"])
    if "initialCash" in updates:
        out["simulation_capital"] = number(updates["initialCash"], number(current.get("simulation_capital"), 10000))
    if "realInitialCash" in updates:
        out["live_capital"] = number(updates["realInitialCash"], number(current.get("live_capital"), 5000))
    if isinstance(updates.get("thsReconciliation"), dict):
        reconciliation = updates["thsReconciliation"]
        reconciliation_mode = updates.get("currentMode") or api_mode_from_account_mode(out.get("account_mode"))
        is_real = reconciliation_mode == "real"
        prefix = "live_ths" if is_real else "ths"
        default_capital = number(out.get("live_capital"), 5000) if is_real else 200000
        out[f"{prefix}_reconciliation_enabled"] = bool(reconciliation.get("enabled", False))
        for api_key, suffix, default in (
            ("accountCapital", "account_capital", default_capital),
            ("totalAssets", "total_assets", default_capital),
            ("availableCash", "available_cash", default_capital),
            ("holdingValue", "holding_value", 0 if is_real else 7090),
            ("holdingPnL", "holding_pnl", 0 if is_real else -57.28),
            ("todayPnL", "today_pnl", 0 if is_real else -242.27),
        ):
            if api_key in reconciliation:
                out[f"{prefix}_{suffix}"] = number(reconciliation[api_key], default)

    mode_for_fee = updates.get("currentMode") or api_mode_from_account_mode(out.get("account_mode"))
    fee_prefix = fee_prefix_for_mode(mode_for_fee)
    explicit_profile_update = "feeProfile" in updates or "fee_profile" in updates
    fee_value_update = any(api_key in updates for api_key in FEE_API_ALIASES)
    if explicit_profile_update and not fee_value_update:
        profile = normalize_fee_profile(updates.get("feeProfile", updates.get("fee_profile")), fee_prefix)
        out[f"{fee_prefix}_fee_profile"] = profile
        defaults = fee_defaults_for_profile(profile)
        for internal_key, default in defaults.items():
            out[f"{fee_prefix}_{internal_key}"] = number(updates.get(_api_key_for_fee(internal_key)), default)

    for api_key, internal_key in FEE_API_ALIASES.items():
        if api_key in updates:
            default = FEE_DEFAULTS[internal_key]
            mode_key = f"{fee_prefix}_{internal_key}"
            out[mode_key] = number(updates[api_key], number(current.get(mode_key), default))
    if fee_value_update:
        out[f"{fee_prefix}_fee_profile"] = normalize_fee_profile(
            updates.get("feeProfile", updates.get("fee_profile", FEE_PROFILE_CUSTOM)),
            fee_prefix,
        )

    active_prefix = fee_prefix_for_mode(out.get("account_mode"))
    out["fee_profile"] = normalize_fee_profile(out.get(f"{active_prefix}_fee_profile"), active_prefix)
    for internal_key in FEE_DEFAULTS:
        out[internal_key] = number(
            out.get(f"{active_prefix}_{internal_key}"),
            FEE_DEFAULTS[internal_key],
        )
    return out


def _api_key_for_fee(internal_key: str) -> str:
    for api_key, mapped_key in FEE_API_ALIASES.items():
        if mapped_key == internal_key:
            return api_key
    return internal_key


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
                "accountMode": str(clean_value(row.get("账户模式"), "模拟训练")),
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
                    "inBuyWindow": bool_value(snapshot.get("inBuyWindow")),
                    "marketRisk": bool_value(snapshot.get("marketRisk")),
                    "marketRiskSource": str(snapshot.get("marketRiskSource") or ""),
                    "marketRiskReasons": parse_tags(snapshot.get("marketRiskReasons")),
                    "marketSnapshot": snapshot.get("marketSnapshot") or {},
                    "sectorSnapshot": snapshot.get("sectorSnapshot") or {},
                    "stopPrice": number(snapshot.get("stopPrice")),
                    "riskAmount": number(snapshot.get("riskAmount")),
                    "maxRiskAmount": number(snapshot.get("maxRiskAmount")),
                    "riskPct": number(snapshot.get("riskPct")),
                    "riskLimitPct": number(snapshot.get("riskLimitPct")),
                    "buyWindow": str(snapshot.get("buyWindow") or ""),
                    "candidateCycleId": str(snapshot.get("candidateCycleId") or ""),
                    "selectionBatchId": str(snapshot.get("selectionBatchId") or ""),
                    "selectionDate": str(snapshot.get("selectionDate") or ""),
                    "eligibleFrom": str(snapshot.get("eligibleFrom") or ""),
                    "ma5Live": number(snapshot.get("ma5Live")),
                    "quoteAgeSeconds": number(snapshot.get("quoteAgeSeconds")),
                    "signalQualified": bool_value(snapshot.get("signalQualified")),
                    "executionAllowed": bool_value(snapshot.get("executionAllowed")),
                    "executionBlockReasons": parse_tags(snapshot.get("executionBlockReasons")),
                    "manualConfirmationRequired": bool_value(snapshot.get("manualConfirmationRequired", True)),
                    "historicalBackfill": bool_value(snapshot.get("historicalBackfill")),
                    "positionBeforeTrade": snapshot.get("positionBeforeTrade") or {},
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
            out[column] = False if column in {"MA5向上", "放量跌破MA5", "is_pool_locked", "is_pinned"} else pd.NA
    return out[WATCHLIST_COLUMNS]
