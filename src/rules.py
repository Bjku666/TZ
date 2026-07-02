from __future__ import annotations

import math
import re
from typing import Any

ALLOWED_PREFIXES = ("600", "601", "603", "605", "000", "001", "002")
PIPELINE_STAGES = [
    "初筛通过",
    "重点观察",
    "等回踩",
    "待买观察",
    "资金不足观察",
    "缺少历史K线",
    "淘汰",
]
GROUPS = PIPELINE_STAGES
MAIN_GROUPS = ["初筛", "观察", "待买", "持仓", "淘汰"]


def stage_to_group(stage: Any) -> str:
    """Map detailed rule stages to the user-facing workbench group."""
    text = str(stage or "").strip()
    if text == "待买观察":
        return "待买"
    if text in {"重点观察", "等回踩", "资金不足观察"}:
        return "观察"
    if text == "淘汰":
        return "淘汰"
    return "初筛"


def clean_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    match = re.search(r"(\d{6})", text)
    return match.group(1) if match else ""


def is_main_board(code: str) -> bool:
    return clean_code(code).startswith(ALLOWED_PREFIXES)


def screening_result(code: str, name: str) -> tuple[bool, str]:
    code = clean_code(code)
    name = str(name or "").strip().upper()
    if not code:
        return False, "股票代码无效"
    if code == "000725":
        return False, "规则排除京东方A"
    if "ST" in name:
        return False, "规则排除ST"
    if not is_main_board(code):
        return False, "非沪深主板范围"
    return True, "通过"


def is_number(value: Any) -> bool:
    try:
        return not math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def ma5_deviation(price: Any, ma5: Any) -> float | None:
    if not is_number(price) or not is_number(ma5) or float(ma5) == 0:
        return None
    return (float(price) - float(ma5)) / float(ma5) * 100


def buy_signal(deviation: float | None) -> str:
    if deviation is None:
        return "待补充MA5"
    if deviation < 0:
        return "跌破5日线，不买"
    if deviation <= 2:
        return "待买观察"
    if deviation <= 5:
        return "重点观察"
    return "远离5日线，不追，等回踩"


def affordability(price: Any, capital: float = 10000) -> tuple[bool, float | None]:
    if not is_number(price):
        return False, None
    lot_cost = float(price) * 100
    return lot_cost <= capital, lot_cost


def score_stock(row: dict[str, Any]) -> tuple[int, str]:
    score = 0
    passed, _ = screening_result(row.get("代码", ""), row.get("名称", ""))
    if passed:
        score += 1
    rank = row.get("成交额排名")
    if is_number(rank) and float(rank) <= 30:
        score += 1
    if is_number(row.get("最近大阳线%")) and float(row["最近大阳线%"]) >= 5:
        score += 2
    if bool(row.get("MA5向上", False)):
        score += 2
    deviation = ma5_deviation(row.get("现价"), row.get("MA5"))
    if deviation is not None and deviation >= 0:
        score += 2
    if not bool(row.get("放量跌破MA5", False)):
        score += 2
    level = "重点观察" if score >= 8 else "初筛通过" if score >= 6 else "淘汰"
    return score, level


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "是", "yes", "y", "可以买"}


def recent_big_line(row: dict[str, Any]) -> bool:
    return is_number(row.get("最近大阳线%")) and float(row.get("最近大阳线%")) >= 5


def rank_top_30(row: dict[str, Any]) -> bool:
    rank = row.get("成交额排名")
    return is_number(rank) and float(rank) <= 30


def valid_history(row: dict[str, Any]) -> bool:
    status = str(row.get("history_status", "") or "")
    if status in {"缺少历史K线", "自动获取失败", "数据不足", "缓存过旧"}:
        return False
    rows = row.get("history_rows")
    if is_number(rows) and float(rows) < 20:
        return False
    return all(is_number(row.get(column)) for column in ("MA5", "MA10", "MA20"))


def stock_stage_result(row: dict[str, Any]) -> tuple[str, str, str]:
    """Classify a stock into the current strong-pullback workflow stage.

    Returns:
        (stage, reason, reminder)
    """
    code = str(row.get("代码", ""))
    name = str(row.get("名称", ""))
    passed, reason = screening_result(code, name)
    if not passed:
        return "淘汰", reason, reason

    if not rank_top_30(row):
        return "淘汰", "成交额未进入前30", "不在今日成交额前30，暂不参与"

    history_status = str(row.get("history_status", "") or "")
    if history_status in {"自动获取失败", "缺少历史K线"}:
        return "缺少历史K线", "缺少有效历史K线", "缺少历史K线，暂不能判断MA5"
    if history_status == "缓存过旧":
        error = str(row.get("history_error", "") or "历史K线缓存过旧")
        return "缺少历史K线", "缓存过旧", error
    if history_status == "数据不足":
        error = str(row.get("history_error", "") or "历史K线数据不足")
        return "缺少历史K线", "历史K线数据不足", error
    if not valid_history(row):
        return "缺少历史K线", "历史K线数据不足", "历史K线数据不足，至少需要20条有效收盘价"

    has_big_line = recent_big_line(row)
    ma5_up = truthy(row.get("MA5向上"))
    deviation = row.get("MA5偏离率%")
    if not is_number(deviation):
        deviation = ma5_deviation(row.get("现价"), row.get("MA5"))
    affordable = str(row.get("本金是否可买", row.get("资金可买", ""))) == "可以买"

    if truthy(row.get("放量跌破MA5")):
        return "淘汰", "放量跌破MA5", "放量跌破MA5，不纳入观察"
    if not has_big_line:
        return "淘汰", "无5%阳线启动信号", "近10-20日无5%强势阳线"
    if not ma5_up:
        return "淘汰", "MA5向下", "MA5未向上，不参与"
    if deviation is None or not is_number(deviation):
        return "初筛通过", "等待MA5偏离率", "初筛通过，等待补充MA5偏离率"

    deviation_f = float(deviation)
    if deviation_f < 0:
        return "淘汰", "跌破MA5", "跌破MA5，不买"
    if deviation_f <= 2:
        if affordable:
            return "待买观察", "回踩MA5 0%-2%，本金可买", "接近5日线，盘中确认"
        return "资金不足观察", "形态接近但本金买不起一手", "形态接近，但本金买不起一手"
    if deviation_f <= 5:
        return "重点观察", "MA5偏离率2%-5%", "强势在线，继续观察回踩"
    return "等回踩", "远离5日线，不追", "远离5日线，不追，等回踩"


def evaluate_stock(row: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one stock row without side effects.

    Rules stay pure here: no file IO, no network, no Streamlit state.
    """
    stage, reason, reminder = stock_stage_result(row)
    group = stage_to_group(stage)
    can_buy = stage == "待买观察"
    if stage == "淘汰":
        risk_level = "danger"
    elif stage in {"缺少历史K线", "资金不足观察"}:
        risk_level = "warning"
    else:
        risk_level = "normal"
    return {
        "code": clean_code(row.get("代码", "")),
        "group": group,
        "stage": stage,
        "can_buy": can_buy,
        "risk_level": risk_level,
        "reason": reason,
        "reminder": reminder,
    }


def holding_advice(
    current_price: Any,
    ma5: Any,
    quantity: Any,
    below_ma5_days: Any = 0,
) -> str:
    deviation = ma5_deviation(current_price, ma5)
    qty = int(quantity) if is_number(quantity) else 0
    days = int(below_ma5_days) if is_number(below_ma5_days) else 0
    if days >= 3:
        return "连续3天未站回MA5，清仓"
    if deviation is None:
        return "补充当前价和MA5"
    if deviation < 0:
        return "14:50仍跌破MA5，考虑全卖" if qty < 200 else "14:50仍跌破MA5，减仓或卖出"
    if deviation > 7:
        return "远离MA5，考虑全卖" if qty < 200 else "远离MA5，考虑卖出一半"
    if deviation <= 2:
        return "回踩MA5未破，继续持有"
    return "趋势未破，持有观察"


def can_be_watchlist_candidate(
    code: str,
    name: str,
    has_history: bool,
    has_big_line: bool,
    ma5_up: bool,
    deviation: float | None,
    affordable: bool,
) -> tuple[bool, str]:
    """Determine if a stock qualifies for 待买.

    Must meet:
    - 主板
    - 非ST
    - non-创业板/科创板/北交所
    - non-京东方A
    - 有历史K线
    - 最近有5%阳线
    - MA5向上
    - 当前价在MA5上方 (偏离率 >= 0)
    - MA5偏离率在0%-2%
    - 当前本金买得起一手

    Returns:
        (qualifies, reason)
    """
    passed, reason = screening_result(code, name)
    if not passed:
        return False, reason

    if not has_history:
        return False, "缺少历史K线，待补充"

    if not has_big_line:
        return False, "缺少5%阳线启动信号"

    if not ma5_up:
        return False, "MA5未向上"

    if deviation is None:
        return False, "无法计算MA5偏离率"

    if deviation < 0:
        return False, "当前价在MA5下方"

    if deviation > 2:
        return False, "偏离MA5超过2%"

    if not affordable:
        return False, "形态符合，但本金买不起一手"

    return True, "符合待买条件"


def can_be_observation_candidate(
    code: str,
    name: str,
    has_history: bool,
    has_big_line: bool,
    ma5_up: bool,
    deviation: float | None,
) -> tuple[bool, str]:
    """Determine if a stock passes the non-capital rule constraints."""
    passed, reason = screening_result(code, name)
    if not passed:
        return False, reason

    if not has_history:
        return False, "缺少历史K线，待补充"

    if not has_big_line:
        return False, "缺少5%阳线启动信号"

    if not ma5_up:
        return False, "MA5未向上"

    if deviation is None:
        return False, "无法计算MA5偏离率"

    if deviation < 0:
        return False, "当前价在MA5下方"

    if deviation > 2:
        return False, "偏离MA5超过2%"

    return True, "符合观察规则"


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
    """Backward-compatible group classifier."""
    if current_group == "淘汰":
        return "淘汰"

    qualifies, _ = can_be_watchlist_candidate(
        code, name, has_history, has_big_line, ma5_up, deviation, affordable
    )
    if qualifies:
        return "待买观察"

    observation_ok, _ = can_be_observation_candidate(
        code, name, has_history, has_big_line, ma5_up, deviation
    )
    if observation_ok:
        if deviation is not None and deviation > 5:
            return "等回踩"
        return "重点观察"

    if not has_history:
        return "缺少历史K线"
    if not affordable and deviation is not None and 0 <= deviation <= 2:
        return "资金不足观察"
    return "初筛通过"


def 提醒_level_for_deviation(deviation: float | None, has_5pct_candle: bool) -> str:
    """Color level for the reminder based on MA5 deviation."""
    if deviation is None:
        return "purple"  # 缺少数据
    if deviation < 0:
        return "red"
    if deviation <= 2:
        return "blue"
    if deviation <= 5:
        return "amber"
    if deviation <= 7:
        return "orange"
    return "red"  # > 7% or has no big candle
