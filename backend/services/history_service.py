from __future__ import annotations

from typing import Any

import pandas as pd

from src.history import load_cached_history
from src.rules import clean_code

from backend.storage.csv_adapter import number


def history_for_api(code: str) -> dict[str, Any]:
    cleaned = clean_code(code)
    frame = load_cached_history(cleaned)
    if frame is None or frame.empty:
        return {"code": cleaned, "klines": []}
    out = frame.copy()
    out["日期"] = pd.to_datetime(out.get("日期"), errors="coerce")
    out = out.dropna(subset=["日期"]).sort_values("日期")
    close = pd.to_numeric(out.get("收盘"), errors="coerce")
    for window in (5, 10, 20):
        column = f"MA{window}"
        if column not in out:
            out[column] = close.rolling(window).mean()

    klines = []
    for _, row in out.tail(120).iterrows():
        klines.append(
            {
                "date": row["日期"].date().isoformat(),
                "open": number(row.get("开盘")),
                "high": number(row.get("最高")),
                "low": number(row.get("最低")),
                "close": number(row.get("收盘")),
                "volume": number(row.get("成交量")),
                "amount": number(row.get("成交额")),
                "ma5": number(row.get("MA5")),
                "ma10": number(row.get("MA10")),
                "ma20": number(row.get("MA20")),
            }
        )
    return {"code": cleaned, "klines": klines}

