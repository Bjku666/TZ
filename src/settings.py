from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_FILE = ROOT / "data" / "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "account_mode": "模拟训练",
    "simulation_capital": 10000,
    "live_capital": 5000,
    "lot_size": 100,
    "max_position_pct": 100,
    "allow_high_price": False,
    "allow_unaffordable_watchlist": False,
    "history_source": "本地缓存 + AKShare",
    "quote_source": "自动切换",
    "quote_refresh_mode": "60秒",
    "quote_refresh_seconds": 60,
    "auto_pool_size": 30,
    "commission_rate": 0.00025,
    "min_commission": 5.0,
    "stamp_tax_rate": 0.0005,
    "transfer_fee_rate": 0.00001,
    "use_min_commission": True,
    "auto_calculate_fees": True,
}


def load_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_SETTINGS.copy()
    return {**DEFAULT_SETTINGS, **saved}


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
