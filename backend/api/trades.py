from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.services import trade_service

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("")
def get_trades(mode: str | None = Query(default=None)) -> dict[str, Any]:
    return trade_service.list_trades(mode)


@router.post("/execute")
def execute_trade(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return trade_service.create_trade(payload, payload.get("mode"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/delete")
def delete_trade_compat(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return trade_service.delete_trade(str(payload.get("id") or ""), payload.get("mode"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/update")
def update_trade_compat(payload: dict[str, Any]) -> dict[str, Any]:
    trade_id = str(payload.get("id") or "")
    try:
        return trade_service.update_trade(trade_id, payload, payload.get("mode"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recalculate-fees")
def recalculate_trade_fees(mode: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        return trade_service.recalculate_trade_fees(mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("")
def create_trade(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return trade_service.create_trade(payload, payload.get("mode"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{trade_id}")
def update_trade(trade_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return trade_service.update_trade(trade_id, payload, payload.get("mode"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{trade_id}")
def delete_trade(trade_id: str, mode: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        return trade_service.delete_trade(trade_id, mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
