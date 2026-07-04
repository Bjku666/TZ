from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Thread
from datetime import date, datetime, time
from time import perf_counter
from typing import Any
from uuid import uuid4

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
from src.history import compute_all_reminders, diagnose_history, fetch_and_cache, load_cached_history
from src.portfolio import account_state_from_trades, build_positions_from_trades
from src.realtime import (
    china_now,
    fetch_auto_stock_pool,
    fetch_raw_turnover_top,
    fetch_realtime_quotes,
    is_a_share_trading_time,
    merge_quotes_into_watchlist,
    realtime_source_health,
)
from src.rule_models import CandidateState
from src.rules import clean_code, evaluate_stock, normalize_stage, stage_to_group
from src.storage import load_quote_snapshot, save_quote_snapshot
from src.trading_calendar import is_trading_day, next_trading_day, previous_trading_day
from src.trading_rules_config import QUOTE_FRESHNESS_SECONDS, TURNOVER_TOP_N
from src.video_original_rules import (
    calculate_ma5_close,
    calculate_ma5_live,
    evaluate_candidate_state,
    filter_raw_top20,
    is_official_selection_qualified,
    official_generation_allowed,
)

from backend.services.risk_service import annotate_watchlist_risk, refresh_market_context_if_stale
from backend.services.portfolio_service import portfolio_snapshot
from backend.services.settings_service import account_mode_name, current_mode, get_settings, initial_cash
from backend.storage.csv_adapter import (
    FRONTEND_GROUP_TO_STAGE,
    ensure_watchlist_frame,
    watchlist_to_api,
)
from backend.storage import trade_repository
from backend.storage import sqlite_store

PINNED_GROUPS = {"观察", "待买", "持仓"}
TRUE_VALUES = {"true", "1", "是", "yes", "y"}
LOGGER = logging.getLogger("tz.performance")
QUOTE_REFRESH_LOCK = Lock()
POOL_REBUILD_LOCK = Lock()
TURNOVER_SCAN_LOCK = Lock()
HISTORY_JOB_LOCK = Lock()
HISTORY_JOBS_STATE_LOCK = Lock()
HISTORY_JOBS: dict[str, dict[str, Any]] = {}


def _iso_now() -> str:
    return china_now().replace(microsecond=0).isoformat()


def _official_selection_date(now: datetime | None = None) -> date:
    current = now or china_now()
    if is_trading_day(current.date()) and current.time() >= time(15, 5):
        return current.date()
    return previous_trading_day(current.date())


def _history_values_for_selection(code: str, selection_date: date) -> dict[str, Any]:
    history = load_cached_history(code)
    empty = {
        "close": None,
        "ma5": None,
        "ma10": None,
        "ma20": None,
        "history_last_trade_date": "",
        "risk": "缺少历史K线，不能确认入选日MA5",
        "previous_four_closes": [],
    }
    if history is None or history.empty or "收盘" not in history:
        return empty
    frame = history.copy()
    frame["日期"] = pd.to_datetime(frame.get("日期"), errors="coerce")
    frame = frame.dropna(subset=["日期"]).sort_values("日期")
    frame = frame[frame["日期"].dt.date <= selection_date].copy()
    if frame.empty:
        return empty
    close = pd.to_numeric(frame["收盘"], errors="coerce").dropna()
    if len(close) < 5:
        return {**empty, "risk": "历史K线不足5个完成交易日"}
    latest = frame.loc[close.index[-1]]
    ma5 = calculate_ma5_close(close.tolist())
    ma10 = float(close.tail(10).mean()) if len(close) >= 10 else None
    ma20 = float(close.tail(20).mean()) if len(close) >= 20 else None
    previous_four = close.iloc[-4:].tolist()
    return {
        "close": float(latest.get("收盘")),
        "ma5": ma5,
        "ma10": round(ma10, 6) if ma10 is not None else None,
        "ma20": round(ma20, 6) if ma20 is not None else None,
        "history_last_trade_date": latest["日期"].date().isoformat(),
        "risk": "" if latest["日期"].date() == selection_date else "历史K线日期与入选日不一致，信号需人工复核",
        "previous_four_closes": previous_four,
    }


def _previous_four_closes_for_live(code: str, today: date) -> tuple[list[float], str]:
    history = load_cached_history(code)
    if history is None or history.empty or "收盘" not in history:
        return [], ""
    frame = history.copy()
    frame["日期"] = pd.to_datetime(frame.get("日期"), errors="coerce")
    frame = frame.dropna(subset=["日期"]).sort_values("日期")
    frame = frame[frame["日期"].dt.date < today].copy()
    close = pd.to_numeric(frame.get("收盘"), errors="coerce").dropna()
    if len(close) < 4:
        return [], ""
    last_date = frame.loc[close.index[-1], "日期"].date().isoformat()
    return [float(value) for value in close.tail(4).tolist()], last_date


def _candidate_waiting_days(selection_date: Any, as_of: date | None = None) -> int:
    start = pd.to_datetime(selection_date, errors="coerce")
    if pd.isna(start):
        return 0
    current = as_of or china_now().date()
    days = 0
    day = next_trading_day(start.date())
    while day <= current:
        if is_trading_day(day):
            days += 1
        day = next_trading_day(day)
    return days


def _selection_item_api(item: dict[str, Any], batch: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "batchId": item.get("batch_id"),
        "code": item.get("code"),
        "name": item.get("name"),
        "rawRank": item.get("raw_rank"),
        "turnover": item.get("turnover"),
        "closePrice": item.get("close_price"),
        "ma5Close": item.get("ma5_close"),
        "marketAllowed": bool(item.get("market_allowed")),
        "exclusionReason": item.get("exclusion_reason") or "",
        "aboveMa5": bool(item.get("above_ma5")),
        "candidateCreated": bool(item.get("candidate_created")),
        "selectionDate": (batch or {}).get("selection_date"),
        "source": (batch or {}).get("source"),
        "dataAsOf": (batch or {}).get("data_as_of"),
    }


def _candidate_api(candidate: dict[str, Any]) -> dict[str, Any]:
    waiting_days = _candidate_waiting_days(candidate.get("selection_date"))
    return {
        "id": candidate.get("id"),
        "code": candidate.get("code"),
        "name": candidate.get("name"),
        "sourceBatchId": candidate.get("source_batch_id"),
        "selectionDate": candidate.get("selection_date"),
        "eligibleFrom": candidate.get("eligible_from"),
        "state": candidate.get("state"),
        "waitingTradeDays": waiting_days,
        "lastClose": candidate.get("last_close"),
        "lastMa5Close": candidate.get("last_ma5_close"),
        "lastLivePrice": candidate.get("last_live_price"),
        "lastMa5Live": candidate.get("last_ma5_live"),
        "lastDeviation": candidate.get("last_deviation"),
        "touchStartedAt": candidate.get("touch_started_at"),
        "touchDetectedAt": candidate.get("touch_detected_at"),
        "boughtTradeId": candidate.get("bought_trade_id"),
        "invalidatedReason": candidate.get("invalidated_reason"),
        "createdAt": candidate.get("created_at"),
        "updatedAt": candidate.get("updated_at"),
    }


def _watchlist_frame_from_selection(items: list[dict[str, Any]], batch: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append(
            {
                "代码": item.get("code"),
                "名称": item.get("name"),
                "现价": item.get("close_price"),
                "涨跌幅%": pd.NA,
                "成交额": item.get("turnover"),
                "成交额排名": item.get("raw_rank"),
                "pool_batch_id": item.get("batch_id"),
                "pool_source": batch.get("source"),
                "pool_generated_at": batch.get("generated_at"),
                "pool_rank_at_generation": item.get("raw_rank"),
                "is_pool_locked": True,
                "is_pinned": bool(item.get("candidate_created")),
                "上市板块": "主板" if item.get("market_allowed") else "不适用",
                "状态": CandidateState.INITIAL_SCREENED.value if item.get("market_allowed") else CandidateState.INITIAL_REJECTED.value,
                "分组": "初筛",
                "MA5": item.get("ma5_close"),
                "MA10": pd.NA,
                "MA20": pd.NA,
                "MA5向上": False,
                "最近大阳线%": pd.NA,
                "放量跌破MA5": False,
                "MA5偏离率%": pd.NA,
                "history_status": "已有缓存" if item.get("ma5_close") else "缺少历史K线",
                "流程阶段": CandidateState.INITIAL_SCREENED.value if item.get("market_allowed") else CandidateState.INITIAL_REJECTED.value,
                "筛选原因": "" if item.get("market_allowed") else item.get("exclusion_reason"),
                "提醒": "入选日收盘站上MA5，转入跨日观察" if item.get("candidate_created") else item.get("exclusion_reason") or "等待历史K线确认",
                "规则状态": "视频原版",
                "备注": "由SQLite正式批次派生",
            }
        )
    return ensure_watchlist_frame(pd.DataFrame(rows))


def _latest_official_payload() -> dict[str, Any]:
    batch = sqlite_store.latest_official_batch()
    if not batch:
        return {
            "officialSelection": None,
            "initialPool": [],
            "observationPool": [_candidate_api(item) for item in sqlite_store.candidate_cycles(active_only=True)],
            "buyReadyPool": [],
        }
    items = sqlite_store.selection_items_for_batch(str(batch["id"]))
    candidates = [_candidate_api(item) for item in sqlite_store.candidate_cycles(active_only=True)]
    buy_ready = [item for item in candidates if item.get("state") == CandidateState.BUY_READY.value]
    return {
        "officialSelection": {
            "batchId": batch.get("id"),
            "selectionDate": batch.get("selection_date"),
            "generatedAt": batch.get("generated_at"),
            "source": batch.get("source"),
            "isOfficial": bool(batch.get("is_official")),
            "dataAsOf": batch.get("data_as_of"),
            "rawTopN": batch.get("raw_top_n"),
        },
        "initialPool": [_selection_item_api(item, batch) for item in items],
        "observationPool": candidates,
        "buyReadyPool": buy_ready,
    }


def _performance_log(
    endpoint: str,
    request_id: str,
    started_at: float,
    *,
    source: str = "",
    source_latency_ms: int = 0,
    cache_hit: bool = False,
    stale: bool = False,
    success: bool = True,
    error_type: str = "",
) -> int:
    duration_ms = round((perf_counter() - started_at) * 1000)
    LOGGER.info(
        json.dumps(
            {
                "endpoint": endpoint,
                "request_id": request_id,
                "source": source,
                "source_latency_ms": source_latency_ms,
                "total_duration_ms": duration_ms,
                "cache_hit": cache_hit,
                "stale": stale,
                "success": success,
                "error_type": error_type,
            },
            ensure_ascii=False,
        )
    )
    return duration_ms


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


def _has_current_day_locked_pool(frame: pd.DataFrame, expected_size: int) -> bool:
    if frame.empty:
        return False
    pool = ensure_watchlist_frame(frame)
    codes = pool["代码"].map(clean_code).astype(bool)
    locked = pool["is_pool_locked"].astype(str).str.strip().str.lower().isin(TRUE_VALUES)
    generated_dates = pd.to_datetime(pool["pool_generated_at"], errors="coerce").dt.date
    current_day_rows = codes & locked & generated_dates.eq(china_now().date())
    return int(current_day_rows.sum()) >= max(int(expected_size or 1), 1)


def _source_failure_message(source_message: object, *, trading_time: bool) -> str:
    reason = str(source_message or "行情源未返回股票池")
    if trading_time:
        return f"当前为交易时间，实时行情源不可用。为避免使用旧数据误判，未重建今日初筛池，已保留当前名单。原因：{reason}"
    return reason


def _account_cash_for_watchlist(frame: pd.DataFrame) -> tuple[float, float]:
    active_mode = current_mode()
    account_mode = account_mode_name(active_mode)
    capital = initial_cash()
    trades = trade_repository.load_trade_frame(active_mode, account_mode)
    legacy_holdings = load_holdings()
    positions = build_positions_from_trades(trades, frame, legacy_holdings)
    state = account_state_from_trades(trades, positions, capital, account_mode)
    return float(state.get("当前现金") or capital), capital


def _quote_target_codes(frame: pd.DataFrame) -> list[str]:
    codes: set[str] = set()
    if not frame.empty and "代码" in frame:
        codes.update(clean_code(code) for code in frame["代码"].dropna().astype(str))
    latest = sqlite_store.latest_official_batch()
    if latest:
        for item in sqlite_store.selection_items_for_batch(str(latest["id"])):
            code = clean_code(item.get("code"))
            if code:
                codes.add(code)
    for candidate in sqlite_store.candidate_cycles(active_only=True):
        code = clean_code(candidate.get("code"))
        if code:
            codes.add(code)
    codes.update(_held_codes(frame))
    return sorted(code for code in codes if code)


def _update_candidates_from_quotes(quotes: pd.DataFrame, *, used_cache: bool, source: str, account_cash: float) -> None:
    if quotes.empty or "代码" not in quotes:
        return
    now = china_now().replace(microsecond=0)
    quote_rows = {clean_code(row.get("代码")): row.to_dict() for _, row in quotes.iterrows()}
    candidates = sqlite_store.candidate_cycles(active_only=True)
    for candidate in candidates:
        code = clean_code(candidate.get("code"))
        quote = quote_rows.get(code)
        if not quote:
            continue
        price = _number(quote.get("最新价"))
        previous_four, history_last_date = _previous_four_closes_for_live(code, now.date())
        ma5_live = calculate_ma5_live(previous_four, price)
        quote_time = str(quote.get("更新时间") or now.isoformat())
        quote_age = 999999 if used_cache else 0
        evaluation = evaluate_candidate_state(
            candidate,
            {
                "price": price,
                "ma5_live": ma5_live,
                "quote_age_seconds": quote_age,
                "tradeable": price is not None and price > 0,
            },
            now,
            account_cash=account_cash,
        )
        previous_state = str(candidate.get("state") or "")
        updates = {
            "state": evaluation.state.value,
            "waiting_trade_days": _candidate_waiting_days(candidate.get("selection_date"), now.date()),
            "last_live_price": price,
            "last_ma5_live": ma5_live,
            "last_deviation": evaluation.deviation,
        }
        if evaluation.state == CandidateState.BUY_READY:
            touch_time = str(candidate.get("touch_started_at") or now.isoformat())
            updates["touch_started_at"] = touch_time
            updates["touch_detected_at"] = now.isoformat()
        sqlite_store.update_candidate_cycle(str(candidate["id"]), updates)
        if previous_state != evaluation.state.value:
            sqlite_store.add_candidate_event(
                str(candidate["id"]),
                "STATE_CHANGED",
                event_time=now.isoformat(),
                trade_date=now.date().isoformat(),
                price=price,
                ma5=ma5_live,
                deviation=evaluation.deviation,
                quote_time=quote_time,
                quote_age_seconds=quote_age,
                source=source,
                reason=evaluation.signal_reason,
                payload={
                    **evaluation.to_api(),
                    "historyLastTradeDate": history_last_date,
                    "quoteTime": quote_time,
                },
            )
        if evaluation.state == CandidateState.BUY_READY or evaluation.signal_qualified:
            sqlite_store.add_signal_event(
                {
                    "candidate_id": candidate["id"],
                    "code": code,
                    "event_time": now.isoformat(),
                    "trade_date": now.date().isoformat(),
                    "signal_type": "MA5_TOUCH_BUY",
                    "signal_qualified": int(evaluation.signal_qualified),
                    "execution_allowed": int(evaluation.execution_allowed),
                    "execution_block_reasons": evaluation.execution_block_reasons,
                    "price": price,
                    "ma5": ma5_live,
                    "deviation": evaluation.deviation,
                    "quote_time": quote_time,
                    "quote_age_seconds": quote_age,
                    "payload": {
                        **evaluation.to_api(),
                        "ma5Type": "live",
                        "calculationTime": now.isoformat(),
                        "historyLastTradeDate": history_last_date,
                    },
                }
            )


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
    payload = _latest_official_payload()
    return {"list": _watchlist_api(frame), **payload}


def generate_watchlist() -> dict[str, Any]:
    return generate_official_selection_batch()


def generate_official_selection_batch(source: str | None = None, force: bool = False) -> dict[str, Any]:
    if not POOL_REBUILD_LOCK.acquire(blocking=False):
        return {
            "success": False,
            "inProgress": True,
            "message": "已有股票池重建任务进行中",
            "list": _watchlist_api(load_watchlist()),
            **_latest_official_payload(),
        }
    try:
        return _generate_official_selection_batch_locked(source=source, force=force)
    finally:
        POOL_REBUILD_LOCK.release()


def _generate_official_selection_batch_locked(source: str | None = None, force: bool = False) -> dict[str, Any]:
    settings = get_settings()
    quote_source = source or str(settings.get("quote_source") or settings.get("quoteSource") or "自动切换")
    now = china_now()
    selection_date = _official_selection_date(now)
    if not force and not official_generation_allowed(now, selection_date):
        payload = _latest_official_payload()
        return {
            "success": False,
            "message": "正式初筛只能在完整交易日收盘数据可用后生成；盘中请使用盘中前20预览",
            "list": _watchlist_api(load_watchlist()),
            **payload,
        }

    raw_top = fetch_raw_turnover_top(limit=TURNOVER_TOP_N, source=quote_source)
    if raw_top.empty:
        cached = load_watchlist()
        source_message = raw_top.attrs.get("message", "行情源未返回原始成交额前20")
        trading_time = is_a_share_trading_time()
        if not trading_time and _has_current_day_locked_pool(cached, TURNOVER_TOP_N):
            cached = recompute_watchlist(cached)
            return {
                "success": True,
                "usedCache": True,
                "message": f"行情源暂时不可用，已保留最近正式初筛池 {len(cached)} 只。原因：{source_message}",
                "list": _watchlist_api(cached),
                **_latest_official_payload(),
            }
        return {
            "success": False,
            "message": _source_failure_message(source_message, trading_time=trading_time),
            "list": _watchlist_api(cached),
            **_latest_official_payload(),
        }

    rows: list[dict[str, Any]] = []
    for _, row in raw_top.iterrows():
        rows.append(
            {
                "code": clean_code(row.get("代码")),
                "name": str(row.get("名称") or ""),
                "raw_rank": int(_number(row.get("raw_rank"), _number(row.get("成交额排名"), len(rows) + 1))),
                "turnover": _number(row.get("成交额")),
                "price": _number(row.get("最新价", row.get("现价"))),
            }
        )
    filtered = filter_raw_top20(rows, raw_top_n=TURNOVER_TOP_N)
    source_label = str(raw_top.attrs.get("source") or quote_source or "自动生成")
    generated_at = now.replace(microsecond=0).isoformat()
    batch_id = f"{selection_date.isoformat()}_{source_label}_official_v1"
    batch = {
        "id": batch_id,
        "selection_date": selection_date.isoformat(),
        "generated_at": generated_at,
        "data_as_of": selection_date.isoformat(),
        "source": source_label,
        "is_official": 1,
        "raw_top_n": TURNOVER_TOP_N,
        "status": "active",
        "source_message": str(raw_top.attrs.get("message") or ""),
    }
    sqlite_store.upsert_selection_batch(batch)

    saved_items: list[dict[str, Any]] = []
    created_count = 0
    for item in filtered:
        code = clean_code(item.get("code"))
        history_values = _history_values_for_selection(code, selection_date)
        close_price = history_values.get("close")
        ma5_close = history_values.get("ma5")
        above_ma5 = bool(item.get("market_allowed")) and is_official_selection_qualified(close_price, ma5_close)
        candidate_created = False
        if above_ma5:
            eligible = next_trading_day(selection_date)
            candidate_id, created = sqlite_store.create_candidate_cycle(
                {
                    "id": f"C_{code}_{selection_date.isoformat()}",
                    "code": code,
                    "name": item.get("name"),
                    "source_batch_id": batch_id,
                    "selection_date": selection_date.isoformat(),
                    "eligible_from": eligible.isoformat(),
                    "state": CandidateState.WAITING_ELIGIBLE_DATE.value if eligible > now.date() else CandidateState.OBSERVING.value,
                    "waiting_trade_days": 0,
                    "last_close": close_price,
                    "last_ma5_close": ma5_close,
                    "event_time": generated_at,
                }
            )
            candidate_created = True
            created_count += int(created)
        selection_item = {
            "id": f"{batch_id}:{code}",
            "batch_id": batch_id,
            "code": code,
            "name": item.get("name"),
            "raw_rank": int(item.get("raw_rank") or 0),
            "turnover": item.get("turnover"),
            "close_price": close_price,
            "ma5_close": ma5_close,
            "market_allowed": int(bool(item.get("market_allowed"))),
            "exclusion_reason": item.get("exclusion_reason") or history_values.get("risk") or ("" if above_ma5 else "入选日收盘未站上MA5"),
            "above_ma5": int(above_ma5),
            "candidate_created": int(candidate_created),
        }
        sqlite_store.upsert_selection_item(selection_item)
        saved_items.append(selection_item)

    frame = _watchlist_frame_from_selection(saved_items, batch)
    save_watchlist(frame)
    market_context = refresh_market_context_if_stale()
    payload = _latest_official_payload()
    return {
        "success": True,
        "message": f"已生成视频原版正式初筛批次：原始前{TURNOVER_TOP_N}，过滤后 {sum(1 for item in saved_items if item['market_allowed'])} 只，新建候选 {created_count} 只",
        "marketContext": {
            "success": bool(market_context.get("success")),
            "message": market_context.get("message", ""),
        },
        "list": _watchlist_api(frame),
        **payload,
    }


def generate_intraday_preview() -> dict[str, Any]:
    settings = get_settings()
    source = str(settings.get("quote_source") or settings.get("quoteSource") or "自动切换")
    raw_top = fetch_raw_turnover_top(limit=TURNOVER_TOP_N, source=source)
    if raw_top.empty:
        return {
            "success": False,
            "message": raw_top.attrs.get("message", "行情源未返回盘中前20预览"),
            "intradayPreview": {"items": [], "changes": {"newEntries": [], "dropped": [], "rankUp": [], "rankDown": []}},
        }
    rows = []
    for _, row in raw_top.iterrows():
        rows.append(
            {
                "code": clean_code(row.get("代码")),
                "name": str(row.get("名称") or ""),
                "raw_rank": int(_number(row.get("raw_rank"), len(rows) + 1)),
                "turnover": _number(row.get("成交额")),
                "price": _number(row.get("最新价")),
            }
        )
    items = filter_raw_top20(rows, raw_top_n=TURNOVER_TOP_N)
    latest = sqlite_store.latest_official_batch()
    old_items = sqlite_store.selection_items_for_batch(str(latest["id"])) if latest else []
    old_rank = {clean_code(item.get("code")): int(item.get("raw_rank") or 0) for item in old_items}
    old_codes = set(old_rank)
    new_rank = {clean_code(item.get("code")): int(item.get("raw_rank") or 0) for item in items}
    new_codes = set(new_rank)

    def payload_for(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "code": item.get("code"),
            "name": item.get("name"),
            "rank": item.get("raw_rank"),
            "volume": item.get("turnover"),
            "price": item.get("price"),
            "marketAllowed": item.get("market_allowed"),
            "exclusionReason": item.get("exclusion_reason"),
        }

    by_code = {clean_code(item.get("code")): item for item in items}
    changes = {
        "newEntries": [payload_for(by_code[code]) for code in sorted(new_codes - old_codes, key=lambda code: new_rank.get(code, 999))],
        "dropped": [{"code": code, "oldRank": old_rank.get(code), "currentRank": None} for code in sorted(old_codes - new_codes, key=lambda code: old_rank.get(code, 999))],
        "rankUp": [],
        "rankDown": [],
    }
    for code in sorted(old_codes & new_codes, key=lambda value: new_rank.get(value, 999)):
        if new_rank[code] < old_rank[code]:
            changes["rankUp"].append({**payload_for(by_code[code]), "oldRank": old_rank[code], "newRank": new_rank[code]})
        elif new_rank[code] > old_rank[code]:
            changes["rankDown"].append({**payload_for(by_code[code]), "oldRank": old_rank[code], "newRank": new_rank[code]})
    return {
        "success": True,
        "message": "盘中前20预览已更新；不会生成正式候选，也不会覆盖收盘批次",
        "intradayPreview": {"items": [payload_for(item) for item in items], "changes": changes},
    }


def import_watchlist_file(content: bytes, filename: str, fetch_history: bool = False, as_official: bool = False) -> dict[str, Any]:
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
    official_payload: dict[str, Any] = {}
    if as_official:
        now = china_now()
        selection_date = _official_selection_date(now)
        generated_at = now.replace(microsecond=0).isoformat()
        batch_id = f"{selection_date.isoformat()}_ths_import_official_v1"
        batch = {
            "id": batch_id,
            "selection_date": selection_date.isoformat(),
            "generated_at": generated_at,
            "data_as_of": selection_date.isoformat(),
            "source": f"同花顺上传:{filename}",
            "is_official": 1,
            "raw_top_n": TURNOVER_TOP_N,
            "status": "active",
            "source_message": "用户确认作为正式收盘批次",
        }
        sqlite_store.upsert_selection_batch(batch)
        saved_items: list[dict[str, Any]] = []
        for _, row in frame.iterrows():
            code = clean_code(row.get("代码"))
            history_values = _history_values_for_selection(code, selection_date)
            close_price = history_values.get("close")
            ma5_close = history_values.get("ma5")
            above_ma5 = is_official_selection_qualified(close_price, ma5_close)
            candidate_created = False
            if above_ma5:
                candidate_id, _created = sqlite_store.create_candidate_cycle(
                    {
                        "id": f"C_{code}_{selection_date.isoformat()}",
                        "code": code,
                        "name": str(row.get("名称") or ""),
                        "source_batch_id": batch_id,
                        "selection_date": selection_date.isoformat(),
                        "eligible_from": next_trading_day(selection_date).isoformat(),
                        "state": CandidateState.OBSERVING.value,
                        "waiting_trade_days": 0,
                        "last_close": close_price,
                        "last_ma5_close": ma5_close,
                        "event_time": generated_at,
                    }
                )
                candidate_created = True
            item = {
                "id": f"{batch_id}:{code}",
                "batch_id": batch_id,
                "code": code,
                "name": str(row.get("名称") or ""),
                "raw_rank": int(_number(row.get("pool_rank_at_generation"), _number(row.get("成交额排名"), 0))),
                "turnover": _number(row.get("成交额")),
                "close_price": close_price,
                "ma5_close": ma5_close,
                "market_allowed": 1,
                "exclusion_reason": history_values.get("risk") or ("" if above_ma5 else "入选日收盘未站上MA5"),
                "above_ma5": int(above_ma5),
                "candidate_created": int(candidate_created),
            }
            sqlite_store.upsert_selection_item(item)
            saved_items.append(item)
        official_payload = _latest_official_payload()

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
        **official_payload,
    }


def refresh_quotes() -> dict[str, Any]:
    request_id = uuid4().hex
    started_at = perf_counter()
    if not QUOTE_REFRESH_LOCK.acquire(blocking=False):
        portfolio = portfolio_snapshot(persist_risk_state=False)
        return {
            "success": True,
            "inProgress": True,
            "requestId": request_id,
            "message": "已有行情刷新任务进行中，返回当前快照",
            "isStale": True,
            "dataAgeSeconds": 0,
            "list": _watchlist_api(load_watchlist()),
            "positions": portfolio["positions"],
            "accountState": portfolio["accountState"],
            **_latest_official_payload(),
            "durationMs": _performance_log(
                "/api/watchlist/refresh-quotes",
                request_id,
                started_at,
                cache_hit=True,
                stale=True,
            ),
        }
    try:
        return _refresh_quotes_locked(request_id, started_at)
    finally:
        QUOTE_REFRESH_LOCK.release()


def _refresh_quotes_locked(request_id: str, started_at: float) -> dict[str, Any]:
    frame = load_watchlist()
    codes = _quote_target_codes(frame)
    if not codes:
        return {"success": True, "requestId": request_id, "list": [], "positions": [], "durationMs": 0, **_latest_official_payload()}
    settings = get_settings()
    source = str(settings.get("quote_source") or "自动切换")
    source_started_at = perf_counter()
    quotes = fetch_realtime_quotes(codes, source=source)
    source_latency_ms = round((perf_counter() - source_started_at) * 1000)
    message = str(quotes.attrs.get("message", ""))
    used_cache = False
    if quotes.empty:
        cached = load_quote_snapshot()
        if not cached.empty:
            quotes = cached
            used_cache = True
            message = message or "行情源失败，已使用最近缓存"
        else:
            duration_ms = _performance_log(
                "/api/watchlist/refresh-quotes",
                request_id,
                started_at,
                source=source,
                source_latency_ms=source_latency_ms,
                success=False,
                error_type="quote_source_unavailable",
            )
            return {
                "success": False,
                "requestId": request_id,
                "message": message or "行情刷新失败，且没有可用缓存",
                "list": _watchlist_api(frame),
                **_latest_official_payload(),
                "durationMs": duration_ms,
            }
    else:
        save_quote_snapshot(
            quotes,
            source=str(quotes.attrs.get("source", source)),
            status="成功",
            message=message,
        )

    if frame.empty:
        frame = ensure_watchlist_frame(pd.DataFrame({"代码": codes}))
    merged = merge_quotes_into_watchlist(frame, quotes)
    merged = recompute_watchlist(merged)
    available_cash, _capital = _account_cash_for_watchlist(merged)
    _update_candidates_from_quotes(
        quotes,
        used_cache=used_cache,
        source=str(quotes.attrs.get("source", source)),
        account_cash=available_cash,
    )
    save_watchlist(merged)
    portfolio = portfolio_snapshot(persist_risk_state=True)
    payload = _latest_official_payload()
    duration_ms = _performance_log(
        "/api/watchlist/refresh-quotes",
        request_id,
        started_at,
        source=str(quotes.attrs.get("source", source)),
        source_latency_ms=source_latency_ms,
        cache_hit=used_cache,
        stale=used_cache,
    )
    return {
        "success": True,
        "requestId": request_id,
        "serverTime": china_now().isoformat(),
        "source": str(quotes.attrs.get("source", source)),
        "isStale": used_cache,
        "dataAgeSeconds": 0,
        "quoteFreshnessSeconds": QUOTE_FRESHNESS_SECONDS,
        "durationMs": duration_ms,
        "message": message,
        "list": _watchlist_api(merged),
        "watchlist": _watchlist_api(merged),
        "positions": portfolio["positions"],
        "accountState": portfolio["accountState"],
        "sourceHealth": realtime_source_health(),
        **payload,
    }


def scan_turnover_changes() -> dict[str, Any]:
    if not TURNOVER_SCAN_LOCK.acquire(blocking=False):
        return {
            "success": False,
            "inProgress": True,
            "message": "已有盘中前20预览扫描进行中",
            "changes": {"newEntries": [], "dropped": [], "rankUp": [], "rankDown": []},
            "list": _watchlist_api(load_watchlist()),
        }
    try:
        result = generate_intraday_preview()
        preview = result.get("intradayPreview") or {}
        return {
            "success": bool(result.get("success")),
            "message": result.get("message", ""),
            "changes": preview.get("changes", {"newEntries": [], "dropped": [], "rankUp": [], "rankDown": []}),
            "intradayPreview": preview,
            "list": _watchlist_api(load_watchlist()),
        }
    finally:
        TURNOVER_SCAN_LOCK.release()


def _scan_turnover_changes_locked() -> dict[str, Any]:
    frame = load_watchlist()
    settings = get_settings()
    source = str(settings.get("quote_source") or settings.get("quoteSource") or "自动切换")
    limit = TURNOVER_TOP_N
    live_pool = fetch_auto_stock_pool(limit=limit, source=source)
    if live_pool.empty:
        return {
            "success": False,
            "message": live_pool.attrs.get("message", "行情源未返回盘中原始成交额前20"),
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
    return {
        "success": False,
        "message": "盘中前20预览不能手动纳入正式池；请等待收盘后生成正式批次或导入收盘表并明确作为正式批次",
        "list": _watchlist_api(load_watchlist()),
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


def _history_job_worker(job_id: str, codes: list[str], skipped: int) -> None:
    results: dict[str, dict[str, Any]] = {}
    fetched = 0
    failed = 0
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(fetch_and_cache, code): code for code in codes}
            for future in as_completed(futures):
                item_code = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"success": False, "status": "自动获取失败", "error": str(exc)}
                fetched += int(bool(result.get("success")))
                failed += int(not result.get("success"))
                results[item_code] = {
                    "success": bool(result.get("success")),
                    "status": result.get("status", ""),
                    "error": result.get("error", ""),
                }
                with HISTORY_JOBS_STATE_LOCK:
                    HISTORY_JOBS[job_id].update(
                        {
                            "completed": fetched + failed,
                            "fetched": fetched,
                            "failed": failed,
                            "results": dict(results),
                        }
                    )

        updated = recompute_watchlist(load_watchlist())
        save_watchlist(updated)
        with HISTORY_JOBS_STATE_LOCK:
            HISTORY_JOBS[job_id].update(
                {
                    "status": "completed",
                    "success": failed == 0,
                    "completed": len(codes),
                    "fetched": fetched,
                    "failed": failed,
                    "skipped": skipped,
                    "list": _watchlist_api(updated),
                }
            )
    except Exception as exc:
        with HISTORY_JOBS_STATE_LOCK:
            HISTORY_JOBS[job_id].update({"status": "failed", "success": False, "error": str(exc)})
    finally:
        HISTORY_JOB_LOCK.release()


def start_history_job() -> dict[str, Any]:
    if not HISTORY_JOB_LOCK.acquire(blocking=False):
        with HISTORY_JOBS_STATE_LOCK:
            running = next((job for job in HISTORY_JOBS.values() if job.get("status") == "running"), None)
        return {"success": True, "inProgress": True, **(running or {"status": "running", "total": 0, "completed": 0})}

    frame = load_watchlist()
    all_codes = [clean_code(value) for value in frame.get("代码", pd.Series(dtype=str)).dropna().astype(str)]
    codes = [code for code in all_codes if code and not diagnose_history(code)["is_valid"]]
    job_id = uuid4().hex
    job: dict[str, Any] = {
        "success": True,
        "jobId": job_id,
        "status": "running",
        "total": len(codes),
        "completed": 0,
        "fetched": 0,
        "failed": 0,
        "skipped": max(0, len(all_codes) - len(codes)),
        "results": {},
    }
    with HISTORY_JOBS_STATE_LOCK:
        HISTORY_JOBS[job_id] = job
    if not codes:
        job["status"] = "completed"
        HISTORY_JOB_LOCK.release()
        return dict(job)
    Thread(target=_history_job_worker, args=(job_id, codes, int(job["skipped"])), daemon=True).start()
    return dict(job)


def get_history_job(job_id: str) -> dict[str, Any]:
    with HISTORY_JOBS_STATE_LOCK:
        job = HISTORY_JOBS.get(job_id)
        if job is None:
            raise ValueError("未找到K线补齐任务")
        return dict(job)


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
