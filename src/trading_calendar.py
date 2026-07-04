from __future__ import annotations

from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
CALENDAR_CACHE = Path(__file__).resolve().parents[1] / "data" / "runtime" / "trading_calendar.json"


def shanghai_now() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def _as_date(value: date | datetime | str | None) -> date:
    if value is None:
        return shanghai_now().date()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.date()
        return value.astimezone(SHANGHAI_TZ).date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _load_cache() -> tuple[set[date], set[date], bool]:
    try:
        payload: Any = json.loads(CALENDAR_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set(), set(), True
    trading_days = {
        date.fromisoformat(str(value))
        for value in payload.get("tradingDays", [])
        if value
    }
    holidays = {
        date.fromisoformat(str(value))
        for value in payload.get("holidays", [])
        if value
    }
    return trading_days, holidays, not bool(trading_days or holidays)


def calendar_degraded() -> bool:
    return _load_cache()[2]


def is_trading_day(value: date | datetime | str | None) -> bool:
    day = _as_date(value)
    trading_days, holidays, _ = _load_cache()
    if day in trading_days:
        return True
    if day in holidays:
        return False
    return day.weekday() < 5


def previous_trading_day(value: date | datetime | str | None) -> date:
    day = _as_date(value) - timedelta(days=1)
    while not is_trading_day(day):
        day -= timedelta(days=1)
    return day


def next_trading_day(value: date | datetime | str | None) -> date:
    day = _as_date(value) + timedelta(days=1)
    while not is_trading_day(day):
        day += timedelta(days=1)
    return day


def current_market_phase(value: datetime | None = None) -> str:
    now = value or shanghai_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=SHANGHAI_TZ)
    else:
        now = now.astimezone(SHANGHAI_TZ)
    if not is_trading_day(now.date()):
        return "weekend" if now.weekday() >= 5 else "holiday"
    clock = now.time()
    if clock < time(9, 30):
        return "pre_market"
    if time(9, 30) <= clock < time(11, 30):
        return "trading"
    if time(11, 30) <= clock < time(13, 0):
        return "lunch_break"
    if time(13, 0) <= clock < time(15, 0):
        return "trading"
    return "after_close"


def effective_trade_date(value: datetime | None = None) -> date:
    now = value or shanghai_now()
    operation_day = _as_date(now)
    if is_trading_day(operation_day):
        return operation_day
    return previous_trading_day(operation_day)


def next_market_open(value: datetime | None = None) -> datetime:
    now = value or shanghai_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=SHANGHAI_TZ)
    else:
        now = now.astimezone(SHANGHAI_TZ)
    day = now.date()
    phase = current_market_phase(now)
    if is_trading_day(day) and phase == "pre_market":
        target = day
    elif is_trading_day(day) and phase in {"trading", "lunch_break"}:
        return now
    else:
        target = next_trading_day(day)
    return datetime.combine(target, time(9, 30), tzinfo=SHANGHAI_TZ)
