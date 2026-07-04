from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock, Thread
from typing import Any
from zoneinfo import ZoneInfo

from backend.storage.csv_adapter import watchlist_to_api
from src.data import load_watchlist
from src.rules import clean_code
from src.storage import load_market_context, save_market_context

MARKET_INDEX_CODES = {
    "000001": "上证指数",
    "399001": "深证成指",
    "399006": "创业板指",
}
MARKET_CONTEXT_REFRESH_LOCK = Lock()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sector_name(stock: dict[str, Any]) -> str:
    for key in ("industry", "industryName", "sector", "sectorName", "board", "上市板块"):
        value = str(stock.get(key) or "").strip()
        if value and value not in {"主板", "综合行业"}:
            return value
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


def _context_time() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")


def _normalise_index_row(row: dict[str, Any]) -> dict[str, Any]:
    code = str(row.get("code") or row.get("代码") or "").strip()
    name = str(row.get("name") or row.get("名称") or MARKET_INDEX_CODES.get(code, "")).strip()
    pct = _number(row.get("pct", row.get("涨跌幅%")))
    price = _number(row.get("price", row.get("最新价")))
    ma5 = _number(row.get("ma5", row.get("MA5")))
    above_ma5 = bool(row.get("aboveMA5")) if "aboveMA5" in row else (price > ma5 if ma5 > 0 else pct >= 0)
    return {
        "code": code,
        "name": name,
        "pct": pct,
        "price": price,
        "ma5": ma5,
        "aboveMA5": above_ma5,
    }


def _normalise_sector_row(row: dict[str, Any]) -> dict[str, Any]:
    avg_change = _number(row.get("avgChangePct", row.get("涨跌幅%")))
    above_ratio = round(_number(row.get("aboveMA5Ratio"), 100 if avg_change >= 0 else 0))
    name = str(row.get("sectorName") or row.get("name") or row.get("板块") or "综合行业").strip()
    return {
        "sectorName": name,
        "avgChangePct": avg_change,
        "aboveMA5Ratio": above_ratio,
        "totalVolume": _number(row.get("totalVolume", row.get("成交额"))),
        "totalCount": int(_number(row.get("totalCount"), 0)),
        "sectorWeak": bool(row.get("sectorWeak")) if "sectorWeak" in row else avg_change < 0 and above_ratio < 40,
        "hotCandidate": bool(row.get("hotCandidate", False)),
        "source": str(row.get("source") or ""),
    }


def market_snapshot_from_indexes(indexes: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [_normalise_index_row(row) for row in indexes]
    valid = [row for row in rows if row["code"] or row["name"]]
    total = len(valid)
    up = len([row for row in valid if row["pct"] > 0])
    down = len([row for row in valid if row["pct"] < 0])
    above_ma5 = len([row for row in valid if row["aboveMA5"]])
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
        "source": "market-indexes",
        "indexes": valid,
    }


def load_external_market_context() -> dict[str, Any]:
    context = load_market_context()
    if not isinstance(context, dict):
        return {}
    indexes = context.get("indexes")
    sectors = context.get("sectors")
    if not isinstance(indexes, list) and not isinstance(sectors, list):
        return {}
    normalised: dict[str, Any] = {
        "updatedAt": str(context.get("updatedAt") or ""),
        "source": str(context.get("source") or "market-context-cache"),
    }
    if isinstance(indexes, list):
        normalised["indexes"] = [_normalise_index_row(row) for row in indexes if isinstance(row, dict)]
    if isinstance(sectors, list):
        normalised["sectors"] = [_normalise_sector_row(row) for row in sectors if isinstance(row, dict)]
    stock_sectors = context.get("stockSectors")
    if isinstance(stock_sectors, dict):
        normalised["stockSectors"] = {
            clean_code(code): str(name)
            for code, name in stock_sectors.items()
            if clean_code(code) and str(name).strip()
        }
    return normalised


def save_external_market_context(
    indexes: list[dict[str, Any]] | None = None,
    sectors: list[dict[str, Any]] | None = None,
    stock_sectors: dict[str, str] | list[dict[str, Any]] | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    stock_sector_map: dict[str, str] = {}
    if isinstance(stock_sectors, dict):
        stock_sector_map = {clean_code(code): str(name) for code, name in stock_sectors.items() if clean_code(code)}
    elif isinstance(stock_sectors, list):
        for row in stock_sectors:
            if not isinstance(row, dict):
                continue
            code = clean_code(row.get("code") or row.get("代码"))
            sector = str(row.get("sectorName") or row.get("industry") or row.get("行业") or "").strip()
            if code and sector:
                stock_sector_map[code] = sector
    context = {
        "updatedAt": _context_time(),
        "source": source,
        "indexes": [_normalise_index_row(row) for row in (indexes or [])],
        "sectors": [_normalise_sector_row(row) for row in (sectors or [])],
        "stockSectors": stock_sector_map,
    }
    save_market_context(context)
    return context


def refresh_external_market_context() -> dict[str, Any]:
    """Best-effort refresh of real market indexes and industry sectors.

    The trading path treats this as advisory data. If the network/provider is
    unavailable, callers can keep using the last cache or the watchlist fallback.
    """
    try:
        import akshare as ak
    except Exception as exc:
        return {"success": False, "message": f"AKShare 不可用: {str(exc)[:120]}", "context": load_external_market_context()}

    indexes: list[dict[str, Any]] = []
    sectors: list[dict[str, Any]] = []
    stock_sector_map: dict[str, str] = {}
    errors: list[str] = []

    try:
        raw_index = ak.stock_zh_index_spot_em()
        if raw_index is not None and not raw_index.empty:
            for code, name in MARKET_INDEX_CODES.items():
                matches = raw_index[raw_index.get("代码").astype(str) == code] if "代码" in raw_index else raw_index.iloc[0:0]
                if matches.empty:
                    continue
                row = matches.iloc[0]
                indexes.append(
                    {
                        "code": code,
                        "name": name,
                        "pct": row.get("涨跌幅"),
                        "price": row.get("最新价"),
                    }
                )
    except Exception as exc:
        errors.append(f"指数: {str(exc)[:120]}")

    try:
        raw_sector = ak.stock_board_industry_name_em()
        if raw_sector is not None and not raw_sector.empty:
            for _, row in raw_sector.head(80).iterrows():
                sectors.append(
                    {
                        "sectorName": row.get("板块名称") or row.get("名称"),
                        "avgChangePct": row.get("涨跌幅"),
                        "totalVolume": row.get("成交额"),
                        "source": "AKShare行业板块",
                    }
                )
    except Exception as exc:
        errors.append(f"行业板块: {str(exc)[:120]}")

    try:
        raw_spot = ak.stock_zh_a_spot_em()
        if raw_spot is not None and not raw_spot.empty and {"代码", "所属行业"}.issubset(raw_spot.columns):
            for _, row in raw_spot.iterrows():
                code = clean_code(row.get("代码"))
                industry = str(row.get("所属行业") or "").strip()
                if code and industry:
                    stock_sector_map[code] = industry
    except Exception as exc:
        errors.append(f"个股行业: {str(exc)[:120]}")

    if not indexes and not sectors and not stock_sector_map:
        return {
            "success": False,
            "message": "；".join(errors) or "未获取到真实市场上下文",
            "context": load_external_market_context(),
        }

    context = save_external_market_context(indexes, sectors, stock_sector_map, source="AKShare")
    return {
        "success": True,
        "message": "真实市场/行业上下文已更新" + (f"；部分失败: {'；'.join(errors)}" if errors else ""),
        "context": context,
    }


def refresh_market_context_if_stale(ttl_seconds: int = 300) -> dict[str, Any]:
    cached = load_external_market_context()
    updated_at = str(cached.get("updatedAt") or "")
    parsed = datetime.fromisoformat(updated_at) if updated_at else None
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    if parsed is not None and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    stale = parsed is None or now - parsed > timedelta(seconds=ttl_seconds)
    if not stale:
        return {"success": True, "stale": False, "context": cached, "message": "使用市场上下文缓存"}
    if MARKET_CONTEXT_REFRESH_LOCK.acquire(blocking=False):
        def worker() -> None:
            try:
                refresh_external_market_context()
            finally:
                MARKET_CONTEXT_REFRESH_LOCK.release()

        Thread(target=worker, daemon=True).start()
    return {
        "success": bool(cached),
        "stale": True,
        "context": cached,
        "message": "先返回最近市场上下文，后台刷新中",
    }


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


def market_risk_snapshot(
    watchlist: list[dict[str, Any]] | None = None,
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = market_context if market_context is not None else load_external_market_context()
    indexes = context.get("indexes") if isinstance(context, dict) else None
    if isinstance(indexes, list) and indexes:
        snapshot = market_snapshot_from_indexes(indexes)
        snapshot["updatedAt"] = str(context.get("updatedAt") or "")
        return snapshot
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
        "source": "watchlist-fallback",
    }


def market_trade_filter_for_watchlist(
    watchlist: list[dict[str, Any]],
    code: str | None = None,
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = market_context if market_context is not None else load_external_market_context()
    market = market_risk_snapshot(watchlist, context)
    external_sectors = context.get("sectors") if isinstance(context, dict) else None
    stock_sector_map = context.get("stockSectors") if isinstance(context, dict) else None
    sectors = (
        [_normalise_sector_row(row) for row in external_sectors if isinstance(row, dict)]
        if isinstance(external_sectors, list) and external_sectors
        else sector_summary(watchlist)
    )
    sector_by_name = {row["sectorName"]: row for row in sectors}

    stock_sector = ""
    sector = None
    cleaned = clean_code(code)
    if isinstance(stock_sector_map, dict) and cleaned:
        stock_sector = str(stock_sector_map.get(cleaned) or "").strip()
        sector = sector_by_name.get(stock_sector) if stock_sector else None
    for stock in watchlist:
        if not stock_sector and sector is None and cleaned and clean_code(stock.get("code")) == cleaned:
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
        "dataSource": "external-context" if isinstance(external_sectors, list) and external_sectors else market.get("source", "watchlist-fallback"),
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
