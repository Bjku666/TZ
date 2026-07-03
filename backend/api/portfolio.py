from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from backend.services.portfolio_service import portfolio_snapshot

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.get("/portfolio")
def get_portfolio(mode: str | None = Query(default=None)) -> dict[str, Any]:
    return portfolio_snapshot(mode, persist_risk_state=True)


@router.get("/account")
def get_account(mode: str | None = Query(default=None)) -> dict[str, Any]:
    return portfolio_snapshot(mode, persist_risk_state=True)["accountState"]
