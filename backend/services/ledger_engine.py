from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, time
from math import isfinite
from typing import Any
from uuid import uuid4

from backend.storage import account_store as store


def _round(value: float, digits: int = 2) -> float:
    return round(float(value or 0), digits)


def _today() -> str:
    return date.today().isoformat()


def _now_hm() -> str:
    return datetime.now().strftime("%H:%M")


def _parse_date(text: str) -> date:
    return date.fromisoformat(text)


def _trading_days(start: str, end: str) -> int:
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if end_date < start_date:
        return 0
    count = 0
    cursor = start_date
    while cursor <= end_date:
        if cursor.weekday() < 5:
            count += 1
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return max(count, 1)


def calculate_fees(side: str, price: float, quantity: int, settings: dict[str, Any]) -> dict[str, float]:
    principal = max(0.0, float(price) * int(quantity))
    commission = principal * float(settings.get("commissionRate", 0))
    if settings.get("enableMinCommission", True) and principal > 0:
        commission = max(commission, float(settings.get("minCommission", 0)))
    stamp_duty = principal * float(settings.get("stampDutyRate", 0)) if side == "SELL" else 0.0
    transfer_fee = principal * float(settings.get("transferFeeRate", 0))
    return {
        "commission": _round(commission),
        "stampDuty": _round(stamp_duty),
        "transferFee": _round(transfer_fee),
        "totalFee": _round(commission + stamp_duty + transfer_fee),
    }


def _minutes(text: str) -> int:
    try:
        hour, minute = map(int, text[:5].split(":"))
        return hour * 60 + minute
    except (ValueError, AttributeError):
        return -1


def _buy_audit(price: float, quantity: int, trade_time: str, available_cash: float, fees: dict[str, float]) -> tuple[str, list[str]]:
    tags: list[str] = []
    if quantity <= 0 or quantity % 100 != 0:
        tags.append("非100股整数倍")
    if price <= 0:
        tags.append("成交价格无效")
    if price * quantity + fees["totalFee"] > available_cash + 1e-8:
        tags.append("可用资金不足")
    minute = _minutes(trade_time)
    in_window = (9 * 60 + 30 <= minute < 10 * 60) or (14 * 60 + 30 <= minute < 15 * 60)
    if not in_window:
        tags.append("不在纪律买入时段")
    if not tags:
        return "符合规则", []
    return ("部分不符" if len(tags) == 1 else "违规交易"), tags


@dataclass
class Lot:
    date: str
    quantity: int
    unit_cost: float


def _simulate(mode: str, trades: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[float]]:
    settings = store.get_settings(mode)
    cash = float(settings.get("initialCash", 0))
    realized_pnl = 0.0
    cycle_pnls: list[float] = []
    lots: dict[str, deque[Lot]] = defaultdict(deque)
    names: dict[str, str] = {}
    last_price: dict[str, float] = {}
    code_realized: dict[str, float] = defaultdict(float)

    ordered = sorted(trades, key=lambda item: (item["date"], item["time"], item.get("createdAt", "")))
    for trade in ordered:
        code = trade["code"]
        names[code] = trade["name"]
        last_price[code] = float(trade["price"])
        qty = int(trade["quantity"])
        amount = float(trade["amount"])
        fee = float(trade["totalFee"])
        if trade["type"] == "BUY":
            cash -= amount + fee
            unit_cost = (amount + fee) / qty
            lots[code].append(Lot(trade["date"], qty, unit_cost))
        else:
            cash += amount - fee
            remaining = qty
            cost_basis = 0.0
            while remaining > 0 and lots[code]:
                lot = lots[code][0]
                used = min(remaining, lot.quantity)
                cost_basis += used * lot.unit_cost
                lot.quantity -= used
                remaining -= used
                if lot.quantity == 0:
                    lots[code].popleft()
            pnl = amount - fee - cost_basis
            realized_pnl += pnl
            code_realized[code] += pnl
            cycle_pnls.append(_round(pnl))

    today = _today()
    positions: list[dict[str, Any]] = []
    holding_value = 0.0
    floating_pnl = 0.0
    for code, queue in lots.items():
        quantity = sum(lot.quantity for lot in queue)
        if quantity <= 0:
            continue
        cost_value = sum(lot.quantity * lot.unit_cost for lot in queue)
        avg_cost = cost_value / quantity
        current_price = last_price.get(code, avg_cost)
        market_value = quantity * current_price
        pnl = market_value - cost_value
        available = sum(lot.quantity for lot in queue if lot.date < today)
        locked = quantity - available
        buy_date = min(lot.date for lot in queue)
        state = store.get_position_state(mode, code)
        deferred = bool(state.get("deferred"))
        now = _minutes(_now_hm())
        if locked == quantity:
            status = "T+1 锁定"
            advice = "当日买入不可卖出；下一交易日再进入观察。"
            next_action = "下一交易日 09:30"
        elif deferred and now < 14 * 60 + 30:
            status = "已延迟至尾盘"
            advice = state.get("deferReason") or "等待 14:30 后重新处理。"
            next_action = "14:30"
        elif deferred and now >= 14 * 60 + 30:
            status = "尾盘待处理"
            advice = "已到尾盘处理时段，请根据原计划记录卖出或撤销延迟。"
            next_action = "现在"
        elif now < 10 * 60:
            status = "次日观察"
            advice = "10:00 前观察承接；不符合预案时按纪律退出。"
            next_action = "10:00"
        else:
            status = "10:00 待处理"
            advice = "已到纪律处理节点，请记录卖出或明确延迟至尾盘。"
            next_action = "现在"
        position = {
            "code": code,
            "name": names.get(code, code),
            "quantity": quantity,
            "availableQuantity": available,
            "t1LockedQuantity": locked,
            "avgCost": _round(avg_cost, 4),
            "currentPrice": _round(current_price, 4),
            "marketValue": _round(market_value),
            "floatingPnL": _round(pnl),
            "floatingPnLPct": _round((pnl / cost_value * 100) if cost_value else 0),
            "ma5": _round(current_price, 4),
            "deviation5": 0.0,
            "buyDate": buy_date,
            "holdDays": _trading_days(buy_date, today),
            "status": status,
            "advice": advice,
            "nextActionTime": next_action,
            "canExecuteSellNow": available > 0,
            "sellBlockedReason": "T+1 可卖数量为 0" if available <= 0 else "",
            "isLimitUp": False,
            "quoteUpdatedAt": "",
            "quoteAgeSeconds": None,
            "notes": state.get("notes", []),
        }
        positions.append(position)
        holding_value += market_value
        floating_pnl += pnl

    computed_assets = cash + holding_value
    reconciliation = settings.get("reconciliation", {})
    reconciliation_mode = bool(reconciliation.get("enabled"))
    if reconciliation_mode:
        total_assets = float(reconciliation.get("totalAssets", computed_assets))
        available_cash = float(reconciliation.get("availableCash", cash))
        holding_value = float(reconciliation.get("holdingValue", holding_value))
        floating_pnl = float(reconciliation.get("holdingPnL", floating_pnl))
        today_pnl = float(reconciliation.get("todayPnL", 0))
    else:
        total_assets = computed_assets
        available_cash = cash
        today_pnl = _today_pnl(ordered, today, code_realized)
    initial_cash = float(settings.get("initialCash", 0))
    account = {
        "mode": mode,
        "initialCash": _round(initial_cash),
        "availableCash": _round(available_cash),
        "holdingValue": _round(holding_value),
        "totalAssets": _round(total_assets),
        "realizedPnL": _round(realized_pnl),
        "floatingPnL": _round(floating_pnl),
        "totalPnL": _round(total_assets - initial_cash),
        "totalReturnPct": _round(((total_assets - initial_cash) / initial_cash * 100) if initial_cash else 0),
        "todayPnL": _round(today_pnl),
        "todayRealizedPnL": _round(_today_realized(ordered, today)),
        "asOfDate": today,
        "reconciliationMode": reconciliation_mode,
    }
    return account, sorted(positions, key=lambda item: item["marketValue"], reverse=True), cycle_pnls


def _today_realized(trades: list[dict[str, Any]], today: str) -> float:
    return _round(sum(-float(item["totalFee"]) for item in trades if item["date"] == today))


def _today_pnl(trades: list[dict[str, Any]], today: str, _code_realized: dict[str, float]) -> float:
    # Without a live quote feed, today's posted change is represented by today's fees and closed trade results.
    return _today_realized(trades, today)


