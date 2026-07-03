from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.services.history_service import history_for_api
from backend.services.market_service import quotes_for_codes

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/history/{code}")
def get_history(code: str) -> dict[str, Any]:
    return history_for_api(code)


@router.post("/market/quotes")
def get_quotes(payload: dict[str, Any]) -> dict[str, Any]:
    return quotes_for_codes(payload.get("codes") or [], payload.get("source") or "自动切换")

