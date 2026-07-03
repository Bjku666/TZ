from __future__ import annotations

from typing import Any

from src.realtime import fetch_realtime_quotes
from src.rules import clean_code

from backend.storage.csv_adapter import records_from_frame


def quotes_for_codes(codes: list[str], source: str = "自动切换") -> dict[str, Any]:
    cleaned = [clean_code(code) for code in codes if clean_code(code)]
    frame = fetch_realtime_quotes(cleaned, source=source)
    return {
        "success": not frame.empty,
        "source": frame.attrs.get("source", source),
        "message": frame.attrs.get("message", ""),
        "quotes": records_from_frame(frame),
    }

