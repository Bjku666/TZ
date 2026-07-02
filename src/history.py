from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request

import pandas as pd

from src.data import ROOT, DATA_DIR, clean_code

HISTORY_DIR = DATA_DIR / "history"


def ensure_history_dir() -> None:
    """Ensure the history cache directory exists."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def history_cache_path(code: str) -> Path:
    """Return the path to the cached history file for a given stock code."""
    return HISTORY_DIR / f"{clean_code(code)}.csv"


def load_cached_history(code: str) -> pd.DataFrame | None:
    """Load cached history for a stock code from local disk.

    Returns a DataFrame with columns: 日期, 开盘, 最高, 最低, 收盘, 成交量
    or None if no cache exists.
    """
    path = history_cache_path(code)
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, dtype={"代码": str})
        if df.empty:
            return None
        return df
    except (OSError, pd.errors.EmptyDataError):
        return None


def has_cached_history(code: str) -> bool:
    """Check if a stock has cached history without loading the full file."""
    path = history_cache_path(code)
    return path.exists() and path.stat().st_size > 50


def diagnose_history(code: str, max_age_days: int = 10) -> dict[str, Any]:
    """Diagnose whether a cached history file is usable for MA rules."""
    cleaned = clean_code(code)
    result: dict[str, Any] = {
        "history_status": "缺少历史K线",
        "history_rows": 0,
        "history_last_date": "",
        "history_error": f"未找到 data/history/{cleaned}.csv",
        "is_valid": False,
    }
    cache = load_cached_history(cleaned)
    if cache is None or cache.empty:
        return result

    cache = cache.copy()
    close = pd.to_numeric(cache.get("收盘"), errors="coerce")
    valid_rows = int(close.notna().sum())
    result["history_rows"] = valid_rows

    dates = pd.to_datetime(cache.get("日期"), errors="coerce")
    last_date = dates.max()
    if pd.notna(last_date):
        result["history_last_date"] = last_date.date().isoformat()

    if valid_rows < 20:
        result.update({
            "history_status": "数据不足",
            "history_error": "历史K线数据不足，至少需要20条有效收盘价",
        })
        return result

    for window in (5, 10, 20):
        col = f"MA{window}"
        if col not in cache:
            cache[col] = close.rolling(window).mean()

    latest = cache.iloc[-1]
    missing_ma = [f"MA{window}" for window in (5, 10, 20) if pd.isna(pd.to_numeric(latest.get(f"MA{window}"), errors="coerce"))]
    if missing_ma:
        result.update({
            "history_status": "数据不足",
            "history_error": "无法计算 " + "、".join(missing_ma),
        })
        return result

    if pd.isna(last_date):
        result.update({
            "history_status": "数据不足",
            "history_error": "历史K线缺少有效日期",
        })
        return result

    age_days = (pd.Timestamp(date.today()).normalize() - last_date.normalize()).days
    if age_days > max_age_days:
        result.update({
            "history_status": "数据不足",
            "history_error": f"最后交易日 {last_date.date().isoformat()} 过旧",
        })
        return result

    result.update({
        "history_status": "已有缓存",
        "history_error": "",
        "is_valid": True,
    })
    return result


def get_history_status(code: str) -> str:
    """Return the diagnostic history status string for a stock."""
    return str(diagnose_history(code)["history_status"])


def fetch_history_akshare(code: str, start_date: str = "20250601",
                          end_date: str | None = None) -> pd.DataFrame | None:
    """Fetch historical daily data for a stock using AkShare.

    Uses akshare.stock_zh_a_hist with qfq (前复权) adjustment.

    Args:
        code: 6-digit stock code.
        start_date: Start date string YYYYMMDD. Defaults to 3 months ago.
        end_date: End date string YYYYMMDD. Defaults to today.

    Returns:
        DataFrame with standardized columns or None on failure.
    """
    import datetime

    if end_date is None:
        end_date = datetime.date.today().isoformat().replace("-", "")
    direct = fetch_history_eastmoney(code, start_date, end_date)
    if direct is not None and not direct.empty:
        return direct

    try:
        import akshare as ak

        raw = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
    except Exception:
        return None

    if raw is None or raw.empty:
        return None

    return standardize_history(raw, code)


def eastmoney_secid(code: str) -> str:
    cleaned = clean_code(code)
    market = "1" if cleaned.startswith(("6", "9")) else "0"
    return f"{market}.{cleaned}"


def fetch_history_eastmoney(code: str, start_date: str = "20250601",
                            end_date: str | None = None) -> pd.DataFrame | None:
    """Fetch daily history directly from Eastmoney's kline endpoint."""
    import datetime

    cleaned = clean_code(code)
    if not cleaned:
        return None
    if end_date is None:
        end_date = datetime.date.today().isoformat().replace("-", "")

    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",
        "fqt": "1",
        "secid": eastmoney_secid(cleaned),
        "beg": start_date,
        "end": end_date,
    }
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    klines = (payload.get("data") or {}).get("klines") or []
    if not klines:
        return None

    rows: list[dict[str, object]] = []
    for item in klines:
        parts = str(item).split(",")
        if len(parts) < 11:
            continue
        rows.append({
            "日期": parts[0],
            "开盘": parts[1],
            "收盘": parts[2],
            "最高": parts[3],
            "最低": parts[4],
            "成交量": parts[5],
            "成交额": parts[6],
            "单日涨幅%": parts[8],
        })
    if not rows:
        return None
    return standardize_history(pd.DataFrame(rows), cleaned)


def standardize_history(raw: pd.DataFrame, code: str) -> pd.DataFrame | None:
    """Standardize raw historical data from AKShare or direct Eastmoney."""
    col_map = {
        "日期": "日期",
        "开盘": "开盘",
        "最高": "最高",
        "最低": "最低",
        "收盘": "收盘",
        "成交量": "成交量",
        "成交额": "成交额",
        "涨跌幅": "单日涨幅%",
    }
    renamed = {}
    for src_col, tgt_col in col_map.items():
        for raw_col in raw.columns:
            if raw_col.strip() == src_col:
                renamed[raw_col] = tgt_col
                break

    if "日期" not in renamed:
        return None

    df = raw.rename(columns=renamed).copy()
    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df["代码"] = clean_code(code)

    # Numeric conversion
    for col in ["开盘", "最高", "最低", "收盘", "成交量", "成交额", "单日涨幅%"]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["日期", "收盘"]).sort_values("日期")

    # Calculate MA values
    for window in (5, 10, 20):
        df[f"MA{window}"] = df["收盘"].rolling(window).mean()
    df["前一日MA5"] = df["MA5"].shift(1)
    df["MA5向上"] = df["MA5"] > df["前一日MA5"]

    if "单日涨幅%" not in df:
        df["单日涨幅%"] = df["收盘"].pct_change() * 100

    return df


def save_history_cache(df: pd.DataFrame) -> int:
    """Save a history DataFrame to the local cache, grouped by stock code.

    Args:
        df: DataFrame containing history data with a '代码' column.

    Returns:
        Number of stocks cached.
    """
    ensure_history_dir()
    count = 0
    for code, group in df.groupby("代码"):
        if not code or not clean_code(str(code)):
            continue
        path = history_cache_path(str(code))
        group.to_csv(path, index=False, encoding="utf-8-sig")
        count += 1
    return count


def get_ma5_from_cache(code: str) -> dict[str, Any]:
    """Get the latest MA5-related values from cached history.

    Returns a dict with keys:
        MA5, MA10, MA20, MA5向上, 最近大阳线%, 最新收盘
    or empty values if not cached.
    """
    cache = load_cached_history(code)
    result: dict[str, Any] = {
        "MA5": None,
        "MA10": None,
        "MA20": None,
        "MA5向上": False,
        "最近大阳线%": None,
        "最新收盘": None,
    }
    if cache is None or cache.empty:
        return result

    latest = cache.iloc[-1]
    result["MA5"] = latest.get("MA5")
    result["MA10"] = latest.get("MA10")
    result["MA20"] = latest.get("MA20")
    result["MA5向上"] = bool(latest.get("MA5向上", False))
    result["最新收盘"] = latest.get("收盘")

    # Compute 最近大阳线%
    if "单日涨幅%" in cache.columns:
        max_up = cache["单日涨幅%"].max()
        if pd.notna(max_up):
            result["最近大阳线%"] = float(max_up)

    return result


def fetch_and_cache(code: str, start_date: str = "20250601",
                    end_date: str | None = None) -> dict[str, Any]:
    """Fetch history via AkShare and cache it.

    Returns a dict with:
        success: bool
        status: str describing the outcome
        data: DataFrame or None
    """
    df = fetch_history_akshare(code, start_date, end_date)
    if df is None:
        return {"success": False, "status": "自动获取失败", "error": "行情源未返回有效历史K线", "data": None}
    save_history_cache(df)
    diagnosis = diagnose_history(code)
    if not diagnosis["is_valid"]:
        return {
            "success": False,
            "status": diagnosis["history_status"],
            "error": diagnosis["history_error"],
            "data": df,
        }
    return {"success": True, "status": "自动获取成功", "error": "", "data": df}


def compute_reminder_from_history(code: str, price: float | None,
                                  available_cash: float = 10000) -> dict[str, Any]:
    """Compute all reminder fields from cached history for a stock.

    Returns a dict with keys:
        MA5, MA10, MA20, MA5向上, 最近大阳线%, MA5偏离率%,
        一手金额, 资金可买, has_history, history_status, 提醒
    """
    result: dict[str, Any] = {
        "MA5": None,
        "MA10": None,
        "MA20": None,
        "MA5向上": False,
        "最近大阳线%": None,
        "MA5偏离率%": None,
        "一手金额": None,
        "资金可买": "资金不足",
        "has_history": False,
        "history_status": "缺少历史K线",
        "history_rows": 0,
        "history_last_date": "",
        "history_error": "",
        "提醒": "",
    }

    diagnosis = diagnose_history(code)
    result["history_status"] = diagnosis["history_status"]
    result["history_rows"] = diagnosis["history_rows"]
    result["history_last_date"] = diagnosis["history_last_date"]
    result["history_error"] = diagnosis["history_error"]
    if not diagnosis["is_valid"]:
        result["提醒"] = diagnosis["history_error"] or "缺少历史K线，暂不能判断MA5"
        return result

    cache = load_cached_history(code)
    if cache is not None and not cache.empty:
        result["has_history"] = True
        latest = cache.iloc[-1]

        result["MA5"] = latest.get("MA5")
        result["MA10"] = latest.get("MA10")
        result["MA20"] = latest.get("MA20")
        result["MA5向上"] = bool(latest.get("MA5向上", False))
        recent = cache.tail(20)
        if "单日涨幅%" in recent.columns:
            max_up = pd.to_numeric(recent["单日涨幅%"], errors="coerce").max()
            if pd.notna(max_up):
                result["最近大阳线%"] = round(float(max_up), 2)

        # Latest price from history if not provided
        if price is None or pd.isna(price):
            price = latest.get("收盘")
    # Compute MA5 deviation
    if price is not None and pd.notna(price) and result["MA5"] is not None and pd.notna(result["MA5"]):
        ma5_val = float(result["MA5"])
        if ma5_val != 0:
            deviation = (float(price) - ma5_val) / ma5_val * 100
            result["MA5偏离率%"] = round(deviation, 2)

    # Compute affordability
    if price is not None and pd.notna(price):
        lot_cost = float(price) * 100
        result["一手金额"] = round(lot_cost, 2)
        result["资金可买"] = "可以买" if lot_cost <= available_cash else "资金不足"

    # Compute reminder
    result["提醒"] = compute_reminder_text(result, float(price) if price is not None and pd.notna(price) else None)

    return result


def compute_reminder_text(info: dict, price: float | None = None) -> str:
    """Generate the reminder text based on stock info."""
    if not info.get("has_history", False):
        return "缺少历史K线，暂不能判断MA5"

    ma5 = info.get("MA5")
    deviation = info.get("MA5偏离率%")
    has_big_line = info.get("最近大阳线%") is not None and float(info.get("最近大阳线%", 0) or 0) >= 5
    affordable = info.get("资金可买") == "可以买"

    if deviation is not None:
        if deviation < 0:
            reminder = "跌破5日线，不纳入待买"
        elif deviation <= 2:
            reminder = "接近5日线，待买观察"
        elif deviation <= 5:
            reminder = "继续观察，等回踩"
        elif deviation <= 7:
            reminder = "偏高，不追"
        else:
            reminder = "远离5日线，不追"
        if not affordable:
            return f"{reminder}；当前本金买不起一手"
        return reminder

    if not has_big_line:
        return "缺少强势启动信号"

    return ""


def compute_all_reminders(watchlist: pd.DataFrame,
                          available_cash: float = 10000) -> pd.DataFrame:
    """Compute reminder fields for all stocks in a watchlist.

    Efficiently loads cached history and computes all fields.
    """
    out = watchlist.copy()

    reminders = []
    for _, row in out.iterrows():
        code = row.get("代码", "")
        price = row.get("现价")
        try:
            price_f = float(price) if pd.notna(price) else None
        except (TypeError, ValueError):
            price_f = None

        info = compute_reminder_from_history(str(code), price_f, available_cash)

        reminders.append({
            "MA5": info["MA5"],
            "MA10": info["MA10"],
            "MA20": info["MA20"],
            "MA5向上": info["MA5向上"],
            "最近大阳线%": info["最近大阳线%"],
            "MA5偏离率%": info["MA5偏离率%"],
            "一手金额": info["一手金额"],
            "当前可用资金": available_cash,
            "当前本金": available_cash,
            "资金可买": info["资金可买"],
            "本金是否可买": info["资金可买"],
            "history_status": info["history_status"],
            "history_rows": info["history_rows"],
            "history_last_date": info["history_last_date"],
            "history_error": info["history_error"],
            "提醒": info["提醒"],
        })

    rem_df = pd.DataFrame(reminders)
    for col in rem_df.columns:
        out[col] = rem_df[col].values

    # Compute 规则状态 based on reminder
    out["规则状态"] = out["提醒"].map(classify_reminder)

    # Compute 明日计划 as empty initially
    if "明日计划" not in out.columns:
        out["明日计划"] = ""

    return out


def classify_reminder(reminder_text: str) -> str:
    """Classify a reminder text into a rule status category."""
    if not reminder_text:
        return "待补充"
    if "缺少历史K线" in reminder_text:
        return "缺少历史K线"
    if "数据不足" in reminder_text:
        return "历史K线数据不足"
    if "跌破5日线" in reminder_text or "跌破" in reminder_text:
        return "跌破不买"
    if "接近5日线" in reminder_text or "重点观察" in reminder_text:
        return "接近买点"
    if "等回踩" in reminder_text:
        return "等回踩"
    if "偏高" in reminder_text:
        return "偏高不追"
    if "远离" in reminder_text:
        return "远离不追"
    if "强势启动" in reminder_text:
        return "缺少启动信号"
    if "买不起一手" in reminder_text or "本金" in reminder_text:
        return "本金买不起一手"
    return "继续观察"
