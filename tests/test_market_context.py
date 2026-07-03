from __future__ import annotations

from unittest import TestCase

from backend.services.risk_service import market_risk_snapshot, market_trade_filter_for_watchlist


class MarketContextTests(TestCase):
    def test_market_snapshot_prefers_index_context_over_watchlist(self) -> None:
        watchlist = [
            {"code": "600001", "name": "强势A", "price": 11, "ma5": 10, "pct": 3},
            {"code": "600002", "name": "强势B", "price": 12, "ma5": 10, "pct": 2},
        ]
        context = {
            "updatedAt": "2026-07-03 10:00:00",
            "indexes": [
                {"code": "000001", "name": "上证指数", "pct": -1.2, "price": 2900, "ma5": 3000},
                {"code": "399001", "name": "深证成指", "pct": -0.8, "price": 9000, "ma5": 9300},
                {"code": "399006", "name": "创业板指", "pct": 0.1, "price": 1800, "ma5": 1850},
            ],
        }

        snapshot = market_risk_snapshot(watchlist, context)

        self.assertEqual(snapshot["source"], "market-indexes")
        self.assertTrue(snapshot["marketWeak"])
        self.assertEqual(snapshot["totalStocks"], 3)

    def test_trade_filter_uses_real_sector_mapping_when_available(self) -> None:
        watchlist = [
            {"code": "600001", "name": "测试科技", "price": 11, "ma5": 10, "pct": 1},
        ]
        context = {
            "indexes": [
                {"code": "000001", "name": "上证指数", "pct": 1, "price": 3100, "ma5": 3000},
                {"code": "399001", "name": "深证成指", "pct": 1, "price": 9500, "ma5": 9300},
            ],
            "sectors": [
                {"sectorName": "真实行业A", "avgChangePct": -1.5, "aboveMA5Ratio": 20},
                {"sectorName": "真实行业B", "avgChangePct": 2.0, "aboveMA5Ratio": 80},
            ],
            "stockSectors": {"600001": "真实行业A"},
        }

        result = market_trade_filter_for_watchlist(watchlist, "600001", context)

        self.assertFalse(result["allowed"])
        self.assertEqual(result["sectorName"], "真实行业A")
        self.assertIn("真实行业A弱", result["reasons"])
        self.assertEqual(result["dataSource"], "external-context")
