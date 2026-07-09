from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

DEFAULT_STRATEGY_ID = "ma5_pullback"

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
        id="mode3",
        name="模式3",
        description="规则名称与交易纪律待配置",
        ruleStatus="待配置",
        buyRuleSummary="暂只执行基础账户约束：价格有效、100 股整数倍、可用资金充足。",
        positionRuleSummary="持仓监控策略待配置，系统先提示人工复核。",
        reviewFocus="复盘模板先沿用通用四段式，后续可替换为模式3专用字段。",
        placeholder=True,
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


def audit_buy(
    strategy_id: str,
    price: float,
    quantity: int,
    trade_time: str,
    available_cash: float,
    fees: dict[str, float],
) -> tuple[str, list[str]]:
    strategy_id = validate_strategy(strategy_id)
    tags: list[str] = []
    if quantity <= 0 or quantity % 100 != 0:
        tags.append("非100股整数倍")
    if price <= 0:
        tags.append("成交价格无效")
    if price * quantity + fees["totalFee"] > available_cash + 1e-8:
        tags.append("可用资金不足")

    if strategy_id == DEFAULT_STRATEGY_ID:
        minute = _minutes(trade_time)
        in_window = (9 * 60 + 30 <= minute < 10 * 60) or (14 * 60 + 30 <= minute < 15 * 60)
        if not in_window:
            tags.append("不在纪律买入时段")

    if not tags:
        return "符合规则", []
    return ("部分不符" if len(tags) == 1 else "违规交易"), tags


def position_decision(
    strategy_id: str,
    *,
    locked_quantity: int,
    total_quantity: int,
    deferred: bool,
    defer_reason: str,
    now_minutes: int,
) -> PositionDecision:
    strategy_id = validate_strategy(strategy_id)
    if locked_quantity == total_quantity:
        return PositionDecision(
            status="T+1 锁定",
            advice="当日买入不可卖出；下一交易日再进入观察。",
            nextActionTime="下一交易日 09:30",
            actionType="T1_LOCKED",
            actionPriority="normal",
            actionTitle="T+1 锁定",
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
