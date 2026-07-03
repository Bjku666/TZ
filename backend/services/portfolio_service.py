from __future__ import annotations

from datetime import date, time
import json
from typing import Any

import pandas as pd

from src.data import DATA_DIR, filter_trades_by_account_mode, load_holdings, load_trades, load_watchlist, save_holdings
from src.history import load_cached_history
from src.portfolio import (
    account_state_from_trades,
    build_positions_from_trades,
    ensure_trade_columns,
    portfolio_to_legacy_holdings,
)
from src.rules import clean_code
from src.trading_rules_config import (
    MAX_SINGLE_TRADE_RISK_PCT,
    TAKE_PROFIT_PRIORITY_DEVIATION_PCT,
)
from src.storage import load_last_refresh, load_quote_snapshot

from backend.services.settings_service import account_mode_name, initial_cash
from backend.storage.csv_adapter import number, trades_to_api


def _risk_level(advice: str, deviation: float) -> str:
    text = str(advice or "")
    if "清仓" in text or "卖出" in text or "跌破" in text:
        return "danger"
    if deviation > TAKE_PROFIT_PRIORITY_DEVIATION_PCT:
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
    return price


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


def _reference_from_history(code: str, today: date) -> float | None:
    history = load_cached_history(code)
    if history is None or history.empty or "日期" not in history or "收盘" not in history:
        return None
    out = history.copy()
    out["日期"] = pd.to_datetime(out["日期"], errors="coerce")
    out = out[out["日期"].dt.date < today].dropna(subset=["日期"])
    if out.empty:
        return None
    return _positive_number(out.iloc[-1].get("收盘"))


def _reference_from_quote_archives(code: str, today: date) -> float | None:
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
    return candidates[-1][1]


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
    candidates = [
        _reference_from_quote(quote_rows.get(code), today),
        _reference_from_watchlist(watchlist_rows.get(code), use_watchlist_pct),
        _positive_number((legacy_rows.get(code) or {}).get("当前价")),
        _reference_from_trade_snapshots(flow, code, today),
        _reference_from_quote_archives(code, today),
        _reference_from_history(code, today),
        _positive_number(opening_row.get("平均成本")),
        _positive_number(opening_row.get("当前价")),
    ]
    for value in candidates:
        if value is not None:
            return value
    return 0.0


def _broker_style_today_pnl(
    trades: pd.DataFrame,
    positions: pd.DataFrame,
    watchlist: pd.DataFrame,
    legacy_holdings: pd.DataFrame,
) -> float:
    flow = ensure_trade_columns(trades)
    today = date.today()
    today_mask = pd.to_datetime(flow["日期"], errors="coerce").dt.date == today
    today_trades = flow[today_mask].copy()
    prior_trades = flow[~today_mask].copy()

    opening_positions = build_positions_from_trades(prior_trades, watchlist, legacy_holdings)
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


def portfolio_snapshot(
    mode: str | None = None,
    sync_legacy: bool = False,
    persist_risk_state: bool = False,
) -> dict[str, Any]:
    account_mode = account_mode_name(mode)
    trades = filter_trades_by_account_mode(load_trades(), account_mode)
    watchlist = load_watchlist()
    legacy_holdings = load_holdings()
    positions = build_positions_from_trades(
        trades,
        watchlist,
        legacy_holdings,
        persist_below_ma5_state=sync_legacy or persist_risk_state,
    )
    if sync_legacy:
        save_holdings(portfolio_to_legacy_holdings(positions))

    state = account_state_from_trades(trades, positions, initial_cash(mode), account_mode)
    today_pnl = _broker_style_today_pnl(trades, positions, watchlist, legacy_holdings)
    grouped_trades = _trades_by_code(trades)
    today = date.today()

    api_positions: list[dict[str, Any]] = []
    for _, row in positions.iterrows():
        market_value = number(row.get("市值"))
        deviation = number(row.get("MA5偏离率%"))
        advice = str(row.get("操作提醒") or "")
        code = str(row.get("代码") or "")
        avg_cost = number(row.get("平均成本"))
        current_price = number(row.get("当前价"))
        quantity = int(number(row.get("数量")))
        current_loss_amount = max(0.0, (avg_cost - current_price) * quantity)
        max_loss_amount = number(state.get("初始本金")) * MAX_SINGLE_TRADE_RISK_PCT
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
                "buyDate": str(row.get("买入日期") or ""),
                "advice": advice,
                "riskLevel": _risk_level(advice, deviation),
                "currentLossAmount": round(current_loss_amount, 2),
                "maxLossAmount": round(max_loss_amount, 2),
                "lossRiskPct": round(current_loss_amount / number(state.get("初始本金")) * 100, 2)
                if number(state.get("初始本金")) > 0
                else 0,
                "tradeLink": _position_trade_link(code, grouped_trades, today),
            }
        )

    account_state = {
        "initialCash": number(state.get("初始本金")),
        "availableCash": number(state.get("当前现金")),
        "holdingValue": number(state.get("持仓市值")),
        "totalAssets": number(state.get("当前总资产")),
        "realizedPnL": number(state.get("已实现盈亏")),
        "floatingPnL": number(state.get("浮动盈亏")),
        "totalPnL": number(state.get("总盈亏")),
        "totalReturnPct": number(state.get("总收益率%")),
        "todayPnL": round(today_pnl, 2),
    }
    return {"accountState": account_state, "positions": api_positions}
