from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


def normalize_symbol(code: str) -> str:
    value = str(code or "").strip()
    if value.startswith(("sh", "sz", "bj")):
        return value
    if value.startswith(("6", "9")):
        return f"sh{value}"
    if value.startswith(("4", "8")):
        return f"bj{value}"
    return f"sz{value}"


def get_quotes(codes: list[str], market_settings: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str]:
    enabled = bool(market_settings.get("enableRealtime"))
    if not enabled:
        return {}, "未连接实时行情"

    unique_codes = sorted({str(code).strip() for code in codes if str(code).strip()})
    if not unique_codes:
        return {}, "实时行情已开启，暂无持仓代码"

    provider = str(market_settings.get("provider") or "sina").lower()
    if provider == "manual":
        return _manual_quotes(unique_codes, market_settings), "手工行情快照"
    if provider == "sina":
        return _sina_quotes(unique_codes, market_settings)
    return {}, f"未知行情源：{provider}"


def _manual_quotes(codes: list[str], market_settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    configured = market_settings.get("quotes") or market_settings.get("manualQuotes") or {}
    quotes: dict[str, dict[str, Any]] = {}
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    for code in codes:
        item = configured.get(code) if isinstance(configured, dict) else None
        if not isinstance(item, dict):
            continue
        price = float(item.get("price") or item.get("currentPrice") or 0)
        if price <= 0:
            continue
        quotes[code] = {
            "code": code,
            "name": str(item.get("name") or ""),
            "price": price,
            "previousClose": float(item.get("previousClose") or item.get("preClose") or 0),
            "updatedAt": str(item.get("updatedAt") or now),
            "source": "manual",
        }
    return quotes


def _sina_quotes(codes: list[str], market_settings: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str]:
    symbols = [normalize_symbol(code) for code in codes]
    timeout = max(1.0, min(10.0, float(market_settings.get("timeoutSeconds") or 3)))
    url = f"https://hq.sinajs.cn/list={quote(','.join(symbols), safe=',')}"
    request = Request(url, headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": "TZ-Workspace/0.3"})
    try:
        with urlopen(request, timeout=timeout) as response:
            text = response.read().decode("gbk", errors="ignore")
    except OSError as exc:
        return {}, f"实时行情获取失败：{exc}"

    quotes: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        symbol, payload = _split_sina_line(line)
        if not symbol or not payload:
            continue
        code = symbol[-6:]
        fields = payload.split(",")
        if len(fields) < 32 or not fields[0]:
            continue
        price = _to_float(fields[3])
        previous_close = _to_float(fields[2])
        if price <= 0:
            price = previous_close
        if price <= 0:
            continue
        updated_at = f"{fields[30]} {fields[31]}".strip()
        quotes[code] = {
            "code": code,
            "name": fields[0],
            "price": price,
            "previousClose": previous_close,
            "updatedAt": updated_at,
            "source": "sina",
        }
    status = f"新浪实时行情 {datetime.now().strftime('%H:%M:%S')}，成功 {len(quotes)}/{len(codes)}"
    return quotes, status


def _split_sina_line(line: str) -> tuple[str, str]:
    if "hq_str_" not in line or '="' not in line:
        return "", ""
    left, right = line.split('="', 1)
    symbol = left.rsplit("hq_str_", 1)[-1].strip()
    payload = right.rsplit('";', 1)[0]
    return symbol, payload


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
