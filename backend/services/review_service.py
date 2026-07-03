from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from src.data import DATA_DIR

from backend.services.portfolio_service import portfolio_snapshot
from backend.services.trade_service import list_trades
from backend.services.watchlist_service import list_watchlist
from backend.storage.backup import backup_before_write
from backend.storage.sqlite_store import register_report

REPORT_ROOT = DATA_DIR / "reports"


def _report_dir(report_type: str) -> Path:
    safe_type = report_type if report_type in {"daily", "weekly", "monthly"} else "daily"
    path = REPORT_ROOT / safe_type
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_before_write(path)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _today() -> str:
    return date.today().isoformat()


def audit(mode: str | None = None) -> dict[str, Any]:
    trades = list_trades(mode)["list"]
    buys = [trade for trade in trades if trade.get("type") == "BUY"]
    total_buy = len(buys)
    compliant = [trade for trade in buys if trade.get("rulesConclusion") == "符合规则"]
    violations = [
        {
            "id": trade.get("id"),
            "code": trade.get("code"),
            "name": trade.get("name"),
            "date": trade.get("date"),
            "price": trade.get("price"),
            "rulesConclusion": trade.get("rulesConclusion"),
            "tags": trade.get("violationTags", []),
        }
        for trade in buys
        if trade.get("rulesConclusion") != "符合规则"
    ]
    rate = round(len(compliant) / total_buy * 100, 2) if total_buy else 100
    return {
        "complianceRate": rate,
        "compliantCount": len(compliant),
        "totalBuy": total_buy,
        "violationsList": violations,
    }


def today_review(mode: str | None = None) -> dict[str, Any]:
    today = _today()
    trades = list_trades(mode)["list"]
    today_trades = [trade for trade in trades if str(trade.get("date")) == today]
    portfolio = portfolio_snapshot(mode)
    return {
        "date": today,
        "todayTrades": today_trades,
        "positions": portfolio["positions"],
        "accountState": portfolio["accountState"],
        "audit": audit(mode),
    }


def report_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report.get('date', _today())} 复盘",
        "",
        f"- 类型: {report.get('type', 'daily')}",
        f"- 买入次数: {report.get('buyCount', 0)}",
        f"- 卖出次数: {report.get('sellCount', 0)}",
        f"- 规则符合率: {report.get('ruleComplianceRate', 100)}%",
        f"- 已实现盈亏: {report.get('realizedPnL', 0)}",
        f"- 持仓风险: {report.get('portfolioRisk', '')}",
        "",
        "## 今日复盘",
        "",
        str(report.get("summary", "")).strip(),
        "",
        "## 明日计划",
        "",
        str(report.get("tomorrowPlan", "")).strip(),
    ]
    market = report.get("marketAnalysis") or {}
    if market:
        lines.extend(
            [
                "",
                "## 复盘大盘",
                "",
                f"- 上证: {market.get('shTrend', '')} / {market.get('shVolume', '')} / {market.get('shFlow', '')}",
                f"- 深成: {market.get('szTrend', '')} / {market.get('szVolume', '')} / {market.get('szFlow', '')}",
                f"- 创业板: {market.get('cyTrend', '')} / {market.get('cyVolume', '')} / {market.get('cyFlow', '')}",
                f"- 系统性风险: {'是' if market.get('systemicRisk') else '否'}",
            ]
        )
    sector = report.get("sectorAnalysis") or {}
    if sector:
        lines.extend(
            [
                "",
                "## 复盘板块",
                "",
                f"- 已复盘 ETF 数: {sector.get('reviewedEtfCount', 0)}",
                f"- 热点板块: {sector.get('hotSectors', '')}",
                f"- 资金备注: {sector.get('etfFlowNotes', '')}",
            ]
        )
    stock = report.get("stockAnalysis") or {}
    diagnosed = stock.get("diagnosedHoldings") or []
    if stock:
        lines.extend(
            [
                "",
                "## 复盘个股",
                "",
                f"- Top200 已复盘: {'是' if stock.get('top200Reviewed') else '否'}",
                f"- 量比已复盘: {'是' if stock.get('volRatioReviewed') else '否'}",
                f"- 涨停已复盘: {'是' if stock.get('limitUpReviewed') else '否'}",
            ]
        )
        for item in diagnosed:
            lines.append(f"- {item.get('code', '')} {item.get('name', '')}: {item.get('judgment', '')}；{item.get('actionPlan', '')}")
    action = report.get("actionAudit") or {}
    if action:
        lines.extend(
            [
                "",
                "## 复盘操作",
                "",
                f"- 卖出纪律: {action.get('sellCompliant', '')}",
                f"- 盈利经验: {action.get('profitExperience', '')}",
                f"- 亏损分析: {action.get('lossAnalysis', '')}",
            ]
        )
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
    portfolio = portfolio_snapshot(mode)
    today = _today()
    today_trades = [trade for trade in trades if str(trade.get("date")) == today]

    total = len(watchlist)
    up = len([stock for stock in watchlist if float(stock.get("pct") or 0) > 0])
    down = len([stock for stock in watchlist if float(stock.get("pct") or 0) < 0])
    above_ma5 = len(
        [
            stock
            for stock in watchlist
            if float(stock.get("ma5") or 0) > 0 and float(stock.get("price") or 0) > float(stock.get("ma5") or 0)
        ]
    )
    rise_ratio = round(up / total * 100) if total else 0
    above_ratio = round(above_ma5 / total * 100) if total else 0
    bullish = round((rise_ratio + above_ratio) / 2) if total else 0

    sectors = _sector_summary(watchlist)
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
    compliant = [trade for trade in today_buys if trade.get("rulesConclusion") == "符合规则"]
    compliance_rate = round(len(compliant) / len(today_buys) * 100) if today_buys else 100
    return {
        "todayTrades": today_trades,
        "currentPositions": portfolio["positions"],
        "marketSnapshot": {
            "totalStocks": total,
            "upStocks": up,
            "downStocks": down,
            "riseRatio": rise_ratio,
            "aboveMA5Count": above_ma5,
            "aboveMA5Ratio": above_ratio,
            "bullishIndex": bullish,
            "marketStrength": "强" if bullish > 60 else "弱" if bullish < 40 else "中",
            "trendStrength": "strong" if bullish > 60 else "weak" if bullish < 40 else "neutral",
            "riseCount": up,
            "fallCount": down,
        },
        "sectors": sectors,
        "holdingDeviation": holding_deviation,
        "summaryStatistics": {"complianceRate": compliance_rate},
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

