from __future__ import annotations

from datetime import datetime, time
from typing import Any

LOT_SIZE = 100

SIMULATION_CAPITAL = 10000
REAL_CAPITAL = 5000

TURNOVER_TOP_N = 30

BIG_CANDLE_LOOKBACK_DAYS = 20
BIG_CANDLE_THRESHOLD_PCT = 5.0

BUY_ZONE_MIN_DEVIATION_PCT = 0.0
BUY_ZONE_MAX_DEVIATION_PCT = 2.5
OBSERVE_ZONE_MAX_DEVIATION_PCT = 5.0
HIGH_ZONE_MAX_DEVIATION_PCT = 7.0

MAX_SINGLE_TRADE_RISK_PCT = 0.02
STEADY_SINGLE_TRADE_RISK_PCT = 0.01

MA5_EFFECTIVE_BREAK_PCT = 0.0
STOP_PRICE_MA5_BUFFER_PCT = 0.01

TAKE_PROFIT_WATCH_DEVIATION_PCT = 5.0
TAKE_PROFIT_PRIORITY_DEVIATION_PCT = 7.0

BUY_WINDOWS = [
    (time(9, 35), time(10, 0)),
    (time(14, 30), time(14, 55)),
]

RISK_CHECK_TIME = time(14, 50)


def is_allowed_buy_window(value: datetime | None) -> bool:
    if value is None or value.weekday() >= 5:
        return False
    current = value.time()
    return any(start <= current <= end for start, end in BUY_WINDOWS)


def lot_cost(price: Any, lot_size: int = LOT_SIZE) -> float | None:
    try:
        numeric = float(price)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    return numeric * lot_size


def stop_price_from_ma5(ma5: Any) -> float | None:
    try:
        numeric = float(ma5)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    return numeric * (1 - STOP_PRICE_MA5_BUFFER_PCT)


def estimate_single_trade_risk(
    buy_price: Any,
    quantity: Any,
    ma5: Any,
    sell_fee: Any = 0,
) -> dict[str, float | None]:
    stop_price = stop_price_from_ma5(ma5)
    try:
        price_f = float(buy_price)
        qty_f = float(quantity)
        fee_f = float(sell_fee or 0)
    except (TypeError, ValueError):
        return {
            "stop_price": stop_price,
            "risk_per_share": None,
            "risk_amount": None,
        }
    if stop_price is None or price_f <= 0 or qty_f <= 0:
        return {
            "stop_price": stop_price,
            "risk_per_share": None,
            "risk_amount": None,
        }
    risk_per_share = max(0.0, price_f - stop_price)
    risk_amount = risk_per_share * qty_f + max(0.0, fee_f)
    return {
        "stop_price": round(stop_price, 4),
        "risk_per_share": round(risk_per_share, 4),
        "risk_amount": round(risk_amount, 2),
    }
