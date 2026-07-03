from __future__ import annotations

from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from backend.services.risk_service import market_trade_filter_for_watchlist
from backend.services.trade_service import _audit_buy, _audit_sell
from src.portfolio import _below_ma5_days_for_snapshot


class TradeAuditTests(TestCase):
    def test_max_loss_sell_is_compliant_trigger(self) -> None:
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
            reason="单笔亏损达到2%风控线",
            account_initial_cash=10000,
        )

        self.assertEqual(conclusion, "符合规则")
        self.assertEqual(tags, [])

    def test_buy_window_boundary_blocks_before_935(self) -> None:
        stock = {
            "historyStatus": "已有缓存",
            "stage": "待买观察",
            "canBuy": True,
            "ma5Upward": True,
            "bigCandlePct": 6,
            "deviation5": 1.2,
            "ma5": 10,
        }

        conclusion, tags, _context = _audit_buy(
            stock,
            "600000",
            "测试股票",
            price=10.1,
            quantity=100,
            available_cash=10000,
            account_initial_cash=10000,
            estimated_sell_fee=5,
            now=datetime(2026, 7, 3, 9, 34),
        )

        self.assertIn("不在允许买入时间窗口", tags)
        self.assertEqual(conclusion, "部分不符")

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

