from __future__ import annotations

from datetime import datetime, time, timedelta
from math import isfinite
from typing import Any
from uuid import uuid4

from backend.services import quote_service
from backend.services.ledger_engine import _now_hm, _round, _simulate, _today, calculate_fees
from backend.services.strategy_rules import MODE3_STRATEGY_ID, audit_buy, audit_sell, get_strategy, list_strategies, validate_strategy
from backend.storage import account_store as store


def _money_sum(trades: list[dict[str, Any]], side: str) -> float:
    return _round(sum(float(item["amount"]) for item in trades if item["type"] == side))


def _minutes(text: str) -> int:
    try:
        hour, minute = map(int, str(text)[:5].split(":"))
        return hour * 60 + minute
    except (ValueError, AttributeError):
        return -1


def _pending_actions(mode: str, strategy_id: str, positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for position in positions:
        action_type = str(position.get("actionType") or position["status"])
        priority = str(position.get("actionPriority") or "warning")
        title = str(position.get("actionTitle") or position["status"])
        actions.append({
            "id": f"{mode}:{strategy_id}:{position['code']}:{action_type}",
            "accountMode": mode,
            "strategyId": strategy_id,
            "code": position["code"],
            "name": position["name"],
            "type": action_type,
            "priority": priority,
            "title": title,
            "message": position["advice"],
            "nextActionTime": position.get("nextActionTime"),
            "position": position,
        })
    if strategy_id == MODE3_STRATEGY_ID and not positions:
        action = _mode3_selection_action(mode, strategy_id)
        if action:
            actions.append(action)
    return actions


def _mode3_selection_action(mode: str, strategy_id: str) -> dict[str, Any] | None:
    now_minutes = _minutes(_now_hm())
    schedule = [
        (10 * 60, "10:00", "第一次筛选", "人工在同花顺完成第一次筛选：前期明显放量、上升趋势、缩量阴线回踩十日线。"),
        (11 * 60, "11:00", "第二次筛选", "人工在同花顺复核候选，不在 TZ 内自动扫描股票。"),
        (13 * 60 + 30, "13:30", "第三次筛选", "继续核对缩量回踩和十日线支撑，剔除趋势已破坏标的。"),
        (14 * 60 + 30, "14:30", "形成最终候选", "形成尾盘候选清单，只保留接近十日线且非第一根回调阴线的标的。"),
        (14 * 60 + 50, "14:50", "执行尾盘买入", "14:50-15:00 是本模式唯一买入登记窗口，执行分仓买入。"),
    ]
    if now_minutes >= 15 * 60:
        return {
            "id": f"{mode}:{strategy_id}:selection:closed",
            "accountMode": mode,
            "strategyId": strategy_id,
            "code": "MODE3",
            "name": "十日线缩量回踩",
            "type": "SELECTION_CLOSED",
            "priority": "normal",
            "title": "停止新增买入",
            "message": "15:00 以后停止新增买入，只做记录、复盘和次日计划准备。",
            "nextActionTime": "下一交易日 10:00",
        }
    next_item = next(((minute, time_text, title, message) for minute, time_text, title, message in schedule if now_minutes < minute), None)
    if not next_item:
        return {
            "id": f"{mode}:{strategy_id}:selection:entry-window",
            "accountMode": mode,
            "strategyId": strategy_id,
            "code": "MODE3",
            "name": "十日线缩量回踩",
            "type": "MODE3_ENTRY_WINDOW",
            "priority": "warning",
            "title": "执行尾盘买入",
            "message": "当前处于 14:50-15:00 买入窗口；只登记已人工确认的缩量阴线十日线回踩，并完成分仓。",
            "nextActionTime": "15:00",
        }
    _minute, time_text, title, message = next_item
    return {
        "id": f"{mode}:{strategy_id}:selection:{time_text}",
        "accountMode": mode,
        "strategyId": strategy_id,
        "code": "MODE3",
        "name": "十日线缩量回踩",
        "type": "MODE3_SELECTION_REMINDER",
        "priority": "normal",
        "title": title,
        "message": message,
        "nextActionTime": time_text,
    }


def _review_summary(mode: str, strategy_id: str, trades: list[dict[str, Any]], account: dict[str, Any], cycle_pnls: list[float]) -> dict[str, Any]:
    wins = [value for value in cycle_pnls if value > 0]
    losses = [value for value in cycle_pnls if value < 0]
    violations = sum(1 for item in trades if item.get("rulesConclusion") != "符合规则")
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    dates = [item["date"] for item in trades]
    summary = {
        "mode": mode,
        "strategyId": strategy_id,
        "startDate": min(dates) if dates else _today(),
        "endDate": max(dates) if dates else _today(),
        "tradeCount": len(trades),
        "completedCycles": len(cycle_pnls),
        "winRate": _round(len(wins) / len(cycle_pnls) * 100 if cycle_pnls else 0),
        "averageWin": _round(avg_win),
        "averageLoss": _round(avg_loss),
        "profitLossRatio": _round(avg_win / avg_loss if avg_loss else 0),
        "totalPnL": account["totalPnL"],
        "totalReturnPct": account["totalReturnPct"],
        "maxSingleWin": _round(max(wins) if wins else 0),
        "maxSingleLoss": _round(min(losses) if losses else 0),
        "totalFees": _round(sum(float(item["totalFee"]) for item in trades)),
        "complianceRate": _round((len(trades) - violations) / len(trades) * 100 if trades else 100),
        "violationCount": violations,
    }
    if strategy_id == MODE3_STRATEGY_ID:
        summary.update(_mode3_review_metrics(trades))
    return summary


def _mode3_review_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(trades)
    sells = [item for item in trades if item["type"] == "SELL"]
    buy_dates_by_code: dict[str, list[str]] = {}
    for trade in sorted(trades, key=lambda item: (item["date"], item["time"], item.get("createdAt", ""))):
        if trade["type"] == "BUY":
            buy_dates_by_code.setdefault(trade["code"], []).append(trade["date"])
    next_day_exits = 0
    before_10_exits = 0
    target_hits = 0
    holding_days: list[int] = []
    overdue = 0
    for sell in sells:
        buy_date = buy_dates_by_code.get(sell["code"], [sell["date"]])[0]
        hold_days = _trading_days_for_summary(buy_date, sell["date"])
        holding_days.append(hold_days)
        if hold_days <= 2:
            next_day_exits += 1
        else:
            overdue += 1
        if _minutes(str(sell.get("time", ""))) < 10 * 60:
            before_10_exits += 1
        snapshot = sell.get("strategySnapshot") or {}
        if isinstance(snapshot, dict) and (snapshot.get("exitReason") == "TARGET_PROFIT" or float(snapshot.get("maxProfitPct") or 0) >= 2):
            target_hits += 1
    return {
        "mode3TradeCount": total,
        "nextDayExitRate": _round(next_day_exits / len(sells) * 100 if sells else 0),
        "exitBefore10Rate": _round(before_10_exits / len(sells) * 100 if sells else 0),
        "targetProfitRate": _round(target_hits / len(sells) * 100 if sells else 0),
        "averageHoldingTradingDays": _round(sum(holding_days) / len(holding_days) if holding_days else 0),
        "overduePositionCount": overdue,
    }


def _trading_days_for_summary(start: str, end: str) -> int:
    try:
        start_date = datetime.fromisoformat(start[:10]).date()
        end_date = datetime.fromisoformat(end[:10]).date()
    except ValueError:
        return 0
    if end_date < start_date:
        return 0
    count = 0
    cursor = start_date
    while cursor <= end_date:
        if cursor.weekday() < 5:
            count += 1
        cursor += timedelta(days=1)
    return count


def _capital_analysis(mode: str, strategy_id: str, trades: list[dict[str, Any]], account: dict[str, Any], positions: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(trades, key=lambda item: (item["date"], item["time"], item.get("createdAt", "")))
    dates = sorted({item["date"] for item in ordered})
    daily: list[dict[str, Any]] = []
    for item_date in dates:
        prefix = [item for item in ordered if item["date"] <= item_date]
        snapshot, _, _ = _simulate(mode, prefix, strategy_id)
        day_trades = [item for item in ordered if item["date"] == item_date]
        daily.append({
            "date": item_date,
            "totalAssets": snapshot["totalAssets"],
            "availableCash": snapshot["availableCash"],
            "holdingValue": snapshot["holdingValue"],
            "realizedPnL": snapshot["realizedPnL"],
            "floatingPnL": snapshot["floatingPnL"],
            "totalPnL": snapshot["totalPnL"],
            "tradeCount": len(day_trades),
            "buyAmount": _money_sum(day_trades, "BUY"),
            "sellAmount": _money_sum(day_trades, "SELL"),
            "fees": _round(sum(float(item["totalFee"]) for item in day_trades)),
        })
    total_assets = float(account["totalAssets"])
    holding_value = float(account["holdingValue"])
    initial_cash = float(account["initialCash"])
    total_fees = _round(sum(float(item["totalFee"]) for item in ordered))
    return {
        "initialCash": account["initialCash"],
        "currentCash": account["availableCash"],
        "holdingValue": account["holdingValue"],
        "totalAssets": account["totalAssets"],
        "cashChange": _round(float(account["availableCash"]) - initial_cash),
        "assetChange": account["totalPnL"],
        "assetChangePct": account["totalReturnPct"],
        "realizedPnL": account["realizedPnL"],
        "floatingPnL": account["floatingPnL"],
        "totalFees": total_fees,
        "netBuyAmount": _round(_money_sum(ordered, "BUY") - _money_sum(ordered, "SELL")),
        "capitalDeploymentPct": _round(holding_value / total_assets * 100 if total_assets else 0),
        "cashRatioPct": _round(float(account["availableCash"]) / total_assets * 100 if total_assets else 0),
        "positionCount": len(positions),
        "daily": daily[-90:],
    }


DEFAULT_MARKET_SETTINGS: dict[str, Any] = {
    "source": "默认离线；开启实时行情后用于持仓监控和股票名称补全",
    "enableRealtime": False,
    "provider": "sina",
    "autoRefresh": False,
    "refreshInterval": 60,
    "refreshOutsideTradingHours": False,
    "expiryThreshold": 0,
    "timeoutSeconds": 3,
    "showExceptionAlert": True,
    "manualQuotes": {},
}

VALID_RULES_CONCLUSIONS = {"符合规则", "部分不符", "违规交易", "无法判断"}


def _non_negative_fee(value: Any, label: str) -> float:
    number = float(value or 0)
    if not isfinite(number) or number < 0:
        raise ValueError(f"{label}不能为负数")
    return _round(number)


def _fees_from_payload(payload: dict[str, Any], fallback: dict[str, float]) -> dict[str, float]:
    if not bool(payload.get("manualFeeOverride", False)):
        return fallback
    commission = _non_negative_fee(payload.get("commission", fallback.get("commission", 0)), "佣金")
    stamp_duty = _non_negative_fee(payload.get("stampDuty", fallback.get("stampDuty", 0)), "印花税")
    transfer_fee = _non_negative_fee(payload.get("transferFee", fallback.get("transferFee", 0)), "过户费")
    return {
        "commission": commission,
        "stampDuty": stamp_duty,
        "transferFee": transfer_fee,
        "totalFee": _round(commission + stamp_duty + transfer_fee),
    }


def _parse_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "")
    for delimiter in ("，", "、", "\n", ";", "；"):
        text = text.replace(delimiter, ",")
    return [item.strip() for item in text.split(",") if item.strip()]


def _historical_audit(payload: dict[str, Any]) -> tuple[str, list[str]]:
    conclusion = str(payload.get("rulesConclusion") or "无法判断").strip()
    if conclusion not in VALID_RULES_CONCLUSIONS:
        raise ValueError("审计评级必须是符合规则、部分不符、违规交易或无法判断")
    tags = _parse_tags(payload.get("violationTags"))
    if not tags and conclusion != "符合规则":
        tags = ["历史补录"]
    return conclusion, tags


def app_settings() -> dict[str, Any]:
    simulation = store.get_settings("simulation")
    real = store.get_settings("real")
    market = {**DEFAULT_MARKET_SETTINGS, **simulation.get("market", real.get("market", {}))}
    return {
        "simulation": {key: value for key, value in simulation.items() if key not in {"reconciliation", "market"}},
        "real": {key: value for key, value in real.items() if key not in {"reconciliation", "market"}},
        "reconciliation": {
            "simulation": simulation.get("reconciliation", {}),
            "real": real.get("reconciliation", {}),
        },
        "market": market,
    }


def workspace(mode: str, strategy_id: str | None = None) -> dict[str, Any]:
    mode = store.validate_mode(mode)
    strategy_id = validate_strategy(strategy_id)
    trades = store.list_trades(mode, strategy_id)
    account_trades = store.list_account_trades(mode)
    strategy_account, positions, cycle_pnls = _simulate(mode, trades, strategy_id)
    account, account_positions, _account_cycle_pnls = _simulate(mode, account_trades, strategy_id)
    settings = app_settings()
    quote_codes = sorted({item["code"] for item in [*positions, *account_positions]})
    quotes, quote_status = quote_service.get_quotes(quote_codes, settings["market"])
    strategy_account, positions = _apply_quotes(strategy_account, positions, quotes)
    account, account_positions = _apply_quotes(account, account_positions, quotes)
    review_summary = _review_summary(mode, strategy_id, trades, strategy_account, cycle_pnls)
    return {
        "mode": mode,
        "strategyId": strategy_id,
        "strategy": get_strategy(strategy_id),
        "strategies": list_strategies(),
        "account": account,
        "strategyAccount": strategy_account,
        "accountPositions": account_positions,
        "positions": positions,
        "trades": trades,
        "pendingActions": _pending_actions(mode, strategy_id, positions),
        "reviewSummary": review_summary,
        "capitalAnalysis": _capital_analysis(mode, strategy_id, account_trades, account, account_positions),
        "strategyCapitalAnalysis": _capital_analysis(mode, strategy_id, trades, strategy_account, positions),
        "reviews": store.list_reviews(mode, strategy_id),
        "notifications": store.list_notifications(mode, strategy_id),
        "settings": settings,
        "marketPhase": _market_phase(),
        "quoteUpdatedAt": quote_status,
    }


def _apply_quotes(account: dict[str, Any], positions: list[dict[str, Any]], quotes: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not quotes:
        return account, positions

    updated_positions: list[dict[str, Any]] = []
    holding_value = 0.0
    floating_pnl = 0.0
    for position in positions:
        quote = quotes.get(position["code"])
        if not quote:
            updated_positions.append(position)
            holding_value += float(position["marketValue"])
            floating_pnl += float(position["floatingPnL"])
            continue

        quantity = int(position["quantity"])
        current_price = float(quote["price"])
        cost_value = float(position["avgCost"]) * quantity
        market_value = current_price * quantity
        pnl = market_value - cost_value
        previous_close = float(quote.get("previousClose") or 0)
        updated = {
            **position,
            "name": quote.get("name") or position["name"],
            "currentPrice": _round(current_price, 4),
            "marketValue": _round(market_value),
            "floatingPnL": _round(pnl),
            "floatingPnLPct": _round((pnl / cost_value * 100) if cost_value else 0),
            "quoteUpdatedAt": quote.get("updatedAt", ""),
            "quoteSource": quote.get("source", ""),
        }
        reference_price = float(updated.get("referencePrice") or 0)
        if reference_price > 0:
            updated["distanceToReferencePct"] = _round((current_price - reference_price) / reference_price * 100)
        if previous_close > 0:
            updated["deviation5"] = _round((current_price - previous_close) / previous_close * 100)
        updated_positions.append(updated)
        holding_value += market_value
        floating_pnl += pnl

    if not bool(account.get("reconciliationMode")):
        total_assets = float(account["availableCash"]) + holding_value
        initial_cash = float(account["initialCash"])
        account = {
            **account,
            "holdingValue": _round(holding_value),
            "totalAssets": _round(total_assets),
            "floatingPnL": _round(floating_pnl),
            "totalPnL": _round(total_assets - initial_cash),
            "totalReturnPct": _round(((total_assets - initial_cash) / initial_cash * 100) if initial_cash else 0),
        }
    return account, sorted(updated_positions, key=lambda item: item["marketValue"], reverse=True)


def lookup_security(mode: str, code: str, strategy_id: str | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id)
    local = store.lookup_security_name(mode, code, strategy_id)
    if local.get("found"):
        return local
    settings = app_settings()
    quotes, _status = quote_service.get_quotes([code], settings["market"])
    quote = quotes.get(str(code).strip())
    if quote and quote.get("name"):
        return {"code": str(code).strip(), "name": quote["name"], "found": True, "source": f"实时行情/{quote.get('source', '')}"}
    return local


def _market_phase() -> str:
    now = datetime.now()
    if now.weekday() >= 5:
        return "休市"
    current = now.time()
    if time(9, 30) <= current < time(11, 30) or time(13, 0) <= current < time(15, 0):
        return "交易中"
    if current < time(9, 30):
        return "盘前"
    return "收盘后"


def create_trade(mode: str, payload: dict[str, Any], strategy_id: str | None = None) -> dict[str, Any]:
    mode = store.validate_mode(mode)
    strategy_id = validate_strategy(strategy_id or payload.get("strategyId"))
    settings = store.get_settings(mode)
    current_workspace = workspace(mode, strategy_id)
    side = str(payload.get("type", "BUY")).upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("type 必须是 BUY 或 SELL")
    price = float(payload.get("price", 0))
    quantity = int(payload.get("quantity", 0))
    if not isfinite(price) or price <= 0 or quantity <= 0:
        raise ValueError("价格和数量必须大于 0")
    fees = _fees_from_payload(payload, calculate_fees(side, price, quantity, settings))
    historical = bool(payload.get("historicalBackfill", False))
    strategy_snapshot = _normalize_strategy_snapshot(strategy_id, side, payload.get("strategySnapshot"))
    if historical:
        conclusion, tags = _historical_audit(payload)
    elif side == "BUY":
        conclusion, tags = audit_buy(
            strategy_id,
            price,
            quantity,
            str(payload.get("time", _now_hm())),
            current_workspace["account"]["availableCash"],
            fees,
            strategy_snapshot,
        )
    else:
        position = next((item for item in current_workspace["positions"] if item["code"] == str(payload.get("code", ""))), None)
        if not position or quantity > int(position["availableQuantity"]):
            raise ValueError("卖出数量超过当前账户的可卖数量，或该账户不存在此持仓")
        conclusion, tags = audit_sell(
            strategy_id,
            trade_date=str(payload.get("date") or _today()),
            trade_time=str(payload.get("time", _now_hm())),
            position=position,
            strategy_snapshot=strategy_snapshot,
        )
    trade = {
        "id": str(payload.get("id") or f"trade-{uuid4().hex}"),
        "accountMode": mode,
        "strategyId": strategy_id,
        "code": str(payload.get("code", "")).strip(),
        "name": str(payload.get("name", "")).strip() or str(payload.get("code", "")).strip(),
        "type": side,
        "date": str(payload.get("date") or _today()),
        "time": str(payload.get("time") or datetime.now().strftime("%H:%M:%S")),
        "price": price,
        "quantity": quantity,
        "amount": _round(price * quantity),
        **fees,
        "reason": str(payload.get("reason", "")),
        "remark": str(payload.get("remark", "")),
        "rulesConclusion": conclusion,
        "violationTags": tags,
        "strategySnapshot": strategy_snapshot,
        "historicalBackfill": historical,
        "manualFeeOverride": bool(payload.get("manualFeeOverride", False)),
    }
    if not trade["code"]:
        raise ValueError("股票代码不能为空")
    saved = store.upsert_trade(mode, trade, strategy_id)
    level = "VIOLATION" if saved["rulesConclusion"] == "违规交易" else "SUCCESS"
    store.add_notification(mode, level, "交易记录已保存", f"{saved['name']} {saved['type']} {saved['quantity']} 股，账户数据已重新计算。", saved["code"], strategy_id)
    return workspace(mode, strategy_id)


def update_trade(mode: str, trade_id: str, payload: dict[str, Any], strategy_id: str | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id or payload.get("strategyId"))
    existing = store.get_trade(store.validate_mode(mode), trade_id, strategy_id)
    if not existing:
        raise ValueError("交易记录不存在")
    merged = {**existing, **payload, "id": trade_id, "accountMode": mode, "strategyId": strategy_id}
    price = float(merged["price"])
    quantity = int(merged["quantity"])
    merged["amount"] = _round(price * quantity)
    auto_fees = calculate_fees(merged["type"], price, quantity, store.get_settings(mode))
    merged.update(_fees_from_payload(merged, auto_fees))
    merged["strategySnapshot"] = _normalize_strategy_snapshot(strategy_id, str(merged.get("type", "BUY")), merged.get("strategySnapshot"))
    if merged.get("historicalBackfill"):
        conclusion, tags = _historical_audit(merged)
        merged["rulesConclusion"] = conclusion
        merged["violationTags"] = tags
    elif str(merged.get("type", "BUY")).upper() == "BUY":
        current_workspace = workspace(mode, strategy_id)
        conclusion, tags = audit_buy(
            strategy_id,
            price,
            quantity,
            str(merged.get("time", _now_hm())),
            current_workspace["account"]["availableCash"],
            auto_fees,
            merged["strategySnapshot"],
        )
        merged["rulesConclusion"] = conclusion
        merged["violationTags"] = tags
    elif strategy_id == MODE3_STRATEGY_ID:
        current_workspace = workspace(mode, strategy_id)
        position = next((item for item in current_workspace["positions"] if item["code"] == str(merged.get("code", ""))), None)
        conclusion, tags = audit_sell(
            strategy_id,
            trade_date=str(merged.get("date") or _today()),
            trade_time=str(merged.get("time", _now_hm())),
            position=position,
            strategy_snapshot=merged["strategySnapshot"],
        )
        merged["rulesConclusion"] = conclusion
        merged["violationTags"] = tags
    store.upsert_trade(mode, merged, strategy_id)
    store.add_notification(mode, "INFO", "交易记录已更新", f"{merged['name']} 的成交记录和账户汇总已重算。", merged["code"], strategy_id)
    return workspace(mode, strategy_id)


def _normalize_strategy_snapshot(strategy_id: str, side: str, value: Any) -> dict[str, Any]:
    snapshot = dict(value) if isinstance(value, dict) else {}
    if strategy_id != MODE3_STRATEGY_ID:
        return snapshot
    if side.upper() == "BUY":
        entry = snapshot.get("entryChecklist") if isinstance(snapshot.get("entryChecklist"), dict) else {}
        snapshot["entryChecklist"] = dict(entry)
        snapshot.setdefault("plannedExitRule", "NEXT_TRADING_DAY")
    else:
        if snapshot.get("extendedObservation") is None:
            snapshot["extendedObservation"] = False
        snapshot.setdefault("exitReason", "")
    return snapshot


def delete_trade(mode: str, trade_id: str, strategy_id: str | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id)
    existing = store.get_trade(store.validate_mode(mode), trade_id, strategy_id)
    if not existing:
        raise ValueError("交易记录不存在")
    store.delete_trade(mode, trade_id, strategy_id)
    store.add_notification(mode, "WARNING", "交易记录已删除", f"已删除 {existing['name']} 的一笔交易，账户流水已重算。", existing["code"], strategy_id)
    return workspace(mode, strategy_id)


def recalculate_fees(mode: str, strategy_id: str | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id)
    settings = store.get_settings(store.validate_mode(mode))
    for trade in store.list_trades(mode, strategy_id):
        if trade.get("manualFeeOverride"):
            continue
        trade.update(calculate_fees(trade["type"], trade["price"], trade["quantity"], settings))
        store.upsert_trade(mode, trade, strategy_id)
    store.add_notification(mode, "SUCCESS", "手续费重算完成", "当前交易模式全部非手工覆盖交易已按最新费率重算。", strategy_id=strategy_id)
    return workspace(mode, strategy_id)


def update_settings(mode: str, app_payload: dict[str, Any], strategy_id: str | None = None) -> dict[str, Any]:
    mode = store.validate_mode(mode)
    strategy_id = validate_strategy(strategy_id)
    if "simulation" in app_payload and "real" in app_payload:
        for target_mode in ("simulation", "real"):
            account_payload = dict(app_payload[target_mode])
            if "reconciliation" in app_payload and target_mode in app_payload["reconciliation"]:
                account_payload["reconciliation"] = app_payload["reconciliation"][target_mode]
            if "market" in app_payload:
                account_payload["market"] = app_payload["market"]
            store.save_settings(target_mode, account_payload)
        store.add_notification(mode, "INFO", "账户设置已更新", "模拟与实盘设置已分别写入各自账本。", strategy_id=strategy_id)
    else:
        account_payload = dict(app_payload.get(mode, app_payload))
        if "reconciliation" in app_payload and mode in app_payload["reconciliation"]:
            account_payload["reconciliation"] = app_payload["reconciliation"][mode]
        if "market" in app_payload:
            account_payload["market"] = app_payload["market"]
        store.save_settings(mode, account_payload)
        store.add_notification(mode, "INFO", "账户设置已更新", "初始资金、费率和对账设置仅应用于当前账户。", strategy_id=strategy_id)
    return workspace(mode, strategy_id)


def defer_position(mode: str, code: str, reason: str = "", strategy_id: str | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id)
    current = workspace(mode, strategy_id)
    position = next((item for item in current["positions"] if item["code"] == code), None)
    if not position:
        raise ValueError("当前账户不存在此持仓")
    store.save_position_state(mode, code, strategy_id=strategy_id, buy_date=position["buyDate"], deferred=True,
                              defer_reason=reason or "用户明确延后处理")
    store.add_notification(mode, "WARNING", "已标记延后处理", f"{position['name']} 已进入当前交易模式的延后处理队列。", code, strategy_id)
    return workspace(mode, strategy_id)


def cancel_defer(mode: str, code: str, strategy_id: str | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id)
    store.save_position_state(mode, code, strategy_id=strategy_id, deferred=False, defer_reason="")
    store.add_notification(mode, "INFO", "已撤销延后处理", f"{code} 已恢复当前交易模式的处理节奏。", code, strategy_id)
    return workspace(mode, strategy_id)


def add_note(mode: str, code: str, note: str, strategy_id: str | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id)
    note = note.strip()
    if not note:
        raise ValueError("备注不能为空")
    current = store.get_position_state(mode, code, strategy_id)
    notes = [*current.get("notes", []), f"{datetime.now().strftime('%Y-%m-%d %H:%M')} {note}"][-50:]
    store.save_position_state(mode, code, strategy_id=strategy_id, notes=notes)
    return workspace(mode, strategy_id)


def save_review(mode: str, payload: dict[str, Any], strategy_id: str | None = None) -> dict[str, Any]:
    strategy_id = validate_strategy(strategy_id or payload.get("strategyId"))
    required = ["planAndBasis", "executionAndDeviation", "resultAndEmotion", "improvementAndNextPlan"]
    if not any(str(payload.get(key, "")).strip() for key in required):
        raise ValueError("复盘内容不能全部为空")
    payload = {**payload, "strategyId": strategy_id}
    store.save_review(store.validate_mode(mode), payload, strategy_id)
    store.add_notification(mode, "SUCCESS", "复盘已保存", f"{payload.get('date', _today())} 的四段式复盘已归档。", strategy_id=strategy_id)
    return workspace(mode, strategy_id)
