from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.services import workspace_service as service
from backend.services.strategy_rules import list_strategies, validate_strategy
from backend.storage import account_store as store

router = APIRouter(prefix="/api/accounts/{mode}", tags=["account-workspace"])


def _handle(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workspace")
def get_workspace(mode: str, strategy: str | None = None) -> dict[str, Any]:
    return _handle(service.workspace, mode, strategy)


@router.post("/refresh")
def refresh_workspace(mode: str, strategy: str | None = None) -> dict[str, Any]:
    return _handle(service.workspace, mode, strategy)


@router.get("/strategies")
def get_strategies(mode: str) -> list[dict[str, Any]]:
    _handle(store.validate_mode, mode)
    return list_strategies()


@router.post("/trades")
def create_trade(mode: str, payload: dict[str, Any], strategy: str | None = None) -> dict[str, Any]:
    return _handle(service.create_trade, mode, payload, strategy)


@router.put("/trades/{trade_id}")
def update_trade(mode: str, trade_id: str, payload: dict[str, Any], strategy: str | None = None) -> dict[str, Any]:
    return _handle(service.update_trade, mode, trade_id, payload, strategy)


@router.delete("/trades/{trade_id}")
def delete_trade(mode: str, trade_id: str, strategy: str | None = None) -> dict[str, Any]:
    return _handle(service.delete_trade, mode, trade_id, strategy)


@router.post("/trades/recalculate-fees")
def recalculate_fees(mode: str, strategy: str | None = None) -> dict[str, Any]:
    return _handle(service.recalculate_fees, mode, strategy)


@router.get("/securities/{code}")
def lookup_security(mode: str, code: str, strategy: str | None = None) -> dict[str, Any]:
    return _handle(service.lookup_security, mode, code, strategy)


@router.put("/settings")
def update_settings(mode: str, payload: dict[str, Any], strategy: str | None = None) -> dict[str, Any]:
    return _handle(service.update_settings, mode, payload, strategy)


@router.get("/settings")
def get_settings(mode: str) -> dict[str, Any]:
    _handle(store.validate_mode, mode)
    return service.app_settings()


@router.post("/positions/{code}/defer-exit")
def defer_position(mode: str, code: str, payload: dict[str, Any] | None = None, strategy: str | None = None) -> dict[str, Any]:
    payload = payload or {}
    return _handle(service.defer_position, mode, code, str(payload.get("reason", "")), strategy)


@router.delete("/positions/{code}/defer-exit")
def cancel_defer(mode: str, code: str, strategy: str | None = None) -> dict[str, Any]:
    return _handle(service.cancel_defer, mode, code, strategy)


@router.post("/positions/{code}/notes")
def add_note(mode: str, code: str, payload: dict[str, Any], strategy: str | None = None) -> dict[str, Any]:
    return _handle(service.add_note, mode, code, str(payload.get("note", "")), strategy)


@router.post("/reviews")
def save_review(mode: str, payload: dict[str, Any], strategy: str | None = None) -> dict[str, Any]:
    return _handle(service.save_review, mode, payload, strategy)


@router.get("/reviews")
def list_reviews(mode: str, strategy: str | None = None) -> list[dict[str, Any]]:
    return _handle(store.list_reviews, mode, strategy)


@router.put("/notifications/{notification_id}/read")
def mark_notification(mode: str, notification_id: str, strategy: str | None = None) -> dict[str, Any]:
    _handle(store.validate_mode, mode)
    _handle(validate_strategy, strategy)
    store.mark_notification(mode, notification_id, strategy)
    return {"notifications": store.list_notifications(mode, strategy)}


@router.post("/notifications/read-all")
def mark_all_notifications(mode: str, strategy: str | None = None) -> dict[str, Any]:
    _handle(store.validate_mode, mode)
    _handle(validate_strategy, strategy)
    store.mark_all_notifications(mode, strategy)
    return {"notifications": store.list_notifications(mode, strategy)}


@router.delete("/notifications")
def clear_notifications(mode: str, strategy: str | None = None) -> dict[str, Any]:
    _handle(store.validate_mode, mode)
    _handle(validate_strategy, strategy)
    store.clear_notifications(mode, strategy)
    return {"notifications": []}
