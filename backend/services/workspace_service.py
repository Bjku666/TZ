from __future__ import annotations

from datetime import datetime, time
from math import isfinite
from typing import Any
from uuid import uuid4

from backend.storage import account_store as store
from backend.services.ledger_engine import _buy_audit, _now_hm, _round, _simulate, _today, calculate_fees

def _pending_actions(mode: str, positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for position in positions:
        status = position["status"]
        if status == "T+1 锁定":
            action_type, priority, title = "T1_LOCKED", "normal", "T+1 锁定"
        elif status == "次日观察":
            action_type, priority, title = "NEXT_DAY_OBSERVING", "warning", "10:00 前观察"
        elif status == "10:00 待处理":
            action_type, priority, title = "MORNING_EXIT_DUE", "danger", "10:00 纪律处理"
        elif status == "已延迟至尾盘":
            action_type, priority, title = "DEFERRED_TO_AFTERNOON", "warning", "已延迟至尾盘"
        else:
            action_type, priority, title = "AFTERNOON_EXIT_DUE", "danger", "尾盘处理到期"
        actions.append({
            "id": f"{mode}:{position['code']}:{action_type}",
            "accountMode": mode,
            "code": position["code"],
            "name": position["name"],
            "type": action_type,
            "priority": priority,
            "title": title,
            "message": position["advice"],
            "nextActionTime": position.get("nextActionTime"),
            "position": position,
        })
    return actions


def _review_summary(mode: str, trades: list[dict[str, Any]], account: dict[str, Any], cycle_pnls: list[float]) -> dict[str, Any]:
    wins = [value for value in cycle_pnls if value > 0]
    losses = [value for value in cycle_pnls if value < 0]
    violations = sum(1 for item in trades if item.get("rulesConclusion") != "符合规则")
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    dates = [item["date"] for item in trades]
    return {
        "mode": mode,
        "startDate": min(dates) if dates else _today(),
        "endDate": max(dates) if dates else _today(),
        "tradeCount": len(trades),
        "completedCycles": len(cycle_pnls),
        "winRate": _round(len(wins) / len(cycle_pnls) * 100 if cycle_pnls else 0),
        "averageWin": _round(avg_win),
        "averageLoss": _round(avg_loss),
        "profitLossRatio": _round(avg_win / avg_loss if avg_loss else 0),
        "totalPnL": account["totalPnL"],
        "totalReturnPct": account["totalReturnPct"],
        "maxSingleWin": _round(max(wins) if wins else 0),
        "maxSingleLoss": _round(min(losses) if losses else 0),
        "totalFees": _round(sum(float(item["totalFee"]) for item in trades)),
        "complianceRate": _round((len(trades) - violations) / len(trades) * 100 if trades else 100),
        "violationCount": violations,
    }


def app_settings() -> dict[str, Any]:
    simulation = store.get_settings("simulation")
    real = store.get_settings("real")
    return {
        "simulation": {key: value for key, value in simulation.items() if key != "reconciliation"},
        "real": {key: value for key, value in real.items() if key != "reconciliation"},
        "reconciliation": {
            "simulation": simulation.get("reconciliation", {}),
            "real": real.get("reconciliation", {}),
        },
        "market": {
            "source": "不连接实时行情；价格取账户最近一次成交记录",
            "autoRefresh": False,
            "refreshInterval": 60,
            "refreshOutsideTradingHours": False,
            "expiryThreshold": 0,
            "showExceptionAlert": True,
        },
    }


def workspace(mode: str) -> dict[str, Any]:
    mode = store.validate_mode(mode)
    trades = store.list_trades(mode)
    account, positions, cycle_pnls = _simulate(mode, trades)
    return {
        "mode": mode,
        "account": account,
        "positions": positions,
        "trades": trades,
        "pendingActions": _pending_actions(mode, positions),
        "reviewSummary": _review_summary(mode, trades, account, cycle_pnls),
        "reviews": store.list_reviews(mode),
        "notifications": store.list_notifications(mode),
        "settings": app_settings(),
        "marketPhase": _market_phase(),
        "quoteUpdatedAt": "未连接实时行情",
    }


def _market_phase() -> str:
    now = datetime.now()
    if now.weekday() >= 5:
        return "休市"
    current = now.time()
    if time(9, 30) <= current < time(11, 30) or time(13, 0) <= current < time(15, 0):
        return "交易中"
    if current < time(9, 30):
        return "盘前"
    return "收盘后"


def create_trade(mode: str, payload: dict[str, Any]) -> dict[str, Any]:
    mode = store.validate_mode(mode)
    settings = store.get_settings(mode)
    current_workspace = workspace(mode)
    side = str(payload.get("type", "BUY")).upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("type 必须是 BUY 或 SELL")
    price = float(payload.get("price", 0))
    quantity = int(payload.get("quantity", 0))
    if not isfinite(price) or price <= 0 or quantity <= 0:
        raise ValueError("价格和数量必须大于 0")
    fees = calculate_fees(side, price, quantity, settings)
    historical = bool(payload.get("historicalBackfill", False))
    if historical:
        conclusion, tags = "无法判断", ["历史补录"]
    elif side == "BUY":
        conclusion, tags = _buy_audit(price, quantity, str(payload.get("time", _now_hm())), current_workspace["account"]["availableCash"], fees)
    else:
        position = next((item for item in current_workspace["positions"] if item["code"] == str(payload.get("code", ""))), None)
        if not position or quantity > int(position["availableQuantity"]):
            raise ValueError("卖出数量超过当前账户的可卖数量，或该账户不存在此持仓")
        conclusion, tags = "符合规则", []
    trade = {
        "id": str(payload.get("id") or f"trade-{uuid4().hex}"),
        "accountMode": mode,
        "code": str(payload.get("code", "")).strip(),
        "name": str(payload.get("name", "")).strip() or str(payload.get("code", "")).strip(),
        "type": side,
        "date": str(payload.get("date") or _today()),
        "time": str(payload.get("time") or datetime.now().strftime("%H:%M:%S")),
        "price": price,
        "quantity": quantity,
        "amount": _round(price * quantity),
        **fees,
        "reason": str(payload.get("reason", "")),
        "remark": str(payload.get("remark", "")),
        "rulesConclusion": str(payload.get("rulesConclusion") or conclusion),
        "violationTags": payload.get("violationTags") or tags,
        "historicalBackfill": historical,
        "manualFeeOverride": bool(payload.get("manualFeeOverride", False)),
    }
    if not trade["code"]:
        raise ValueError("股票代码不能为空")
    saved = store.upsert_trade(mode, trade)
    level = "VIOLATION" if saved["rulesConclusion"] == "违规交易" else "SUCCESS"
    store.add_notification(mode, level, "交易记录已保存", f"{saved['name']} {saved['type']} {saved['quantity']} 股，账户数据已重新计算。", saved["code"])
    return workspace(mode)


def update_trade(mode: str, trade_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    existing = store.get_trade(store.validate_mode(mode), trade_id)
    if not existing:
        raise ValueError("交易记录不存在")
    merged = {**existing, **payload, "id": trade_id, "accountMode": mode}
    price = float(merged["price"])
    quantity = int(merged["quantity"])
    merged["amount"] = _round(price * quantity)
    if not merged.get("manualFeeOverride"):
        merged.update(calculate_fees(merged["type"], price, quantity, store.get_settings(mode)))
    store.upsert_trade(mode, merged)
    store.add_notification(mode, "INFO", "交易记录已更新", f"{merged['name']} 的成交记录和账户汇总已重算。", merged["code"])
    return workspace(mode)


def delete_trade(mode: str, trade_id: str) -> dict[str, Any]:
    existing = store.get_trade(store.validate_mode(mode), trade_id)
    if not existing:
        raise ValueError("交易记录不存在")
    store.delete_trade(mode, trade_id)
    store.add_notification(mode, "WARNING", "交易记录已删除", f"已删除 {existing['name']} 的一笔交易，账户流水已重算。", existing["code"])
    return workspace(mode)


def recalculate_fees(mode: str) -> dict[str, Any]:
    settings = store.get_settings(store.validate_mode(mode))
    for trade in store.list_trades(mode):
        if trade.get("manualFeeOverride"):
            continue
        trade.update(calculate_fees(trade["type"], trade["price"], trade["quantity"], settings))
        store.upsert_trade(mode, trade)
    store.add_notification(mode, "SUCCESS", "手续费重算完成", "当前账户全部非手工覆盖交易已按最新费率重算。")
    return workspace(mode)


def update_settings(mode: str, app_payload: dict[str, Any]) -> dict[str, Any]:
    mode = store.validate_mode(mode)
    account_payload = dict(app_payload.get(mode, app_payload))
    if "reconciliation" in app_payload and mode in app_payload["reconciliation"]:
        account_payload["reconciliation"] = app_payload["reconciliation"][mode]
    store.save_settings(mode, account_payload)
    store.add_notification(mode, "INFO", "账户设置已更新", "初始资金、费率和对账设置仅应用于当前账户。")
    return workspace(mode)


def defer_position(mode: str, code: str, reason: str = "") -> dict[str, Any]:
    current = workspace(mode)
    position = next((item for item in current["positions"] if item["code"] == code), None)
    if not position:
        raise ValueError("当前账户不存在此持仓")
    store.save_position_state(mode, code, buy_date=position["buyDate"], deferred=True,
                              defer_reason=reason or "用户明确延迟至 14:30 后处理")
    store.add_notification(mode, "WARNING", "已延迟至尾盘", f"{position['name']} 已进入当前账户的尾盘处理队列。", code)
    return workspace(mode)


def cancel_defer(mode: str, code: str) -> dict[str, Any]:
    store.save_position_state(mode, code, deferred=False, defer_reason="")
    store.add_notification(mode, "INFO", "已撤销尾盘延迟", f"{code} 已恢复标准处理节奏。", code)
    return workspace(mode)


def add_note(mode: str, code: str, note: str) -> dict[str, Any]:
    note = note.strip()
    if not note:
        raise ValueError("备注不能为空")
    current = store.get_position_state(mode, code)
    notes = [*current.get("notes", []), f"{datetime.now().strftime('%Y-%m-%d %H:%M')} {note}"][-50:]
    store.save_position_state(mode, code, notes=notes)
    return workspace(mode)


def save_review(mode: str, payload: dict[str, Any]) -> dict[str, Any]:
    required = ["planAndBasis", "executionAndDeviation", "resultAndEmotion", "improvementAndNextPlan"]
    if not any(str(payload.get(key, "")).strip() for key in required):
        raise ValueError("复盘内容不能全部为空")
    store.save_review(store.validate_mode(mode), payload)
    store.add_notification(mode, "SUCCESS", "复盘已保存", f"{payload.get('date', _today())} 的四段式复盘已归档。")
    return workspace(mode)
