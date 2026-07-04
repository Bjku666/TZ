from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.services.rules_service import rules_config

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("")
def get_rules() -> dict[str, Any]:
    return rules_config()


@router.get("/config")
def get_rules_config() -> dict[str, Any]:
    return rules_config()
