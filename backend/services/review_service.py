from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from src.data import DATA_DIR

from backend.services.portfolio_service import portfolio_snapshot
from backend.services.risk_service import market_risk_snapshot, sector_summary
from backend.services.trade_service import list_trades
from backend.services.watchlist_service import list_watchlist
from backend.storage.sqlite_store import register_report
from src.storage import safe_write_text

REPORT_ROOT = DATA_DIR / "reports"


def _report_dir(report_type: str) -> Path:
    safe_type = report_type if report_type in {"daily", "weekly", "monthly"} else "daily"
    path = REPORT_ROOT / safe_type
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_write_text(path: Path, content: str) -> None:
    safe_write_text(path, content)


def _today() -> str:
    return date.today().isoformat()


def audit(mode: str | None = None) -> dict[str, Any]:
    trades = list_trades(mode)["list"]
    buys = [trade for trade in trades if trade.get("type") == "BUY"]
    sells = [trade for trade in trades if trade.get("type") == "SELL"]
    total_buy = len(buys)
    total_sell = len(sells)
    total_trades = len(trades)
    compliant = [trade for trade in buys if trade.get("rulesConclusion") == "符合规则"]
    compliant_sells = [trade for trade in sells if trade.get("rulesConclusion") == "符合规则"]
    compliant_trades = [trade for trade in trades if trade.get("rulesConclusion") == "符合规则"]
    violations = [
        {
            "id": trade.get("id"),
            "code": trade.get("code"),
            "name": trade.get("name"),
            "date": trade.get("date"),
            "type": trade.get("type"),
            "price": trade.get("price"),
            "rulesConclusion": trade.get("rulesConclusion"),
            "tags": trade.get("violationTags", []),
        }
        for trade in trades
        if trade.get("rulesConclusion") != "符合规则"
    ]
    buy_rate = round(len(compliant) / total_buy * 100, 2) if total_buy else 100
    sell_rate = round(len(compliant_sells) / total_sell * 100, 2) if total_sell else 100
    trade_rate = round(len(compliant_trades) / total_trades * 100, 2) if total_trades else 100
    return {
        "complianceRate": trade_rate,
        "buyComplianceRate": buy_rate,
        "sellComplianceRate": sell_rate,
        "compliantCount": len(compliant),
        "compliantTradeCount": len(compliant_trades),
        "totalBuy": total_buy,
        "totalSell": total_sell,
        "totalTrades": total_trades,
        "violationsList": violations,
    }


def _trade_brief(trade: dict[str, Any] | None) -> dict[str, Any] | None:
    if not trade:
        return None
    return {
        "id": trade.get("id"),
        "date": trade.get("date"),
        "time": trade.get("time"),
        "type": trade.get("type"),
        "price": trade.get("price"),
        "quantity": trade.get("quantity"),
        "reason": trade.get("reason"),
        "rulesConclusion": trade.get("rulesConclusion"),
        "violationTags": trade.get("violationTags", []),
    }


def _stock_links(trades: list[dict[str, Any]], positions: list[dict[str, Any]], target_date: str) -> list[dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {}
    for pos in positions:
        code = str(pos.get("code") or "")
        if not code:
            continue
        by_code[code] = {
            "code": code,
            "name": pos.get("name"),
            "position": pos,
            "todayTrades": [],
            "allTrades": [],
        }
    for trade in trades:
        code = str(trade.get("code") or "")
        if not code:
            continue
        item = by_code.setdefault(
            code,
            {"code": code, "name": trade.get("name"), "position": None, "todayTrades": [], "allTrades": []},
        )
        item["name"] = item.get("name") or trade.get("name")
        item["allTrades"].append(trade)
        if str(trade.get("date")) == target_date:
            item["todayTrades"].append(trade)

    links: list[dict[str, Any]] = []
    for item in by_code.values():
        all_rows = sorted(item["allTrades"], key=lambda trade: (str(trade.get("date") or ""), str(trade.get("time") or "")))
        today_rows = sorted(item["todayTrades"], key=lambda trade: str(trade.get("time") or ""))
        buys = [trade for trade in all_rows if trade.get("type") == "BUY"]
        sells = [trade for trade in all_rows if trade.get("type") == "SELL"]
        position = item.get("position") or {}
        tags = sorted(
            {
                str(tag)
                for trade in all_rows
                if trade.get("rulesConclusion") != "符合规则"
                for tag in trade.get("violationTags", [])
            }
        )
        position_advice = str(position.get("advice") or "")
        if tags:
            review_focus = "有违规标签，复盘先解释交易依据"
        elif position and position.get("riskLevel") == "danger":
            review_focus = "当前持仓触发风险，复盘卖点执行"
        elif today_rows:
            review_focus = "今日有交易，复盘买卖是否按计划"
        else:
            review_focus = "继续跟踪持仓纪律"
        links.append(
            {
                "code": item.get("code"),
                "name": item.get("name"),
                "position": position or None,
                "todayTrades": [_trade_brief(trade) for trade in today_rows],
                "lastBuy": _trade_brief(buys[-1] if buys else None),
                "lastSell": _trade_brief(sells[-1] if sells else None),
                "hasComplianceIssue": bool(tags),
                "complianceTags": tags,
                "reviewFocus": review_focus,
                "actionPlan": position_advice or "按交易记录复查买卖依据，明日只执行既定计划",
            }
        )
    links.sort(key=lambda item: (0 if item.get("position") else 1, str(item.get("code") or "")))
    return links


def today_review(mode: str | None = None) -> dict[str, Any]:
    today = _today()
    trades = list_trades(mode)["list"]
    today_trades = [trade for trade in trades if str(trade.get("date")) == today]
    portfolio = portfolio_snapshot(mode, persist_risk_state=True)
    return {
        "date": today,
        "todayTrades": today_trades,
        "positions": portfolio["positions"],
        "accountState": portfolio["accountState"],
        "audit": audit(mode),
        "stockLinks": _stock_links(trades, portfolio["positions"], today),
    }


def _clean_text(value: Any, fallback: str = "未填写") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _fmt_money(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _fmt_pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    prefix = "+" if number > 0 else ""
    return f"{prefix}{number:.2f}%"


def _fmt_amount_yi(value: Any) -> str:
    try:
        return f"{float(value) / 100000000:.1f}亿"
    except (TypeError, ValueError):
        return "-"


def _diagnosis_type_label(value: Any) -> str:
    labels = {
        "holding": "当前持仓",
        "todayBuy": "今日买入",
        "todaySell": "今日卖出",
        "manual": "手动加入",
        "step1": "步骤1手动加入",
        "step2": "步骤2手动加入",
        "step3": "步骤3手动加入",
    }
    return labels.get(str(value or ""), str(value or "手动加入"))


def _stock_screening(report: dict[str, Any]) -> dict[str, Any]:
    stock = report.get("stockAnalysis") or {}
    screening = report.get("stockScreening") or {}
    return {
        "step1": screening.get("step1")
        or {"title": "当前成交额前30初筛池复查", "reviewed": stock.get("top200Reviewed"), "stocks": stock.get("step1Screened") or []},
        "step2": screening.get("step2")
        or {"title": "量比前50且成交额10-20亿", "reviewed": stock.get("volRatioReviewed"), "stocks": stock.get("step2Screened") or []},
        "step3": screening.get("step3")
        or {"title": "涨跌停板与情绪高度核查", "reviewed": stock.get("limitUpReviewed"), "stocks": stock.get("step3Screened") or []},
    }


def report_markdown(report: dict[str, Any]) -> str:
    stats = report.get("summaryStats") or {}
    account = report.get("accountSnapshot") or {}
    trades = report.get("todayTrades") or []
    positions = report.get("currentPositions") or []
    stock_links = report.get("stockLinks") or report.get("linkedStockReviews") or []
    market = report.get("marketAnalysis") or {}
    sector = report.get("sectorAnalysis") or {}
    action = report.get("actionAudit") or {}
    reflection = report.get("reflection") or {}
    stock = report.get("stockAnalysis") or {}
    diagnosis = report.get("selfDiagnosis") or {}
    diagnosed = diagnosis.get("items") or stock.get("selfDiagnostics") or stock.get("diagnosedHoldings") or []
    summary = _clean_text(reflection.get("summary") or report.get("summary"))
    tomorrow_plan = _clean_text(reflection.get("tomorrowPlan") or report.get("tomorrowPlan"))

    buy_count = stats.get("buyCount", report.get("buyCount", 0))
    sell_count = stats.get("sellCount", report.get("sellCount", 0))
    compliance = stats.get("ruleComplianceRate", report.get("ruleComplianceRate", 100))
    buy_compliance = stats.get("buyComplianceRate", report.get("buyComplianceRate", compliance))
    sell_compliance = stats.get("sellComplianceRate", report.get("sellComplianceRate", compliance))
    trade_compliance = stats.get("tradeComplianceRate", report.get("tradeComplianceRate", compliance))
    realized_pnl = stats.get("realizedPnL", report.get("realizedPnL", 0))
    portfolio_risk = stats.get("portfolioRisk", report.get("portfolioRisk", ""))

    lines = [
        f"# {report.get('date', _today())} 强势回踩系统日报",
        "",
        "## 一、账户与交易结果",
        f"- 买入次数: {buy_count}",
        f"- 卖出次数: {sell_count}",
        f"- 买入规则符合率: {buy_compliance}%",
        f"- 卖出规则符合率: {sell_compliance}%",
        f"- 总交易符合率: {trade_compliance}%",
        f"- 已实现盈亏: {_fmt_money(realized_pnl)}",
        f"- 持仓风险: {_clean_text(portfolio_risk)}",
        f"- 今日交易流水: {len(trades)} 条",
        f"- 当前持仓: {len(positions)} 只",
        f"- 账户总资产: {_fmt_money(account.get('totalAssets'))}",
        f"- 可用现金: {_fmt_money(account.get('availableCash'))}",
        f"- 浮动盈亏: {_fmt_money(account.get('floatingPnL'))}",
        "",
        "## 二、大盘与系统环境",
        f"- 上证判断: {_clean_text(market.get('shTrend'))} / {_clean_text(market.get('shVolume'))} / {_clean_text(market.get('shFlow'))}",
        f"- 深成判断: {_clean_text(market.get('szTrend'))} / {_clean_text(market.get('szVolume'))} / {_clean_text(market.get('szFlow'))}",
        f"- 创业板判断: {_clean_text(market.get('cyTrend'))} / {_clean_text(market.get('cyVolume'))} / {_clean_text(market.get('cyFlow'))}",
        f"- 系统性风险: {'是' if market.get('systemicRisk') else '否'}",
        f"- 我的市场结论: {_clean_text(market.get('marketConclusion'))}",
        "",
        "## 三、板块复盘",
        f"- 已复盘 ETF 数量: {sector.get('reviewedEtfCount', 0)}",
        f"- 热点板块: {_clean_text(sector.get('hotSectors'))}",
        f"- 资金流与题材备注: {_clean_text(sector.get('etfFlowNotes'))}",
        "",
        "## 四、当前初筛池三步复查",
    ]

    for step_key, fallback_title in [
        ("step1", "当前成交额前30初筛池复查"),
        ("step2", "量比前50且成交额10-20亿"),
        ("step3", "涨跌停板与情绪高度核查"),
    ]:
        step = _stock_screening(report).get(step_key) or {}
        title = _clean_text(step.get("title"), fallback_title)
        stocks = step.get("stocks") or []
        lines.extend(["", f"### {title}", f"- 已复查: {'是' if step.get('reviewed') else '否'}"])
        if not stocks:
            lines.append("- 暂无扫描结果")
            continue
        lines.append(f"- 摘要前10只，完整 {len(stocks)} 只见 JSON")
        for item in stocks[:10]:
            name = _clean_text(item.get("name"), "")
            code = _clean_text(item.get("code"), "")
            reason = _clean_text(item.get("reason"), "")
            source_note = _clean_text(item.get("volRatioSource") or item.get("conceptSource"), "")
            lines.append(
                f"- {name} {code} | 涨跌 {_fmt_pct(item.get('pct'))} | 成交 {_fmt_amount_yi(item.get('volume'))} | {reason}"
                + (f" | {source_note}" if source_note != "未填写" else "")
            )

    lines.extend(["", "## 五、我的自我诊断记录"])
    if not diagnosed:
        lines.append("- 暂无自我诊断记录")
    for item in diagnosed:
        label = _clean_text(item.get("sourceTitle"), _diagnosis_type_label(item.get("type")))
        lines.extend(
            [
                f"- {item.get('name', '')} {item.get('code', '')}",
                f"  - 类型: {label}",
                f"  - 客观判断: {_clean_text(item.get('judgment'))}",
                f"  - 明日执行指令: {_clean_text(item.get('actionPlan'))}",
                f"  - 手写诊断: {_clean_text(item.get('notes'))}",
            ]
        )

    lines.extend(["", "## 六、交易-持仓闭环"])
    if not stock_links:
        lines.append("- 暂无按股票聚合的交易持仓闭环记录")
    for item in stock_links:
        last_buy = item.get("lastBuy") or {}
        last_sell = item.get("lastSell") or {}
        tags = item.get("complianceTags") or []
        lines.extend(
            [
                f"- {item.get('name', '')} {item.get('code', '')}",
                f"  - 最近买入: {_clean_text(last_buy.get('date'), '无')} {_fmt_money(last_buy.get('price'))} / {last_buy.get('quantity', 0)}股",
                f"  - 最近卖出: {_clean_text(last_sell.get('date'), '无')} {_fmt_money(last_sell.get('price'))} / {last_sell.get('quantity', 0)}股",
                f"  - 当前指令: {_clean_text(item.get('actionPlan'))}",
                f"  - 合规标签: {_clean_text('、'.join(tags), '无')}",
            ]
        )

    lines.extend(["", "## 七、纠错自省"])
    if any(action.values()):
        lines.extend(
            [
                f"- 卖出纪律: {_clean_text(action.get('sellCompliant'))}",
                f"- 盈利经验: {_clean_text(action.get('profitExperience'))}",
                f"- 亏损分析: {_clean_text(action.get('lossAnalysis'))}",
                "",
            ]
        )
    lines.append(summary)

    lines.extend(["", "## 八、明日计划", "", tomorrow_plan])
    return "\n".join(lines).strip() + "\n"


def save_report(report: dict[str, Any]) -> dict[str, Any]:
    report_type = str(report.get("type") or "daily")
    report_date = str(report.get("date") or _today())
    report_id = str(report.get("id") or f"{report_type}_{report_date}")
    report = {**report, "id": report_id, "type": report_type, "date": report_date}
    directory = _report_dir(report_type)
    json_path = directory / f"{report_date}.json"
    md_path = directory / f"{report_date}.md"
    _safe_write_text(json_path, json.dumps(report, ensure_ascii=False, indent=2))
    _safe_write_text(md_path, report_markdown(report))
    register_report(report_id, report_type, report_date, json_path, md_path)
    return {"success": True, "report": report, "jsonPath": str(json_path), "mdPath": str(md_path)}


def list_reports(report_type: str = "daily") -> dict[str, Any]:
    directory = _report_dir(report_type)
    reports: list[dict[str, Any]] = []
    for path in directory.glob("*.json"):
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    reports.sort(key=lambda item: str(item.get("date", "")), reverse=True)
    return {"reports": reports}


def context(mode: str | None = None) -> dict[str, Any]:
    trades = list_trades(mode)["list"]
    watchlist = list_watchlist()["list"]
    portfolio = portfolio_snapshot(mode, persist_risk_state=True)
    today = _today()
    today_trades = [trade for trade in trades if str(trade.get("date")) == today]

    market_snapshot = market_risk_snapshot(watchlist)
    sectors = sector_summary(watchlist)
    holding_deviation = [
        {
            "code": pos.get("code"),
            "name": pos.get("name"),
            "currentPrice": pos.get("currentPrice"),
            "ma5": pos.get("ma5"),
            "deviationPct": pos.get("deviation5"),
            "stateLabel": _deviation_label(float(pos.get("deviation5") or 0)),
            "recommendedAction": pos.get("advice"),
            "riskLevel": pos.get("riskLevel"),
        }
        for pos in portfolio["positions"]
    ]
    today_buys = [trade for trade in today_trades if trade.get("type") == "BUY"]
    today_sells = [trade for trade in today_trades if trade.get("type") == "SELL"]
    compliant = [trade for trade in today_buys if trade.get("rulesConclusion") == "符合规则"]
    compliant_sells = [trade for trade in today_sells if trade.get("rulesConclusion") == "符合规则"]
    compliant_trades = [trade for trade in today_trades if trade.get("rulesConclusion") == "符合规则"]
    compliance_rate = round(len(compliant) / len(today_buys) * 100) if today_buys else 100
    trade_compliance_rate = round(len(compliant_trades) / len(today_trades) * 100) if today_trades else 100
    sell_compliance_rate = round(len(compliant_sells) / len(today_sells) * 100) if today_sells else 100
    return {
        "todayTrades": today_trades,
        "currentPositions": portfolio["positions"],
        "marketSnapshot": market_snapshot,
        "sectors": sectors,
        "holdingDeviation": holding_deviation,
        "stockLinks": _stock_links(trades, portfolio["positions"], today),
        "summaryStatistics": {
            "complianceRate": trade_compliance_rate,
            "buyComplianceRate": compliance_rate,
            "sellComplianceRate": sell_compliance_rate,
        },
    }


def _sector_name(stock: dict[str, Any]) -> str:
    name = str(stock.get("name") or "")
    if "银行" in name:
        return "银行金融"
    if "证券" in name or "保险" in name:
        return "非银金融"
    if "酒" in name or "食品" in name:
        return "食品消费"
    if "药" in name or "医" in name:
        return "医药生物"
    if "电" in name or "能源" in name or "石油" in name:
        return "能源公用"
    if "科技" in name or "电子" in name or "半导体" in name:
        return "科技半导体"
    if "车" in name or "汽车" in name:
        return "新能源汽车"
    return "综合行业"


def _sector_summary(watchlist: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for stock in watchlist:
        sector = _sector_name(stock)
        item = groups.setdefault(
            sector,
            {"sectorName": sector, "sumPct": 0.0, "above": 0, "totalVolume": 0.0, "totalCount": 0},
        )
        item["sumPct"] += float(stock.get("pct") or 0)
        item["totalVolume"] += float(stock.get("volume") or 0)
        item["totalCount"] += 1
        if float(stock.get("ma5") or 0) > 0 and float(stock.get("price") or 0) > float(stock.get("ma5") or 0):
            item["above"] += 1
    result = []
    for item in groups.values():
        count = item["totalCount"] or 1
        result.append(
            {
                "sectorName": item["sectorName"],
                "avgChangePct": round(item["sumPct"] / count, 2),
                "aboveMA5Ratio": round(item["above"] / count * 100),
                "totalVolume": item["totalVolume"],
                "totalCount": item["totalCount"],
                "hotCandidate": False,
            }
        )
    result.sort(key=lambda row: row["avgChangePct"], reverse=True)
    if result:
        result[0]["hotCandidate"] = True
    return result


def _deviation_label(deviation: float) -> str:
    if deviation > 5:
        return "向上发散"
    if deviation < -3:
        return "向下破位"
    if abs(deviation) <= 1.5:
        return "窄幅粘合"
    return "温和发散"
