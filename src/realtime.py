from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from src.data import clean_code
from src.rules import screening_result

QUOTE_COLUMNS = [
    "代码",
    "名称",
    "最新价",
    "涨跌幅%",
    "成交额",
    "开盘",
    "昨收",
    "最高",
    "最低",
    "更新时间",
    "来源",
    "状态",
]

EASTMONEY_SPOT_HOSTS = [
    "push2.eastmoney.com",
    "82.push2.eastmoney.com",
]

QUOTE_SOURCE_OPTIONS = ["自动切换", "东方财富", "新浪行情", "AKShare", "手动上传/不刷新"]


def china_now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Shanghai"))


def is_a_share_trading_time(now: datetime | None = None) -> bool:
    current = now.astimezone(ZoneInfo("Asia/Shanghai")) if now else china_now()
    if current.weekday() >= 5:
        return False
    current_time = current.time()
    return (
        time(9, 25) <= current_time <= time(11, 30)
        or time(13, 0) <= current_time <= time(15, 0)
    )


def _with_status(df: pd.DataFrame, source: str = "", message: str = "") -> pd.DataFrame:
    if not df.empty:
        refresh_time = china_now().strftime("%Y-%m-%d %H:%M:%S")
        if "更新时间" not in df:
            df["更新时间"] = refresh_time
        else:
            df["更新时间"] = df["更新时间"].fillna(refresh_time).replace("", refresh_time)
        if "来源" not in df:
            df["来源"] = source
        else:
            df["来源"] = df["来源"].fillna(source).replace("", source)
        quote_status = "部分成功" if "未获取" in str(message) else "成功"
        if "状态" not in df:
            df["状态"] = quote_status
        else:
            df["状态"] = df["状态"].fillna(quote_status).replace("", quote_status)
    df.attrs["source"] = source
    df.attrs["message"] = message
    return df


def _short_error(exc: Exception) -> str:
    text = str(exc).strip()
    if not text:
        text = exc.__class__.__name__
    return text[:180]


def _clean_numeric(value: object) -> object:
    if value in {"-", ""}:
        return pd.NA
    return value


def empty_quotes(message: str = "", source: str = "") -> pd.DataFrame:
    return _with_status(pd.DataFrame(columns=QUOTE_COLUMNS), source, message)


def _empty_full_quotes(message: str = "", source: str = "") -> pd.DataFrame:
    return _with_status(pd.DataFrame(columns=QUOTE_COLUMNS), source, message)


def _eastmoney_market(code: str) -> str:
    code = clean_code(code)
    return "1" if code.startswith(("6", "9")) else "0"


def _sina_symbol(code: str) -> str:
    code = clean_code(code)
    return ("sh" if code.startswith(("6", "9")) else "sz") + code


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def fetch_realtime_quotes(
    codes: list[str],
    timeout: int = 8,
    source: str = "自动切换",
) -> pd.DataFrame:
    wanted = {clean_code(code) for code in codes if clean_code(code)}
    if not wanted:
        return empty_quotes()

    if source == "AKShare":
        return fetch_realtime_quotes_akshare(wanted)
    if source == "东方财富":
        return fetch_realtime_quotes_eastmoney(wanted, timeout=timeout)
    if source == "新浪行情":
        return fetch_realtime_quotes_sina(wanted, timeout=timeout)
    if source == "手动上传/不刷新":
        return empty_quotes("当前设置为手动上传/不刷新", source)

    return fetch_realtime_quotes_auto(wanted, timeout=timeout)


def fetch_realtime_quotes_auto(wanted: set[str], timeout: int = 8) -> pd.DataFrame:
    remaining = set(wanted)
    frames: list[pd.DataFrame] = []
    messages: list[str] = []
    sources: list[str] = []

    for source_name, fetcher in [
        ("东方财富", lambda values: fetch_realtime_quotes_eastmoney(values, timeout=timeout)),
        ("AKShare", fetch_realtime_quotes_akshare),
        ("新浪行情", lambda values: fetch_realtime_quotes_sina(values, timeout=timeout)),
    ]:
        if not remaining:
            break
        frame = fetcher(remaining)
        message = frame.attrs.get("message", "")
        if frame.empty:
            if message:
                messages.append(f"{source_name}: {message}")
            continue
        frames.append(frame)
        sources.append(source_name)
        remaining -= set(frame["代码"].dropna().astype(str))

    if not frames:
        return empty_quotes("；".join(messages) or "所有行情源均未返回数据", "自动切换")

    combined = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates("代码", keep="first")
        .reset_index(drop=True)
    )
    missing = sorted(remaining)
    message = f"来自{' + '.join(sources)}"
    if missing:
        message += f"，未获取 {len(missing)} 只"
    return _with_status(combined[QUOTE_COLUMNS], "自动切换", message)


def fetch_realtime_quotes_eastmoney(wanted: set[str], timeout: int = 8) -> pd.DataFrame:
    rows: list[dict] = []
    errors: list[str] = []
    codes = sorted(clean_code(code) for code in wanted if clean_code(code))
    if not codes:
        return empty_quotes("未提供股票代码", "东方财富")

    for chunk in _chunks(codes, 80):
        secids = [f"{_eastmoney_market(code)}.{code}" for code in chunk]
        for host in EASTMONEY_SPOT_HOSTS:
            try:
                payload = _eastmoney_ulist_request(host, secids=secids, timeout=timeout)
                rows.extend((payload.get("data") or {}).get("diff") or [])
                break
            except Exception as exc:
                errors.append(f"{host}: {_short_error(exc)}")

    frame = _standardize_eastmoney_rows(rows)
    if frame.empty:
        return empty_quotes("；".join(errors) or "东方财富未返回指定股票", "东方财富")
    frame = frame[frame["代码"].isin(wanted)].copy()
    if frame.empty:
        return empty_quotes("东方财富未返回指定股票", "东方财富")
    return _with_status(frame[QUOTE_COLUMNS].reset_index(drop=True), "东方财富", "东方财富行情已更新")


def _eastmoney_clist_request(host: str, page: int, page_size: int, timeout: int) -> dict:
    params = {
        "pn": str(page),
        "pz": str(page_size),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:1+t:2,m:1+t:23,m:0+t:6,m:0+t:80",
        "fields": "f12,f14,f2,f3,f6,f17,f18,f15,f16",
    }
    url = f"https://{host}/api/qt/clist/get?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _eastmoney_turnover_rank_request(host: str, page_size: int, timeout: int) -> dict:
    params = {
        "pn": "1",
        "pz": str(page_size),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f6",
        "fs": "m:1+t:2,m:1+t:23,m:0+t:6,m:0+t:80",
        "fields": "f12,f14,f2,f3,f6,f17,f18,f15,f16",
    }
    url = f"https://{host}/api/qt/clist/get?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _eastmoney_ulist_request(host: str, secids: list[str], timeout: int) -> dict:
    params = {
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fields": "f12,f14,f2,f3,f6,f17,f18,f15,f16",
        "secids": ",".join(secids),
    }
    url = f"https://{host}/api/qt/ulist.np/get?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _standardize_eastmoney_rows(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return _empty_full_quotes("东方财富返回空数据", "东方财富")
    frame = pd.DataFrame(rows).rename(
        columns={
            "f12": "代码",
            "f14": "名称",
            "f2": "最新价",
            "f3": "涨跌幅%",
            "f6": "成交额",
            "f17": "开盘",
            "f18": "昨收",
            "f15": "最高",
            "f16": "最低",
        }
    )
    for column in QUOTE_COLUMNS:
        if column not in frame:
            frame[column] = pd.NA
    frame["代码"] = frame["代码"].map(clean_code)
    for column in ["最新价", "涨跌幅%", "成交额", "开盘", "昨收", "最高", "最低"]:
        frame[column] = pd.to_numeric(frame[column].map(_clean_numeric), errors="coerce")
    return frame[QUOTE_COLUMNS].drop_duplicates("代码", keep="first").reset_index(drop=True)


def fetch_turnover_rank_quotes_eastmoney(limit: int = 30, timeout: int = 8, page_size: int = 240) -> pd.DataFrame:
    errors: list[str] = []
    safe_limit = max(int(limit or 30), 30)
    safe_page_size = max(int(page_size or 240), safe_limit)
    for host in EASTMONEY_SPOT_HOSTS:
        try:
            payload = _eastmoney_turnover_rank_request(host, page_size=safe_page_size, timeout=timeout)
            rows = (payload.get("data") or {}).get("diff") or []
            frame = _standardize_eastmoney_rows(rows)
            if not frame.empty:
                return _with_status(frame, "东方财富", f"{host} 成交额榜已更新")
            errors.append(frame.attrs.get("message", f"{host} 成交额榜返回空数据"))
        except Exception as exc:
            errors.append(f"{host}: {_short_error(exc)}")
    return _empty_full_quotes("；".join(errors), "东方财富")


def fetch_full_market_quotes_eastmoney(timeout: int = 8) -> pd.DataFrame:
    errors: list[str] = []
    page_size = 6000
    for host in EASTMONEY_SPOT_HOSTS:
        try:
            payload = _eastmoney_clist_request(host, page=1, page_size=page_size, timeout=timeout)
            data = payload.get("data") or {}
            rows = data.get("diff") or []
            total = int(data.get("total") or len(rows))
            pages = max(1, math.ceil(total / page_size))
            for page in range(2, pages + 1):
                next_payload = _eastmoney_clist_request(
                    host,
                    page=page,
                    page_size=page_size,
                    timeout=timeout,
                )
                rows.extend((next_payload.get("data") or {}).get("diff") or [])
            frame = _standardize_eastmoney_rows(rows)
            if not frame.empty:
                return _with_status(frame, "东方财富", f"{host} 行情已更新")
            errors.append(frame.attrs.get("message", f"{host} 返回空数据"))
        except Exception as exc:
            errors.append(f"{host}: {_short_error(exc)}")
    return _empty_full_quotes("；".join(errors), "东方财富")


def fetch_realtime_quotes_sina(wanted: set[str], timeout: int = 8) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    errors: list[str] = []
    for codes in _chunks(sorted(wanted), 80):
        symbols = ",".join(_sina_symbol(code) for code in codes)
        url = "https://hq.sinajs.cn/list=" + symbols
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://finance.sina.com.cn/",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("gb18030", errors="ignore")
        except Exception as exc:
            errors.append(_short_error(exc))
            continue

        for match in re.finditer(r'var hq_str_(s[hz]\d{6})="([^"]*)"', text):
            symbol, body = match.groups()
            parts = body.split(",")
            if len(parts) < 32 or not parts[0]:
                continue
            code = symbol[-6:]
            open_price = pd.to_numeric(parts[1], errors="coerce")
            prev_close = pd.to_numeric(parts[2], errors="coerce")
            latest = pd.to_numeric(parts[3], errors="coerce")
            high = pd.to_numeric(parts[4], errors="coerce")
            low = pd.to_numeric(parts[5], errors="coerce")
            amount = pd.to_numeric(parts[9], errors="coerce")
            if pd.notna(latest) and float(latest) == 0 and pd.notna(prev_close):
                latest = prev_close
            pct = pd.NA
            if pd.notna(latest) and pd.notna(prev_close) and float(prev_close) != 0:
                pct = (float(latest) - float(prev_close)) / float(prev_close) * 100
            rows.append({
                "代码": code,
                "名称": parts[0].strip(),
                "最新价": latest,
                "涨跌幅%": pct,
                "成交额": amount,
                "开盘": open_price,
                "昨收": prev_close,
                "最高": high,
                "最低": low,
            })

    if not rows:
        return empty_quotes("；".join(errors) or "新浪行情未返回数据", "新浪行情")
    frame = pd.DataFrame(rows)
    for column in QUOTE_COLUMNS:
        if column not in frame:
            frame[column] = pd.NA
    return _with_status(
        frame[QUOTE_COLUMNS].drop_duplicates("代码", keep="first").reset_index(drop=True),
        "新浪行情",
        "新浪行情已更新",
    )


def fetch_full_market_quotes(source: str = "自动切换") -> pd.DataFrame:
    if source == "手动上传/不刷新":
        return _empty_full_quotes("当前设置为手动上传/不刷新", source)
    if source == "AKShare":
        return fetch_full_market_quotes_akshare()
    if source == "东方财富":
        return fetch_full_market_quotes_eastmoney()
    if source == "新浪行情":
        return _empty_full_quotes("新浪行情只能刷新已知股票，不能生成全市场股票池", source)

    eastmoney = fetch_full_market_quotes_eastmoney()
    if not eastmoney.empty:
        return eastmoney
    akshare = fetch_full_market_quotes_akshare()
    if not akshare.empty:
        return akshare
    return _empty_full_quotes(
        "东方财富: "
        + eastmoney.attrs.get("message", "失败")
        + "；AKShare: "
        + akshare.attrs.get("message", "失败"),
        "自动切换",
    )


def fetch_realtime_quotes_akshare(wanted: set[str]) -> pd.DataFrame:
    try:
        import akshare as ak

        raw = ak.stock_zh_a_spot_em()
    except Exception as exc:
        return empty_quotes(_short_error(exc), "AKShare")
    if raw is None or raw.empty:
        return empty_quotes("AKShare 返回空数据", "AKShare")

    aliases = {
        "代码": ["代码"],
        "名称": ["名称"],
        "最新价": ["最新价"],
        "涨跌幅%": ["涨跌幅"],
        "成交额": ["成交额"],
        "开盘": ["今开", "开盘"],
        "昨收": ["昨收"],
        "最高": ["最高"],
        "最低": ["最低"],
    }
    result = pd.DataFrame()
    for target, names in aliases.items():
        source = next((name for name in names if name in raw.columns), None)
        result[target] = raw[source] if source else pd.NA
    result["代码"] = result["代码"].map(clean_code)
    result = result[result["代码"].isin(wanted)].copy()
    for column in ["最新价", "涨跌幅%", "成交额", "开盘", "昨收", "最高", "最低"]:
        result[column] = pd.to_numeric(result[column].map(_clean_numeric), errors="coerce")
    result = result[QUOTE_COLUMNS].drop_duplicates("代码", keep="first").reset_index(drop=True)
    if result.empty:
        return empty_quotes("AKShare 未返回指定股票", "AKShare")
    return _with_status(result, "AKShare", "AKShare 行情已更新")


def fetch_auto_stock_pool(limit: int = 30, source: str = "自动切换") -> pd.DataFrame:
    """Generate a main-board stock pool ranked by turnover amount."""
    rank_quotes = pd.DataFrame()
    if source in {"自动切换", "东方财富"}:
        rank_quotes = fetch_turnover_rank_quotes_eastmoney(limit=max(limit * 20, 600))
    quotes = rank_quotes if not rank_quotes.empty else fetch_full_market_quotes(source)
    if quotes.empty:
        return _with_status(pd.DataFrame(), quotes.attrs.get("source", source), quotes.attrs.get("message", "自动股票池行情为空"))

    pool = quotes.copy()
    pool["代码"] = pool["代码"].map(clean_code)
    pool["名称"] = pool["名称"].fillna("").astype(str).str.strip()
    for column in ["最新价", "涨跌幅%", "成交额"]:
        pool[column] = pd.to_numeric(pool[column], errors="coerce")

    passed = pool.apply(
        lambda row: screening_result(str(row.get("代码", "")), str(row.get("名称", "")))[0],
        axis=1,
    )
    pool = pool[passed].dropna(subset=["成交额"]).sort_values("成交额", ascending=False).head(limit)
    if len(pool) < limit and not rank_quotes.empty and source not in {"自动切换", "东方财富"}:
        full_quotes = fetch_full_market_quotes(source)
        if not full_quotes.empty:
            pool = full_quotes.copy()
            pool["代码"] = pool["代码"].map(clean_code)
            pool["名称"] = pool["名称"].fillna("").astype(str).str.strip()
            for column in ["最新价", "涨跌幅%", "成交额"]:
                pool[column] = pd.to_numeric(pool[column], errors="coerce")
            passed = pool.apply(
                lambda row: screening_result(str(row.get("代码", "")), str(row.get("名称", "")))[0],
                axis=1,
            )
            pool = pool[passed].dropna(subset=["成交额"]).sort_values("成交额", ascending=False).head(limit)
            quotes = full_quotes
    if pool.empty:
        return _with_status(pd.DataFrame(), quotes.attrs.get("source", source), "全市场数据中没有符合主板过滤条件的股票")

    result = pd.DataFrame({
        "代码": pool["代码"],
        "名称": pool["名称"],
        "现价": pool["最新价"],
        "涨跌幅%": pool["涨跌幅%"],
        "成交额": pool["成交额"],
        "成交额排名": range(1, len(pool) + 1),
        "上市板块": "主板",
    })
    return _with_status(result.reset_index(drop=True), quotes.attrs.get("source", source), quotes.attrs.get("message", "自动股票池已生成"))


def fetch_full_market_quotes_akshare() -> pd.DataFrame:
    try:
        import akshare as ak

        raw = ak.stock_zh_a_spot_em()
    except Exception as exc:
        return _empty_full_quotes(_short_error(exc), "AKShare")
    if raw is None or raw.empty:
        return _empty_full_quotes("AKShare 返回空数据", "AKShare")

    aliases = {
        "代码": ["代码"],
        "名称": ["名称"],
        "最新价": ["最新价"],
        "涨跌幅%": ["涨跌幅"],
        "成交额": ["成交额"],
    }
    out = pd.DataFrame()
    for target, names in aliases.items():
        source = next((name for name in names if name in raw.columns), None)
        out[target] = raw[source] if source else pd.NA
    for column in QUOTE_COLUMNS:
        if column not in out:
            out[column] = pd.NA
    out["代码"] = out["代码"].map(clean_code)
    for column in ["最新价", "涨跌幅%", "成交额", "开盘", "昨收", "最高", "最低"]:
        out[column] = pd.to_numeric(out[column].map(_clean_numeric), errors="coerce")
    return _with_status(out[QUOTE_COLUMNS].drop_duplicates("代码", keep="first").reset_index(drop=True), "AKShare", "AKShare 全市场行情已更新")


def merge_quotes_into_watchlist(watchlist: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    if watchlist.empty or quotes.empty:
        return watchlist
    out = watchlist.copy()
    quote_map = quotes.set_index("代码")
    for index, row in out.iterrows():
        code = clean_code(row.get("代码", ""))
        if code not in quote_map.index:
            continue
        quote = quote_map.loc[code]
        if pd.notna(quote.get("最新价")):
            out.loc[index, "现价"] = quote["最新价"]
        if pd.notna(quote.get("涨跌幅%")):
            out.loc[index, "涨跌幅%"] = quote["涨跌幅%"]
        if pd.notna(quote.get("成交额")):
            out.loc[index, "成交额"] = quote["成交额"]
        if pd.notna(quote.get("名称")) and str(quote.get("名称")).strip():
            out.loc[index, "名称"] = quote["名称"]
    return out


def merge_quotes_into_holdings(holdings: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    if holdings.empty or quotes.empty:
        return holdings
    out = holdings.copy()
    quote_map = quotes.set_index("代码")
    for index, row in out.iterrows():
        code = clean_code(row.get("代码", ""))
        if code not in quote_map.index:
            continue
        quote = quote_map.loc[code]
        if pd.notna(quote.get("最新价")):
            out.loc[index, "当前价"] = quote["最新价"]
    return out
