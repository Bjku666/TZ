from __future__ import annotations

from typing import Any

import pandas as pd

from src.data import (
    WATCHLIST_COLUMNS,
    archive_import_file,
    enrich_watchlist,
    load_watchlist,
    save_watchlist,
    standardize_import_file,
)
from src.history import compute_all_reminders, fetch_and_cache
from src.realtime import (
    fetch_auto_stock_pool,
    fetch_realtime_quotes,
    merge_quotes_into_watchlist,
)
from src.rules import clean_code, evaluate_stock
from src.storage import load_quote_snapshot, save_quote_snapshot

from backend.services.settings_service import get_settings, initial_cash
from backend.storage.csv_adapter import (
    FRONTEND_GROUP_TO_STAGE,
    ensure_watchlist_frame,
    watchlist_to_api,
)


def _empty_watchlist() -> pd.DataFrame:
    return pd.DataFrame(columns=WATCHLIST_COLUMNS)


def recompute_watchlist(frame: pd.DataFrame, cash: float | None = None) -> pd.DataFrame:
    if frame.empty:
        return ensure_watchlist_frame(frame)
    available_cash = initial_cash() if cash is None else cash
    out = ensure_watchlist_frame(frame)
    reminders = compute_all_reminders(out, available_cash)
    for column in reminders.columns:
        if column in out.columns and len(reminders) == len(out):
            out[column] = reminders[column].values
    enriched = enrich_watchlist(out, available_cash)
    for column in enriched.columns:
        if column in out.columns and len(enriched) == len(out):
            out[column] = enriched[column].values

    for index, row in out.iterrows():
        result = evaluate_stock(row.to_dict())
        out.loc[index, "流程阶段"] = result["stage"]
        out.loc[index, "状态"] = result["stage"]
        out.loc[index, "分组"] = result["group"]
        out.loc[index, "筛选原因"] = result["reason"]
        out.loc[index, "提醒"] = result["reminder"]
    return ensure_watchlist_frame(out)


def list_watchlist() -> dict[str, Any]:
    frame = load_watchlist()
    return {"list": watchlist_to_api(frame)}


def generate_watchlist() -> dict[str, Any]:
    settings = get_settings()
    source = str(settings.get("quote_source") or settings.get("quoteSource") or "自动切换")
    limit = int(settings.get("auto_pool_size") or 30)
    pool = fetch_auto_stock_pool(limit=limit, source=source)
    if pool.empty:
        cached = load_watchlist()
        return {
            "success": False,
            "message": pool.attrs.get("message", "行情源未返回股票池，保留本地缓存"),
            "list": watchlist_to_api(cached),
        }

    existing = load_watchlist()
    remarks: dict[str, Any] = {}
    plans: dict[str, Any] = {}
    if not existing.empty:
        for _, row in existing.iterrows():
            code = clean_code(row.get("代码"))
            remarks[code] = row.get("备注", "")
            plans[code] = row.get("明日计划", "")

    frame = ensure_watchlist_frame(pool)
    for index, row in frame.iterrows():
        code = clean_code(row.get("代码"))
        if code in remarks:
            frame.loc[index, "备注"] = remarks[code]
        if code in plans:
            frame.loc[index, "明日计划"] = plans[code]

    frame = recompute_watchlist(frame)
    save_watchlist(frame)
    return {"success": True, "message": f"已自动筛选并覆盖当前初筛池 {len(frame)} 只", "list": watchlist_to_api(frame)}


def import_watchlist_file(content: bytes, filename: str, fetch_history: bool = False) -> dict[str, Any]:
    if not content:
        raise ValueError("上传文件为空")
    frame, summary = standardize_import_file(content, filename)
    if frame.empty:
        raise ValueError("未能从表格中识别出有效沪深主板股票代码")

    archive_path = archive_import_file(content, filename)
    frame["备注"] = frame["备注"].fillna("").replace("", "同花顺表格导入初筛")
    frame = recompute_watchlist(frame)
    save_watchlist(frame)

    refresh_result = refresh_quotes()
    frame = load_watchlist()
    history_result: dict[str, Any] | None = None
    if fetch_history:
        history_result = fetch_history_for_watchlist(fetch_all=True)
        frame = load_watchlist()

    return {
        "success": True,
        "message": f"已按同花顺上传表格覆盖当前初筛池 {len(frame)} 只",
        "sourceFile": str(archive_path.relative_to(archive_path.parents[1])),
        "summary": summary,
        "refresh": {
            "success": bool(refresh_result.get("success")),
            "message": refresh_result.get("message", ""),
        },
        "history": history_result,
        "list": watchlist_to_api(frame),
    }


def refresh_quotes() -> dict[str, Any]:
    frame = load_watchlist()
    if frame.empty:
        return {"success": True, "list": []}
    codes = [clean_code(code) for code in frame["代码"].dropna().astype(str)]
    settings = get_settings()
    source = str(settings.get("quote_source") or "自动切换")
    quotes = fetch_realtime_quotes(codes, source=source)
    message = str(quotes.attrs.get("message", ""))
    if quotes.empty:
        cached = load_quote_snapshot()
        if not cached.empty:
            quotes = cached
            message = message or "行情源失败，已使用最近缓存"
        else:
            return {"success": False, "message": message or "行情刷新失败，且没有可用缓存", "list": watchlist_to_api(frame)}
    else:
        save_quote_snapshot(
            quotes,
            source=str(quotes.attrs.get("source", source)),
            status="成功",
            message=message,
        )

    merged = merge_quotes_into_watchlist(frame, quotes)
    merged = recompute_watchlist(merged)
    save_watchlist(merged)
    return {"success": True, "message": message, "list": watchlist_to_api(merged)}


def fetch_history_for_watchlist(code: str | None = None, fetch_all: bool = False) -> dict[str, Any]:
    frame = load_watchlist()
    if frame.empty:
        return {"success": True, "message": "股票池为空", "list": []}
    if fetch_all:
        codes = [clean_code(value) for value in frame["代码"].dropna().astype(str)]
    elif code:
        codes = [clean_code(code)]
    else:
        codes = [
            clean_code(row.get("代码"))
            for _, row in frame.iterrows()
            if str(row.get("history_status", "")) != "已有缓存"
        ]
    codes = [value for value in codes if value]

    summary = {"success": True, "fetched": 0, "failed": 0, "results": {}}
    for item_code in codes:
        try:
            result = fetch_and_cache(item_code)
        except Exception as exc:
            result = {"success": False, "status": "自动获取失败", "error": str(exc)}
        if result.get("success"):
            summary["fetched"] += 1
        else:
            summary["failed"] += 1
            summary["success"] = False
        summary["results"][item_code] = {
            "success": bool(result.get("success")),
            "status": result.get("status", ""),
            "error": result.get("error", ""),
        }

    updated = recompute_watchlist(frame)
    save_watchlist(updated)
    summary["list"] = watchlist_to_api(updated)
    return summary


def update_stock(payload: dict[str, Any]) -> dict[str, Any]:
    code = clean_code(payload.get("code"))
    if not code:
        raise ValueError("股票代码缺失")
    frame = load_watchlist()
    if frame.empty:
        frame = _empty_watchlist()
    matches = frame.index[frame["代码"].astype(str).map(clean_code) == code].tolist() if "代码" in frame else []
    if matches:
        index = matches[0]
    else:
        frame = pd.concat([frame, pd.DataFrame([{}])], ignore_index=True)
        index = len(frame) - 1
        frame.loc[index, "代码"] = code
        frame.loc[index, "名称"] = str(payload.get("name") or "")
        frame.loc[index, "状态"] = "初筛通过"
        frame.loc[index, "流程阶段"] = "初筛通过"
        frame.loc[index, "分组"] = "初筛"

    if "name" in payload and payload.get("name"):
        frame.loc[index, "名称"] = str(payload["name"])
    if "group" in payload and payload.get("group"):
        group = str(payload["group"])
        frame.loc[index, "分组"] = group
        frame.loc[index, "流程阶段"] = FRONTEND_GROUP_TO_STAGE.get(group, group)
        frame.loc[index, "状态"] = frame.loc[index, "流程阶段"]
    if "remark" in payload:
        frame.loc[index, "备注"] = str(payload.get("remark") or "")
    if "tomorrowPlan" in payload:
        frame.loc[index, "明日计划"] = str(payload.get("tomorrowPlan") or "")

    frame = ensure_watchlist_frame(frame)
    save_watchlist(frame)
    return {"success": True, "stock": watchlist_to_api(frame.iloc[[index]])[0]}
