from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CandidateState(StrEnum):
    INITIAL_SCREENED = "INITIAL_SCREENED"
    INITIAL_REJECTED = "INITIAL_REJECTED"
    WAITING_ELIGIBLE_DATE = "WAITING_ELIGIBLE_DATE"
    OBSERVING = "OBSERVING"
    IN_TOUCH_ZONE_OUTSIDE_WINDOW = "IN_TOUCH_ZONE_OUTSIDE_WINDOW"
    BUY_READY = "BUY_READY"
    BELOW_MA5 = "BELOW_MA5"
    BOUGHT = "BOUGHT"
    NEXT_DAY_OBSERVING = "NEXT_DAY_OBSERVING"
    MORNING_EXIT_DUE = "MORNING_EXIT_DUE"
    DEFERRED_TO_AFTERNOON = "DEFERRED_TO_AFTERNOON"
    AFTERNOON_EXIT_DUE = "AFTERNOON_EXIT_DUE"
    LIMIT_UP_HOLD = "LIMIT_UP_HOLD"
    CLOSED = "CLOSED"
    INVALIDATED = "INVALIDATED"
    CANCELLED = "CANCELLED"


class Ma5Type(StrEnum):
    CLOSE = "close"
    LIVE = "live"


class TouchZone(StrEnum):
    TOUCH = "TOUCH"
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    UNKNOWN = "UNKNOWN"


class RuleLayer(StrEnum):
    VIDEO_SIGNAL = "video_signal"
    EXECUTION_CONSTRAINT = "execution_constraint"
    ENGINEERING_DEFINITION = "engineering_definition"


@dataclass(frozen=True)
class SecurityCheck:
    allowed: bool
    reason: str = "通过"


@dataclass(frozen=True)
class Ma5Snapshot:
    ma5_value: float | None
    ma5_type: Ma5Type
    calculation_time: str
    history_last_trade_date: str = ""
    quote_time: str = ""
    risk: str = ""


@dataclass(frozen=True)
class CandidateEvaluation:
    state: CandidateState
    signal_qualified: bool
    signal_reason: str
    execution_allowed: bool
    execution_block_reasons: list[str] = field(default_factory=list)
    manual_confirmation_required: bool = True
    deviation: float | None = None
    touch_zone: TouchZone = TouchZone.UNKNOWN
    ma5_value: float | None = None
    ma5_type: Ma5Type = Ma5Type.LIVE
    buy_window: str = ""

    def to_api(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "signalQualified": self.signal_qualified,
            "signalReason": self.signal_reason,
            "executionAllowed": self.execution_allowed,
            "executionBlockReasons": self.execution_block_reasons,
            "manualConfirmationRequired": self.manual_confirmation_required,
            "deviation": self.deviation,
            "touchZone": self.touch_zone.value,
            "ma5Value": self.ma5_value,
            "ma5Type": self.ma5_type.value,
            "buyWindow": self.buy_window,
        }

