from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from src.rules import (
    GROUPS,
    affordability,
    buy_signal,
    clean_code,
    ma5_deviation,
    normalize_stage,
    recent_big_candle_pct,
    screening_result,
    stage_to_group,
)
from src.storage import backup_file, safe_write_csv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCE_FILE = DATA_DIR / "模式2_2026-07-01.xlsx"
WATCHLIST_FILE = DATA_DIR / "watchlist.csv"
HOLDINGS_FILE = DATA_DIR / "holdings.csv"
LEGACY_TRADES_FILE = DATA_DIR / "trades.csv"
TRADES_FILE = DATA_DIR / "trades" / "trade_log.csv"

WATCHLIST_COLUMNS = [
    "代码",
    "名称",
    "现价",
    "涨跌幅%",
    "成交额",
    "成交额排名",
    "pool_batch_id",
    "pool_source",
    "pool_generated_at",
    "pool_rank_at_generation",
    "is_pool_locked",
    "is_pinned",
    "上市板块",
    "状态",
    "分组",
    "MA5",
    "MA10",
    "MA20",
    "MA5向上",
    "最近大阳线%",
    "放量跌破MA5",
    "MA5偏离率%",
    "一手金额",
    "当前本金",
    "当前可用资金",
    "本金是否可买",
    "history_status",
    "history_rows",
    "history_last_date",
    "history_error",
    "流程阶段",
    "筛选原因",
    "提醒",
    "规则状态",
    "明日计划",
    "备注",
]

HOLDING_COLUMNS = [
    "代码",
    "名称",
    "买入日期",
    "买入价",
    "数量",
    "当前价",
    "MA5",
    "跌破MA5天数",
    "备注",
]

TRADE_COLUMNS = [
    "代码",
    "名称",
    "类型",
    "日期",
    "时间",
    "价格",
    "数量",
    "金额",
    "手续费",
    "印花税",
    "过户费",
    "总费用",
    "原因",
    "备注",
    "规则快照",
    "规则结论",
    "违规标签",
]

LEGACY_TRADE_COLUMNS = [
    "买入日期",
    "卖出日期",
    "代码",
    "名称",
    "买入原因",
    "买入价",
    "卖出价",
    "数量",
    "买入时MA5",
    "买入时偏离率%",
    "是否符合规则",
    "是否按规则卖出",
    "错误类型",
    "备注",
]

ALIASES = {
    "代码": ["代码", "股票代码", "证券代码", "股票代码代码", "证券代码代码"],
    "名称": ["名称", "股票简称", "股票名称", "证券简称", "简称"],
    "现价": ["现价", "现价(元)", "最新价", "最新", "收盘价", "价格"],
    "涨跌幅%": ["涨跌幅%", "涨跌幅(%)", "涨跌幅", "涨幅%", "涨幅"],
    "成交额": ["成交额", "成交额(元)", "成交金额", "金额", "总金额", "成交额(万)", "成交额(亿)"],
    "成交额排名": ["成交额排名名次", "成交额排名", "排名", "名次", "成交额排行"],
    "上市板块": ["上市板块", "板块"],
    "日期": ["日期", "交易日期", "时间"],
    "开盘": ["开盘", "开盘价"],
    "最高": ["最高", "最高价"],
    "最低": ["最低", "最低价"],
    "收盘": ["收盘", "收盘价", "现价"],
    "成交量": ["成交量", "总手"],
}

HEADER_HINTS = ["代码", "证券代码", "股票代码", "名称", "股票简称", "证券简称", "现价", "成交额", "涨跌幅"]

# Simplified internal directories
REQUIRED_DIRS = [
    DATA_DIR / "raw" / "stock_pool",
    DATA_DIR / "history",
    DATA_DIR / "processed",
    DATA_DIR / "portfolio",
    DATA_DIR / "reports" / "daily",
    DATA_DIR / "reports" / "weekly",
    DATA_DIR / "reports" / "monthly",
    DATA_DIR / "exports",
    DATA_DIR / "trades",
    DATA_DIR / "runtime",
    DATA_DIR / "backups",
]


def normalize_watchlist_stage(value: object, default: str = "初筛通过") -> str:
    """Normalize legacy watchlist stage values to the v3 pipeline vocabulary."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text:
        return default
    stage = normalize_stage(text)
    return stage if stage in GROUPS else default


def ensure_data_dir() -> None:
    for d in REQUIRED_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _read_csv_bytes(raw: bytes, header: int | list[int] = 0) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "gb18030", "gbk"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=encoding, header=header, dtype=object)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(io.BytesIO(raw), header=header, dtype=object)


def _flatten_header(columns: pd.Index) -> list[str]:
    flattened: list[str] = []
    seen: dict[str, int] = {}
    for column in columns:
        if isinstance(column, tuple):
            parts = [
                str(part).strip()
                for part in column
                if pd.notna(part) and not str(part).startswith("Unnamed:")
            ]
            text = " ".join(parts)
        else:
            text = "" if pd.isna(column) else str(column).strip()
        text = text or "未命名列"
        count = seen.get(text, 0)
        seen[text] = count + 1
        flattened.append(f"{text}_{count + 1}" if count else text)
    return flattened


def _sheet_score(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    columns_text = " ".join(str(column) for column in frame.columns)
    hits = sum(1 for hint in HEADER_HINTS if hint in columns_text)
    code_col = find_column(list(frame.columns), ALIASES["代码"])
    name_col = find_column(list(frame.columns), ALIASES["名称"])
    if code_col:
        hits += int(frame[code_col].map(clean_code).str.len().eq(6).sum())
    if name_col:
        hits += int(frame[name_col].notna().sum() > 0)
    return hits


def _candidate_headers(raw: bytes | str | Path | BinaryIO, suffix: str, sheet_name: str | int | None = 0) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    for header in (0, 1, 2, 3, 4, [0, 1]):
        try:
            if suffix in {".xlsx", ".xls"}:
                frame = pd.read_excel(raw, sheet_name=sheet_name, header=header, dtype=object)
            else:
                if not isinstance(raw, bytes):
                    continue
                frame = _read_csv_bytes(raw, header=header)
        except (ValueError, OSError, UnicodeDecodeError, pd.errors.ParserError):
            continue
        frame = frame.dropna(how="all")
        frame.columns = _flatten_header(frame.columns)
        frames.append(frame)
    return frames


def read_tabular(source: str | Path | BinaryIO, filename: str | None = None) -> pd.DataFrame:
    name = filename or str(source)
    suffix = Path(name).suffix.lower()
    raw_bytes: bytes | None = None
    if hasattr(source, "read"):
        raw = source.read()
        raw_bytes = raw.encode() if isinstance(raw, str) else raw

    if suffix in {".xlsx", ".xls"}:
        excel_source: str | Path | io.BytesIO = io.BytesIO(raw_bytes) if raw_bytes is not None else source
        excel = pd.ExcelFile(excel_source)
        candidates: list[pd.DataFrame] = []
        for sheet_name in excel.sheet_names:
            sheet_source: str | Path | io.BytesIO = io.BytesIO(raw_bytes) if raw_bytes is not None else source
            candidates.extend(_candidate_headers(sheet_source, suffix, sheet_name))
        if not candidates:
            return pd.read_excel(excel_source, dtype=object)
        return max(candidates, key=_sheet_score)
    if suffix == ".csv":
        raw = raw_bytes if raw_bytes is not None else Path(source).read_bytes()
        candidates = _candidate_headers(raw, suffix)
        if candidates:
            return max(candidates, key=_sheet_score)
        return _read_csv_bytes(raw)
    raise ValueError("仅支持 .xlsx、.xls 或 .csv 文件")


def find_column(columns: list[str], aliases: list[str]) -> str | None:
    normalized = {
        str(col)
        .replace("\n", "")
        .replace("\r", "")
        .replace(" ", "")
        .replace("_", "")
        .replace("-", ""): col
        for col in columns
    }
    for alias in aliases:
        key = alias.replace("\n", "").replace(" ", "").replace("_", "").replace("-", "")
        for normalized_name, original in normalized.items():
            if normalized_name == key or normalized_name.startswith(key) or key in normalized_name:
                return original
    return None


def parse_number(value: object) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("，", "")
    if not text or text in {"--", "-", "None", "nan"}:
        return None
    multiplier = 1.0
    if text.endswith("%"):
        text = text[:-1]
    if "万" in text:
        multiplier = 10000.0
        text = text.replace("万元", "").replace("万", "")
    elif "亿" in text:
        multiplier = 100000000.0
        text = text.replace("亿元", "").replace("亿", "")
    if "/" in text:
        text = text.split("/", 1)[0]
    numeric = pd.to_numeric(text, errors="coerce")
    return float(numeric) * multiplier if pd.notna(numeric) else None


def parse_rank(value: object) -> float | None:
    parsed = parse_number(value)
    if parsed is not None:
        return parsed
    if pd.isna(value):
        return None
    text = str(value).strip()
    if "/" in text:
        return parse_number(text.split("/", 1)[0])
    return None


def normalize_imported_candidates(df: pd.DataFrame, limit: int = 30) -> pd.DataFrame:
    out = df.copy()
    out["代码"] = out["代码"].map(clean_code)
    out["名称"] = out["名称"].fillna("").astype(str).str.strip()
    out = out[out["代码"].str.len() == 6].copy()
    passed = out.apply(
        lambda row: screening_result(str(row.get("代码", "")), str(row.get("名称", "")))[0],
        axis=1,
    )
    out = out[passed].copy()
    for column in ["现价", "涨跌幅%", "成交额"]:
        out[column] = out[column].map(parse_number)
    out["成交额排名"] = out["成交额排名"].map(parse_rank)
    out["_rank_sort"] = pd.to_numeric(out["成交额排名"], errors="coerce").fillna(999999)
    out["_turnover_sort"] = pd.to_numeric(out["成交额"], errors="coerce").fillna(-1)
    out = (
        out.sort_values(["_rank_sort", "_turnover_sort"], ascending=[True, False], kind="stable")
        .drop_duplicates("代码", keep="first")
        .head(limit)
        .drop(columns=["_rank_sort", "_turnover_sort"])
        .copy()
    )
    out["成交额排名"] = range(1, len(out) + 1)
    out["上市板块"] = out["上市板块"].fillna("主板").replace("", "主板")
    return out.reset_index(drop=True)


def imported_codes_summary(raw: pd.DataFrame) -> dict[str, int]:
    source = find_column(list(raw.columns), ALIASES["代码"])
    if not source:
        return {"rawRows": int(len(raw)), "codeRows": 0, "mainBoardRows": 0}
    codes = raw[source].map(clean_code)
    code_rows = int(codes.str.len().eq(6).sum())
    names_source = find_column(list(raw.columns), ALIASES["名称"])
    names = raw[names_source].fillna("").astype(str) if names_source else pd.Series([""] * len(raw))
    main_board_rows = 0
    for code, name in zip(codes, names):
        if screening_result(code, name)[0]:
            main_board_rows += 1
    return {"rawRows": int(len(raw)), "codeRows": code_rows, "mainBoardRows": main_board_rows}


def archive_import_file(content: bytes, filename: str) -> Path:
    ensure_data_dir()
    suffix = Path(filename).suffix.lower() or ".dat"
    stem = Path(filename).stem or "import"
    safe_stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in stem)[:80]
    stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y%m%d_%H%M%S")
    target = DATA_DIR / "raw" / "stock_pool" / f"{stamp}_{safe_stem}{suffix}"
    target.write_bytes(content)
    return target


def standardize_candidates(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.copy()
    mapped: dict[str, pd.Series] = {}
    base_cols = ["代码", "名称", "现价", "涨跌幅%", "成交额", "成交额排名", "上市板块"]
    for target in base_cols:
        source = find_column(list(raw.columns), ALIASES.get(target, [target]))
        mapped[target] = raw[source] if source else pd.Series([pd.NA] * len(raw))
    df = pd.DataFrame(mapped)
    df = normalize_imported_candidates(df)
    df["状态"] = "初筛通过"
    df["分组"] = "初筛"
    df["流程阶段"] = "初筛通过"
    df["pool_rank_at_generation"] = df["成交额排名"]
    df["is_pool_locked"] = True
    df["is_pinned"] = False

    # Initialize all watchlist columns
    for col in WATCHLIST_COLUMNS:
        if col not in df:
            if col in {"MA5向上", "放量跌破MA5", "is_pool_locked", "is_pinned"}:
                df[col] = False
            else:
                df[col] = pd.NA

    return df[WATCHLIST_COLUMNS].drop_duplicates("代码", keep="first").reset_index(drop=True)


def assign_pool_batch(
    df: pd.DataFrame,
    source: str,
    generated_at: str | None = None,
    batch_id: str | None = None,
    locked: bool = True,
) -> pd.DataFrame:
    """Stamp a newly generated/imported pool with immutable batch metadata."""
    out = df.copy()
    stamp = generated_at or pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M:%S")
    safe_source = str(source or "未知来源")
    if not batch_id:
        compact_stamp = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y%m%d_%H%M%S")
        batch_id = f"{compact_stamp}_{safe_source}"
    out["pool_batch_id"] = batch_id
    out["pool_source"] = safe_source
    out["pool_generated_at"] = stamp
    rank_source = out["成交额排名"] if "成交额排名" in out else pd.Series([pd.NA] * len(out), index=out.index)
    out["pool_rank_at_generation"] = pd.to_numeric(
        rank_source,
        errors="coerce",
    ).fillna(pd.Series(range(1, len(out) + 1), index=out.index))
    out["is_pool_locked"] = locked
    if "is_pinned" not in out:
        out["is_pinned"] = False
    return out


def standardize_import_file(content: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, int]]:
    raw = read_tabular(io.BytesIO(content), filename)
    summary = imported_codes_summary(raw)
    frame = standardize_candidates(raw)
    summary["imported"] = int(len(frame))
    return frame, summary


def load_watchlist() -> pd.DataFrame:
    ensure_data_dir()
    if WATCHLIST_FILE.exists():
        try:
            df = pd.read_csv(WATCHLIST_FILE, dtype={"代码": str}, encoding="utf-8-sig")
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
            backup_file(WATCHLIST_FILE, label="bad")
            df = empty_frame(WATCHLIST_COLUMNS)
    elif SOURCE_FILE.exists():
        df = standardize_candidates(read_tabular(SOURCE_FILE))
        save_watchlist(df)
    else:
        df = empty_frame(WATCHLIST_COLUMNS)
    for column in WATCHLIST_COLUMNS:
        if column not in df:
            if column in {"MA5向上", "放量跌破MA5", "is_pool_locked", "is_pinned"}:
                df[column] = False
            else:
                df[column] = pd.NA
    df["代码"] = df["代码"].map(clean_code)
    status_source = df["状态"].replace("", pd.NA)
    group_source = df["分组"].replace("", pd.NA)
    stage_source = df["流程阶段"].replace("", pd.NA).fillna(status_source).fillna(group_source)
    df["流程阶段"] = stage_source.map(normalize_watchlist_stage)
    df["状态"] = df["流程阶段"]
    df["分组"] = df["流程阶段"].map(stage_to_group)
    rank = pd.to_numeric(df.get("成交额排名"), errors="coerce")
    generation_rank = pd.to_numeric(df.get("pool_rank_at_generation"), errors="coerce")
    turnover = pd.to_numeric(df.get("成交额"), errors="coerce")
    df["_rank_sort"] = generation_rank.fillna(rank).fillna(999999)
    df["_turnover_sort"] = turnover.fillna(-1)
    df = (
        df.sort_values(["_rank_sort", "_turnover_sort"], ascending=[True, False], kind="stable")
        .drop(columns=["_rank_sort", "_turnover_sort"])
        .copy()
    )
    return df[WATCHLIST_COLUMNS]


def save_watchlist(df: pd.DataFrame) -> None:
    ensure_data_dir()
    out = df.copy()
    for column in WATCHLIST_COLUMNS:
        if column not in out:
            if column in {"MA5向上", "放量跌破MA5", "is_pool_locked", "is_pinned"}:
                out[column] = False
            else:
                out[column] = pd.NA
    safe_write_csv(out[WATCHLIST_COLUMNS], WATCHLIST_FILE, columns=WATCHLIST_COLUMNS)


def merge_candidates(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return incoming.copy()
    indexed = existing.set_index("代码")
    incoming_indexed = incoming.set_index("代码")
    for code, row in incoming_indexed.iterrows():
        if code in indexed.index:
            for column in ["名称", "现价", "涨跌幅%", "成交额", "成交额排名", "上市板块"]:
                if pd.notna(row.get(column)):
                    indexed.loc[code, column] = row[column]
        else:
            indexed.loc[code] = row
    return indexed.reset_index()[WATCHLIST_COLUMNS]


def enrich_watchlist(
    df: pd.DataFrame,
    available_cash: float = 10000,
    max_position_ratio: float = 1.0,
    lot_size: int = 100,
) -> pd.DataFrame:
    out = df.copy()
    out["MA5偏离率%"] = [
        ma5_deviation(price, ma5) for price, ma5 in zip(out["现价"], out["MA5"])
    ]
    out["建议动作"] = out["MA5偏离率%"].map(buy_signal)

    # Affordability
    out["一手金额"] = (pd.to_numeric(out["现价"], errors="coerce").fillna(0) * lot_size).round(2)
    out["当前本金"] = available_cash
    out["本金是否可买"] = out["一手金额"].apply(lambda x: "可以买" if x <= available_cash else "资金不足")
    out["当前可用资金"] = available_cash

    # Budget calculations
    numeric_price = pd.to_numeric(out["现价"], errors="coerce")
    max_budget = available_cash * max_position_ratio
    out["最大可买股数"] = ((max_budget / numeric_price / lot_size).fillna(0).astype(int) * lot_size)
    out["建议买入数量"] = ((max_budget / numeric_price / lot_size).fillna(0).astype(int) * lot_size)
    out["买入后剩余资金"] = available_cash - out["一手金额"]
    out["仓位占比%"] = (out["一手金额"] / available_cash * 100) if available_cash else pd.NA
    out["是否超过单笔比例"] = out["一手金额"] > max_budget

    return out


def auto_assign_groups(df: pd.DataFrame) -> pd.DataFrame:
    from src.rules import determine_group

    out = df.copy()
    for index, row in out.iterrows():
        code = str(row.get("代码", ""))
        name = str(row.get("名称", ""))
        deviation = ma5_deviation(row.get("现价"), row.get("MA5"))
        has_big_line = pd.notna(row.get("最近大阳线%")) and float(row.get("最近大阳线%", 0) or 0) >= 5
        ma5_up = pd.notna(row.get("MA5向上", False)) and str(row.get("MA5向上", False)).lower() in {"true", "1", "是"}
        has_history = pd.notna(row.get("MA5"))  # has MA5 means has history
        new_group = determine_group(
            code, name, has_history, has_big_line, ma5_up, deviation, True,
            current_group=str(row.get("状态", "")) if pd.notna(row.get("状态")) else None,
        )
        out.loc[index, "状态"] = new_group
    return out


def save_history_cache(history: pd.DataFrame) -> int:
    history_dir = DATA_DIR / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for code, group in history.groupby("代码"):
        if not code:
            continue
        group.to_csv(history_dir / f"{code}.csv", index=False, encoding="utf-8-sig")
        count += 1
    return count


def load_simple_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    ensure_data_dir()
    if not path.exists():
        return empty_frame(columns)
    try:
        df = pd.read_csv(path, dtype={"代码": str}, encoding="utf-8-sig")
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        backup_file(path, label="bad")
        return empty_frame(columns)
    for column in columns:
        if column not in df:
            df[column] = pd.NA
    if "代码" in df:
        df["代码"] = df["代码"].map(clean_code)
    return df[columns]


def save_simple_csv(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    ensure_data_dir()
    out = df.copy()
    for column in columns:
        if column not in out:
            out[column] = pd.NA
    safe_write_csv(out[columns], path, columns=columns)


def load_holdings() -> pd.DataFrame:
    return normalize_holdings(load_simple_csv(HOLDINGS_FILE, HOLDING_COLUMNS))


def save_holdings(df: pd.DataFrame) -> None:
    save_simple_csv(normalize_holdings(df), HOLDINGS_FILE, HOLDING_COLUMNS)


def normalize_holdings(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in HOLDING_COLUMNS:
        if column not in out:
            out[column] = pd.NA
    out["代码"] = out["代码"].map(clean_code)
    out["名称"] = out["名称"].fillna("").astype(str).str.strip()
    out["买入日期"] = out["买入日期"].fillna("").astype(str)
    out["备注"] = out["备注"].fillna("").astype(str)
    for column in ["买入价", "数量", "当前价", "MA5", "跌破MA5天数"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out["跌破MA5天数"] = out["跌破MA5天数"].fillna(0)
    return out[HOLDING_COLUMNS]


def load_trades() -> pd.DataFrame:
    ensure_data_dir()
    if TRADES_FILE.exists():
        try:
            df = pd.read_csv(TRADES_FILE, dtype={"代码": str}, encoding="utf-8-sig")
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
            backup_file(TRADES_FILE, label="bad")
            return empty_frame(TRADE_COLUMNS)
        return normalize_trade_records(df)
    if LEGACY_TRADES_FILE.exists():
        try:
            df = pd.read_csv(LEGACY_TRADES_FILE, dtype={"代码": str}, encoding="utf-8-sig")
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
            backup_file(LEGACY_TRADES_FILE, label="bad")
            return empty_frame(TRADE_COLUMNS)
        return normalize_trade_records(df)
    else:
        return empty_frame(TRADE_COLUMNS)


def save_trades(df: pd.DataFrame) -> None:
    save_simple_csv(normalize_trade_records(df), TRADES_FILE, TRADE_COLUMNS)


def has_value(value: object) -> bool:
    return pd.notna(value) and str(value).strip() != ""


def trade_amount(price: object, quantity: object) -> object:
    numeric_price = pd.to_numeric(price, errors="coerce")
    numeric_quantity = pd.to_numeric(quantity, errors="coerce")
    if pd.isna(numeric_price) or pd.isna(numeric_quantity):
        return pd.NA
    return round(float(numeric_price) * float(numeric_quantity), 2)


def normalize_trade_records(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return empty_frame(TRADE_COLUMNS)

    if {"类型", "日期", "价格"}.issubset(df.columns):
        out = df.copy()
    else:
        rows: list[dict[str, object]] = []
        for _, row in df.iterrows():
            base = {
                "代码": row.get("代码", ""),
                "名称": row.get("名称", ""),
                "数量": row.get("数量", pd.NA),
                "时间": row.get("时间", ""),
                "手续费": row.get("手续费", 0),
                "印花税": row.get("印花税", 0),
                "过户费": row.get("过户费", 0),
                "总费用": row.get("总费用", 0),
                "原因": row.get("买入原因", ""),
                "备注": row.get("备注", ""),
                "规则快照": row.get("规则快照", ""),
                "规则结论": row.get("规则结论", ""),
                "违规标签": row.get("违规标签", ""),
            }
            if has_value(row.get("买入日期")):
                price = row.get("买入价", pd.NA)
                rows.append({
                    **base,
                    "类型": "买入",
                    "日期": row.get("买入日期"),
                    "价格": price,
                    "金额": trade_amount(price, base["数量"]),
                    "原因": row.get("买入原因", ""),
                })
            if has_value(row.get("卖出日期")):
                price = row.get("卖出价", pd.NA)
                rows.append({
                    **base,
                    "类型": "卖出",
                    "日期": row.get("卖出日期"),
                    "价格": price,
                    "金额": trade_amount(price, base["数量"]),
                    "原因": row.get("错误类型", ""),
                })
        out = pd.DataFrame(rows, columns=TRADE_COLUMNS)

    for column in TRADE_COLUMNS:
        if column not in out:
            out[column] = pd.NA
    out["代码"] = out["代码"].map(clean_code)
    out["名称"] = out["名称"].fillna("").astype(str).str.strip()
    out["类型"] = out["类型"].where(out["类型"].isin(["买入", "卖出"]), "买入")
    out["日期"] = out["日期"].fillna("").astype(str)
    out["时间"] = out["时间"].fillna("").astype(str)
    out["原因"] = out["原因"].fillna("").astype(str)
    out["备注"] = out["备注"].fillna("").astype(str)
    out["规则快照"] = out["规则快照"].fillna("").astype(str)
    out["规则结论"] = out["规则结论"].fillna("").astype(str)
    out["违规标签"] = out["违规标签"].fillna("").astype(str)
    for column in ["价格", "数量", "金额", "手续费", "印花税", "过户费", "总费用"]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0)
    out["金额"] = out["金额"].where(out["金额"] > 0, out["价格"] * out["数量"])
    out.loc[out["类型"] == "买入", "印花税"] = 0.0
    calculated_total_fee = out["手续费"] + out["印花税"] + out["过户费"]
    out["总费用"] = out["总费用"].where(out["总费用"] > 0, calculated_total_fee)
    return out[TRADE_COLUMNS]


def import_history(raw: pd.DataFrame) -> pd.DataFrame:
    mapped = {}
    for target in ["日期", "代码", "名称", "开盘", "最高", "最低", "收盘", "成交量"]:
        source = find_column(list(raw.columns), ALIASES.get(target, [target]))
        mapped[target] = raw[source] if source else pd.Series([pd.NA] * len(raw))
    history = pd.DataFrame(mapped)
    history["代码"] = history["代码"].map(clean_code)
    history["日期"] = pd.to_datetime(history["日期"], errors="coerce")
    for column in ["开盘", "最高", "最低", "收盘", "成交量"]:
        history[column] = pd.to_numeric(history[column], errors="coerce")
    history = history.dropna(subset=["日期", "代码", "收盘"]).sort_values(["代码", "日期"])
    for window in (5, 10, 20):
        history[f"MA{window}"] = history.groupby("代码")["收盘"].transform(
            lambda values: values.rolling(window).mean()
        )
    history["前一日MA5"] = history.groupby("代码")["MA5"].shift(1)
    history["MA5向上"] = history["MA5"] > history["前一日MA5"]
    history["单日涨幅%"] = history.groupby("代码")["收盘"].pct_change() * 100
    return history


def apply_latest_history(watchlist: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return watchlist
    latest = history.groupby("代码", as_index=False).tail(1).set_index("代码")
    out = watchlist.set_index("代码").copy()
    for code in out.index.intersection(latest.index):
        row = latest.loc[code]
        out.loc[code, "现价"] = row["收盘"]
        out.loc[code, "MA5"] = row["MA5"]
        out.loc[code, "MA10"] = row["MA10"]
        out.loc[code, "MA20"] = row["MA20"]
        out.loc[code, "MA5向上"] = bool(row["MA5向上"])
        max_up = recent_big_candle_pct(history[history["代码"] == code])
        out.loc[code, "最近大阳线%"] = max_up if max_up is not None else pd.NA
    return out.reset_index()[WATCHLIST_COLUMNS]
