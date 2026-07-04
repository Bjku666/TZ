from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.storage import safe_write_text

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_FILE = ROOT / "data" / "settings.json"

FEE_PROFILE_THS_SIMULATION = "ths_simulation"
FEE_PROFILE_REAL_A_SHARE = "real_a_share"
FEE_PROFILES = {
    FEE_PROFILE_THS_SIMULATION,
    FEE_PROFILE_REAL_A_SHARE,
}

ZERO_FEE_DEFAULTS: dict[str, float] = {
    "commission_rate": 0.0,
    "min_commission": 0.0,
    "stamp_tax_rate": 0.0,
    "transfer_fee_rate": 0.0,
}

FEE_DEFAULTS: dict[str, float] = {
    "commission_rate": 0.00025,
    "min_commission": 5.0,
    "stamp_tax_rate": 0.0005,
    "transfer_fee_rate": 0.00001,
}

FEE_API_ALIASES: dict[str, str] = {
    "commissionRate": "commission_rate",
    "minCommission": "min_commission",
    "stampDutyRate": "stamp_tax_rate",
    "transferFeeRate": "transfer_fee_rate",
}

MODE_PREFIXES = ("simulation", "live")

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
    "quote_refresh_mode": "手动",
    "quote_refresh_seconds": 60,
    "auto_pool_size": 30,
    "fee_profile": FEE_PROFILE_THS_SIMULATION,
    "commission_rate": ZERO_FEE_DEFAULTS["commission_rate"],
    "min_commission": ZERO_FEE_DEFAULTS["min_commission"],
    "stamp_tax_rate": ZERO_FEE_DEFAULTS["stamp_tax_rate"],
    "transfer_fee_rate": ZERO_FEE_DEFAULTS["transfer_fee_rate"],
    "simulation_fee_profile": FEE_PROFILE_THS_SIMULATION,
    "simulation_commission_rate": ZERO_FEE_DEFAULTS["commission_rate"],
    "simulation_min_commission": ZERO_FEE_DEFAULTS["min_commission"],
    "simulation_stamp_tax_rate": ZERO_FEE_DEFAULTS["stamp_tax_rate"],
    "simulation_transfer_fee_rate": ZERO_FEE_DEFAULTS["transfer_fee_rate"],
    "live_fee_profile": FEE_PROFILE_REAL_A_SHARE,
    "live_commission_rate": FEE_DEFAULTS["commission_rate"],
    "live_min_commission": FEE_DEFAULTS["min_commission"],
    "live_stamp_tax_rate": FEE_DEFAULTS["stamp_tax_rate"],
    "live_transfer_fee_rate": FEE_DEFAULTS["transfer_fee_rate"],
    "use_min_commission": True,
    "auto_calculate_fees": True,
}


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fee_prefix_for_mode(mode: Any) -> str:
    text = str(mode or "").strip()
    return "live" if text in {"real", "live", "实盘记录"} else "simulation"


def _default_fee_profile(prefix: str) -> str:
    return FEE_PROFILE_REAL_A_SHARE if prefix == "live" else FEE_PROFILE_THS_SIMULATION


def normalize_fee_profile(value: Any, prefix: str = "simulation") -> str:
    profile = str(value or "").strip()
    if profile in FEE_PROFILES:
        return profile
    return _default_fee_profile(prefix)


def _fee_values_are_zero(values: dict[str, float]) -> bool:
    return all(abs(float(values.get(key, 0.0))) < 1e-12 for key in FEE_DEFAULTS)


def profile_from_fee_values(values: dict[str, Any], prefix: str = "simulation") -> str:
    fees = {key: _number(values.get(key), 0.0) for key in FEE_DEFAULTS}
    return FEE_PROFILE_THS_SIMULATION if _fee_values_are_zero(fees) else FEE_PROFILE_REAL_A_SHARE


def api_mode_from_account_mode(account_mode: Any) -> str:
    return "real" if str(account_mode or "").strip() == "实盘记录" else "simulation"


def account_mode_from_api(mode: Any) -> str:
    return "实盘记录" if str(mode or "").strip() in {"real", "live", "实盘记录"} else "模拟训练"


def mode_fee_settings(settings: dict[str, Any], mode: Any | None = None) -> dict[str, Any]:
    prefix = fee_prefix_for_mode(mode if mode is not None else settings.get("account_mode"))
    profile = normalize_fee_profile(settings.get(f"{prefix}_fee_profile"), prefix)
    defaults = ZERO_FEE_DEFAULTS if profile == FEE_PROFILE_THS_SIMULATION else FEE_DEFAULTS
    fees = {
        key: _number(settings.get(f"{prefix}_{key}"), default)
        for key, default in defaults.items()
    }
    return fees | {"fee_profile": profile_from_fee_values(fees, prefix)}


def _legacy_fee_value(settings: dict[str, Any], key: str, default: float) -> float:
    for api_key, internal_key in FEE_API_ALIASES.items():
        if internal_key == key and api_key in settings:
            return _number(settings.get(api_key), default)
    return _number(settings.get(key), default)


def normalize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    out = {**DEFAULT_SETTINGS, **settings}
    out["currentMode"] = api_mode_from_account_mode(out.get("account_mode"))
    active_prefix = fee_prefix_for_mode(out.get("account_mode"))
    legacy_profile = settings.get("feeProfile") or settings.get("fee_profile")
    explicit_profile: dict[str, bool] = {}
    for prefix in MODE_PREFIXES:
        profile_key = f"{prefix}_fee_profile"
        explicit_profile[prefix] = profile_key in settings and settings.get(profile_key) is not None
        profile_value = settings.get(profile_key)
        if profile_value is None and prefix == active_prefix:
            profile_value = legacy_profile
        out[profile_key] = normalize_fee_profile(profile_value, prefix)

    for prefix in MODE_PREFIXES:
        defaults = ZERO_FEE_DEFAULTS if out[f"{prefix}_fee_profile"] == FEE_PROFILE_THS_SIMULATION else FEE_DEFAULTS
        for key, default in defaults.items():
            mode_key = f"{prefix}_{key}"
            if prefix == "simulation" and not explicit_profile[prefix]:
                out[mode_key] = ZERO_FEE_DEFAULTS[key]
            elif mode_key not in settings or settings.get(mode_key) is None:
                out[mode_key] = _legacy_fee_value(settings, key, default)
            else:
                out[mode_key] = _number(settings.get(mode_key), default)
        out[f"{prefix}_fee_profile"] = profile_from_fee_values(
            {key: out.get(f"{prefix}_{key}") for key in FEE_DEFAULTS},
            prefix,
        )

    active_fees = mode_fee_settings(out)
    out["fee_profile"] = active_fees["fee_profile"]
    out.update(active_fees)
    out["feeProfile"] = active_fees["fee_profile"]
    for api_key, internal_key in FEE_API_ALIASES.items():
        out[api_key] = active_fees[internal_key]
    return out


def load_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return normalize_settings(DEFAULT_SETTINGS.copy())
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return normalize_settings(DEFAULT_SETTINGS.copy())
    return normalize_settings(saved)


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_settings(settings)
    safe_write_text(SETTINGS_FILE, json.dumps(normalized, ensure_ascii=False, indent=2))
