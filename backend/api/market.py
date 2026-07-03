from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.services.history_service import history_for_api
from backend.services.market_service import quotes_for_codes
from backend.services.risk_service import (
    load_external_market_context,
    refresh_external_market_context,
    save_external_market_context,
)

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/history/{code}")
def get_history(code: str) -> dict[str, Any]:
    return history_for_api(code)


@router.post("/market/quotes")
def get_quotes(payload: dict[str, Any]) -> dict[str, Any]:
    return quotes_for_codes(payload.get("codes") or [], payload.get("source") or "自动切换")


@router.get("/market/context")
def get_market_context() -> dict[str, Any]:
    return {"context": load_external_market_context()}


@router.post("/market/context")
def update_market_context(payload: dict[str, Any]) -> dict[str, Any]:
    context = save_external_market_context(
        indexes=payload.get("indexes") or [],
        sectors=payload.get("sectors") or [],
        stock_sectors=payload.get("stockSectors") or payload.get("stockSectorsMap") or {},
        source=str(payload.get("source") or "manual"),
    )
    return {"success": True, "context": context}


@router.post("/market/context/refresh")
def refresh_market_context() -> dict[str, Any]:
    return refresh_external_market_context()
