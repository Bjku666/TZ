from __future__ import annotations

from datetime import datetime
from typing import Any

from src.video_original_rules import (
    LOT_SIZE,
    QUOTE_FRESHNESS_SECONDS,
    STRATEGY_NAME,
    STRATEGY_VERSION,
    TURNOVER_TOP_N,
    buy_window_label,
    is_buy_window,
    rules_config as video_rules_config,
)

SIMULATION_CAPITAL = 10000
REAL_CAPITAL = 5000


def trading_rules_config() -> dict[str, Any]:
    """Return the read-only strategy contract plus execution defaults."""
    config = video_rules_config()
    return {
        **config,
        "simulationCapital": SIMULATION_CAPITAL,
        "realCapital": REAL_CAPITAL,
        "manualConfirmationRequired": True,
        "executionConstraints": {
            "lotSize": LOT_SIZE,
            "tPlusOne": True,
            "cashRequired": True,
            "brokerConnection": False,
            "autoOrder": False,
        },
    }


def is_allowed_buy_window(value: datetime | None) -> bool:
    return is_buy_window(value)


def active_buy_window_label(value: datetime | None) -> str:
    return buy_window_label(value)


def lot_cost(price: Any, lot_size: int = LOT_SIZE) -> float | None:
    try:
        numeric = float(price)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    return numeric * lot_size


def estimate_execution_loss_reference(
    buy_price: Any,
    quantity: Any,
    reference_price: Any,
    sell_fee: Any = 0,
) -> dict[str, float | None]:
    """Display-only loss estimate.

    Video original rules do not define a fixed stop-loss. This helper exists
    only for account risk visibility and must not be used to qualify signals.
    """
    try:
        price_f = float(buy_price)
        qty_f = float(quantity)
        ref_f = float(reference_price)
        fee_f = float(sell_fee or 0)
    except (TypeError, ValueError):
        return {"reference_price": None, "risk_per_share": None, "risk_amount": None}
    if price_f <= 0 or qty_f <= 0 or ref_f <= 0:
        return {"reference_price": None, "risk_per_share": None, "risk_amount": None}
    risk_per_share = max(0.0, price_f - ref_f)
    return {
        "reference_price": round(ref_f, 4),
        "risk_per_share": round(risk_per_share, 4),
        "risk_amount": round(risk_per_share * qty_f + max(0.0, fee_f), 2),
    }


__all__ = [
    "LOT_SIZE",
    "QUOTE_FRESHNESS_SECONDS",
    "REAL_CAPITAL",
    "SIMULATION_CAPITAL",
    "STRATEGY_NAME",
    "STRATEGY_VERSION",
    "TURNOVER_TOP_N",
    "active_buy_window_label",
    "estimate_execution_loss_reference",
    "is_allowed_buy_window",
    "lot_cost",
    "trading_rules_config",
]
