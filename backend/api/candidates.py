from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.storage import sqlite_store
from src.rule_models import CandidateState
from src.realtime import china_now

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


def _candidate_api(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": candidate.get("id"),
        "code": candidate.get("code"),
        "name": candidate.get("name"),
        "sourceBatchId": candidate.get("source_batch_id"),
        "selectionDate": candidate.get("selection_date"),
        "eligibleFrom": candidate.get("eligible_from"),
        "state": candidate.get("state"),
        "waitingTradeDays": candidate.get("waiting_trade_days"),
        "lastClose": candidate.get("last_close"),
        "lastMa5Close": candidate.get("last_ma5_close"),
        "lastLivePrice": candidate.get("last_live_price"),
        "lastMa5Live": candidate.get("last_ma5_live"),
        "lastDeviation": candidate.get("last_deviation"),
        "touchStartedAt": candidate.get("touch_started_at"),
        "touchDetectedAt": candidate.get("touch_detected_at"),
        "boughtTradeId": candidate.get("bought_trade_id"),
        "invalidatedReason": candidate.get("invalidated_reason"),
        "createdAt": candidate.get("created_at"),
        "updatedAt": candidate.get("updated_at"),
    }


@router.get("")
def list_candidates() -> dict[str, Any]:
    rows = sqlite_store.candidate_cycles(active_only=True)
    return {"candidates": [_candidate_api(row) for row in rows]}


@router.get("/{candidate_id}/events")
def candidate_events(candidate_id: str) -> dict[str, Any]:
    return {"events": sqlite_store.candidate_events(candidate_id)}


@router.post("/{candidate_id}/cancel")
def cancel_candidate(candidate_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    now = china_now().replace(microsecond=0).isoformat()
    matches = [row for row in sqlite_store.candidate_cycles(active_only=True) if row.get("id") == candidate_id]
    if not matches:
        raise HTTPException(status_code=404, detail="未找到活跃候选周期")
    sqlite_store.update_candidate_cycle(
        candidate_id,
        {
            "state": CandidateState.CANCELLED.value,
            "closed_at": now,
            "invalidated_reason": str(payload.get("reason") or "用户手动取消"),
        },
    )
    sqlite_store.add_candidate_event(
        candidate_id,
        "CANDIDATE_CANCELLED",
        event_time=now,
        reason=str(payload.get("reason") or "用户手动取消"),
        payload=payload,
    )
    return {"success": True}

