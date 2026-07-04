from __future__ import annotations

from datetime import datetime

import pytest

from src.rule_models import CandidateState, TouchZone
from src.video_original_rules import (
    calculate_ma5_close,
    calculate_ma5_live,
    classify_touch_zone,
    evaluate_buy_compliance,
    evaluate_candidate_state,
    evaluate_next_day_exit,
    filter_raw_top20,
    is_allowed_security,
    is_buy_window,
    is_official_selection_qualified,
    next_eligible_trade_date,
    official_generation_allowed,
)


@pytest.mark.parametrize("code", ["600000", "601000", "603000", "605000", "000001", "001001", "002001", "000725"])
def test_allowed_main_board_codes_include_boe(code: str) -> None:
    assert is_allowed_security(code, "测试").allowed


@pytest.mark.parametrize(
    ("code", "name"),
    [
        ("300001", "创业测试"),
        ("301001", "创业测试"),
        ("688001", "科创测试"),
        ("689001", "科创测试"),
        ("430001", "北交测试"),
        ("830001", "北交测试"),
        ("920001", "北交测试"),
        ("600001", "ST测试"),
        ("600002", "*ST测试"),
        ("600003", "测试退"),
    ],
)
def test_excluded_security_ranges_and_names(code: str, name: str) -> None:
    assert not is_allowed_security(code, name).allowed


def test_filter_raw_top20_filters_after_cut_and_does_not_refill() -> None:
    rows = [
        {"code": f"300{i:03d}", "name": "创业", "raw_rank": i + 1, "turnover": 1000 - i, "price": 10}
        for i in range(10)
    ] + [
        {"code": f"600{i:03d}", "name": "主板", "raw_rank": i + 11, "turnover": 900 - i, "price": 10}
        for i in range(10)
    ] + [
        {"code": f"600{i:03d}", "name": "补位", "raw_rank": i + 21, "turnover": 800 - i, "price": 10}
        for i in range(10)
    ]

    result = filter_raw_top20(rows)

    assert len(result) == 20
    assert sum(1 for item in result if item["market_allowed"]) == 10
    assert all(int(item["raw_rank"]) <= 20 for item in result)


def test_ma5_close_uses_last_five_completed_closes() -> None:
    assert calculate_ma5_close([1, 2, 3, 4, 5, 6]) == 4


def test_ma5_live_uses_previous_four_closes_and_current_price() -> None:
    assert calculate_ma5_live([10, 11, 12, 13], 14) == 12


@pytest.mark.parametrize(
    ("close", "ma5", "expected"),
    [(10, 10, True), (10.01, 10, True), (9.99, 10, False)],
)
def test_official_selection_requires_close_at_or_above_ma5(close: float, ma5: float, expected: bool) -> None:
    assert is_official_selection_qualified(close, ma5) is expected


def test_friday_selection_eligible_from_next_monday() -> None:
    assert next_eligible_trade_date("2026-07-03").isoformat() == "2026-07-06"


@pytest.mark.parametrize(
    ("clock", "expected"),
    [
        ("2026-07-03T09:29:59", False),
        ("2026-07-03T09:30:00", True),
        ("2026-07-03T09:59:59", True),
        ("2026-07-03T10:00:00", False),
        ("2026-07-03T14:29:59", False),
        ("2026-07-03T14:30:00", True),
        ("2026-07-03T14:59:59", True),
        ("2026-07-03T15:00:00", False),
    ],
)
def test_video_buy_window_boundaries(clock: str, expected: bool) -> None:
    assert is_buy_window(datetime.fromisoformat(clock)) is expected


@pytest.mark.parametrize(
    ("price", "ma5", "zone"),
    [(100.5, 100, TouchZone.TOUCH), (99.5, 100, TouchZone.TOUCH), (100.51, 100, TouchZone.ABOVE), (99.49, 100, TouchZone.BELOW)],
)
def test_touch_zone_boundaries(price: float, ma5: float, zone: TouchZone) -> None:
    assert classify_touch_zone(price, ma5)["zone"] is zone


def _candidate() -> dict[str, object]:
    return {
        "id": "C1",
        "code": "600000",
        "name": "测试",
        "source_batch_id": "B1",
        "selection_date": "2026-07-02",
        "eligible_from": "2026-07-03",
        "state": "OBSERVING",
        "above_ma5": True,
    }


def test_candidate_before_eligible_date_cannot_buy() -> None:
    result = evaluate_candidate_state(_candidate(), {"price": 100, "ma5_live": 100, "quote_age_seconds": 0}, datetime(2026, 7, 2, 14, 30))
    assert result.state is CandidateState.WAITING_ELIGIBLE_DATE


def test_candidate_touch_zone_outside_window_is_not_buy_ready() -> None:
    result = evaluate_candidate_state(_candidate(), {"price": 100, "ma5_live": 100, "quote_age_seconds": 0}, datetime(2026, 7, 3, 11, 0))
    assert result.state is CandidateState.IN_TOUCH_ZONE_OUTSIDE_WINDOW
    assert not result.signal_qualified


def test_stale_quote_cannot_create_new_buy_signal() -> None:
    result = evaluate_candidate_state(_candidate(), {"price": 100, "ma5_live": 100, "quote_age_seconds": 21}, datetime(2026, 7, 3, 14, 30))
    assert not result.signal_qualified
    assert "行情数据过期，无法确认" in result.execution_block_reasons


def test_fresh_touch_quote_creates_buy_ready_signal() -> None:
    result = evaluate_candidate_state(_candidate(), {"price": 100, "ma5_live": 100, "quote_age_seconds": 0}, datetime(2026, 7, 3, 14, 30), account_cash=20000)
    assert result.state is CandidateState.BUY_READY
    assert result.signal_qualified
    assert result.execution_allowed


def test_cash_shortage_blocks_execution_but_not_signal() -> None:
    result = evaluate_candidate_state(_candidate(), {"price": 100, "ma5_live": 100, "quote_age_seconds": 0}, datetime(2026, 7, 3, 14, 30), account_cash=100)
    assert result.signal_qualified
    assert not result.execution_allowed
    assert "资金不足，买不起100股整数倍" in result.execution_block_reasons


def test_below_ma5_is_below_state() -> None:
    result = evaluate_candidate_state(_candidate(), {"price": 99.4, "ma5_live": 100, "quote_age_seconds": 0}, datetime(2026, 7, 3, 14, 30))
    assert result.state is CandidateState.BELOW_MA5


def test_above_touch_zone_keeps_observing() -> None:
    result = evaluate_candidate_state(_candidate(), {"price": 100.7, "ma5_live": 100, "quote_age_seconds": 0}, datetime(2026, 7, 3, 14, 30))
    assert result.state is CandidateState.OBSERVING


def test_buy_compliance_accepts_valid_video_signal() -> None:
    result = evaluate_buy_compliance(
        candidate=_candidate(),
        trade_datetime=datetime(2026, 7, 3, 9, 30),
        trade_price=100,
        quantity=100,
        ma5_live=100,
        quote_age_seconds=0,
        available_cash=20000,
        manual_confirmed=True,
    )
    assert result["conclusion"] == "符合规则"
    assert result["signalQualified"]
    assert result["executionAllowed"]


@pytest.mark.parametrize(
    ("quantity", "tag"),
    [(99, "数量不是100股整数倍"), (101, "数量不是100股整数倍")],
)
def test_buy_compliance_rejects_non_lot_quantities(quantity: int, tag: str) -> None:
    result = evaluate_buy_compliance(
        candidate=_candidate(),
        trade_datetime=datetime(2026, 7, 3, 9, 30),
        trade_price=100,
        quantity=quantity,
        ma5_live=100,
        quote_age_seconds=0,
        available_cash=20000,
        manual_confirmed=True,
    )
    assert tag in result["tags"]
    assert not result["executionAllowed"]


def test_historical_backfill_uses_trade_time_and_ignores_current_cash() -> None:
    result = evaluate_buy_compliance(
        candidate=_candidate(),
        trade_datetime=datetime(2026, 7, 3, 14, 59, 59),
        trade_price=100,
        quantity=100,
        ma5_live=100,
        quote_age_seconds=0,
        available_cash=0,
        manual_confirmed=True,
        is_historical=True,
    )
    assert "账户现金不足" not in result["tags"]


def test_intraday_preview_time_is_not_official_generation_time() -> None:
    assert not official_generation_allowed(datetime(2026, 7, 3, 14, 59), "2026-07-03")
    assert official_generation_allowed(datetime(2026, 7, 3, 15, 5), "2026-07-03")


def test_exit_today_buy_is_t1_locked() -> None:
    result = evaluate_next_day_exit(buy_date="2026-07-03", now=datetime(2026, 7, 3, 14, 45))
    assert result["state"] == CandidateState.BOUGHT.value
    assert "T+1" in result["message"]


def test_exit_next_day_morning_observes_limit_up() -> None:
    result = evaluate_next_day_exit(buy_date="2026-07-03", now=datetime(2026, 7, 6, 9, 45))
    assert result["state"] == CandidateState.NEXT_DAY_OBSERVING.value


def test_exit_after_ten_without_limit_up_is_due() -> None:
    result = evaluate_next_day_exit(buy_date="2026-07-03", now=datetime(2026, 7, 6, 10, 0), current_price=10, previous_close=10)
    assert result["state"] == CandidateState.MORNING_EXIT_DUE.value


def test_exit_deferred_after_1430_is_afternoon_due() -> None:
    result = evaluate_next_day_exit(buy_date="2026-07-03", now=datetime(2026, 7, 6, 14, 30), current_price=10, previous_close=10, deferred=True)
    assert result["state"] == CandidateState.AFTERNOON_EXIT_DUE.value


def test_exit_limit_up_holds_after_ten() -> None:
    result = evaluate_next_day_exit(buy_date="2026-07-03", now=datetime(2026, 7, 6, 10, 0), current_price=11, previous_close=10)
    assert result["state"] == CandidateState.LIMIT_UP_HOLD.value


def test_execution_blocked_is_not_active_rule_violation() -> None:
    result = evaluate_next_day_exit(
        buy_date="2026-07-03",
        now=datetime(2026, 7, 6, 15, 0),
        current_price=10,
        previous_close=10,
        limit_down_or_suspended=True,
    )
    assert result["executionBlocked"]
    assert not result["ruleViolation"]

