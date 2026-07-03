from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.services.settings_service import get_settings, update_settings

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def read_settings() -> dict[str, Any]:
    return get_settings()


@router.post("/settings")
def write_settings(payload: dict[str, Any]) -> dict[str, Any]:
    return update_settings(payload)


@router.post("/account/settings")
def write_account_settings(payload: dict[str, Any]) -> dict[str, Any]:
    initial_cash = payload.get("initialCash")
    if not isinstance(initial_cash, (int, float)) or initial_cash <= 0:
        raise HTTPException(status_code=400, detail="初始资金输入有误")
    settings = get_settings()
    if settings.get("currentMode") == "real":
        updated = update_settings({"realInitialCash": initial_cash})
    else:
        updated = update_settings({"initialCash": initial_cash})
    return {"success": True, "settings": updated, "initialCash": initial_cash}

