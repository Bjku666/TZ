from __future__ import annotations

import math
import re
from datetime import date, datetime, time
from typing import Any, Iterable

import pandas as pd

from src.rule_models import CandidateEvaluation, CandidateState, Ma5Snapshot, Ma5Type, SecurityCheck, TouchZone
from src.trading_calendar import next_trading_day

STRATEGY_NAME = "视频原版五日线回踩隔日超短交易纪律系统"
STRATEGY_VERSION = "video-original-v1"
TURNOVER_TOP_N = 20
MA5_TOUCH_TOLERANCE_PCT = 0.5
QUOTE_FRESHNESS_SECONDS = 20
LOT_SIZE = 100
MORNING_BUY_WINDOW = (time(9, 30), time(10, 0))
AFTERNOON_BUY_WINDOW = (time(14, 30), time(15, 0))
BUY_WINDOWS = (MORNING_BUY_WINDOW, AFTERNOON_BUY_WINDOW)
ALLOWED_PREFIXES = ("600", "601", "603", "605", "000", "001", "002")
EXCLUDED_PREFIXES = ("300", "301", "688", "689", "920", "4", "8")
OFFICIAL_GENERATE_AFTER = time(15, 5)


def clean_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    match = re.search(r"(\d{6})", text)
    return match.group(1) if match else ""


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed):
        return None
    return parsed


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return pd.to_datetime(value, errors="coerce").to_pydatetime()


def is_allowed_security(
    code: Any,
    name: Any = "",
    *,
    suspended: bool = False,
    price: Any = None,
    delisted: bool = False,
) -> SecurityCheck:
    code_text = clean_code(code)
    name_text = str(name or "").strip().upper()
    if not code_text:
        return SecurityCheck(False, "股票代码无效")
    if code_text.startswith(("300", "301")):
        return SecurityCheck(False, "创业板不属于视频原版股票范围")
    if code_text.startswith(("688", "689")):
        return SecurityCheck(False, "科创板不属于视频原版股票范围")
    if code_text.startswith(("920", "4", "8")):
        return SecurityCheck(False, "北交所股票不属于视频原版股票范围")
    if "ST" in name_text:
        return SecurityCheck(False, "ST或*ST排除")
    if delisted or "退" in name_text:
        return SecurityCheck(False, "已退市或退市整理股票排除")
    if not code_text.startswith(ALLOWED_PREFIXES):
        return SecurityCheck(False, "非沪深主板允许代码范围")
    numeric_price = _number(price)
    if suspended:
        return SecurityCheck(False, "当日停牌或无法正常交易")
    if price is not None and (numeric_price is None or numeric_price <= 0):
        return SecurityCheck(False, "无有效价格")
    return SecurityCheck(True, "通过")


def _rank_value(row: dict[str, Any]) -> float:
    for key in ("raw_rank", "rank", "成交额排名", "pool_rank_at_generation"):
        parsed = _number(row.get(key))
        if parsed is not None:
            return parsed
    turnover = _number(row.get("turnover", row.get("成交额")))
    return -turnover if turnover is not None else 999999


def filter_raw_top20(rows: Iterable[dict[str, Any]], *, raw_top_n: int = TURNOVER_TOP_N) -> list[dict[str, Any]]:
    prepared = [dict(row) for row in rows]
    prepared.sort(key=_rank_value)
    raw = prepared[: int(raw_top_n)]
    result: list[dict[str, Any]] = []
    for index, row in enumerate(raw, start=1):
        raw_rank = int(_number(row.get("raw_rank", row.get("rank", row.get("成交额排名")))) or index)
        code = clean_code(row.get("code", row.get("代码")))
        name = str(row.get("name", row.get("名称", "")) or "")
        price = row.get("price", row.get("现价", row.get("close_price")))
        check = is_allowed_security(
            code,
            name,
            suspended=bool(row.get("suspended", False)),
            price=price,
            delisted=bool(row.get("delisted", False)),
        )
        result.append(
            {
                **row,
                "code": code,
                "name": name,
                "raw_rank": raw_rank,
                "market_allowed": check.allowed,
                "exclusion_reason": "" if check.allowed else check.reason,
            }
        )
    return result


def calculate_ma5_close(closes: Iterable[Any]) -> float | None:
    values = [_number(value) for value in closes]
    valid = [value for value in values if value is not None]
    if len(valid) < 5:
        return None
    return round(sum(valid[-5:]) / 5, 6)


def calculate_ma5_live(previous_four_closes: Iterable[Any], current_price: Any) -> float | None:
    closes = [_number(value) for value in previous_four_closes]
    valid = [value for value in closes if value is not None]
    price = _number(current_price)
    if len(valid) < 4 or price is None:
        return None
    return round((sum(valid[-4:]) + price) / 5, 6)


def ma5_deviation(price: Any, ma5: Any) -> float | None:
    price_f = _number(price)
    ma5_f = _number(ma5)
    if price_f is None or ma5_f is None or ma5_f <= 0:
        return None
    return (price_f - ma5_f) / ma5_f * 100


def is_official_selection_qualified(close_price: Any, ma5_close: Any) -> bool:
    close_f = _number(close_price)
    ma5_f = _number(ma5_close)
    return close_f is not None and ma5_f is not None and close_f >= ma5_f


def next_eligible_trade_date(selection_date: Any) -> date:
    return next_trading_day(_as_date(selection_date))


def is_buy_window(value: datetime | None) -> bool:
    if value is None:
        return False
    current = value.time()
    return any(start <= current < end for start, end in BUY_WINDOWS)


def buy_window_label(value: datetime | None) -> str:
    if value is None:
        return ""
    current = value.time()
    if MORNING_BUY_WINDOW[0] <= current < MORNING_BUY_WINDOW[1]:
        return "morning"
    if AFTERNOON_BUY_WINDOW[0] <= current < AFTERNOON_BUY_WINDOW[1]:
        return "afternoon"
    return ""


def classify_touch_zone(price: Any, ma5_live: Any, *, tolerance_pct: float = MA5_TOUCH_TOLERANCE_PCT) -> dict[str, Any]:
    deviation = ma5_deviation(price, ma5_live)
    if deviation is None:
        return {"zone": TouchZone.UNKNOWN, "deviation": None, "reason": "无法计算MA5偏离率"}
    if deviation < -abs(tolerance_pct):
        return {"zone": TouchZone.BELOW, "deviation": deviation, "reason": "当前价低于MA5回踩容差下沿"}
    if deviation <= abs(tolerance_pct):
        return {"zone": TouchZone.TOUCH, "deviation": deviation, "reason": "当前位于MA5回踩区"}
    return {"zone": TouchZone.ABOVE, "deviation": deviation, "reason": "仍在MA5回踩区上方等待"}


def official_generation_allowed(now: datetime, selection_date: Any | None = None) -> bool:
    day = _as_date(selection_date) if selection_date is not None else now.date()
    if now.date() > day:
        return True
    return now.date() == day and now.time() >= OFFICIAL_GENERATE_AFTER


def evaluate_candidate_state(
    candidate: dict[str, Any],
    quote: dict[str, Any],
    now: datetime,
    *,
    account_cash: Any = None,
    lot_size: int = LOT_SIZE,
    quote_freshness_seconds: int = QUOTE_FRESHNESS_SECONDS,
) -> CandidateEvaluation:
    state_text = str(candidate.get("state") or "")
    if state_text in {CandidateState.BOUGHT.value, CandidateState.CLOSED.value, CandidateState.INVALIDATED.value, CandidateState.CANCELLED.value}:
        state = CandidateState(state_text)
        return CandidateEvaluation(state, False, "候选周期已结束", False, ["候选周期已结束"])

    eligible_from = candidate.get("eligible_from") or candidate.get("eligibleFrom")
    if eligible_from and now.date() < _as_date(eligible_from):
        return CandidateEvaluation(
            CandidateState.WAITING_ELIGIBLE_DATE,
            False,
            "入选当天不能买，尚未到最早可交易日",
            False,
            ["尚未到最早可交易日"],
        )

    price = quote.get("price", quote.get("最新价", quote.get("现价", candidate.get("last_live_price"))))
    ma5_live = quote.get("ma5_live", quote.get("ma5Live", candidate.get("last_ma5_live", candidate.get("last_ma5_close"))))
    quote_age = _number(quote.get("quote_age_seconds", quote.get("quoteAgeSeconds")))
    tradeable = bool(quote.get("tradeable", True)) and _number(price) is not None and _number(price) > 0
    zone = classify_touch_zone(price, ma5_live)
    deviation = zone["deviation"]
    touch_zone = zone["zone"]
    block_reasons: list[str] = []
    if not tradeable:
        block_reasons.append("停牌、无有效价格或无法正常交易")
    if quote_age is None or quote_age > quote_freshness_seconds:
        block_reasons.append("行情数据过期，无法确认")

    if touch_zone is TouchZone.BELOW:
        return CandidateEvaluation(
            CandidateState.BELOW_MA5,
            False,
            "当前低于MA5回踩容差下沿",
            False,
            block_reasons or ["当前价明显低于回踩区"],
            deviation=deviation,
            touch_zone=touch_zone,
            ma5_value=_number(ma5_live),
        )
    if touch_zone is TouchZone.ABOVE:
        return CandidateEvaluation(
            CandidateState.OBSERVING,
            False,
            "仍在MA5回踩区上方等待",
            False,
            block_reasons,
            deviation=deviation,
            touch_zone=touch_zone,
            ma5_value=_number(ma5_live),
        )
    if touch_zone is TouchZone.UNKNOWN:
        return CandidateEvaluation(
            CandidateState.OBSERVING,
            False,
            "缺少MA5或价格，无法确认回踩",
            False,
            block_reasons or ["缺少MA5或有效价格"],
            deviation=deviation,
            touch_zone=touch_zone,
            ma5_value=_number(ma5_live),
        )

    in_window = is_buy_window(now)
    if not in_window:
        return CandidateEvaluation(
            CandidateState.IN_TOUCH_ZONE_OUTSIDE_WINDOW,
            False,
            "处于回踩区，但不在视频允许买入时段",
            False,
            block_reasons or ["不在09:30-10:00或14:30-15:00买入时段"],
            deviation=deviation,
            touch_zone=touch_zone,
            ma5_value=_number(ma5_live),
        )

    signal_qualified = not block_reasons
    execution_allowed = signal_qualified
    execution_reasons = list(block_reasons)
    cash = _number(account_cash)
    price_f = _number(price)
    if cash is not None and price_f is not None:
        max_lots = int(cash // (price_f * lot_size))
        if max_lots <= 0:
            execution_allowed = False
            execution_reasons.append("资金不足，买不起100股整数倍")

    return CandidateEvaluation(
        CandidateState.BUY_READY if signal_qualified else CandidateState.IN_TOUCH_ZONE_OUTSIDE_WINDOW,
        signal_qualified,
        "视频原版买点信号成立" if signal_qualified else "处于回踩区，但行情或交易状态无法确认",
        execution_allowed,
        execution_reasons,
        deviation=deviation,
        touch_zone=touch_zone,
        ma5_value=_number(ma5_live),
        buy_window=buy_window_label(now),
    )


def evaluate_buy_compliance(
    *,
    candidate: dict[str, Any] | None,
    trade_datetime: datetime,
    trade_price: Any,
    quantity: Any,
    ma5_live: Any,
    quote_age_seconds: Any,
    available_cash: Any,
    manual_confirmed: bool,
    is_historical: bool = False,
) -> dict[str, Any]:
    tags: list[str] = []
    signal_tags: list[str] = []
    execution_tags: list[str] = []
    if not candidate:
        signal_tags.append("不属于有效候选周期")
    else:
        if not candidate.get("source_batch_id") and not candidate.get("selectionBatchId"):
            signal_tags.append("候选未关联正式收盘批次")
        if not bool(candidate.get("above_ma5", candidate.get("aboveMa5", True))):
            signal_tags.append("入选日收盘未站上MA5")
        eligible_from = candidate.get("eligible_from") or candidate.get("eligibleFrom")
        if eligible_from and trade_datetime.date() < _as_date(eligible_from):
            signal_tags.append("买入日期早于最早可交易日")
    if not is_buy_window(trade_datetime):
        signal_tags.append("不在09:30-10:00或14:30-15:00买入时段")

    zone = classify_touch_zone(trade_price, ma5_live)
    if zone["zone"] is not TouchZone.TOUCH:
        signal_tags.append("买入时不在MA5回踩容差区")
    quote_age = _number(quote_age_seconds)
    if quote_age is None or quote_age > QUOTE_FRESHNESS_SECONDS:
        signal_tags.append("买入时行情数据过期或缺失")

    qty = _number(quantity) or 0
    price = _number(trade_price) or 0
    if qty <= 0 or int(qty) % LOT_SIZE != 0:
        execution_tags.append("数量不是100股整数倍")
    cash = _number(available_cash)
    if not is_historical and cash is not None and price * qty > cash:
        execution_tags.append("账户现金不足")
    if not manual_confirmed:
        execution_tags.append("交易未人工确认")

    tags.extend(signal_tags)
    tags.extend(execution_tags)
    conclusion = "符合规则" if not tags else "部分不符" if len(tags) <= 2 else "违规交易"
    return {
        "conclusion": conclusion,
        "tags": tags,
        "signalQualified": not signal_tags,
        "executionAllowed": not execution_tags,
        "executionBlockReasons": execution_tags,
        "deviation": zone["deviation"],
        "buyWindow": buy_window_label(trade_datetime),
        "manualConfirmationRequired": True,
        "historicalBackfill": bool(is_historical),
    }


def is_limit_up(current_price: Any, previous_close: Any = None, limit_up_price: Any = None, tolerance: float = 0.0001) -> bool:
    current = _number(current_price)
    if current is None:
        return False
    explicit = _number(limit_up_price)
    if explicit is not None and explicit > 0:
        return current >= explicit * (1 - tolerance)
    prev = _number(previous_close)
    if prev is None or prev <= 0:
        return False
    calculated = round(prev * 1.10, 2)
    return current >= calculated * (1 - tolerance)


def evaluate_next_day_exit(
    *,
    buy_date: Any,
    now: datetime,
    current_price: Any = None,
    previous_close: Any = None,
    limit_up_price: Any = None,
    deferred: bool = False,
    limit_down_or_suspended: bool = False,
    sellable_quantity: Any = None,
) -> dict[str, Any]:
    buy_day = _as_date(buy_date)
    exit_day = next_trading_day(buy_day)
    if now.date() <= buy_day:
        return {
            "state": CandidateState.BOUGHT.value,
            "message": "今日买入，T+1锁定",
            "nextActionTime": f"{exit_day.isoformat()} 09:30",
            "ruleViolation": False,
        }
    if now.date() < exit_day:
        return {
            "state": CandidateState.BOUGHT.value,
            "message": "等待下一交易日早盘观察",
            "nextActionTime": f"{exit_day.isoformat()} 09:30",
            "ruleViolation": False,
        }
    sellable = _number(sellable_quantity)
    blocked = bool(limit_down_or_suspended) or (sellable is not None and sellable <= 0)
    clock = now.time()
    up = is_limit_up(current_price, previous_close, limit_up_price)
    if clock < time(9, 30):
        state = CandidateState.NEXT_DAY_OBSERVING
        message = "下一交易日09:30-10:00观察是否涨停"
    elif time(9, 30) <= clock < time(10, 0):
        state = CandidateState.NEXT_DAY_OBSERVING
        message = "若10点前不能涨停，冲高卖出；也可显式延迟至14:30后"
    elif up:
        state = CandidateState.LIMIT_UP_HOLD
        message = "10点时仍处于涨停，原版不要求此时卖出"
    elif deferred and clock < time(14, 30):
        state = CandidateState.DEFERRED_TO_AFTERNOON
        message = "已选择延迟至14:30后处理"
    elif deferred and clock >= time(14, 30):
        state = CandidateState.AFTERNOON_EXIT_DUE
        message = "尾盘分支：未继续涨停则明确提示卖出"
    else:
        state = CandidateState.MORNING_EXIT_DUE
        message = "10点未涨停，视频原版要求卖出"
    return {
        "state": state.value,
        "message": message,
        "isLimitUp": up,
        "executionBlocked": blocked,
        "executionBlockReason": "跌停、停牌或可卖数量异常导致无法执行" if blocked else "",
        "ruleViolation": bool(now.time() >= time(15, 0) and not up and not blocked),
        "nextActionTime": "立即处理" if state in {CandidateState.MORNING_EXIT_DUE, CandidateState.AFTERNOON_EXIT_DUE} else "",
        "programCompletionNote": "10点涨停后的处理属于程序最小补全，视频未详细说明",
    }


def rules_config() -> dict[str, Any]:
    return {
        "strategyName": STRATEGY_NAME,
        "strategyVersion": STRATEGY_VERSION,
        "turnoverTopN": TURNOVER_TOP_N,
        "touchTolerancePct": MA5_TOUCH_TOLERANCE_PCT,
        "morningBuyWindow": {"start": "09:30", "end": "10:00", "endExclusive": True},
        "afternoonBuyWindow": {"start": "14:30", "end": "15:00", "endExclusive": True},
        "quoteFreshnessSeconds": QUOTE_FRESHNESS_SECONDS,
        "lotSize": LOT_SIZE,
        "ma5LiveFormula": "(前4个完成交易日收盘价之和 + 当前实时价格) / 5",
        "ruleBoundaries": {
            "videoSignal": "成交额原始前20、入选日收盘站上MA5、下一交易日起等待回踩、视频买入时段、隔日超短卖出提醒",
            "executionConstraints": "100股一手、现金、T+1、停牌、费用、人工确认",
            "engineeringDefinitions": "MA5回踩容差0.5%、行情新鲜度20秒、10点涨停后最小补全",
        },
    }

