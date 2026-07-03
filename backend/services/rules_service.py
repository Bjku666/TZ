from __future__ import annotations

from typing import Any

from src.trading_rules_config import trading_rules_config


def rules_config() -> dict[str, Any]:
    return {
        "version": "strong-pullback-v1",
        "config": trading_rules_config(),
    }
