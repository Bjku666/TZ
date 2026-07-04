from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.services import review_service

router = APIRouter(prefix="/api", tags=["review"])


@router.get("/review/today")
def get_today_review(
    mode: str | None = Query(default=None),
    asOfDate: str | None = Query(default=None),
) -> dict[str, Any]:
    return review_service.today_review(mode, asOfDate)


@router.post("/review/save")
def save_review(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return review_service.save_report(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reports/audit")
def get_report_audit(mode: str | None = Query(default=None)) -> dict[str, Any]:
    return review_service.audit(mode)


@router.get("/reports/list")
def get_reports(type: str = Query(default="daily")) -> dict[str, Any]:
    return review_service.list_reports(type)


@router.get("/reports/context")
def get_report_context(
    mode: str | None = Query(default=None),
    asOfDate: str | None = Query(default=None),
) -> dict[str, Any]:
    return review_service.context(mode, asOfDate)


@router.post("/reports/save")
def save_report_compat(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return review_service.save_report(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
