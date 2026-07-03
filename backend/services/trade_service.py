from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import pandas as pd

from src.data import (
    filter_trades_by_account_mode,
    load_trades,
    load_watchlist,
    save_trades,
    trade_account_mode_name,
)
from src.portfolio import calculate_trade_fees
from src.realtime import china_now, is_a_share_trading_time
from src.rules import clean_code, screening_result
from src.trading_rules_config import (
    BIG_CANDLE_THRESHOLD_PCT,
    BUY_ZONE_MAX_DEVIATION_PCT,
    BUY_ZONE_MIN_DEVIATION_PCT,
    LOT_SIZE,
    MAX_SINGLE_TRADE_RISK_PCT,
    OBSERVE_ZONE_MAX_DEVIATION_PCT,
    TAKE_PROFIT_PRIORITY_DEVIATION_PCT,
    TAKE_PROFIT_WATCH_DEVIATION_PCT,
    estimate_single_trade_risk,
    is_allowed_buy_window,
)

from backend.services.portfolio_service import portfolio_snapshot
from backend.services.risk_service import market_trade_filter
from backend.services.settings_service import account_mode_name, initial_cash, trade_fee_settings
from backend.storage import sqlite_store
from backend.storage.csv_adapter import (
    api_trade_id,
    api_trades_for_sqlite,
    ensure_trade_frame,
    number,
    parse_tags,
    trade_index_from_id,
    trades_to_api,
    watchlist_to_api,
)


def list_trades(mode: str | None = None) -> dict[str, Any]:
    frame = filter_trades_by_account_mode(load_trades(), account_mode_name(mode))
    api_trades = trades_to_api(frame)
    sqlite_store.replace_trades(mode or "default", api_trades_for_sqlite(api_trades))
    return {"list": api_trades}


def _mode_row_indices(frame: pd.DataFrame, mode: str | None) -> list[int]:
    mode_name = account_mode_name(mode)
    normalized = ensure_trade_frame(frame)
    return [
        int(index)
        for index, value in normalized["账户模式"].items()
        if trade_account_mode_name(value) == mode_name
    ]


def _source_index_for_trade_id(frame: pd.DataFrame, trade_id: str, mode: str | None) -> int:
    index = trade_index_from_id(trade_id)
    if index is None:
        raise ValueError("交易流水ID无效")
    mode_indices = _mode_row_indices(frame, mode)
    if index < 0 or index >= len(mode_indices):
        raise ValueError("未找到该笔交易记录")
    return mode_indices[index]


def _current_stock(code: str) -> dict[str, Any] | None:
    watchlist = load_watchlist()
    if watchlist.empty:
        return None
    matches = watchlist[watchlist["代码"].astype(str).map(clean_code) == clean_code(code)]
    if matches.empty:
        return None
    return watchlist_to_api(matches.iloc[[0]])[0]


def _audit_buy(
    stock: dict[str, Any] | None,
    code: str,
    name: str,
    price: float,
    quantity: float,
    available_cash: float,
    account_initial_cash: float,
    estimated_sell_fee: float,
    now: datetime,
    market_risk: bool = False,
    market_risk_reasons: list[str] | None = None,
) -> tuple[str, list[str], dict[str, Any]]:
    tags: list[str] = []
    passed, reason = screening_result(code, name)
    if not passed:
        tags.append(reason)
    if not is_allowed_buy_window(now):
        tags.append("不在允许买入时间窗口")
    if market_risk:
        reason_text = "、".join(market_risk_reasons or []) or "大盘或板块弱"
        tags.append(f"{reason_text}，不允许开新仓")
    risk_context: dict[str, Any] = {
        "stopPrice": 0,
        "riskAmount": 0,
        "maxRiskAmount": round(account_initial_cash * MAX_SINGLE_TRADE_RISK_PCT, 2),
        "riskPct": 0,
    }
    if stock is None:
        tags.append("不在股票池")
    else:
        if stock.get("historyStatus") != "已有缓存" and number(stock.get("ma5")) <= 0:
            tags.append("缺少有效历史K线")
        if stock.get("stage") != "待买观察":
            tags.append("不在待买观察")
        elif not stock.get("canBuy"):
            tags.append("待买硬约束未通过")
        if not stock.get("ma5Upward"):
            tags.append("MA5未向上")
        if number(stock.get("bigCandlePct")) < BIG_CANDLE_THRESHOLD_PCT:
            tags.append("无5%大阳线")
        deviation = number(stock.get("deviation5"))
        if deviation < BUY_ZONE_MIN_DEVIATION_PCT:
            tags.append("跌破MA5买入")
        elif deviation > BUY_ZONE_MAX_DEVIATION_PCT:
            tags.append("偏离MA5超过2.5%")
        risk_info = estimate_single_trade_risk(price, quantity, stock.get("ma5"), estimated_sell_fee)
        risk_amount = number(risk_info.get("risk_amount"))
        max_risk = account_initial_cash * MAX_SINGLE_TRADE_RISK_PCT
        risk_context = {
            "stopPrice": number(risk_info.get("stop_price")),
            "riskAmount": round(risk_amount, 2),
            "maxRiskAmount": round(max_risk, 2),
            "riskPct": round(risk_amount / account_initial_cash * 100, 2) if account_initial_cash else 0,
        }
        if risk_amount <= 0:
            tags.append("无法计算单笔风险")
        elif risk_amount > max_risk:
            tags.append("单笔风险超过本金2%")
    if available_cash < price * LOT_SIZE:
        tags.append("现金不足一手")
    if not tags:
        return "符合规则", [], risk_context
    if len(tags) <= 2:
        return "部分不符", tags, risk_context
    return "违规交易", tags, risk_context


def _audit_sell(position: dict[str, Any] | None, quantity: float, reason: str, account_initial_cash: float) -> tuple[str, list[str]]:
    tags: list[str] = []
    if not position:
        return "违规交易", ["无持仓卖出"]

    owned = number(position.get("quantity"))
    available = number(position.get("availableQuantity"))
    current_price = number(position.get("currentPrice"))
    avg_cost = number(position.get("avgCost"))
    ma5 = number(position.get("ma5"))
    deviation = number(position.get("deviation5"))
    below_days = int(number(position.get("belowMa5Days")))
    hold_days = int(number(position.get("holdDays")))
    reason_text = str(reason or "")

    if quantity > owned:
        tags.append("卖出数量超过持仓")
    if quantity > available:
        tags.append("T+1可卖数量不足")

    hit_ma5_risk = ma5 > 0 and deviation < 0
    hit_clear = below_days >= 3
    hit_take_profit_watch = ma5 > 0 and deviation >= TAKE_PROFIT_WATCH_DEVIATION_PCT
    hit_take_profit_priority = ma5 > 0 and deviation > TAKE_PROFIT_PRIORITY_DEVIATION_PCT
    current_loss_amount = max(0.0, (avg_cost - current_price) * owned)
    hit_max_loss = account_initial_cash > 0 and current_loss_amount >= account_initial_cash * MAX_SINGLE_TRADE_RISK_PCT
    hit_next_day = hold_days <= 1 and any(key in reason_text for key in ["次日", "10点", "10:00", "不强", "冲高", "退出"])

    allowed_trigger = (
        hit_ma5_risk
        or hit_clear
        or hit_take_profit_watch
        or hit_take_profit_priority
        or hit_max_loss
        or hit_next_day
    )

    if ma5 <= 0 and not hit_max_loss:
        tags.append("缺少MA5卖出依据")
    if not allowed_trigger:
        tags.append("未触发卖出纪律")

    if not tags:
        return "符合规则", []
    if len(tags) <= 2 and "卖出数量超过持仓" not in tags and "T+1可卖数量不足" not in tags:
        return "部分不符", tags
    return "违规交易", tags


def _position_snapshot(position: dict[str, Any] | None) -> dict[str, Any]:
    if not position:
        return {}
    return {
        "quantity": number(position.get("quantity")),
        "availableQuantity": number(position.get("availableQuantity")),
        "avgCost": number(position.get("avgCost")),
        "currentPrice": number(position.get("currentPrice")),
        "ma5": number(position.get("ma5")),
        "deviation5": number(position.get("deviation5")),
        "holdDays": int(number(position.get("holdDays"))),
        "belowMa5Days": int(number(position.get("belowMa5Days"))),
        "advice": str(position.get("advice") or ""),
        "riskLevel": str(position.get("riskLevel") or "normal"),
    }


def _sync_after_trade(mode: str | None = None) -> None:
    portfolio_snapshot(mode, sync_legacy=True)
    list_trades(mode)


def create_trade(payload: dict[str, Any], mode: str | None = None) -> dict[str, Any]:
    code = clean_code(payload.get("code"))
    name = str(payload.get("name") or "")
    side_raw = str(payload.get("type") or payload.get("side") or "BUY").upper()
    side = "卖出" if side_raw in {"SELL", "卖出"} else "买入"
    price = number(payload.get("price"))
    quantity = number(payload.get("quantity"))
    if not code or not name or price <= 0 or quantity <= 0:
        raise ValueError("交易参数不完整")

    active_mode = mode or payload.get("mode")
    portfolio = portfolio_snapshot(active_mode, persist_risk_state=True)
    account_state = portfolio["accountState"]
    positions = {item["code"]: item for item in portfolio["positions"]}
    fees = calculate_trade_fees(side, price, quantity, trade_fee_settings(active_mode))
    total_cost = fees["amount"] + fees["total_fee"]
    if side == "买入" and number(account_state.get("availableCash")) < total_cost:
        raise ValueError(f"可用资金不足，需要 {total_cost:.2f} 元")
    position = positions.get(code)
    if side == "卖出":
        owned = number((position or {}).get("quantity"))
        available = number((position or {}).get("availableQuantity"))
        if owned < quantity:
            raise ValueError(f"持仓不足，当前仅持有 {owned:.0f} 股")
        if available < quantity:
            raise ValueError(f"T+1可卖数量不足，当前可卖 {available:.0f} 股")

    now = china_now()
    trade_date = str(payload.get("date") or now.date().isoformat())
    trade_time = str(payload.get("time") or now.strftime("%H:%M:%S"))
    stock = _current_stock(code)
    market_filter = market_trade_filter(code)
    manual_market_risk = bool(payload.get("systemicRisk") or payload.get("marketRisk"))
    market_risk = manual_market_risk or bool(market_filter.get("marketRisk"))
    market_reasons = list(market_filter.get("reasons") or [])
    if manual_market_risk and not market_reasons:
        market_reasons = ["手动确认系统性风险"]
    account_initial_cash = initial_cash(active_mode)
    estimated_sell_fee = calculate_trade_fees("卖出", price, quantity, trade_fee_settings(active_mode))["total_fee"]
    buy_risk_context: dict[str, Any] = {}
    snapshot = {
        "group": (stock or {}).get("group", "初筛"),
        "stage": (stock or {}).get("stage", "初筛通过"),
        "ma5": number((stock or {}).get("ma5")),
        "deviation5": number((stock or {}).get("deviation5")),
        "bigCandlePct": number((stock or {}).get("bigCandlePct")),
        "ma5Upward": bool((stock or {}).get("ma5Upward")),
        "cashSufficient": number(account_state.get("availableCash")) >= price * LOT_SIZE,
        "inTradingTime": is_a_share_trading_time(now),
        "inBuyWindow": is_allowed_buy_window(now),
        "marketRisk": market_risk,
        "marketRiskSource": "manual+auto" if manual_market_risk and market_filter.get("marketRisk") else "manual" if manual_market_risk else "auto",
        "marketRiskReasons": market_reasons,
        "marketSnapshot": market_filter.get("marketSnapshot", {}),
        "sectorSnapshot": market_filter.get("sectorSnapshot", {}),
        "buyWindow": "09:35-10:00 / 14:30-14:55",
        "riskLimitPct": MAX_SINGLE_TRADE_RISK_PCT * 100,
        "positionBeforeTrade": _position_snapshot(position),
    }
    if side == "买入":
        conclusion, tags, buy_risk_context = _audit_buy(
            stock,
            code,
            name,
            price,
            quantity,
            number(account_state.get("availableCash")),
            account_initial_cash,
            estimated_sell_fee,
            now,
            market_risk=market_risk,
            market_risk_reasons=market_reasons,
        )
        snapshot.update(buy_risk_context)
    else:
        conclusion, tags = _audit_sell(position, quantity, str(payload.get("reason") or ""), account_initial_cash)

    frame = ensure_trade_frame(load_trades())
    new_row = {
        "账户模式": account_mode_name(active_mode),
        "代码": code,
        "名称": name,
        "类型": side,
        "日期": trade_date,
        "时间": trade_time,
        "价格": price,
        "数量": quantity,
        "金额": fees["amount"],
        "手续费": fees["commission"],
        "印花税": fees["stamp_tax"],
        "过户费": fees["transfer_fee"],
        "总费用": fees["total_fee"],
        "原因": str(payload.get("reason") or ""),
        "备注": str(payload.get("remark") or ""),
        "规则快照": json.dumps(snapshot, ensure_ascii=False),
        "规则结论": conclusion,
        "违规标签": json.dumps(tags, ensure_ascii=False),
    }
    updated = pd.concat([frame, pd.DataFrame([new_row])], ignore_index=True)
    save_trades(updated)
    _sync_after_trade(active_mode)
    trade = trades_to_api(updated.iloc[[-1]])[0]
    trade["id"] = api_trade_id(len(updated) - 1)
    return {"success": True, "trade": trade}


def delete_trade(trade_id: str, mode: str | None = None) -> dict[str, Any]:
    active_mode = mode
    index = trade_index_from_id(trade_id)
    frame = ensure_trade_frame(load_trades()).reset_index(drop=True)
    if str(trade_id or "").upper() == "ALL":
        drop_indices = _mode_row_indices(frame, active_mode)
        updated = frame.drop(index=drop_indices).reset_index(drop=True)
    else:
        if index is None:
            raise ValueError("交易流水ID无效")
        source_index = _source_index_for_trade_id(frame, trade_id, active_mode)
        updated = frame.drop(index=source_index).reset_index(drop=True)
    save_trades(updated)
    _sync_after_trade(active_mode)
    return {"success": True}


def update_trade(trade_id: str, payload: dict[str, Any], mode: str | None = None) -> dict[str, Any]:
    active_mode = mode
    frame = ensure_trade_frame(load_trades()).reset_index(drop=True)
    index = _source_index_for_trade_id(frame, trade_id, active_mode)

    column_map = {
        "code": "代码",
        "name": "名称",
        "date": "日期",
        "time": "时间",
        "price": "价格",
        "quantity": "数量",
        "reason": "原因",
        "remark": "备注",
        "rulesConclusion": "规则结论",
    }
    for api_key, column in column_map.items():
        if api_key in payload:
            frame.loc[index, column] = payload[api_key]
    if "type" in payload:
        frame.loc[index, "类型"] = "卖出" if str(payload["type"]).upper() in {"SELL", "卖出"} else "买入"
    if "commission" in payload:
        frame.loc[index, "手续费"] = number(payload["commission"])
    if "stampDuty" in payload:
        frame.loc[index, "印花税"] = number(payload["stampDuty"])
    if "transferFee" in payload:
        frame.loc[index, "过户费"] = number(payload["transferFee"])
    if "violationTags" in payload:
        frame.loc[index, "违规标签"] = json.dumps(parse_tags(payload["violationTags"]), ensure_ascii=False)

    price = number(frame.loc[index, "价格"])
    quantity = number(frame.loc[index, "数量"])
    frame.loc[index, "金额"] = round(price * quantity, 2)
    if "totalFee" in payload:
        frame.loc[index, "总费用"] = number(payload["totalFee"])
    else:
        frame.loc[index, "总费用"] = (
            number(frame.loc[index, "手续费"])
            + number(frame.loc[index, "印花税"])
            + number(frame.loc[index, "过户费"])
        )
    save_trades(frame)
    _sync_after_trade(active_mode)
    mode_frame = filter_trades_by_account_mode(frame, account_mode_name(active_mode))
    mode_indices = _mode_row_indices(frame, active_mode)
    mode_index = mode_indices.index(index)
    trade = trades_to_api(mode_frame.iloc[[mode_index]])[0]
    trade["id"] = api_trade_id(mode_index)
    return {"success": True, "trade": trade}
