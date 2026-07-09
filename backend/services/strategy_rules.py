from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal

DEFAULT_STRATEGY_ID = "ma5_pullback"
MODE3_STRATEGY_ID = "mode3"

ActionPriority = Literal["normal", "warning", "danger"]


@dataclass(frozen=True)
class StrategyMode:
    id: str
    name: str
    description: str
    ruleStatus: str
    buyRuleSummary: str
    positionRuleSummary: str
    reviewFocus: str
    placeholder: bool = False


@dataclass(frozen=True)
class PositionDecision:
    status: str
    advice: str
    nextActionTime: str
    actionType: str
    actionPriority: ActionPriority
    actionTitle: str


STRATEGIES: dict[str, StrategyMode] = {
    DEFAULT_STRATEGY_ID: StrategyMode(
        id=DEFAULT_STRATEGY_ID,
        name="五日线回踩",
        description="当前系统原有交易纪律模式",
        ruleStatus="已启用",
        buyRuleSummary="100 股整数倍、可用资金充足，并限制在 09:30-10:00 或 14:30-15:00 买入窗口。",
        positionRuleSummary="T+1 锁定后进入次日观察，10:00 处理；可明确延迟至 14:30 尾盘。",
        reviewFocus="计划依据、执行偏差、结果情绪、下一交易日硬规则。",
    ),
    "mode2": StrategyMode(
        id="mode2",
        name="模式2",
        description="规则名称与交易纪律待配置",
        ruleStatus="待配置",
        buyRuleSummary="暂只执行基础账户约束：价格有效、100 股整数倍、可用资金充足。",
        positionRuleSummary="持仓监控策略待配置，系统先提示人工复核。",
        reviewFocus="复盘模板先沿用通用四段式，后续可替换为模式2专用字段。",
        placeholder=True,
    ),
    "mode3": StrategyMode(
        id=MODE3_STRATEGY_ID,
        name="十日线缩量回踩隔日反弹",
        description="前期明显放量、上升趋势中缩量阴线回踩十日线，尾盘分仓买入，次日早盘利用反弹退出。",
        ruleStatus="已启用",
        buyRuleSummary="只在 14:50-15:00 尾盘登记买入；必须确认缩量阴线、回踩十日线、趋势未破坏、非第一根回调阴线并完成分仓。",
        positionRuleSummary="今日买入 T+1 锁定；次日 09:25 起检查，09:45-10:00 为主要退出窗口，10:00 后需卖出或登记突破五日线延长至尾盘。",
        reviewFocus="放量与缩量条件、14:50 后执行、分仓确认、次日退出率、10:00 前处理和超期持仓。",
        placeholder=False,
    ),
}


def validate_strategy(strategy_id: str | None = None) -> str:
    normalized = str(strategy_id or DEFAULT_STRATEGY_ID).strip() or DEFAULT_STRATEGY_ID
    if normalized not in STRATEGIES:
        allowed = "、".join(item.name for item in STRATEGIES.values())
        raise ValueError(f"strategy 必须是已配置交易模式：{allowed}")
    return normalized


def get_strategy(strategy_id: str | None = None) -> dict[str, Any]:
    return asdict(STRATEGIES[validate_strategy(strategy_id)])


def list_strategies() -> list[dict[str, Any]]:
    return [asdict(strategy) for strategy in STRATEGIES.values()]


def _minutes(text: str) -> int:
    try:
        hour, minute = map(int, text[:5].split(":"))
        return hour * 60 + minute
    except (ValueError, AttributeError):
        return -1


def _snapshot_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _checklist(snapshot: dict[str, Any]) -> dict[str, Any]:
    value = snapshot.get("entryChecklist")
    return value if isinstance(value, dict) else {}


def _bool_value(data: dict[str, Any], key: str) -> bool | None:
    if key not in data:
        return None
    value = data.get(key)
    return value if isinstance(value, bool) else bool(value)


def _number_value(data: dict[str, Any], key: str) -> float | None:
    if key not in data or data.get(key) in ("", None):
        return None
    try:
        return float(data.get(key))
    except (TypeError, ValueError):
        return None


def _append_if_false(tags: list[str], checks: dict[str, Any], key: str, label: str, missing: list[str]) -> None:
    value = _bool_value(checks, key)
    if value is False:
        tags.append(label)
    elif value is None:
        missing.append(key)


def _mode3_buy_audit(trade_time: str, snapshot: dict[str, Any], base_hard_tags: list[str]) -> tuple[str, list[str]]:
    hard_tags = [*base_hard_tags]
    soft_tags: list[str] = []
    checks = _checklist(snapshot)
    missing: list[str] = []
    minute = _minutes(trade_time)

    if minute < 0:
        hard_tags.append("成交时间无效")
    elif minute < 14 * 60 + 50:
        hard_tags.append("14:50以前买入")
    elif minute >= 15 * 60:
        hard_tags.append("15:00以后买入")

    _append_if_false(hard_tags, checks, "bearishCandle", "买入阳线", missing)
    _append_if_false(hard_tags, checks, "pullbackVolumeShrunk", "回调未缩量", missing)
    _append_if_false(hard_tags, checks, "nearMa10", "未回踩十日线", missing)
    _append_if_false(hard_tags, checks, "ma10Uptrend", "均线空头或趋势已经破坏", missing)
    _append_if_false(hard_tags, checks, "notFirstPullbackBearish", "买入第一根回调阴线", missing)

    prior_volume = _bool_value(checks, "priorVolumeExpansion")
    if prior_volume is False:
        soft_tags.append("前期放量上涨确认缺失")
    elif prior_volume is None:
        missing.append("priorVolumeExpansion")

    mid_distance = _bool_value(checks, "midTermDistanceOk")
    if mid_distance is False:
        soft_tags.append("十日线与中期均线距离偏大")
    elif mid_distance is None:
        missing.append("midTermDistanceOk")

    split_confirmed = _bool_value(checks, "positionSplit")
    if split_confirmed is False:
        soft_tags.append("未完成分仓确认")
    elif split_confirmed is None:
        missing.append("positionSplit")

    if _number_value(snapshot, "ma10AtEntry") is None or _number_value(snapshot, "distanceToMa10Pct") is None or missing:
        soft_tags.append("买入依据填写不完整")

    if hard_tags:
        return "违规交易", _dedupe_tags(hard_tags + soft_tags)
    if soft_tags:
        return "部分不符", _dedupe_tags(soft_tags)
    return "符合规则", []


def _dedupe_tags(tags: list[str]) -> list[str]:
    result: list[str] = []
    for tag in tags:
        if tag and tag not in result:
            result.append(tag)
    return result


def audit_buy(
    strategy_id: str,
    price: float,
    quantity: int,
    trade_time: str,
    available_cash: float,
    fees: dict[str, float],
    strategy_snapshot: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    strategy_id = validate_strategy(strategy_id)
    tags: list[str] = []
    if quantity <= 0 or quantity % 100 != 0:
        tags.append("非100股整数倍")
    if price <= 0:
        tags.append("成交价格无效")
    if price * quantity + fees["totalFee"] > available_cash + 1e-8:
        tags.append("可用资金不足")

    if strategy_id == MODE3_STRATEGY_ID:
        return _mode3_buy_audit(trade_time, _snapshot_dict(strategy_snapshot), tags)

    if strategy_id == DEFAULT_STRATEGY_ID:
        minute = _minutes(trade_time)
        in_window = (9 * 60 + 30 <= minute < 10 * 60) or (14 * 60 + 30 <= minute < 15 * 60)
        if not in_window:
            tags.append("不在纪律买入时段")

    if not tags:
        return "符合规则", []
    return ("部分不符" if len(tags) == 1 else "违规交易"), tags


MODE3_EXIT_REASONS = {
    "TARGET_PROFIT",
    "OPEN_BELOW_MA10",
    "INTRADAY_AVERAGE_BROKEN",
    "MA5_PRESSURE_FAILED",
    "MA10_STOP",
    "HARD_STOP",
    "EXTENDED_SAME_DAY_EXIT",
    "OTHER",
}

MODE3_NORMAL_EXIT_REASONS = {
    "TARGET_PROFIT",
    "OPEN_BELOW_MA10",
    "INTRADAY_AVERAGE_BROKEN",
    "MA5_PRESSURE_FAILED",
    "MA10_STOP",
    "HARD_STOP",
    "EXTENDED_SAME_DAY_EXIT",
}


def _parse_date(text: str | None) -> date | None:
    try:
        return date.fromisoformat(str(text or "")[:10])
    except ValueError:
        return None


def _trading_day_gap(start: str | None, end: str | None) -> int:
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if not start_date or not end_date or end_date < start_date:
        return 0
    count = 0
    cursor = start_date
    while cursor <= end_date:
        if cursor.weekday() < 5:
            count += 1
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return count


def audit_sell(
    strategy_id: str,
    *,
    trade_date: str,
    trade_time: str,
    position: dict[str, Any] | None = None,
    strategy_snapshot: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    strategy_id = validate_strategy(strategy_id)
    if strategy_id != MODE3_STRATEGY_ID:
        return "符合规则", []

    snapshot = _snapshot_dict(strategy_snapshot)
    tags: list[str] = []
    exit_reason = str(snapshot.get("exitReason") or "").strip()
    extended = bool(snapshot.get("extendedObservation"))
    minute = _minutes(trade_time)
    buy_date = str((position or {}).get("buyDate") or "")
    hold_days = _trading_day_gap(buy_date, trade_date)

    if exit_reason not in MODE3_EXIT_REASONS:
        tags.append("卖出依据填写不完整")
    elif exit_reason == "OTHER":
        tags.append("卖出原因需人工复核")

    if hold_days > 2 and not extended:
        tags.append("持有超过次日")
    if hold_days > 2 and extended:
        tags.append("登记延长后当日仍未退出")
    if exit_reason == "EXTENDED_SAME_DAY_EXIT" and not extended:
        tags.append("卖出原因与实际操作节点不符")
    if extended and minute >= 15 * 60:
        tags.append("登记延长后当日仍未退出")
    if extended and minute < 14 * 60 + 50 and exit_reason == "EXTENDED_SAME_DAY_EXIT":
        tags.append("卖出原因与实际操作节点不符")

    if tags:
        return ("违规交易" if "登记延长后当日仍未退出" in tags else "部分不符"), _dedupe_tags(tags)
    if exit_reason in MODE3_NORMAL_EXIT_REASONS:
        return "符合规则", []
    return "无法判断", ["卖出原因需人工复核"]


def position_decision(
    strategy_id: str,
    *,
    locked_quantity: int,
    total_quantity: int,
    deferred: bool,
    defer_reason: str,
    now_minutes: int,
    hold_days: int = 1,
) -> PositionDecision:
    strategy_id = validate_strategy(strategy_id)
    if locked_quantity == total_quantity:
        if strategy_id == MODE3_STRATEGY_ID:
            return PositionDecision(
                status="今日买入，T+1锁定",
                advice="今日买入不可卖出；本模式禁止当日做 T 或追加计划外仓位，下一交易日 09:25 开始处理。",
                nextActionTime="下一交易日 09:25",
                actionType="T1_LOCKED",
                actionPriority="normal",
                actionTitle="今日买入，T+1锁定",
            )
        return PositionDecision(
            status="T+1 锁定",
            advice="当日买入不可卖出；下一交易日再进入观察。",
            nextActionTime="下一交易日 09:30",
            actionType="T1_LOCKED",
            actionPriority="normal",
            actionTitle="T+1 锁定",
        )

    if strategy_id == MODE3_STRATEGY_ID:
        if hold_days > 2:
            return PositionDecision(
                status="超期持仓",
                advice="已经超过十日线缩量回踩隔日反弹的规定持仓时间，请优先处理并在复盘中标记偏差。",
                nextActionTime="现在",
                actionType="OVERDUE_POSITION",
                actionPriority="danger",
                actionTitle="超期持仓",
            )
        if deferred and now_minutes < 14 * 60 + 50:
            return PositionDecision(
                status="已延长至尾盘",
                advice=defer_reason or "仅因 10:00 前有效突破五日线而延长观察，14:50 后必须处理。",
                nextActionTime="14:50",
                actionType="EXTENDED_AFTER_MA5_BREAK",
                actionPriority="warning",
                actionTitle="突破五日线后延长至尾盘",
            )
        if deferred and now_minutes >= 14 * 60 + 50:
            return PositionDecision(
                status="尾盘必须处理",
                advice="延长观察已到期，应在收盘前记录卖出，不能转为中长期持仓。",
                nextActionTime="现在",
                actionType="SAME_DAY_FINAL_EXIT_DUE",
                actionPriority="danger",
                actionTitle="延长观察到期",
            )
        if now_minutes < 9 * 60 + 25:
            return PositionDecision(
                status="等待集合竞价",
                advice="次日盘前等待集合竞价，09:25 开始检查开盘价与十日线关系。",
                nextActionTime="09:25",
                actionType="AUCTION_CHECK_PENDING",
                actionPriority="normal",
                actionTitle="等待集合竞价",
            )
        if now_minutes < 9 * 60 + 30:
            return PositionDecision(
                status="检查开盘位置",
                advice="检查开盘价与十日线关系，若支撑失效应按纪律退出。",
                nextActionTime="09:30",
                actionType="OPEN_POSITION_CHECK",
                actionPriority="warning",
                actionTitle="检查开盘价与十日线",
            )
        if now_minutes < 9 * 60 + 45:
            return PositionDecision(
                status="前十五分钟观察",
                advice="观察开盘下杀后能否站回分时均价线和开盘价，不能把短线处理拖成中长期持仓。",
                nextActionTime="09:45",
                actionType="FIRST_15_MIN_OBSERVING",
                actionPriority="warning",
                actionTitle="前十五分钟反弹观察",
            )
        if now_minutes < 10 * 60:
            return PositionDecision(
                status="主要退出窗口",
                advice="已进入 09:45-10:00 主要退出窗口，应登记卖出或明确 10:00 前突破五日线的延长理由。",
                nextActionTime="10:00",
                actionType="MORNING_EXIT_DUE",
                actionPriority="danger",
                actionTitle="主要退出窗口",
            )
        return PositionDecision(
            status="应卖出或登记延长",
            advice="10:00 后应完成卖出；若 10:00 前已有效突破五日线，只能登记延长至当日尾盘并保留理由。",
            nextActionTime="现在",
            actionType="MORNING_EXIT_DUE",
            actionPriority="danger",
            actionTitle="10:00 后处理到期",
        )

    if strategy_id == DEFAULT_STRATEGY_ID:
        if deferred and now_minutes < 14 * 60 + 30:
            return PositionDecision(
                status="已延迟至尾盘",
                advice=defer_reason or "等待 14:30 后重新处理。",
                nextActionTime="14:30",
                actionType="DEFERRED_TO_AFTERNOON",
                actionPriority="warning",
                actionTitle="已延迟至尾盘",
            )
        if deferred and now_minutes >= 14 * 60 + 30:
            return PositionDecision(
                status="尾盘待处理",
                advice="已到尾盘处理时段，请根据原计划记录卖出或撤销延迟。",
                nextActionTime="现在",
                actionType="AFTERNOON_EXIT_DUE",
                actionPriority="danger",
                actionTitle="尾盘处理到期",
            )
        if now_minutes < 10 * 60:
            return PositionDecision(
                status="次日观察",
                advice="10:00 前观察承接；不符合预案时按纪律退出。",
                nextActionTime="10:00",
                actionType="NEXT_DAY_OBSERVING",
                actionPriority="warning",
                actionTitle="10:00 前观察",
            )
        return PositionDecision(
            status="10:00 待处理",
            advice="已到纪律处理节点，请记录卖出或明确延迟至尾盘。",
            nextActionTime="现在",
            actionType="MORNING_EXIT_DUE",
            actionPriority="danger",
            actionTitle="10:00 纪律处理",
        )

    if deferred:
        return PositionDecision(
            status="已标记延后处理",
            advice=defer_reason or "该交易模式的持仓监控规则尚未配置，请按人工计划复核。",
            nextActionTime="人工确认",
            actionType="MANUAL_REVIEW_DEFERRED",
            actionPriority="warning",
            actionTitle="延后处理待复核",
        )
    return PositionDecision(
        status="策略待配置",
        advice="该交易模式的持仓监控规则尚未配置，请按人工计划记录处理。",
        nextActionTime="人工确认",
        actionType="STRATEGY_RULE_PENDING",
        actionPriority="warning",
        actionTitle="持仓监控待配置",
    )
