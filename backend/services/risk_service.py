from __future__ import annotations

from typing import Any

from backend.storage.csv_adapter import watchlist_to_api
from src.data import load_watchlist
from src.rules import clean_code


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sector_name(stock: dict[str, Any]) -> str:
    text = f"{stock.get('name') or ''}{stock.get('board') or ''}{stock.get('sector') or ''}"
    if "银行" in text:
        return "银行金融"
    if "证券" in text or "保险" in text:
        return "非银金融"
    if "酒" in text or "食品" in text:
        return "食品消费"
    if "药" in text or "医" in text:
        return "医药生物"
    if "电" in text or "能源" in text or "石油" in text:
        return "能源公用"
    if "科技" in text or "电子" in text or "半导体" in text:
        return "科技半导体"
    if "车" in text or "汽车" in text:
        return "新能源汽车"
    return "综合行业"


def sector_summary(watchlist: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for stock in watchlist:
        sector = _sector_name(stock)
        item = groups.setdefault(
            sector,
            {"sectorName": sector, "sumPct": 0.0, "above": 0, "totalVolume": 0.0, "totalCount": 0},
        )
        item["sumPct"] += _number(stock.get("pct"))
        item["totalVolume"] += _number(stock.get("volume"))
        item["totalCount"] += 1
        ma5 = _number(stock.get("ma5"))
        price = _number(stock.get("price"))
        if ma5 > 0 and price > ma5:
            item["above"] += 1

    result: list[dict[str, Any]] = []
    for item in groups.values():
        count = item["totalCount"] or 1
        above_ratio = round(item["above"] / count * 100)
        avg_change = round(item["sumPct"] / count, 2)
        result.append(
            {
                "sectorName": item["sectorName"],
                "avgChangePct": avg_change,
                "aboveMA5Ratio": above_ratio,
                "totalVolume": item["totalVolume"],
                "totalCount": item["totalCount"],
                "sectorWeak": avg_change < 0 and above_ratio < 40,
                "hotCandidate": False,
            }
        )
    result.sort(key=lambda row: row["avgChangePct"], reverse=True)
    if result:
        result[0]["hotCandidate"] = True
    return result


def market_risk_snapshot(watchlist: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if watchlist is None:
        watchlist = watchlist_to_api(load_watchlist())
    total = len(watchlist)
    up = len([stock for stock in watchlist if _number(stock.get("pct")) > 0])
    down = len([stock for stock in watchlist if _number(stock.get("pct")) < 0])
    above_ma5 = len(
        [
            stock
            for stock in watchlist
            if _number(stock.get("ma5")) > 0 and _number(stock.get("price")) > _number(stock.get("ma5"))
        ]
    )
    rise_ratio = round(up / total * 100) if total else 0
    above_ratio = round(above_ma5 / total * 100) if total else 0
    bullish = round((rise_ratio + above_ratio) / 2) if total else 0
    trend_strength = "strong" if bullish > 60 else "weak" if bullish < 40 else "neutral"
    return {
        "totalStocks": total,
        "upStocks": up,
        "downStocks": down,
        "riseRatio": rise_ratio,
        "aboveMA5Count": above_ma5,
        "aboveMA5Ratio": above_ratio,
        "bullishIndex": bullish,
        "marketStrength": "强" if trend_strength == "strong" else "弱" if trend_strength == "weak" else "中",
        "trendStrength": trend_strength,
        "riseCount": up,
        "fallCount": down,
        "marketWeak": trend_strength == "weak",
    }


def market_trade_filter_for_watchlist(watchlist: list[dict[str, Any]], code: str | None = None) -> dict[str, Any]:
    market = market_risk_snapshot(watchlist)
    sectors = sector_summary(watchlist)
    sector_by_name = {row["sectorName"]: row for row in sectors}

    stock_sector = ""
    sector = None
    cleaned = clean_code(code)
    for stock in watchlist:
        if cleaned and clean_code(stock.get("code")) == cleaned:
            stock_sector = _sector_name(stock)
            sector = sector_by_name.get(stock_sector)
            break

    if sector is None and sectors:
        sector = sectors[-1] if market["marketWeak"] else None

    sector_weak = bool(sector and sector.get("sectorWeak"))
    allowed = not market["marketWeak"] and not sector_weak
    reasons: list[str] = []
    if market["marketWeak"]:
        reasons.append("大盘弱")
    if sector_weak:
        reasons.append(f"{sector.get('sectorName', '所属板块')}弱")
    return {
        "allowed": allowed,
        "marketRisk": not allowed,
        "reasons": reasons,
        "marketSnapshot": market,
        "sectorSnapshot": sector or {},
        "sectors": sectors,
        "sectorName": stock_sector,
    }


def annotate_watchlist_risk(watchlist: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **stock,
            "marketTradeAllowed": market_filter["allowed"],
            "marketRisk": market_filter["marketRisk"],
            "marketRiskReasons": market_filter["reasons"],
            "sectorName": market_filter["sectorName"],
            "sectorWeak": bool((market_filter.get("sectorSnapshot") or {}).get("sectorWeak")),
        }
        for stock in watchlist
        for market_filter in [market_trade_filter_for_watchlist(watchlist, stock.get("code"))]
    ]


def market_trade_filter(code: str | None = None) -> dict[str, Any]:
    return market_trade_filter_for_watchlist(watchlist_to_api(load_watchlist()), code)
