from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TZ_DATA_DIR", str(tmp_path))
    import backend.storage.account_store as account_store
    import backend.main as main

    importlib.reload(account_store)
    importlib.reload(main)
    return TestClient(main.create_app())


def trade_payload(**overrides):
    payload = {
        "code": "002594",
        "name": "比亚迪",
        "type": "BUY",
        "date": "2026-07-08",
        "time": "14:35:00",
        "price": 100.0,
        "quantity": 100,
        "amount": 10000.0,
        "commission": 0,
        "stampDuty": 0,
        "transferFee": 0,
        "totalFee": 0,
        "reason": "回踩后人工确认",
        "remark": "测试",
        "rulesConclusion": "符合规则",
        "violationTags": [],
        "historicalBackfill": True,
        "manualFeeOverride": False,
    }
    payload.update(overrides)
    return payload


def test_health_and_removed_legacy_api(client: TestClient):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["contract"] == "account-workspace-v3"
    assert client.get("/api/selection/latest").status_code == 404
    assert client.get("/api/candidates").status_code == 404
    assert client.get("/api/market/quotes").status_code == 404


def test_simulation_and_real_are_isolated(client: TestClient):
    response = client.post("/api/accounts/simulation/trades", json=trade_payload())
    assert response.status_code == 200
    assert len(response.json()["trades"]) == 1
    assert len(response.json()["positions"]) == 1

    real = client.get("/api/accounts/real/workspace")
    assert real.status_code == 200
    assert real.json()["trades"] == []
    assert real.json()["positions"] == []
    assert real.json()["account"]["availableCash"] == 5000


def test_account_specific_settings_do_not_leak(client: TestClient):
    current = client.get("/api/accounts/simulation/workspace").json()["settings"]
    current["simulation"]["initialCash"] = 300000
    response = client.put("/api/accounts/simulation/settings", json=current)
    assert response.status_code == 200
    assert response.json()["account"]["initialCash"] == 300000

    real = client.get("/api/accounts/real/workspace").json()
    assert real["account"]["initialCash"] == 5000


def test_trade_update_delete_and_fee_recalculation(client: TestClient):
    created = client.post("/api/accounts/simulation/trades", json=trade_payload()).json()
    trade = created["trades"][0]
    trade["price"] = 101
    updated = client.put(f"/api/accounts/simulation/trades/{trade['id']}", json=trade)
    assert updated.status_code == 200
    assert updated.json()["trades"][0]["amount"] == 10100

    recalculated = client.post("/api/accounts/simulation/trades/recalculate-fees", json={})
    assert recalculated.status_code == 200
    assert recalculated.json()["trades"][0]["totalFee"] > 0

    deleted = client.delete(f"/api/accounts/simulation/trades/{trade['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["trades"] == []


def test_defer_note_review_and_notifications_are_mode_scoped(client: TestClient):
    buy = trade_payload(date="2026-07-01")
    created = client.post("/api/accounts/simulation/trades", json=buy)
    assert created.status_code == 200

    deferred = client.post("/api/accounts/simulation/positions/002594/defer-exit", json={"reason": "等待尾盘确认"})
    assert deferred.status_code == 200
    assert deferred.json()["positions"][0]["status"] in {"已延迟至尾盘", "尾盘待处理"}

    noted = client.post("/api/accounts/simulation/positions/002594/notes", json={"note": "只观察计划内信号"})
    assert noted.status_code == 200
    assert any("只观察计划内信号" in item for item in noted.json()["positions"][0]["notes"])

    review = {
        "id": "daily-2026-07-08",
        "accountMode": "simulation",
        "type": "daily",
        "date": "2026-07-08",
        "planAndBasis": "尾盘回踩后再决定",
        "executionAndDeviation": "执行符合计划",
        "resultAndEmotion": "结果一般，但过程稳定",
        "improvementAndNextPlan": "明日 10:00 前不提前卖出",
    }
    saved = client.post("/api/accounts/simulation/reviews", json=review)
    assert saved.status_code == 200
    assert saved.json()["reviews"][0]["planAndBasis"] == review["planAndBasis"]

    real = client.get("/api/accounts/real/workspace").json()
    assert real["reviews"] == []
    assert real["notifications"] == []


def test_sell_cannot_cross_t1_or_account_boundary(client: TestClient):
    client.post("/api/accounts/simulation/trades", json=trade_payload(historicalBackfill=False, date=__import__("datetime").date.today().isoformat(), time="14:35:00"))
    sell = trade_payload(type="SELL", historicalBackfill=False, date=__import__("datetime").date.today().isoformat(), time="14:40:00")
    response = client.post("/api/accounts/simulation/trades", json=sell)
    assert response.status_code == 400
    assert "可卖数量" in response.json()["detail"]

    response_real = client.post("/api/accounts/real/trades", json=sell)
    assert response_real.status_code == 400
