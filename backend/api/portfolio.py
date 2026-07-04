from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from backend.services.portfolio_service import defer_position_exit, portfolio_snapshot

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.get("/portfolio")
def get_portfolio(
    mode: str | None = Query(default=None),
    asOfDate: str | None = Query(default=None),
) -> dict[str, Any]:
    return portfolio_snapshot(mode, persist_risk_state=True, as_of_date=asOfDate)


@router.get("/account")
def get_account(
    mode: str | None = Query(default=None),
    asOfDate: str | None = Query(default=None),
) -> dict[str, Any]:
    return portfolio_snapshot(mode, persist_risk_state=True, as_of_date=asOfDate)["accountState"]


@router.post("/positions/{code}/defer-exit")
def defer_exit(code: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return defer_position_exit(code, payload or {})
