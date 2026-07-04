from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from backend.services import portfolio_service
from src.portfolio import build_positions_from_trades
from src.trading_calendar import SHANGHAI_TZ, current_market_phase, next_trading_day


def _trade(day: str, quantity: int, side: str = "买入") -> dict[str, object]:
    return {
        "账户模式": "模拟训练",
        "代码": "600176",
        "名称": "中国巨石",
        "类型": side,
        "日期": day,
        "时间": "10:00:00",
        "价格": 10,
        "数量": quantity,
        "金额": quantity * 10,
        "手续费": 0,
        "印花税": 0,
        "过户费": 0,
        "总费用": 0,
    }


def _positions(trades: list[dict[str, object]], operation_date: str) -> pd.DataFrame:
    return build_positions_from_trades(
        pd.DataFrame(trades),
        pd.DataFrame(),
        pd.DataFrame(),
        as_of_date=operation_date,
    )


def test_friday_buy_remains_locked_over_weekend() -> None:
    saturday = _positions([_trade("2026-07-03", 100)], "2026-07-04").iloc[0]
    sunday = _positions([_trade("2026-07-03", 100)], "2026-07-05").iloc[0]
    monday = _positions([_trade("2026-07-03", 100)], "2026-07-06").iloc[0]

    assert saturday["今日买入数量"] == 0
    assert saturday["可卖数量"] == 0
    assert saturday["T1锁定数量"] == 100
    assert sunday["可卖数量"] == 0
    assert monday["可卖数量"] == 100
    assert monday["T1锁定数量"] == 0
    assert next_trading_day(date(2026, 7, 3)) == date(2026, 7, 6)


def test_old_position_and_today_addition_are_partially_locked() -> None:
    row = _positions(
        [_trade("2026-07-02", 100), _trade("2026-07-03", 100)],
        "2026-07-03",
    ).iloc[0]

    assert row["数量"] == 200
    assert row["可卖数量"] == 100
    assert row["今日买入数量"] == 100
    assert row["T1锁定数量"] == 100


def test_market_phase_distinguishes_weekend_premarket_and_trading() -> None:
    assert current_market_phase(datetime(2026, 7, 4, 10, tzinfo=SHANGHAI_TZ)) == "weekend"
    assert current_market_phase(datetime(2026, 7, 6, 8, tzinfo=SHANGHAI_TZ)) == "pre_market"
    assert current_market_phase(datetime(2026, 7, 6, 10, tzinfo=SHANGHAI_TZ)) == "trading"


def test_execution_status_does_not_call_old_position_today_buy() -> None:
    row = _positions([_trade("2026-07-03", 100)], "2026-07-04").iloc[0]
    status = portfolio_service._position_execution_status(row, date(2026, 7, 4))

    assert status["isTodayBuy"] is False
    assert status["isT1Locked"] is True
    assert status["nextSellableTradeDate"] == "2026-07-06"
    assert status["marketPhase"] == "weekend"
    assert status["canExecuteSellNow"] is False
    assert "休市" in status["sellBlockedReason"]
