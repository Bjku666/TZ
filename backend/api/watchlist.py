from __future__ import annotations

import urllib.parse
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.services import watchlist_service

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
def get_watchlist() -> dict[str, Any]:
    return watchlist_service.list_watchlist()


@router.post("/generate")
def generate_watchlist() -> dict[str, Any]:
    return watchlist_service.generate_watchlist()


@router.post("/import-file")
async def import_watchlist_file(
    request: Request,
    filename: str = "",
    fetchHistory: bool = False,
) -> dict[str, Any]:
    try:
        content = await request.body()
        uploaded_name = urllib.parse.unquote(
            filename or request.headers.get("x-filename", "") or "同花顺导入.xlsx"
        )
        return watchlist_service.import_watchlist_file(
            content,
            uploaded_name,
            fetch_history=fetchHistory,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/refresh-quotes")
def refresh_quotes() -> dict[str, Any]:
    return watchlist_service.refresh_quotes()


@router.post("/scan-turnover-changes")
def scan_turnover_changes() -> dict[str, Any]:
    return watchlist_service.scan_turnover_changes()


@router.post("/include-turnover-stock")
def include_turnover_stock(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return watchlist_service.include_turnover_stock(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/fetch-history")
def fetch_history(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return watchlist_service.fetch_history_for_watchlist(
        code=payload.get("code"),
        fetch_all=bool(payload.get("fetchAll")),
    )


@router.post("/update-stock")
def update_stock(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return watchlist_service.update_stock(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
