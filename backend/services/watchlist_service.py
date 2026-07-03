from __future__ import annotations

from typing import Any

import pandas as pd

from src.data import (
    WATCHLIST_COLUMNS,
    archive_import_file,
    assign_pool_batch,
    enrich_watchlist,
    load_holdings,
    load_watchlist,
    save_watchlist,
    standardize_import_file,
)
from src.history import compute_all_reminders, diagnose_history, fetch_and_cache
from src.portfolio import account_state_from_trades, build_positions_from_trades
from src.realtime import (
    fetch_auto_stock_pool,
    fetch_realtime_quotes,
    merge_quotes_into_watchlist,
)
from src.rules import clean_code, evaluate_stock, normalize_stage, stage_to_group
from src.storage import load_quote_snapshot, save_quote_snapshot

from backend.services.risk_service import annotate_watchlist_risk, refresh_external_market_context
from backend.services.settings_service import account_mode_name, current_mode, get_settings, initial_cash
from backend.storage.csv_adapter import (
    FRONTEND_GROUP_TO_STAGE,
    ensure_watchlist_frame,
    watchlist_to_api,
)
from backend.storage import trade_repository

PINNED_GROUPS = {"观察", "待买", "持仓"}


def _watchlist_api(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return annotate_watchlist_risk(watchlist_to_api(frame))


def _empty_watchlist() -> pd.DataFrame:
    return pd.DataFrame(columns=WATCHLIST_COLUMNS)


def _number(value: Any, default: float = 0.0) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    return float(parsed) if pd.notna(parsed) else default


def _held_codes(watchlist: pd.DataFrame) -> set[str]:
    codes: set[str] = set()
    try:
        legacy_holdings = load_holdings()
        active_mode = current_mode()
        account_mode = account_mode_name(active_mode)
        trades = trade_repository.load_trade_frame(active_mode, account_mode)
        positions = build_positions_from_trades(trades, watchlist, legacy_holdings)
        if not positions.empty and "代码" in positions:
            codes.update(clean_code(value) for value in positions["代码"].dropna().astype(str))
        if not legacy_holdings.empty and "代码" in legacy_holdings:
            if "数量" in legacy_holdings:
                qty = pd.to_numeric(legacy_holdings["数量"], errors="coerce").fillna(0)
                holding_rows = legacy_holdings[qty > 0]
            else:
                holding_rows = legacy_holdings
            codes.update(clean_code(value) for value in holding_rows["代码"].dropna().astype(str))
    except Exception:
        return codes
    return {code for code in codes if code}


def _account_cash_for_watchlist(frame: pd.DataFrame) -> tuple[float, float]:
    active_mode = current_mode()
    account_mode = account_mode_name(active_mode)
    capital = initial_cash()
    trades = trade_repository.load_trade_frame(active_mode, account_mode)
    legacy_holdings = load_holdings()
    positions = build_positions_from_trades(trades, frame, legacy_holdings)
    state = account_state_from_trades(trades, positions, capital, account_mode)
    return float(state.get("当前现金") or capital), capital


def recompute_watchlist(frame: pd.DataFrame, cash: float | None = None) -> pd.DataFrame:
    if frame.empty:
        return ensure_watchlist_frame(frame)
    available_cash, capital = _account_cash_for_watchlist(frame) if cash is None else (cash, initial_cash())
    out = ensure_watchlist_frame(frame)
    reminders = compute_all_reminders(out, available_cash)
    for column in reminders.columns:
        if column in out.columns and len(reminders) == len(out):
            out[column] = reminders[column].values
    enriched = enrich_watchlist(out, available_cash, initial_capital=capital)
    for column in enriched.columns:
        if column in out.columns and len(enriched) == len(out):
            out[column] = enriched[column].values

    held_codes = _held_codes(out)
    for index, row in out.iterrows():
        code = clean_code(row.get("代码"))
        result = evaluate_stock(row.to_dict())
        out.loc[index, "流程阶段"] = result["stage"]
        out.loc[index, "状态"] = result["stage"]
        out.loc[index, "分组"] = result["group"]
        out.loc[index, "筛选原因"] = result["reason"]
        out.loc[index, "提醒"] = result["reminder"]
        was_pinned = str(row.get("is_pinned", "")).strip().lower() in {"true", "1", "是", "yes", "y"}
        if was_pinned or result["group"] in PINNED_GROUPS or code in held_codes:
            out.loc[index, "is_pinned"] = True
    return ensure_watchlist_frame(out)


def list_watchlist() -> dict[str, Any]:
    frame = recompute_watchlist(load_watchlist())
    return {"list": _watchlist_api(frame)}


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
            "list": _watchlist_api(cached),
        }

    existing = load_watchlist()
    remarks: dict[str, Any] = {}
    plans: dict[str, Any] = {}
    if not existing.empty:
        for _, row in existing.iterrows():
            code = clean_code(row.get("代码"))
            remarks[code] = row.get("备注", "")
            plans[code] = row.get("明日计划", "")

    source_label = str(pool.attrs.get("source") or source or "自动生成")
    frame = ensure_watchlist_frame(assign_pool_batch(pool, f"自动生成:{source_label}"))
    for index, row in frame.iterrows():
        code = clean_code(row.get("代码"))
        if code in remarks:
            frame.loc[index, "备注"] = remarks[code]
        if code in plans:
            frame.loc[index, "明日计划"] = plans[code]

    frame = recompute_watchlist(frame)
    save_watchlist(frame)
    market_context = refresh_external_market_context()
    batch_id = str(frame["pool_batch_id"].dropna().iloc[0]) if "pool_batch_id" in frame and not frame.empty else ""
    return {
        "success": True,
        "message": f"已生成并锁定今日初筛池 {len(frame)} 只，批次 {batch_id}",
        "marketContext": {
            "success": bool(market_context.get("success")),
            "message": market_context.get("message", ""),
        },
        "list": _watchlist_api(frame),
    }


def import_watchlist_file(content: bytes, filename: str, fetch_history: bool = False) -> dict[str, Any]:
    if not content:
        raise ValueError("上传文件为空")
    frame, summary = standardize_import_file(content, filename)
    if frame.empty:
        raise ValueError("未能从表格中识别出有效沪深主板股票代码")

    archive_path = archive_import_file(content, filename)
    frame = assign_pool_batch(frame, f"同花顺上传:{filename}")
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
        "list": _watchlist_api(frame),
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
            return {"success": False, "message": message or "行情刷新失败，且没有可用缓存", "list": _watchlist_api(frame)}
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
    market_context = refresh_external_market_context()
    return {
        "success": True,
        "message": message,
        "marketContext": {
            "success": bool(market_context.get("success")),
            "message": market_context.get("message", ""),
        },
        "list": _watchlist_api(merged),
    }


def scan_turnover_changes() -> dict[str, Any]:
    frame = load_watchlist()
    settings = get_settings()
    source = str(settings.get("quote_source") or settings.get("quoteSource") or "自动切换")
    limit = int(settings.get("auto_pool_size") or 30)
    live_pool = fetch_auto_stock_pool(limit=limit, source=source)
    if live_pool.empty:
        return {
            "success": False,
            "message": live_pool.attrs.get("message", "行情源未返回实时成交额前30"),
            "changes": {"newEntries": [], "dropped": [], "rankUp": [], "rankDown": []},
            "list": _watchlist_api(frame),
        }

    current_codes = {clean_code(value) for value in frame.get("代码", pd.Series(dtype=str)).dropna().astype(str)}
    live_codes = {clean_code(value) for value in live_pool.get("代码", pd.Series(dtype=str)).dropna().astype(str)}

    current_rank: dict[str, int] = {}
    if not frame.empty:
        rank_source = frame.get("pool_rank_at_generation", frame.get("成交额排名"))
        for code, rank in zip(frame["代码"], rank_source):
            parsed = pd.to_numeric(rank, errors="coerce")
            if pd.notna(parsed):
                current_rank[clean_code(code)] = int(parsed)

    live_rank = {
        clean_code(row.get("代码")): int(_number(row.get("成交额排名")))
        for _, row in live_pool.iterrows()
        if pd.notna(pd.to_numeric(row.get("成交额排名"), errors="coerce"))
    }

    def stock_payload(row: pd.Series, rank_key: str = "成交额排名") -> dict[str, Any]:
        code = clean_code(row.get("代码"))
        return {
            "code": code,
            "name": str(row.get("名称") or ""),
            "rank": int(_number(row.get(rank_key))),
            "volume": _number(row.get("成交额")),
            "price": _number(row.get("现价")),
            "pct": _number(row.get("涨跌幅%")),
        }

    live_by_code = {clean_code(row.get("代码")): row for _, row in live_pool.iterrows()}
    current_by_code = {clean_code(row.get("代码")): row for _, row in frame.iterrows()}

    new_entries = [
        stock_payload(live_by_code[code])
        for code in sorted(live_codes - current_codes, key=lambda item: live_rank.get(item, 999999))
    ]
    dropped = [
        {
            **stock_payload(current_by_code[code], "pool_rank_at_generation"),
            "currentRank": None,
            "isPinned": bool(str(current_by_code[code].get("is_pinned", "")).strip().lower() in {"true", "1", "是", "yes", "y"}),
        }
        for code in sorted(current_codes - live_codes, key=lambda item: current_rank.get(item, 999999))
    ]

    rank_up: list[dict[str, Any]] = []
    rank_down: list[dict[str, Any]] = []
    for code in sorted(current_codes & live_codes, key=lambda item: live_rank.get(item, 999999)):
        old_rank = current_rank.get(code)
        new_rank = live_rank.get(code)
        if old_rank is None or new_rank is None or old_rank == new_rank:
            continue
        item = stock_payload(live_by_code[code])
        item["oldRank"] = old_rank
        item["newRank"] = new_rank
        if new_rank < old_rank:
            rank_up.append(item)
        else:
            rank_down.append(item)

    changes = {
        "newEntries": new_entries,
        "dropped": dropped,
        "rankUp": rank_up,
        "rankDown": rank_down,
    }
    return {
        "success": True,
        "message": (
            f"扫描完成：新进 {len(new_entries)} 只，跌出 {len(dropped)} 只，"
            f"排名上升 {len(rank_up)} 只，排名下降 {len(rank_down)} 只。当前初筛池未被替换。"
        ),
        "changes": changes,
        "list": _watchlist_api(frame),
    }


def include_turnover_stock(payload: dict[str, Any]) -> dict[str, Any]:
    code = clean_code(payload.get("code"))
    if not code:
        raise ValueError("股票代码缺失")

    frame = ensure_watchlist_frame(load_watchlist())
    matches = frame.index[frame["代码"].astype(str).map(clean_code) == code].tolist() if not frame.empty else []
    rank = int(_number(payload.get("rank"), len(frame) + 1))

    if matches:
        index = matches[0]
    else:
        if frame.empty:
            batch = assign_pool_batch(pd.DataFrame([{}]), "手动纳入新进前30")
            batch_id = str(batch.loc[0, "pool_batch_id"])
            source = str(batch.loc[0, "pool_source"])
            generated_at = str(batch.loc[0, "pool_generated_at"])
        else:
            batch_ids = frame["pool_batch_id"].replace("", pd.NA).dropna()
            sources = frame["pool_source"].replace("", pd.NA).dropna()
            generated_times = frame["pool_generated_at"].replace("", pd.NA).dropna()
            if batch_ids.empty or generated_times.empty:
                batch = assign_pool_batch(pd.DataFrame([{}]), "手动纳入新进前30")
                batch_id = str(batch.loc[0, "pool_batch_id"])
                generated_at = str(batch.loc[0, "pool_generated_at"])
            else:
                batch_id = str(batch_ids.iloc[0])
                generated_at = str(generated_times.iloc[0])
            source = str(sources.iloc[0]) if not sources.empty else "当前初筛池"
        row = {
            "代码": code,
            "名称": str(payload.get("name") or ""),
            "现价": _number(payload.get("price")),
            "涨跌幅%": _number(payload.get("pct")),
            "成交额": _number(payload.get("volume")),
            "成交额排名": rank,
            "pool_batch_id": batch_id,
            "pool_source": f"{source};手动纳入",
            "pool_generated_at": generated_at,
            "pool_rank_at_generation": rank,
            "is_pool_locked": True,
            "is_pinned": False,
            "上市板块": "主板",
            "状态": "初筛通过",
            "流程阶段": "初筛通过",
            "分组": "初筛",
            "备注": "新进成交额前30手动纳入",
        }
        index = len(frame)
        frame.loc[index, WATCHLIST_COLUMNS] = pd.NA
        for column, value in row.items():
            frame.loc[index, column] = value

    for field, column in {
        "name": "名称",
        "price": "现价",
        "pct": "涨跌幅%",
        "volume": "成交额",
        "rank": "成交额排名",
    }.items():
        if field in payload and payload.get(field) not in {None, ""}:
            frame.loc[index, column] = payload.get(field)
    frame.loc[index, "pool_rank_at_generation"] = rank

    frame = recompute_watchlist(frame)
    save_watchlist(frame)
    return {
        "success": True,
        "message": f"已手动纳入今日初筛池：{code}",
        "list": _watchlist_api(frame),
    }


def fetch_history_for_watchlist(code: str | None = None, fetch_all: bool = False) -> dict[str, Any]:
    frame = load_watchlist()
    if frame.empty:
        return {"success": True, "message": "股票池为空", "list": []}
    all_codes = [clean_code(value) for value in frame["代码"].dropna().astype(str)]
    all_codes = [value for value in all_codes if value]
    if fetch_all:
        codes = [
            value
            for value in all_codes
            if not diagnose_history(value)["is_valid"]
        ]
    elif code:
        codes = [clean_code(code)]
    else:
        codes = [
            clean_code(row.get("代码"))
            for _, row in frame.iterrows()
            if str(row.get("history_status", "")) != "已有缓存"
        ]
    codes = [value for value in codes if value]

    summary = {
        "success": True,
        "fetched": 0,
        "failed": 0,
        "skipped": max(0, len(all_codes) - len(codes)) if fetch_all else 0,
        "results": {},
    }
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
    summary["list"] = _watchlist_api(updated)
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
        stage = normalize_stage(FRONTEND_GROUP_TO_STAGE.get(group, group))
        frame.loc[index, "流程阶段"] = stage
        frame.loc[index, "状态"] = stage
        frame.loc[index, "分组"] = stage_to_group(stage)
        if stage_to_group(stage) in PINNED_GROUPS:
            frame.loc[index, "is_pinned"] = True
    if "remark" in payload:
        frame.loc[index, "备注"] = str(payload.get("remark") or "")
    if "tomorrowPlan" in payload:
        frame.loc[index, "明日计划"] = str(payload.get("tomorrowPlan") or "")

    frame = ensure_watchlist_frame(frame)
    save_watchlist(frame)
    return {"success": True, "stock": _watchlist_api(frame.iloc[[index]])[0]}
