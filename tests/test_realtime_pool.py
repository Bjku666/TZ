from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from src import realtime


def eastmoney_row(code: str, amount: int) -> dict[str, object]:
    return {
        "f12": code,
        "f14": f"测试{code}",
        "f2": 10,
        "f3": 1.2,
        "f6": amount,
        "f17": 9.8,
        "f18": 9.7,
        "f15": 10.2,
        "f16": 9.6,
    }


def quote_frame(count: int) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "代码": [f"600{i:03d}" for i in range(count)],
            "名称": [f"测试{i}" for i in range(count)],
            "最新价": [10 + i / 100 for i in range(count)],
            "涨跌幅%": [1.0 for _ in range(count)],
            "成交额": [10_000_000 - i for i in range(count)],
        }
    )
    for column in realtime.QUOTE_COLUMNS:
        if column not in frame:
            frame[column] = pd.NA
    return realtime._with_status(frame[realtime.QUOTE_COLUMNS], "东方财富", "成交额榜测试数据")


class RealtimePoolTests(TestCase):
    def test_turnover_rank_fetches_small_pages_until_enough_main_board_candidates(self) -> None:
        page1 = {
            "data": {
                "total": 90,
                "diff": [eastmoney_row(f"300{i:03d}", 20_000_000 - i) for i in range(30)],
            }
        }
        page2 = {
            "data": {
                "total": 90,
                "diff": [eastmoney_row(f"600{i:03d}", 10_000_000 - i) for i in range(30)],
            }
        }

        with (
            patch.object(realtime, "EASTMONEY_SPOT_HOSTS", ["push2.test"]),
            patch.object(
                realtime,
                "_eastmoney_turnover_rank_request",
                side_effect=[page1, page2],
            ) as request,
        ):
            frame = realtime.fetch_turnover_rank_quotes_eastmoney(limit=30, page_size=30, max_pages=3)

        self.assertFalse(frame.empty)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[0].kwargs["page"], 1)
        self.assertEqual(request.call_args_list[1].kwargs["page"], 2)
        self.assertIn("分页扫描 60 条", frame.attrs["message"])

    def test_auto_stock_pool_uses_turnover_rank_without_full_market_fallback(self) -> None:
        rank_quotes = quote_frame(30)

        with (
            patch.object(realtime, "fetch_turnover_rank_quotes_eastmoney", return_value=rank_quotes),
            patch.object(realtime, "fetch_full_market_quotes") as full_market,
            patch.object(realtime, "fetch_full_market_quotes_akshare") as akshare_market,
        ):
            pool = realtime.fetch_auto_stock_pool(limit=30, source="自动切换")

        self.assertEqual(len(pool), 30)
        self.assertEqual(pool["成交额排名"].tolist(), list(range(1, 31)))
        full_market.assert_not_called()
        akshare_market.assert_not_called()

    def test_auto_stock_pool_does_not_generate_partial_pool(self) -> None:
        partial_quotes = quote_frame(12)
        empty_fallback = realtime._empty_full_quotes("AKShare 失败", "AKShare")

        with (
            patch.object(realtime, "fetch_turnover_rank_quotes_eastmoney", return_value=partial_quotes),
            patch.object(realtime, "fetch_full_market_quotes_akshare", return_value=empty_fallback),
        ):
            pool = realtime.fetch_auto_stock_pool(limit=30, source="自动切换")

        self.assertTrue(pool.empty)
        self.assertIn("只获取到 12/30", pool.attrs["message"])
