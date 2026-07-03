from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.data import HOLDING_COLUMNS
from src.history import load_cached_history
from src.rules import clean_code, holding_advice, ma5_deviation

POSITION_COLUMNS = [
    "代码",
    "名称",
    "数量",
    "可卖数量",
    "平均成本",
    "当前价",
    "市值",
    "浮动盈亏",
    "浮动盈亏%",
    "MA5",
    "MA5偏离率%",
    "持仓天数",
    "跌破MA5天数",
    "操作提醒",
    "买入日期",
]

ACCOUNT_STATE_COLUMNS = [
    "账户模式",
    "初始本金",
    "当前现金",
    "持仓市值",
    "当前总资产",
    "已实现盈亏",
    "浮动盈亏",
    "总盈亏",
    "总收益率%",
    "更新时间",
]

CLOSED_TRADE_COLUMNS = [
    "买入日期",
    "卖出日期",
    "代码",
    "名称",
    "买入均价",
    "卖出价",
    "数量",
    "收益金额",
    "收益率%",
    "持仓天数",
    "备注",
]


def number_or(value: object, default: float = 0.0) -> float:
    numeric = pd.to_numeric(value, errors="coerce")
    return float(numeric) if pd.notna(numeric) else float(default)


def calculate_trade_fees(
    side: str,
    price: object,
    quantity: object,
    settings: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Calculate A-share fees for one trade."""
    settings = settings or {}
    amount = round(number_or(price) * number_or(quantity), 2)
    commission_rate = number_or(settings.get("commission_rate", 0.00025), 0.00025)
    min_commission = number_or(settings.get("min_commission", 5.0), 5.0)
    stamp_tax_rate = number_or(settings.get("stamp_tax_rate", 0.0005), 0.0005)
    transfer_fee_rate = number_or(settings.get("transfer_fee_rate", 0.00001), 0.00001)
    use_min_commission = bool(settings.get("use_min_commission", True))

    commission = amount * commission_rate
    if use_min_commission and amount > 0:
        commission = max(commission, min_commission)
    stamp_tax = amount * stamp_tax_rate if side == "卖出" else 0.0
    transfer_fee = amount * transfer_fee_rate
    total_fee = commission + stamp_tax + transfer_fee

    return {
        "amount": round(amount, 2),
        "commission": round(commission, 2),
        "stamp_tax": round(stamp_tax, 2),
        "transfer_fee": round(transfer_fee, 2),
        "total_fee": round(total_fee, 2),
    }


def date_or_today(value: object) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.Timestamp(date.today())
    return parsed


def ensure_trade_columns(trades: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "代码",
        "名称",
        "类型",
        "日期",
        "时间",
        "价格",
        "数量",
        "金额",
        "手续费",
        "印花税",
        "过户费",
        "总费用",
        "原因",
        "备注",
        "规则快照",
        "规则结论",
        "违规标签",
    ]
    if trades.empty:
        return pd.DataFrame(columns=columns)
    out = trades.copy()
    for column in columns:
        if column not in out:
            out[column] = 0 if column in {"手续费", "印花税", "过户费", "总费用"} else pd.NA
    out["代码"] = out["代码"].map(clean_code)
    out["名称"] = out["名称"].fillna("").astype(str).str.strip()
    out["类型"] = out["类型"].where(out["类型"].isin(["买入", "卖出"]), "买入")
    out["日期"] = pd.to_datetime(out["日期"], errors="coerce").fillna(pd.Timestamp(date.today()))
    for column in ["时间", "原因", "备注", "规则快照", "规则结论", "违规标签"]:
        out[column] = out[column].fillna("").astype(str)
    for column in ["价格", "数量", "金额", "手续费", "印花税", "过户费", "总费用"]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0)
    out["金额"] = out["金额"].where(out["金额"] > 0, out["价格"] * out["数量"])
    out.loc[out["类型"] == "买入", "印花税"] = 0.0
    out["总费用"] = out["总费用"].where(out["总费用"] > 0, out["手续费"] + out["印花税"] + out["过户费"])
    out = out[out["代码"].str.len() == 6].copy()
    return out[columns].sort_values(["日期"]).reset_index(drop=True)


def quote_lookup(frame: pd.DataFrame | None, code: str, price_col: str) -> dict[str, Any]:
    if frame is None or frame.empty or "代码" not in frame:
        return {}
    matches = frame[frame["代码"].astype(str).map(clean_code) == clean_code(code)]
    if matches.empty:
        return {}
    row = matches.iloc[-1].to_dict()
    price = row.get(price_col)
    if pd.isna(pd.to_numeric(price, errors="coerce")):
        return row
    row["当前价"] = price
    return row


def latest_history_values(code: str) -> dict[str, Any]:
    history = load_cached_history(code)
    if history is None or history.empty:
        return {}
    latest = history.iloc[-1].to_dict()
    return {
        "当前价": latest.get("收盘"),
        "MA5": latest.get("MA5"),
    }


def current_context(code: str, watchlist: pd.DataFrame | None, legacy_holdings: pd.DataFrame | None) -> dict[str, Any]:
    context = quote_lookup(watchlist, code, "现价")
    legacy = quote_lookup(legacy_holdings, code, "当前价")
    history = latest_history_values(code)
    merged = {**history, **legacy, **context}
    return merged


def build_positions_from_trades(
    trades: pd.DataFrame,
    watchlist: pd.DataFrame | None = None,
    legacy_holdings: pd.DataFrame | None = None,
) -> pd.DataFrame:
    flow = ensure_trade_columns(trades)
    if flow.empty:
        return pd.DataFrame(columns=POSITION_COLUMNS)

    states: dict[str, dict[str, Any]] = {}
    for _, trade in flow.iterrows():
        code = clean_code(trade["代码"])
        if not code:
            continue
        state = states.setdefault(
            code,
            {
                "代码": code,
                "名称": trade.get("名称", ""),
                "数量": 0.0,
                "成本总额": 0.0,
                "买入日期": trade["日期"],
            },
        )
        qty = number_or(trade.get("数量"))
        price = number_or(trade.get("价格"))
        amount = number_or(trade.get("金额"), price * qty)
        fee = number_or(trade.get("手续费"))
        tax = number_or(trade.get("印花税"))
        transfer_fee = number_or(trade.get("过户费"))
        total_fee = number_or(trade.get("总费用"), fee + tax + transfer_fee)
        if trade["类型"] == "买入":
            if state["数量"] <= 0:
                state["买入日期"] = trade["日期"]
                state["成本总额"] = 0.0
                state["数量"] = 0.0
            state["数量"] += qty
            state["成本总额"] += amount + total_fee
            if str(trade.get("名称", "")).strip():
                state["名称"] = trade.get("名称", "")
        else:
            sell_qty = min(qty, state["数量"])
            if sell_qty <= 0:
                continue
            avg_cost = state["成本总额"] / state["数量"] if state["数量"] else 0
            state["数量"] -= sell_qty
            state["成本总额"] -= avg_cost * sell_qty
            if state["数量"] <= 0:
                state["数量"] = 0.0
                state["成本总额"] = 0.0

    rows: list[dict[str, Any]] = []
    today = pd.Timestamp(date.today())
    for code, state in states.items():
        qty = number_or(state.get("数量"))
        if qty <= 0:
            continue
        avg_cost = state["成本总额"] / qty if qty else 0
        context = current_context(code, watchlist, legacy_holdings)
        current_price = number_or(context.get("当前价"), avg_cost)
        ma5 = context.get("MA5")
        if pd.isna(pd.to_numeric(ma5, errors="coerce")):
            ma5 = latest_history_values(code).get("MA5")
        market_value = qty * current_price
        floating_pnl = (current_price - avg_cost) * qty
        floating_pct = floating_pnl / (avg_cost * qty) * 100 if avg_cost and qty else 0
        deviation = ma5_deviation(current_price, ma5)
        below_ma5_days = int(number_or(context.get("跌破MA5天数"), 0))
        if deviation is not None:
            below_ma5_days = max(1, below_ma5_days) if deviation < 0 else 0
        buy_date = date_or_today(state.get("买入日期"))
        rows.append({
            "代码": code,
            "名称": state.get("名称") or context.get("名称", ""),
            "数量": int(qty),
            "可卖数量": int(qty),
            "平均成本": avg_cost,
            "当前价": current_price,
            "市值": market_value,
            "浮动盈亏": floating_pnl,
            "浮动盈亏%": floating_pct,
            "MA5": ma5,
            "MA5偏离率%": deviation,
            "持仓天数": max(0, int((today - buy_date.normalize()).days)),
            "跌破MA5天数": below_ma5_days,
            "操作提醒": holding_advice(current_price, ma5, qty, below_ma5_days),
            "买入日期": buy_date.date().isoformat(),
        })
    return pd.DataFrame(rows, columns=POSITION_COLUMNS)


def realized_pnl_from_trades(trades: pd.DataFrame) -> float:
    closed = closed_trades_from_flow(trades)
    if closed.empty:
        return 0.0
    return float(pd.to_numeric(closed["收益金额"], errors="coerce").fillna(0).sum())


def account_state_from_trades(
    trades: pd.DataFrame,
    positions: pd.DataFrame,
    initial_capital: float,
    account_mode: str,
) -> dict[str, float | str]:
    flow = ensure_trade_columns(trades)
    cash = float(initial_capital)
    for _, trade in flow.iterrows():
        amount = number_or(trade.get("金额"), number_or(trade.get("价格")) * number_or(trade.get("数量")))
        fee = number_or(trade.get("手续费"))
        tax = number_or(trade.get("印花税"))
        transfer_fee = number_or(trade.get("过户费"))
        total_fee = number_or(trade.get("总费用"), fee + tax + transfer_fee)
        if trade["类型"] == "买入":
            cash -= amount + total_fee
        else:
            cash += amount - total_fee

    market_value = float(pd.to_numeric(positions.get("市值", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    floating_pnl = float(pd.to_numeric(positions.get("浮动盈亏", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    realized_pnl = realized_pnl_from_trades(flow)
    total_assets = cash + market_value
    total_pnl = total_assets - float(initial_capital)
    total_return_pct = total_pnl / float(initial_capital) * 100 if initial_capital else 0.0
    return {
        "账户模式": account_mode,
        "初始本金": float(initial_capital),
        "当前现金": cash,
        "持仓市值": market_value,
        "当前总资产": total_assets,
        "已实现盈亏": realized_pnl,
        "浮动盈亏": floating_pnl,
        "总盈亏": total_pnl,
        "总收益率%": total_return_pct,
        "更新时间": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def portfolio_to_legacy_holdings(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame(columns=HOLDING_COLUMNS)
    out = pd.DataFrame({
        "代码": positions["代码"],
        "名称": positions["名称"],
        "买入日期": positions["买入日期"],
        "买入价": positions["平均成本"],
        "数量": positions["数量"],
        "当前价": positions["当前价"],
        "MA5": positions["MA5"],
        "跌破MA5天数": positions["跌破MA5天数"] if "跌破MA5天数" in positions else 0,
        "备注": "由交易记录自动生成",
    })
    return out[HOLDING_COLUMNS]


def closed_trades_from_flow(trades: pd.DataFrame) -> pd.DataFrame:
    flow = ensure_trade_columns(trades)
    if flow.empty:
        return pd.DataFrame(columns=CLOSED_TRADE_COLUMNS)

    states: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for _, trade in flow.iterrows():
        code = clean_code(trade.get("代码"))
        state = states.setdefault(
            code,
            {"qty": 0.0, "cost": 0.0, "first_buy": trade["日期"], "name": trade.get("名称", "")},
        )
        qty = number_or(trade.get("数量"))
        price = number_or(trade.get("价格"))
        amount = number_or(trade.get("金额"), price * qty)
        fee = number_or(trade.get("手续费"))
        tax = number_or(trade.get("印花税"))
        transfer_fee = number_or(trade.get("过户费"))
        total_fee = number_or(trade.get("总费用"), fee + tax + transfer_fee)
        if trade["类型"] == "买入":
            if state["qty"] <= 0:
                state["first_buy"] = trade["日期"]
                state["cost"] = 0.0
                state["qty"] = 0.0
            state["qty"] += qty
            state["cost"] += amount + total_fee
            if str(trade.get("名称", "")).strip():
                state["name"] = trade.get("名称", "")
            continue

        sell_qty = min(qty, state["qty"])
        if sell_qty <= 0:
            continue
        avg_cost = state["cost"] / state["qty"] if state["qty"] else 0.0
        realized = (price - avg_cost) * sell_qty - total_fee
        return_pct = realized / (avg_cost * sell_qty) * 100 if avg_cost and sell_qty else 0.0
        buy_date = date_or_today(state["first_buy"])
        sell_date = date_or_today(trade["日期"])
        rows.append({
            "买入日期": buy_date.date().isoformat(),
            "卖出日期": sell_date.date().isoformat(),
            "代码": code,
            "名称": state.get("name") or trade.get("名称", ""),
            "买入均价": avg_cost,
            "卖出价": price,
            "数量": int(sell_qty),
            "收益金额": realized,
            "收益率%": return_pct,
            "持仓天数": max(0, int((sell_date.normalize() - buy_date.normalize()).days)),
            "备注": trade.get("备注", ""),
        })
        state["qty"] -= sell_qty
        state["cost"] -= avg_cost * sell_qty
        if state["qty"] <= 0:
            state["qty"] = 0.0
            state["cost"] = 0.0

    return pd.DataFrame(rows, columns=CLOSED_TRADE_COLUMNS)


def asset_curve_from_trades(trades: pd.DataFrame, initial_capital: float) -> pd.DataFrame:
    flow = ensure_trade_columns(trades)
    if flow.empty:
        return pd.DataFrame(columns=["日期", "现金", "当日交易金额", "累计投入"])

    cash = float(initial_capital)
    rows: list[dict[str, Any]] = []
    for day, group in flow.groupby(flow["日期"].dt.date):
        day_amount = 0.0
        for _, trade in group.iterrows():
            amount = number_or(trade.get("金额"), number_or(trade.get("价格")) * number_or(trade.get("数量")))
            fee = number_or(trade.get("手续费"))
            tax = number_or(trade.get("印花税"))
            transfer_fee = number_or(trade.get("过户费"))
            total_fee = number_or(trade.get("总费用"), fee + tax + transfer_fee)
            if trade["类型"] == "买入":
                cash -= amount + total_fee
                day_amount -= amount + total_fee
            else:
                cash += amount - total_fee
                day_amount += amount - total_fee
        rows.append({"日期": day.isoformat(), "现金": cash, "当日交易金额": day_amount, "累计投入": float(initial_capital) - cash})
    return pd.DataFrame(rows)


def max_drawdown(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return 0.0
    running_max = numeric.cummax()
    drawdown = (numeric - running_max) / running_max * 100
    return float(drawdown.min())
