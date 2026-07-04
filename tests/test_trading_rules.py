from __future__ import annotations

from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from backend.services.risk_service import market_trade_filter_for_watchlist
from backend.services.trade_service import _audit_buy, _audit_sell
from src.portfolio import _below_ma5_days_for_snapshot


class TradeAuditTests(TestCase):
    def test_loss_limit_is_not_video_original_sell_trigger(self) -> None:
        conclusion, tags = _audit_sell(
            {
                "quantity": 100,
                "availableQuantity": 100,
                "currentPrice": 8,
                "avgCost": 10,
                "ma5": 0,
                "deviation5": 0,
                "belowMa5Days": 0,
                "holdDays": 5,
            },
            quantity=100,
            reason="浮亏风险提示",
            account_initial_cash=10000,
        )

        self.assertNotEqual(conclusion, "符合规则")
        self.assertIn("未对应视频原版隔日卖出提醒", tags)

    def test_buy_window_boundary_allows_930_with_candidate(self) -> None:
        stock = {
            "historyStatus": "已有缓存",
            "stage": "BUY_READY",
            "canBuy": True,
            "candidateCycleId": "C1",
            "selectionBatchId": "B1",
            "selectionDate": "2026-07-02",
            "eligibleFrom": "2026-07-03",
            "deviation5": 0.2,
            "ma5": 10,
            "quoteAgeSeconds": 0,
        }

        with patch("backend.services.trade_service.sqlite_store.active_candidate_for_code", return_value=None):
            conclusion, tags, _context = _audit_buy(
                stock,
                "600000",
                "测试股票",
                price=10.02,
                quantity=100,
                available_cash=10000,
                account_initial_cash=10000,
                estimated_sell_fee=5,
                now=datetime(2026, 7, 3, 9, 30),
            )

        self.assertEqual(conclusion, "符合规则")
        self.assertEqual(tags, [])

    def test_market_risk_does_not_cancel_video_buy_signal(self) -> None:
        stock = {
            "candidateCycleId": "C1",
            "selectionBatchId": "B1",
            "selectionDate": "2026-07-02",
            "eligibleFrom": "2026-07-03",
            "ma5": 10,
            "quoteAgeSeconds": 0,
        }
        with patch("backend.services.trade_service.sqlite_store.active_candidate_for_code", return_value=None):
            conclusion, tags, context = _audit_buy(
                stock,
                "000725",
                "京东方A",
                price=10,
                quantity=100,
                available_cash=10000,
                account_initial_cash=10000,
                estimated_sell_fee=5,
                now=datetime(2026, 7, 3, 14, 30),
                market_risk=True,
                market_risk_reasons=["大盘弱"],
            )

        self.assertEqual(conclusion, "符合规则")
        self.assertEqual(tags, [])
        self.assertTrue(context["signalQualified"])
        self.assertEqual(context["marketRiskReasons"], ["大盘弱"])

    def test_auto_market_filter_blocks_weak_market(self) -> None:
        watchlist = [
            {"code": "600001", "name": "测试A", "price": 9, "ma5": 10, "pct": -1, "volume": 1},
            {"code": "600002", "name": "测试B", "price": 8, "ma5": 10, "pct": -2, "volume": 1},
            {"code": "600003", "name": "测试C", "price": 11, "ma5": 10, "pct": -0.5, "volume": 1},
        ]

        result = market_trade_filter_for_watchlist(watchlist, "600001")

        self.assertFalse(result["allowed"])
        self.assertTrue(result["marketRisk"])
        self.assertIn("大盘弱", result["reasons"])


class BelowMa5Tests(TestCase):
    def test_below_ma5_days_prefers_recent_trading_history(self) -> None:
        history = pd.DataFrame(
            {
                "日期": pd.to_datetime(["2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02", "2026-07-03"]),
                "收盘": [10.3, 10.2, 9.9, 9.8, 9.7],
                "MA5": [10, 10, 10, 10, 10],
            }
        )
        state: dict[str, dict[str, object]] = {}

        with patch("src.portfolio.load_cached_history", return_value=history):
            days = _below_ma5_days_for_snapshot(
                "600000",
                deviation=-3,
                context_days=1,
                current_price=9.7,
                ma5=10,
                today=pd.Timestamp("2026-07-04"),
                state=state,
                persist=True,
            )

        self.assertEqual(days, 3)
        self.assertEqual(state["600000"]["below_ma5_days"], 3)
        self.assertEqual(state["600000"]["source"], "history")
