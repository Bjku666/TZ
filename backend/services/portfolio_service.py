from __future__ import annotations

from datetime import date, datetime, time, timedelta
import json
from typing import Any

import pandas as pd

from src.data import DATA_DIR, load_holdings, load_watchlist, save_holdings
from src.history import load_cached_history
from src.portfolio import (
    account_state_from_trades,
    build_positions_from_trades,
    ensure_trade_columns,
    portfolio_to_legacy_holdings,
    realized_pnl_by_date,
)
from src.rules import clean_code
from src.video_original_rules import evaluate_next_day_exit
from src.storage import load_last_refresh, load_quote_snapshot
from src.trading_calendar import (
    SHANGHAI_TZ,
    calendar_degraded,
    current_market_phase,
    is_trading_day,
    next_market_open,
    next_trading_day,
    previous_trading_day,
    shanghai_now,
)

from backend.services.settings_service import account_mode_name, current_mode, get_settings, initial_cash
from backend.storage.csv_adapter import number, trades_to_api
from backend.storage import trade_repository
from backend.storage.sqlite_store import load_kv, save_kv


def _risk_level(advice: str, deviation: float) -> str:
    text = str(advice or "")
    if "待卖" in text or "卖出" in text or "超时" in text:
        return "danger"
    if "延迟" in text or "观察" in text:
        return "warning"
    return "normal"


def _positive_number(value: Any) -> float | None:
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.notna(parsed) and float(parsed) > 0:
        return float(parsed)
    return None


def _latest_rows_by_code(frame: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    if frame is None or frame.empty or "代码" not in frame:
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        code = clean_code(row.get("代码"))
        if code:
            rows[code] = row.to_dict()
    return rows


def _parse_date(value: Any) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _previous_weekday(day: date) -> date:
    current = day
    while current.weekday() >= 5:
        current = current - timedelta(days=1)
    return current


def _latest_quote_trade_date() -> date | None:
    candidates: list[date] = []
    snapshot = load_quote_snapshot()
    if not snapshot.empty and "更新时间" in snapshot:
        parsed = pd.to_datetime(snapshot["更新时间"], errors="coerce").dropna()
        candidates.extend(item.date() for item in parsed if item.date().weekday() < 5)
    refresh_date = _parse_date(load_last_refresh().get("更新时间"))
    if refresh_date and refresh_date.weekday() < 5:
        candidates.append(refresh_date)
    return max(candidates) if candidates else None


def _last_trade_date(trades: pd.DataFrame) -> date | None:
    flow = ensure_trade_columns(trades)
    if flow.empty:
        return None
    parsed = pd.to_datetime(flow["日期"], errors="coerce").dropna()
    return parsed.max().date() if not parsed.empty else None


def resolve_portfolio_as_of_date(trades: pd.DataFrame, as_of_date: Any | None = None) -> date:
    explicit = _parse_date(as_of_date)
    if explicit is not None:
        return explicit
    quote_date = _latest_quote_trade_date()
    trade_date = _last_trade_date(trades)
    if quote_date is not None and trade_date is not None:
        return max(quote_date, trade_date)
    if quote_date is not None:
        return quote_date
    if trade_date is not None:
        return trade_date
    return _previous_weekday(date.today())


def resolve_operation_date(value: Any | None = None) -> date:
    return _parse_date(value) or shanghai_now().date()


def resolve_valuation_date(trades: pd.DataFrame, operation_date: date) -> date:
    quote_date = _latest_quote_trade_date()
    trade_date = _last_trade_date(trades)
    candidates = [day for day in (quote_date, trade_date) if day is not None and day <= operation_date]
    if candidates:
        candidate = max(candidates)
        return candidate if is_trading_day(candidate) else previous_trading_day(candidate)
    return operation_date if is_trading_day(operation_date) else previous_trading_day(operation_date)


def _market_clock_for_operation(operation_date: date) -> datetime:
    now = shanghai_now()
    if operation_date == now.date():
        return now
    return datetime.combine(operation_date, time(12, 0), tzinfo=SHANGHAI_TZ)


def _position_execution_status(row: pd.Series, operation_date: date) -> dict[str, Any]:
    quantity = int(number(row.get("数量")))
    available = int(number(row.get("可卖数量")))
    today_buy = int(number(row.get("今日买入数量")))
    t1_locked = int(number(row.get("T1锁定数量")))
    buy_date = _parse_date(row.get("买入日期"))
    clock = _market_clock_for_operation(operation_date)
    phase = current_market_phase(clock)
    is_today_buy = buy_date == operation_date
    next_sellable = next_trading_day(operation_date) if t1_locked > 0 else operation_date
    if t1_locked > 0 and buy_date is not None:
        next_sellable = next_trading_day(buy_date)

    can_execute = available > 0 and phase == "trading"
    if phase in {"weekend", "holiday"}:
        blocked = f"休市，下一交易日 {next_trading_day(operation_date).isoformat()} 可处理"
    elif phase == "pre_market":
        blocked = "盘前不可交易，今日开盘后可卖" if available > 0 else "盘前暂无可卖数量"
    elif phase == "lunch_break":
        blocked = "午间休市，13:00 后可处理" if available > 0 else "当前无可卖数量"
    elif phase == "after_close":
        blocked = f"已收盘，下一交易日 {next_trading_day(operation_date).isoformat()} 可处理"
    elif available <= 0 and t1_locked > 0:
        blocked = f"T+1 锁定 {t1_locked} 股，{next_sellable.isoformat()} 可处理"
    elif available <= 0:
        blocked = "当前无可卖数量，请检查交易流水或账户同步状态"
    else:
        blocked = ""

    next_open = next_market_open(clock)
    return {
        "operationDate": operation_date.isoformat(),
        "isTodayBuy": is_today_buy,
        "todayBuyQuantity": today_buy,
        "t1LockedQuantity": t1_locked,
        "isT1Locked": t1_locked > 0,
        "nextSellableTradeDate": next_sellable.isoformat(),
        "marketPhase": phase,
        "canExecuteSellNow": can_execute,
        "sellBlockedReason": blocked,
        "nextActionTime": next_open.isoformat(),
        "calendarDegraded": calendar_degraded(),
        "settledQuantity": max(0, quantity - t1_locked),
    }


def _trades_on_or_before(trades: pd.DataFrame, settlement_date: date) -> pd.DataFrame:
    flow = ensure_trade_columns(trades)
    if flow.empty:
        return flow
    parsed = pd.to_datetime(flow["日期"], errors="coerce")
    return flow[parsed.dt.date <= settlement_date].reset_index(drop=True)


def _is_intraday_timestamp(value: Any, today: date) -> bool:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return False
    return parsed.date() == today and parsed.time() >= time(9, 25)


def _reference_from_quote(row: dict[str, Any] | None, today: date) -> float | None:
    if not row:
        return None
    latest = _positive_number(row.get("最新价"))
    previous_close = _positive_number(row.get("昨收"))
    timestamp = pd.to_datetime(row.get("更新时间"), errors="coerce")
    if pd.notna(timestamp):
        if timestamp.date() < today:
            return latest or previous_close
        if timestamp.date() == today and timestamp.time() < time(9, 25):
            return latest or previous_close
    return previous_close or latest


def _reference_from_watchlist(row: dict[str, Any] | None, use_intraday_pct: bool) -> float | None:
    if not row:
        return None
    price = _positive_number(row.get("现价"))
    pct = pd.to_numeric(row.get("涨跌幅%"), errors="coerce")
    if use_intraday_pct and price is not None and pd.notna(pct) and float(pct) != -100:
        divisor = 1 + float(pct) / 100
        if divisor:
            return price / divisor
    return None


def _reference_from_trade_snapshots(flow: pd.DataFrame, code: str, today: date) -> float | None:
    if flow.empty:
        return None
    code = clean_code(code)
    dates = pd.to_datetime(flow["日期"], errors="coerce")
    today_flow = flow[(flow["代码"].map(clean_code) == code) & (dates.dt.date == today)]
    for _, trade in today_flow.iloc[::-1].iterrows():
        raw = str(trade.get("规则快照") or "").strip()
        if not raw:
            continue
        try:
            snapshot = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for key in ("dayReferencePrice", "referencePrice", "prevClose"):
            value = _positive_number(snapshot.get(key))
            if value is not None:
                return value
    return None


def _reference_from_history(code: str, today: date) -> tuple[pd.Timestamp, float] | None:
    history = load_cached_history(code)
    if history is None or history.empty or "日期" not in history or "收盘" not in history:
        return None
    out = history.copy()
    out["日期"] = pd.to_datetime(out["日期"], errors="coerce")
    out = out[out["日期"].dt.date < today].dropna(subset=["日期"])
    if out.empty:
        return None
    latest = out.sort_values("日期").iloc[-1]
    price = _positive_number(latest.get("收盘"))
    if price is None:
        return None
    close_timestamp = pd.Timestamp.combine(latest["日期"].date(), time.max)
    return close_timestamp, price


def _reference_from_quote_archives(code: str, today: date) -> tuple[pd.Timestamp, float] | None:
    backup_dir = DATA_DIR / "backups"
    if not backup_dir.exists():
        return None

    code = clean_code(code)
    cutoff = pd.Timestamp.combine(today, time(9, 25))
    candidates: list[tuple[pd.Timestamp, float]] = []
    for path in backup_dir.glob("runtime__quote_snapshot.csv.backup.*.csv"):
        try:
            frame = pd.read_csv(path, dtype={"代码": str}, encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
        if frame.empty or "代码" not in frame:
            continue
        matches = frame[frame["代码"].map(clean_code) == code]
        if matches.empty:
            continue
        for _, row in matches.iterrows():
            timestamp = pd.to_datetime(row.get("更新时间"), errors="coerce")
            price = _positive_number(row.get("最新价"))
            if pd.notna(timestamp) and timestamp < cutoff and price is not None:
                candidates.append((timestamp, price))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[-1]


def _opening_reference_price(
    code: str,
    opening_row: pd.Series,
    flow: pd.DataFrame,
    quote_rows: dict[str, dict[str, Any]],
    watchlist_rows: dict[str, dict[str, Any]],
    legacy_rows: dict[str, dict[str, Any]],
    use_watchlist_pct: bool,
    today: date,
) -> float:
    code = clean_code(code)
    direct_candidates = [
        _reference_from_quote(quote_rows.get(code), today),
        _reference_from_watchlist(watchlist_rows.get(code), use_watchlist_pct),
        _reference_from_trade_snapshots(flow, code, today),
    ]
    for value in direct_candidates:
        if value is not None:
            return value

    dated_candidates = [
        _reference_from_history(code, today),
        _reference_from_quote_archives(code, today),
    ]
    available_dated = [item for item in dated_candidates if item is not None]
    if available_dated:
        return max(available_dated, key=lambda item: item[0])[1]

    fallback_candidates = [
        _positive_number((legacy_rows.get(code) or {}).get("当前价")),
        _positive_number(opening_row.get("平均成本")),
        _positive_number(opening_row.get("当前价")),
    ]
    for value in fallback_candidates:
        if value is not None:
            return value
    return 0.0


def _broker_style_today_pnl(
    trades: pd.DataFrame,
    positions: pd.DataFrame,
    watchlist: pd.DataFrame,
    legacy_holdings: pd.DataFrame,
    settlement_date: date,
) -> float:
    flow = ensure_trade_columns(trades)
    today = settlement_date
    today_mask = pd.to_datetime(flow["日期"], errors="coerce").dt.date == today
    today_trades = flow[today_mask].copy()
    prior_trades = flow[~today_mask].copy()

    opening_positions = build_positions_from_trades(prior_trades, watchlist, legacy_holdings, as_of_date=today)
    quote_rows = _latest_rows_by_code(load_quote_snapshot())
    watchlist_rows = _latest_rows_by_code(watchlist)
    legacy_rows = _latest_rows_by_code(legacy_holdings)
    use_watchlist_pct = _is_intraday_timestamp(load_last_refresh().get("更新时间"), today)

    opening_value = 0.0
    for _, row in opening_positions.iterrows():
        code = clean_code(row.get("代码"))
        quantity = number(row.get("数量"))
        if not code or quantity <= 0:
            continue
        reference_price = _opening_reference_price(
            code,
            row,
            flow,
            quote_rows,
            watchlist_rows,
            legacy_rows,
            use_watchlist_pct,
            today,
        )
        opening_value += quantity * reference_price

    current_value = float(pd.to_numeric(positions.get("市值", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    today_buys = today_trades[today_trades["类型"] == "买入"]
    buy_amount = float(
        (
            pd.to_numeric(today_buys["金额"], errors="coerce").fillna(0)
            + pd.to_numeric(today_buys["总费用"], errors="coerce").fillna(0)
        ).sum()
    )
    today_sells = today_trades[today_trades["类型"] == "卖出"]
    sell_amount = float(
        (
            pd.to_numeric(today_sells["金额"], errors="coerce").fillna(0)
            - pd.to_numeric(today_sells["总费用"], errors="coerce").fillna(0)
        ).sum()
    )
    return round(current_value + sell_amount - buy_amount - opening_value, 2)


def _trade_brief(trade: dict[str, Any] | None) -> dict[str, Any] | None:
    if not trade:
        return None
    return {
        "id": trade.get("id"),
        "date": trade.get("date"),
        "time": trade.get("time"),
        "type": trade.get("type"),
        "price": trade.get("price"),
        "quantity": trade.get("quantity"),
        "reason": trade.get("reason"),
        "rulesConclusion": trade.get("rulesConclusion"),
        "violationTags": trade.get("violationTags", []),
    }


def _trades_by_code(trades: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for trade in trades_to_api(trades):
        code = clean_code(trade.get("code"))
        if code:
            grouped.setdefault(code, []).append(trade)
    for rows in grouped.values():
        rows.sort(key=lambda item: (str(item.get("date") or ""), str(item.get("time") or "")))
    return grouped


def _position_trade_link(code: str, grouped_trades: dict[str, list[dict[str, Any]]], today: date) -> dict[str, Any]:
    rows = grouped_trades.get(clean_code(code), [])
    buys = [trade for trade in rows if trade.get("type") == "BUY"]
    sells = [trade for trade in rows if trade.get("type") == "SELL"]
    today_rows = [trade for trade in rows if str(trade.get("date")) == today.isoformat()]
    violation_tags: list[str] = []
    for trade in rows:
        if trade.get("rulesConclusion") != "符合规则":
            violation_tags.extend(str(tag) for tag in trade.get("violationTags", []))
    return {
        "lastBuy": _trade_brief(buys[-1] if buys else None),
        "lastSell": _trade_brief(sells[-1] if sells else None),
        "todayTrades": [_trade_brief(trade) for trade in today_rows],
        "hasComplianceIssue": bool(violation_tags),
        "complianceTags": sorted(set(violation_tags)),
        "tradeCount": len(rows),
    }


def _defer_key(code: str, buy_date: Any) -> str:
    return f"defer_exit:{clean_code(code)}:{str(buy_date)[:10]}"


def defer_position_exit(code: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    buy_date = str(payload.get("buyDate") or "")
    if not clean_code(code):
        raise ValueError("股票代码缺失")
    if not buy_date:
        snapshot = portfolio_snapshot(payload.get("mode"), persist_risk_state=False)
        match = next((item for item in snapshot["positions"] if item.get("code") == clean_code(code)), None)
        if not match:
            raise ValueError("未找到持仓")
        buy_date = str(match.get("buyDate") or "")
    decision = {
        "code": clean_code(code),
        "buyDate": buy_date,
        "deferReason": str(payload.get("reason") or "用户选择延迟至14:30后处理"),
        "decisionTime": shanghai_now().replace(microsecond=0).isoformat(),
    }
    save_kv(_defer_key(code, buy_date), decision)
    return {"success": True, "decision": decision}


def portfolio_snapshot(
    mode: str | None = None,
    sync_legacy: bool = False,
    persist_risk_state: bool = False,
    as_of_date: Any | None = None,
) -> dict[str, Any]:
    account_mode = account_mode_name(mode)
    active_mode = mode or current_mode()
    all_trades = trade_repository.load_trade_frame(active_mode, account_mode)
    operation_date = resolve_operation_date(as_of_date)
    valuation_date = resolve_valuation_date(all_trades, operation_date)
    trades = _trades_on_or_before(all_trades, operation_date)
    watchlist = load_watchlist()
    legacy_holdings = load_holdings()
    positions = build_positions_from_trades(
        trades,
        watchlist,
        legacy_holdings,
        persist_below_ma5_state=sync_legacy or persist_risk_state,
        as_of_date=operation_date,
    )
    if sync_legacy:
        save_holdings(portfolio_to_legacy_holdings(positions))

    state = account_state_from_trades(trades, positions, initial_cash(mode), account_mode)
    today_pnl = _broker_style_today_pnl(trades, positions, watchlist, legacy_holdings, valuation_date)
    today_realized_pnl = realized_pnl_by_date(trades, operation_date)
    grouped_trades = _trades_by_code(trades)
    today = operation_date

    api_positions: list[dict[str, Any]] = []
    for _, row in positions.iterrows():
        market_value = number(row.get("市值"))
        deviation = number(row.get("MA5偏离率%"))
        advice = str(row.get("操作提醒") or "")
        code = str(row.get("代码") or "")
        avg_cost = number(row.get("平均成本"))
        current_price = number(row.get("当前价"))
        quantity = int(number(row.get("数量")))
        execution_status = _position_execution_status(row, operation_date)
        buy_date = str(row.get("买入日期") or "")
        defer_decision = load_kv(_defer_key(code, buy_date), {})
        exit_eval = evaluate_next_day_exit(
            buy_date=buy_date,
            now=_market_clock_for_operation(operation_date),
            current_price=current_price,
            deferred=bool(defer_decision),
            sellable_quantity=int(number(row.get("可卖数量"))),
        )
        original_advice = str(exit_eval.get("message") or advice)
        api_positions.append(
            {
                "code": code,
                "name": str(row.get("名称") or ""),
                "quantity": quantity,
                "availableQuantity": int(number(row.get("可卖数量"))),
                "avgCost": avg_cost,
                "currentPrice": current_price,
                "marketValue": market_value,
                "floatingPnL": number(row.get("浮动盈亏")),
                "floatingPnLPct": number(row.get("浮动盈亏%")),
                "ma5": number(row.get("MA5")),
                "deviation5": deviation,
                "holdDays": int(number(row.get("持仓天数"))),
                "belowMa5Days": int(number(row.get("跌破MA5天数"))),
                "buyDate": buy_date,
                "valuationDate": valuation_date.isoformat(),
                "advice": original_advice,
                "riskLevel": _risk_level(original_advice, deviation),
                "currentLossAmount": round(max(0.0, (avg_cost - current_price) * quantity), 2),
                "maxLossAmount": 0,
                "lossRiskPct": 0,
                "originalExitState": exit_eval.get("state"),
                "originalExitMessage": exit_eval.get("message"),
                "nextOriginalActionTime": exit_eval.get("nextActionTime"),
                "isLimitUp": bool(exit_eval.get("isLimitUp")),
                "deferExitDecision": defer_decision or None,
                "executionBlocked": bool(exit_eval.get("executionBlocked")),
                "executionBlockReason": exit_eval.get("executionBlockReason", ""),
                "originalRuleViolation": bool(exit_eval.get("ruleViolation")),
                "programCompletionNote": exit_eval.get("programCompletionNote", ""),
                "tradeLink": _position_trade_link(code, grouped_trades, today),
                **execution_status,
            }
        )

    account_state = {
        "initialCash": round(number(state.get("初始本金")), 2),
        "availableCash": round(number(state.get("当前现金")), 2),
        "holdingValue": round(number(state.get("持仓市值")), 2),
        "totalAssets": round(number(state.get("当前总资产")), 2),
        "realizedPnL": round(number(state.get("已实现盈亏")), 2),
        "floatingPnL": round(number(state.get("浮动盈亏")), 2),
        "holdingPnL": round(number(state.get("浮动盈亏")), 2),
        "totalPnL": round(number(state.get("总盈亏")), 2),
        "accountPnL": round(number(state.get("总盈亏")), 2),
        "totalReturnPct": round(number(state.get("总收益率%")), 2),
        "todayPnL": round(today_pnl, 2),
        "todayRealizedPnL": round(today_realized_pnl, 2),
        "asOfDate": operation_date.isoformat(),
        "operationDate": operation_date.isoformat(),
        "valuationDate": valuation_date.isoformat(),
    }
    settings = get_settings()
    reconciliation_key = "realThsReconciliation" if active_mode == "real" else "simulationThsReconciliation"
    reconciliation = settings.get(reconciliation_key) or settings.get("thsReconciliation") or {}
    if reconciliation.get("enabled"):
        discipline_capital = number(state.get("初始本金"))
        broker_capital = number(reconciliation.get("accountCapital"), 200000)
        capital_offset = broker_capital - discipline_capital
        total_assets = number(reconciliation.get("totalAssets")) - capital_offset
        available_cash = number(reconciliation.get("availableCash")) - capital_offset
        holding_value = number(reconciliation.get("holdingValue"))
        holding_pnl = number(reconciliation.get("holdingPnL"))
        account_pnl = total_assets - discipline_capital
        account_state.update(
            {
                "availableCash": round(available_cash, 2),
                "holdingValue": round(holding_value, 2),
                "totalAssets": round(total_assets, 2),
                "floatingPnL": round(holding_pnl, 2),
                "holdingPnL": round(holding_pnl, 2),
                "totalPnL": round(account_pnl, 2),
                "accountPnL": round(account_pnl, 2),
                "totalReturnPct": round(account_pnl / discipline_capital * 100, 2)
                if discipline_capital
                else 0,
                "todayPnL": round(number(reconciliation.get("todayPnL")), 2),
                "reconciliationMode": True,
            }
        )
        if len(api_positions) == 1:
            position = api_positions[0]
            quantity = number(position.get("quantity"))
            if quantity > 0:
                reconciled_cost = (holding_value - holding_pnl) / quantity
                current_price = number(position.get("currentPrice"))
                position.update(
                    {
                        "avgCost": round(reconciled_cost, 3),
                        "marketValue": round(holding_value, 2),
                        "floatingPnL": round(holding_pnl, 2),
                        "floatingPnLPct": round(holding_pnl / (reconciled_cost * quantity) * 100, 2)
                        if reconciled_cost
                        else 0,
                        "currentLossAmount": round(max(0.0, (reconciled_cost - current_price) * quantity), 2),
                    }
                )
    else:
        account_state["reconciliationMode"] = False
    return {
        "accountState": account_state,
        "positions": api_positions,
        "asOfDate": operation_date.isoformat(),
        "operationDate": operation_date.isoformat(),
        "valuationDate": valuation_date.isoformat(),
    }
