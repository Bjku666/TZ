from __future__ import annotations

import urllib.parse
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.services import watchlist_service

router = APIRouter(prefix="/api/selection", tags=["selection"])


@router.get("/official/latest")
def latest_official_selection() -> dict[str, Any]:
    return watchlist_service.list_watchlist()


@router.post("/official/generate")
def generate_official_selection(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return watchlist_service.generate_official_selection_batch(
        source=payload.get("source"),
        force=bool(payload.get("force")),
    )


@router.get("/preview")
def selection_preview() -> dict[str, Any]:
    return watchlist_service.generate_intraday_preview()


@router.post("/import")
async def import_selection(request: Request, filename: str = "", asOfficial: bool = False, fetchHistory: bool = False) -> dict[str, Any]:
    try:
        content = await request.body()
        uploaded_name = urllib.parse.unquote(
            filename or request.headers.get("x-filename", "") or "同花顺导入.xlsx"
        )
        return watchlist_service.import_watchlist_file(
            content,
            uploaded_name,
            fetch_history=fetchHistory,
            as_official=asOfficial,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

