from __future__ import annotations

from typing import Any

import pandas as pd

from src.data import load_holdings, load_trades, load_watchlist, save_holdings
from src.portfolio import (
    account_state_from_trades,
    build_positions_from_trades,
    portfolio_to_legacy_holdings,
)

from backend.services.settings_service import account_mode_name, initial_cash
from backend.storage.csv_adapter import number


def _risk_level(advice: str, deviation: float) -> str:
    text = str(advice or "")
    if "清仓" in text or "卖出" in text or "跌破" in text:
        return "danger"
    if deviation > 7:
        return "warning"
    return "normal"


def portfolio_snapshot(mode: str | None = None, sync_legacy: bool = False) -> dict[str, Any]:
    trades = load_trades()
    watchlist = load_watchlist()
    legacy_holdings = load_holdings()
    positions = build_positions_from_trades(trades, watchlist, legacy_holdings)
    if sync_legacy:
        save_holdings(portfolio_to_legacy_holdings(positions))

    account_mode = account_mode_name(mode)
    state = account_state_from_trades(trades, positions, initial_cash(mode), account_mode)
    pct_map: dict[str, float] = {}
    if not watchlist.empty:
        for _, row in watchlist.iterrows():
            pct_map[str(row.get("代码"))] = number(row.get("涨跌幅%"))

    api_positions: list[dict[str, Any]] = []
    today_pnl = 0.0
    for _, row in positions.iterrows():
        market_value = number(row.get("市值"))
        pct = pct_map.get(str(row.get("代码")), 0.0)
        if pct != -100:
            today_pnl += market_value - (market_value / (1 + pct / 100))
        deviation = number(row.get("MA5偏离率%"))
        advice = str(row.get("操作提醒") or "")
        api_positions.append(
            {
                "code": str(row.get("代码") or ""),
                "name": str(row.get("名称") or ""),
                "quantity": int(number(row.get("数量"))),
                "availableQuantity": int(number(row.get("可卖数量"))),
                "avgCost": number(row.get("平均成本")),
                "currentPrice": number(row.get("当前价")),
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
