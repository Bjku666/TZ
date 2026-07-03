from __future__ import annotations

from typing import Any

from src.settings import load_settings, save_settings

from backend.storage.csv_adapter import frontend_settings, settings_from_frontend
from backend.storage.sqlite_store import save_kv


def get_settings() -> dict[str, Any]:
    return frontend_settings(load_settings())


def update_settings(updates: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    merged = settings_from_frontend(current, updates)
    save_settings(merged)
    api_settings = frontend_settings(merged)
    save_kv("settings", api_settings)
    return api_settings


def current_mode() -> str:
    return str(get_settings().get("currentMode", "simulation"))


def account_mode_name(mode: str | None = None) -> str:
    active = mode or current_mode()
    return "实盘记录" if active == "real" else "模拟训练"


def initial_cash(mode: str | None = None) -> float:
    settings = get_settings()
    active = mode or str(settings.get("currentMode", "simulation"))
    if active == "real":
        return float(settings.get("realInitialCash", 5000) or 5000)
    return float(settings.get("initialCash", 10000) or 10000)

