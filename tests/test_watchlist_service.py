from __future__ import annotations

from datetime import datetime
from unittest import TestCase
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd

from backend.services import watchlist_service


def locked_pool(count: int, generated_at: str = "2026-07-03 17:05:38") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "代码": [f"600{i:03d}" for i in range(count)],
            "名称": [f"测试{i}" for i in range(count)],
            "现价": [10.0 for _ in range(count)],
            "涨跌幅%": [1.0 for _ in range(count)],
            "成交额": [10_000_000 - i for i in range(count)],
            "成交额排名": list(range(1, count + 1)),
            "pool_generated_at": [generated_at for _ in range(count)],
            "is_pool_locked": [True for _ in range(count)],
        }
    )


class WatchlistServiceTests(TestCase):
    def test_generate_watchlist_keeps_current_day_locked_pool_after_trading_hours_when_sources_fail(self) -> None:
        failed_pool = pd.DataFrame()
        failed_pool.attrs["message"] = "东方财富成交额榜失败；AKShare 失败"
        cached = locked_pool(20)

        with (
            patch.object(watchlist_service, "get_settings", return_value={"quote_source": "自动切换", "auto_pool_size": 20}),
            patch.object(watchlist_service, "fetch_raw_turnover_top", return_value=failed_pool),
            patch.object(watchlist_service, "load_watchlist", return_value=cached),
            patch.object(watchlist_service, "recompute_watchlist", side_effect=lambda frame: frame),
            patch.object(watchlist_service, "_watchlist_api", return_value=[{"code": "600000"}] * 20),
            patch.object(watchlist_service, "is_a_share_trading_time", return_value=False),
            patch.object(
                watchlist_service,
                "china_now",
                return_value=datetime(2026, 7, 3, 23, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            ),
        ):
            result = watchlist_service.generate_watchlist()

        self.assertTrue(result["success"])
        self.assertTrue(result["usedCache"])
        self.assertIn("已保留最近正式初筛池 20 只", result["message"])
        self.assertIn("东方财富成交额榜失败", result["message"])

    def test_generate_watchlist_does_not_use_locked_pool_during_trading_hours_when_sources_fail(self) -> None:
        failed_pool = pd.DataFrame()
        failed_pool.attrs["message"] = "实时接口断开"
        cached = locked_pool(20)

        with (
            patch.object(watchlist_service, "get_settings", return_value={"quote_source": "自动切换", "auto_pool_size": 20}),
            patch.object(watchlist_service, "fetch_raw_turnover_top", return_value=failed_pool),
            patch.object(watchlist_service, "load_watchlist", return_value=cached),
            patch.object(watchlist_service, "_watchlist_api", return_value=[{"code": "600000"}] * 20),
            patch.object(watchlist_service, "is_a_share_trading_time", return_value=True),
        ):
            result = watchlist_service.generate_watchlist()

        self.assertFalse(result["success"])
        self.assertNotIn("usedCache", result)
        self.assertIn("当前为交易时间", result["message"])
        self.assertIn("为避免使用旧数据误判", result["message"])
        self.assertIn("实时接口断开", result["message"])

    def test_generate_watchlist_still_fails_without_complete_current_day_pool(self) -> None:
        failed_pool = pd.DataFrame()
        failed_pool.attrs["message"] = "行情源失败"
        cached = locked_pool(12)

        with (
            patch.object(watchlist_service, "get_settings", return_value={"quote_source": "自动切换", "auto_pool_size": 20}),
            patch.object(watchlist_service, "fetch_raw_turnover_top", return_value=failed_pool),
            patch.object(watchlist_service, "load_watchlist", return_value=cached),
            patch.object(watchlist_service, "_watchlist_api", return_value=[]),
            patch.object(watchlist_service, "is_a_share_trading_time", return_value=False),
            patch.object(
                watchlist_service,
                "china_now",
                return_value=datetime(2026, 7, 3, 23, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            ),
        ):
            result = watchlist_service.generate_watchlist()

        self.assertFalse(result["success"])
        self.assertNotIn("usedCache", result)
        self.assertEqual(result["message"], "行情源失败")
