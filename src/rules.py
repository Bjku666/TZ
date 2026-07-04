from __future__ import annotations

import math
from typing import Any

from src.rule_models import CandidateState, TouchZone
from src.trading_rules_config import LOT_SIZE, TURNOVER_TOP_N, lot_cost
from src.video_original_rules import (
    MA5_TOUCH_TOLERANCE_PCT,
    calculate_ma5_close,
    classify_touch_zone,
    clean_code,
    filter_raw_top20,
    is_allowed_security,
    ma5_deviation,
)

PIPELINE_STAGES = [
    CandidateState.INITIAL_SCREENED.value,
    CandidateState.INITIAL_REJECTED.value,
    CandidateState.WAITING_ELIGIBLE_DATE.value,
    CandidateState.OBSERVING.value,
    CandidateState.IN_TOUCH_ZONE_OUTSIDE_WINDOW.value,
    CandidateState.BUY_READY.value,
    CandidateState.BELOW_MA5.value,
    CandidateState.BOUGHT.value,
    CandidateState.NEXT_DAY_OBSERVING.value,
    CandidateState.MORNING_EXIT_DUE.value,
    CandidateState.DEFERRED_TO_AFTERNOON.value,
    CandidateState.AFTERNOON_EXIT_DUE.value,
    CandidateState.LIMIT_UP_HOLD.value,
    CandidateState.CLOSED.value,
    CandidateState.INVALIDATED.value,
    CandidateState.CANCELLED.value,
]
GROUPS = PIPELINE_STAGES
MAIN_GROUPS = ["初筛", "观察", "待买"]
OBSERVATION_STAGES = {CandidateState.OBSERVING.value, CandidateState.IN_TOUCH_ZONE_OUTSIDE_WINDOW.value}
LEGACY_STAGE_ALIASES = {
    "初筛": CandidateState.INITIAL_SCREENED.value,
    "观察": CandidateState.OBSERVING.value,
    "待买": CandidateState.BUY_READY.value,
    "持仓": CandidateState.BOUGHT.value,
    "接近买点": CandidateState.BUY_READY.value,
    "等回踩": CandidateState.OBSERVING.value,
    "重点观察": CandidateState.OBSERVING.value,
    "资金不足观察": CandidateState.BUY_READY.value,
    "缺少历史K线": CandidateState.INITIAL_REJECTED.value,
    "初筛通过": CandidateState.INITIAL_SCREENED.value,
    "强势确认": CandidateState.OBSERVING.value,
    "继续观察": CandidateState.OBSERVING.value,
    "待买观察": CandidateState.BUY_READY.value,
    "未达规则": CandidateState.INITIAL_REJECTED.value,
    "风险排除": CandidateState.INITIAL_REJECTED.value,
    "淘汰": CandidateState.INITIAL_REJECTED.value,
}


def normalize_stage(stage: Any) -> str:
    text = str(stage or "").strip()
    if not text:
        return CandidateState.INITIAL_SCREENED.value
    return LEGACY_STAGE_ALIASES.get(text, text)


def stage_to_group(stage: Any) -> str:
    text = normalize_stage(stage)
    if text == CandidateState.BUY_READY.value:
        return "待买"
    if text in {
        CandidateState.WAITING_ELIGIBLE_DATE.value,
        CandidateState.OBSERVING.value,
        CandidateState.IN_TOUCH_ZONE_OUTSIDE_WINDOW.value,
        CandidateState.BELOW_MA5.value,
    }:
        return "观察"
    return "初筛"


def is_main_board(code: str) -> bool:
    return is_allowed_security(code, "").allowed


def screening_result(code: str, name: str) -> tuple[bool, str]:
    check = is_allowed_security(code, name)
    return check.allowed, check.reason


def is_number(value: Any) -> bool:
    try:
        return not math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def buy_signal(deviation: float | None) -> str:
    if deviation is None:
        return CandidateState.OBSERVING.value
    if deviation < -MA5_TOUCH_TOLERANCE_PCT:
        return CandidateState.BELOW_MA5.value
    if deviation <= MA5_TOUCH_TOLERANCE_PCT:
        return CandidateState.BUY_READY.value
    return CandidateState.OBSERVING.value


def affordability(price: Any, capital: float = 10000) -> tuple[bool, float | None]:
    cost = lot_cost(price, LOT_SIZE)
    if cost is None:
        return False, None
    return cost <= capital, cost


def score_stock(row: dict[str, Any]) -> tuple[int, str]:
    passed, _ = screening_result(row.get("代码", ""), row.get("名称", ""))
    rank = pool_generation_rank(row)
    above = is_official_like_above_ma5(row)
    score = int(passed) + int(is_number(rank) and float(rank) <= TURNOVER_TOP_N) + int(above)
    return score, CandidateState.INITIAL_SCREENED.value if score >= 3 else CandidateState.INITIAL_REJECTED.value


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "是", "yes", "y", "可以买"}


def recent_big_line(row: dict[str, Any]) -> bool:
    return True


def pool_generation_rank(row: dict[str, Any]) -> Any:
    rank = row.get("pool_rank_at_generation")
    return rank if is_number(rank) else row.get("成交额排名")


def recent_big_candle_pct(history: Any, lookback: int = 20) -> float | None:
    """Compatibility metric only; no longer participates in video rules."""
    try:
        import pandas as pd
    except ImportError:
        return None

    if history is None or getattr(history, "empty", True):
        return None
    if "收盘" not in history:
        return None
    close = pd.to_numeric(history.get("收盘"), errors="coerce")
    if "单日涨幅%" in history:
        daily_pct = pd.to_numeric(history.get("单日涨幅%"), errors="coerce")
    else:
        daily_pct = close.pct_change() * 100
    max_up = daily_pct.tail(lookback).max()
    return float(max_up) if pd.notna(max_up) else None


def rank_top_n(row: dict[str, Any], n: int = TURNOVER_TOP_N) -> bool:
    rank = pool_generation_rank(row)
    return is_number(rank) and float(rank) <= n


def valid_history(row: dict[str, Any]) -> bool:
    status = str(row.get("history_status", "") or "")
    if status in {"缺少历史K线", "自动获取失败", "数据不足", "缓存过旧"}:
        return False
    return is_number(row.get("MA5"))


def is_official_like_above_ma5(row: dict[str, Any]) -> bool:
    close = row.get("入选日收盘价", row.get("close_price", row.get("现价")))
    ma5 = row.get("入选日MA5", row.get("ma5_close", row.get("MA5")))
    if not is_number(close) or not is_number(ma5):
        return False
    return float(close) >= float(ma5)


def stock_stage_result(row: dict[str, Any]) -> tuple[str, str, str]:
    passed, reason = screening_result(str(row.get("代码", "")), str(row.get("名称", "")))
    if not passed:
        return CandidateState.INITIAL_REJECTED.value, reason, reason
    if not rank_top_n(row):
        return (
            CandidateState.INITIAL_REJECTED.value,
            f"未进入原始成交额前{TURNOVER_TOP_N}",
            f"正式初筛只使用原始成交额前{TURNOVER_TOP_N}，过滤后不补位",
        )
    if not valid_history(row):
        return CandidateState.INITIAL_REJECTED.value, "缺少有效历史K线", "缺少历史K线，暂不能确认入选日MA5"
    if not is_official_like_above_ma5(row):
        return CandidateState.INITIAL_REJECTED.value, "入选日收盘未站上MA5", "只展示在今日初筛，不转入跨日观察"

    deviation = row.get("MA5偏离率%")
    if not is_number(deviation):
        deviation = ma5_deviation(row.get("现价"), row.get("MA5"))
    zone = classify_touch_zone(row.get("现价"), row.get("MA5"))
    if zone["zone"] is TouchZone.BELOW:
        return CandidateState.BELOW_MA5.value, "当前价低于MA5回踩容差下沿", "盘中低于MA5，等待重新回到回踩区"
    if zone["zone"] is TouchZone.TOUCH:
        return CandidateState.BUY_READY.value, "当前位于MA5回踩区", "若处于视频买入时段且行情新鲜，可人工确认"
    return CandidateState.OBSERVING.value, "等待回踩MA5", "继续跨日观察，不设置任意过期天数"


def evaluate_stock(row: dict[str, Any]) -> dict[str, Any]:
    stage, reason, reminder = stock_stage_result(row)
    group = stage_to_group(stage)
    price = row.get("现价")
    available_cash = row.get("当前可用资金", row.get("当前本金", 10000))
    lot_ok, one_lot_cost = affordability(price, float(available_cash) if is_number(available_cash) else 10000)
    signal_qualified = stage == CandidateState.BUY_READY.value
    execution_block_reasons: list[str] = []
    if signal_qualified and not lot_ok:
        execution_block_reasons.append("资金不足，不能买入100股整数倍")
    execution_allowed = signal_qualified and not execution_block_reasons
    return {
        "code": clean_code(row.get("代码", "")),
        "group": group,
        "stage": stage,
        "can_buy": signal_qualified,
        "signal_qualified": signal_qualified,
        "signal_reason": "视频原版买点信号成立" if signal_qualified else reason,
        "execution_allowed": execution_allowed,
        "execution_block_reasons": execution_block_reasons,
        "manual_confirmation_required": True,
        "risk_level": "warning" if stage in {CandidateState.BELOW_MA5.value, CandidateState.INITIAL_REJECTED.value} else "normal",
        "reason": reason,
        "reminder": reminder,
        "lot_cost": one_lot_cost,
        "max_lot_quantity": int(float(available_cash or 0) // float(one_lot_cost or 1) * LOT_SIZE) if one_lot_cost else 0,
        "risk_amount": None,
        "max_risk_amount": None,
        "stop_price": None,
    }


def holding_advice(
    current_price: Any,
    ma5: Any,
    quantity: Any,
    below_ma5_days: Any = 0,
    available_quantity: Any | None = None,
    holding_days: Any | None = None,
) -> str:
    hold_days = int(float(holding_days)) if is_number(holding_days) else 0
    available_qty = int(float(available_quantity)) if is_number(available_quantity) else 0
    if available_qty <= 0 or hold_days <= 0:
        return "今日买入，T+1锁定；下一交易日09:30-10:00观察是否涨停"
    if hold_days == 1:
        return "次日早盘观察；10点前不能涨停则按视频原版提示卖出，可显式延迟至14:30后"
    return "隔日超短持仓已超过原版节奏；请复盘是否按规则处理"


def can_be_watchlist_candidate(
    code: str,
    name: str,
    has_history: bool,
    has_big_line: bool,
    ma5_up: bool,
    deviation: float | None,
    affordable: bool,
) -> tuple[bool, str]:
    passed, reason = screening_result(code, name)
    if not passed:
        return False, reason
    if not has_history:
        return False, "缺少历史K线，待补充"
    zone = classify_touch_zone(0 if deviation is None else 100 + float(deviation), 100)
    return zone["zone"] is TouchZone.TOUCH, zone["reason"]


def can_be_observation_candidate(
    code: str,
    name: str,
    has_history: bool,
    has_big_line: bool,
    ma5_up: bool,
    deviation: float | None,
) -> tuple[bool, str]:
    passed, reason = screening_result(code, name)
    if not passed:
        return False, reason
    if not has_history:
        return False, "缺少历史K线，待补充"
    if deviation is not None and float(deviation) < -MA5_TOUCH_TOLERANCE_PCT:
        return False, "当前低于MA5回踩容差下沿"
    return True, "符合跨日观察规则"


def determine_group(
    code: str,
    name: str,
    has_history: bool,
    has_big_line: bool,
    ma5_up: bool,
    deviation: float | None,
    affordable: bool,
    current_group: str | None = None,
) -> str:
    ok, _ = can_be_observation_candidate(code, name, has_history, has_big_line, ma5_up, deviation)
    if not ok:
        return CandidateState.INITIAL_REJECTED.value
    if deviation is not None and abs(float(deviation)) <= MA5_TOUCH_TOLERANCE_PCT:
        return CandidateState.BUY_READY.value
    if deviation is not None and float(deviation) < -MA5_TOUCH_TOLERANCE_PCT:
        return CandidateState.BELOW_MA5.value
    return CandidateState.OBSERVING.value


def 提醒_level_for_deviation(deviation: float | None, has_5pct_candle: bool = True) -> str:
    if deviation is None:
        return "purple"
    if deviation < -MA5_TOUCH_TOLERANCE_PCT:
        return "red"
    if deviation <= MA5_TOUCH_TOLERANCE_PCT:
        return "blue"
    return "amber"

