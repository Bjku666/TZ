from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd

from src.data import (
    load_watchlist,
)
from src.portfolio import calculate_trade_fees
from src.realtime import china_now, is_a_share_trading_time
from src.rules import clean_code
from src.trading_rules_config import LOT_SIZE, is_allowed_buy_window
from src.video_original_rules import evaluate_buy_compliance, evaluate_next_day_exit

from backend.services.portfolio_service import portfolio_snapshot
from backend.services.risk_service import market_trade_filter
from backend.services.settings_service import account_mode_name, current_mode, initial_cash, trade_fee_settings
from backend.storage import sqlite_store
from backend.storage.csv_adapter import (
    api_trade_id,
    api_trades_for_sqlite,
    number,
    parse_tags,
    trade_index_from_id,
    trades_to_api,
    watchlist_to_api,
)
from backend.storage import trade_repository


def list_trades(mode: str | None = None) -> dict[str, Any]:
    active_mode = mode or current_mode()
    api_trades = trade_repository.list_api_trades(active_mode, account_mode_name(mode))
    sqlite_store.replace_trades(active_mode, api_trades_for_sqlite(api_trades))
    return {"list": api_trades}


def _source_index_for_trade_id(frame: pd.DataFrame, trade_id: str) -> int:
    index = trade_index_from_id(trade_id)
    if index is None:
        raise ValueError("交易流水ID无效")
    if index < 0 or index >= len(frame):
        raise ValueError("未找到该笔交易记录")
    return index


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
    is_historical: bool = False,
    manual_confirmed: bool = True,
) -> tuple[str, list[str], dict[str, Any]]:
    candidate = sqlite_store.active_candidate_for_code(clean_code(code))
    if candidate is None and stock is not None:
        candidate = {
            "id": stock.get("candidateCycleId") or stock.get("candidateId"),
            "source_batch_id": stock.get("selectionBatchId") or stock.get("poolBatchId"),
            "selection_date": stock.get("selectionDate"),
            "eligible_from": stock.get("eligibleFrom"),
            "above_ma5": True,
        }
    ma5_live = (stock or {}).get("ma5Live", (stock or {}).get("ma5"))
    quote_age = (stock or {}).get("quoteAgeSeconds", 0)
    result = evaluate_buy_compliance(
        candidate=candidate,
        trade_datetime=now,
        trade_price=price,
        quantity=quantity,
        ma5_live=ma5_live,
        quote_age_seconds=quote_age,
        available_cash=available_cash,
        manual_confirmed=manual_confirmed,
        is_historical=is_historical,
    )
    context = {
        "candidateCycleId": (candidate or {}).get("id"),
        "selectionBatchId": (candidate or {}).get("source_batch_id"),
        "selectionDate": (candidate or {}).get("selection_date"),
        "eligibleFrom": (candidate or {}).get("eligible_from"),
        "tradeDateTime": now.isoformat(),
        "tradePrice": price,
        "ma5Live": number(ma5_live),
        "deviation": result.get("deviation"),
        "buyWindow": result.get("buyWindow"),
        "quoteAgeSeconds": quote_age,
        "signalQualified": result.get("signalQualified"),
        "executionAllowed": result.get("executionAllowed"),
        "executionBlockReasons": result.get("executionBlockReasons"),
        "manualConfirmationRequired": True,
        "marketRisk": market_risk,
        "marketRiskReasons": market_risk_reasons or [],
        "marketInfoNote": "市场信息仅供查看，不属于视频原版交易条件",
    }
    return str(result["conclusion"]), list(result["tags"]), context


def _audit_sell(position: dict[str, Any] | None, quantity: float, reason: str, account_initial_cash: float) -> tuple[str, list[str]]:
    tags: list[str] = []
    if not position:
        return "违规交易", ["无持仓卖出"]

    owned = number(position.get("quantity"))
    available = number(position.get("availableQuantity"))

    if quantity > owned:
        tags.append("卖出数量超过持仓")
    if quantity > available:
        tags.append(str(position.get("sellBlockedReason") or "可卖数量不足"))
    exit_state = str(position.get("originalExitState") or position.get("exitState") or "")
    reason_text = str(reason or "")
    if exit_state not in {"MORNING_EXIT_DUE", "AFTERNOON_EXIT_DUE", "LIMIT_UP_OPENED_EXIT_DUE"} and not any(
        key in reason_text for key in ["次日", "10点", "10:00", "尾盘", "涨停打开", "原版"]
    ):
        tags.append("未对应视频原版隔日卖出提醒")

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

    now = china_now()
    trade_date = str(payload.get("date") or now.date().isoformat())
    trade_time = str(payload.get("time") or now.strftime("%H:%M:%S"))
    try:
        trade_dt = datetime.fromisoformat(f"{trade_date}T{trade_time}")
    except ValueError:
        trade_dt = now
    is_historical = bool(payload.get("historicalBackfill")) or trade_dt.date() != now.date()
    active_mode = mode or payload.get("mode")
    portfolio = portfolio_snapshot(active_mode, persist_risk_state=True)
    account_state = portfolio["accountState"]
    positions = {item["code"]: item for item in portfolio["positions"]}
    fees = calculate_trade_fees(side, price, quantity, trade_fee_settings(active_mode))
    total_cost = fees["amount"] + fees["total_fee"]
    if side == "买入" and not is_historical and number(account_state.get("availableCash")) < total_cost:
        raise ValueError(f"可用资金不足，需要 {total_cost:.2f} 元")
    position = positions.get(code)
    if side == "卖出":
        owned = number((position or {}).get("quantity"))
        available = number((position or {}).get("availableQuantity"))
        if owned < quantity:
            raise ValueError(f"持仓不足，当前仅持有 {owned:.0f} 股")
        if available < quantity:
            reason = str((position or {}).get("sellBlockedReason") or f"可卖数量不足，当前可卖 {available:.0f} 股")
            raise ValueError(reason)
        if not bool((position or {}).get("canExecuteSellNow")):
            raise ValueError(str((position or {}).get("sellBlockedReason") or "当前不可执行卖出"))

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
        "buyWindow": "09:30-10:00 / 14:30-15:00",
        "ruleBoundaryNote": "市场、板块和账户资金属于辅助信息或执行约束，不属于视频原版买点条件",
        "historicalBackfill": is_historical,
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
            trade_dt,
            market_risk=market_risk,
            market_risk_reasons=market_reasons,
            is_historical=is_historical,
            manual_confirmed=bool(payload.get("manualConfirmed", True)),
        )
        snapshot.update(buy_risk_context)
    else:
        conclusion, tags = _audit_sell(position, quantity, str(payload.get("reason") or ""), account_initial_cash)

    active_mode_key = active_mode or current_mode()
    active_mode_name = account_mode_name(active_mode)
    trade_id = trade_repository.next_trade_id(active_mode_key, active_mode_name)
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
    trade = trades_to_api(pd.DataFrame([new_row]))[0]
    trade["id"] = trade_id
    trade_repository.append_api_trade(active_mode_key, active_mode_name, trade)
    if side == "买入":
        candidate_id = str(snapshot.get("candidateCycleId") or "")
        if candidate_id:
            sqlite_store.update_candidate_cycle(
                candidate_id,
                {"state": "BOUGHT", "bought_trade_id": trade_id},
            )
            sqlite_store.add_candidate_event(
                candidate_id,
                "BUY_RECORDED",
                event_time=trade_dt.isoformat(),
                trade_date=trade_date,
                price=price,
                ma5=snapshot.get("ma5Live"),
                deviation=snapshot.get("deviation"),
                quote_age_seconds=snapshot.get("quoteAgeSeconds"),
                source="manual_trade_record",
                reason="用户人工确认买入记录",
                payload=snapshot,
            )
    _sync_after_trade(active_mode)
    return {"success": True, "trade": trade}


def delete_trade(trade_id: str, mode: str | None = None) -> dict[str, Any]:
    active_mode = mode or current_mode()
    active_mode_name = account_mode_name(mode)
    if str(trade_id or "").upper() == "ALL":
        trade_repository.delete_all_api_trades(active_mode, active_mode_name)
    else:
        if trade_index_from_id(trade_id) is None:
            raise ValueError("交易流水ID无效")
        trade_repository.delete_api_trade(active_mode, active_mode_name, trade_id)
    _sync_after_trade(mode)
    return {"success": True}


def update_trade(trade_id: str, payload: dict[str, Any], mode: str | None = None) -> dict[str, Any]:
    active_mode = mode or current_mode()
    active_mode_name = account_mode_name(mode)
    frame = trade_repository.load_trade_frame(active_mode, active_mode_name).reset_index(drop=True)
    index = _source_index_for_trade_id(frame, trade_id)

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
    if "violationTags" in payload:
        frame.loc[index, "违规标签"] = json.dumps(parse_tags(payload["violationTags"]), ensure_ascii=False)

    price = number(frame.loc[index, "价格"])
    quantity = number(frame.loc[index, "数量"])
    manual_fee_override = bool(payload.get("manualFeeOverride"))
    if manual_fee_override:
        if "commission" in payload:
            frame.loc[index, "手续费"] = number(payload["commission"])
        if "stampDuty" in payload:
            frame.loc[index, "印花税"] = number(payload["stampDuty"])
        if "transferFee" in payload:
            frame.loc[index, "过户费"] = number(payload["transferFee"])
        frame.loc[index, "金额"] = round(price * quantity, 2)
        frame.loc[index, "总费用"] = (
            number(payload.get("totalFee"))
            if "totalFee" in payload
            else number(frame.loc[index, "手续费"])
            + number(frame.loc[index, "印花税"])
            + number(frame.loc[index, "过户费"])
        )
    else:
        fees = calculate_trade_fees(frame.loc[index, "类型"], price, quantity, trade_fee_settings(active_mode))
        frame.loc[index, "金额"] = fees["amount"]
        frame.loc[index, "手续费"] = fees["commission"]
        frame.loc[index, "印花税"] = fees["stamp_tax"]
        frame.loc[index, "过户费"] = fees["transfer_fee"]
        frame.loc[index, "总费用"] = fees["total_fee"]
    api_trades = trades_to_api(frame)
    for item_index, item in enumerate(api_trades):
        item["id"] = api_trade_id(item_index)
    trade_repository.save_api_trades(active_mode, active_mode_name, api_trades)
    _sync_after_trade(mode)
    trade = api_trades[index]
    return {"success": True, "trade": trade}


def recalculate_trade_fees(mode: str | None = None) -> dict[str, Any]:
    active_mode = mode or current_mode()
    active_mode_name = account_mode_name(active_mode)
    api_trades = trade_repository.recalculate_api_trade_fees(
        active_mode,
        active_mode_name,
        trade_fee_settings(active_mode),
    )
    portfolio = portfolio_snapshot(active_mode, sync_legacy=True)
    sqlite_store.replace_trades(active_mode, api_trades_for_sqlite(api_trades))
    return {
        "success": True,
        "updatedCount": len(api_trades),
        "trades": api_trades,
        "accountState": portfolio["accountState"],
    }
