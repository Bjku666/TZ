from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from src.rules import GROUPS, affordability, buy_signal, clean_code, ma5_deviation, screening_result

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
    "上市板块",
    "状态",
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
    "代码": ["代码", "股票代码", "证券代码"],
    "名称": ["名称", "股票简称", "股票名称", "证券简称"],
    "现价": ["现价", "现价(元)", "最新价", "收盘价"],
    "涨跌幅%": ["涨跌幅%", "涨跌幅(%)", "涨跌幅"],
    "成交额": ["成交额", "成交额(元)", "总金额"],
    "成交额排名": ["成交额排名名次", "成交额排名", "排名"],
    "上市板块": ["上市板块", "板块"],
    "日期": ["日期", "交易日期", "时间"],
    "开盘": ["开盘", "开盘价"],
    "最高": ["最高", "最高价"],
    "最低": ["最低", "最低价"],
    "收盘": ["收盘", "收盘价", "现价"],
    "成交量": ["成交量", "总手"],
}

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
]


def ensure_data_dir() -> None:
    for d in REQUIRED_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def read_tabular(source: str | Path | BinaryIO, filename: str | None = None) -> pd.DataFrame:
    name = filename or str(source)
    suffix = Path(name).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(source, dtype=object)
    if suffix == ".csv":
        raw = source.read() if hasattr(source, "read") else Path(source).read_bytes()
        if isinstance(raw, str):
            raw = raw.encode()
        for encoding in ("utf-8-sig", "gb18030", "gbk"):
            try:
                return pd.read_csv(io.BytesIO(raw), encoding=encoding, dtype=object)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(io.BytesIO(raw), dtype=object)
    raise ValueError("仅支持 .xlsx、.xls 或 .csv 文件")


def find_column(columns: list[str], aliases: list[str]) -> str | None:
    normalized = {str(col).replace("\n", "").replace(" ", ""): col for col in columns}
    for alias in aliases:
        key = alias.replace("\n", "").replace(" ", "")
        for normalized_name, original in normalized.items():
            if normalized_name == key or normalized_name.startswith(key):
                return original
    return None


def standardize_candidates(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.copy()
    mapped: dict[str, pd.Series] = {}
    base_cols = ["代码", "名称", "现价", "涨跌幅%", "成交额", "成交额排名", "上市板块"]
    for target in base_cols:
        source = find_column(list(raw.columns), ALIASES.get(target, [target]))
        mapped[target] = raw[source] if source else pd.Series([pd.NA] * len(raw))
    df = pd.DataFrame(mapped)
    df["代码"] = df["代码"].map(clean_code)
    df["名称"] = df["名称"].fillna("").astype(str).str.strip()
    df = df[df["代码"].str.len() == 6].copy()
    for column in ["现价", "涨跌幅%", "成交额", "成交额排名"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["状态"] = "初筛通过"

    # Initialize all watchlist columns
    for col in WATCHLIST_COLUMNS:
        if col not in df:
            if col in {"MA5向上", "放量跌破MA5"}:
                df[col] = False
            else:
                df[col] = pd.NA

    return df[WATCHLIST_COLUMNS].drop_duplicates("代码", keep="first").reset_index(drop=True)


def load_watchlist() -> pd.DataFrame:
    ensure_data_dir()
    if WATCHLIST_FILE.exists():
        df = pd.read_csv(WATCHLIST_FILE, dtype={"代码": str}, encoding="utf-8-sig")
    elif SOURCE_FILE.exists():
        df = standardize_candidates(read_tabular(SOURCE_FILE))
        save_watchlist(df)
    else:
        df = empty_frame(WATCHLIST_COLUMNS)
    for column in WATCHLIST_COLUMNS:
        if column not in df:
            if column in {"MA5向上", "放量跌破MA5"}:
                df[column] = False
            else:
                df[column] = pd.NA
    df["代码"] = df["代码"].map(clean_code)
    df["状态"] = df["状态"].replace({
        "初筛": "初筛通过",
        "观察": "重点观察",
        "待买": "待买观察",
        "持仓": "重点观察",
        "待买观察": "待买观察",
    })
    df["状态"] = df["状态"].where(df["状态"].isin(GROUPS), "初筛通过")
    rank = pd.to_numeric(df.get("成交额排名"), errors="coerce")
    turnover = pd.to_numeric(df.get("成交额"), errors="coerce")
    df["_rank_sort"] = rank.fillna(999999)
    df["_turnover_sort"] = turnover.fillna(-1)
    df = (
        df.sort_values(["_rank_sort", "_turnover_sort"], ascending=[True, False])
        .head(30)
        .drop(columns=["_rank_sort", "_turnover_sort"])
        .copy()
    )
    return df[WATCHLIST_COLUMNS]


def save_watchlist(df: pd.DataFrame) -> None:
    ensure_data_dir()
    out = df.copy()
    for column in WATCHLIST_COLUMNS:
        if column not in out:
            if column in {"MA5向上", "放量跌破MA5"}:
                out[column] = False
            else:
                out[column] = pd.NA
    out[WATCHLIST_COLUMNS].to_csv(WATCHLIST_FILE, index=False, encoding="utf-8-sig")


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
    from src.rules import can_be_watchlist_candidate, determine_group

    out = df.copy()
    for index, row in out.iterrows():
        code = str(row.get("代码", ""))
        name = str(row.get("名称", ""))
        deviation = ma5_deviation(row.get("现价"), row.get("MA5"))
        has_big_line = pd.notna(row.get("最近大阳线%")) and float(row.get("最近大阳线%", 0) or 0) >= 5
        ma5_up = pd.notna(row.get("MA5向上", False)) and str(row.get("MA5向上", False)).lower() in {"true", "1", "是"}
        has_history = pd.notna(row.get("MA5"))  # has MA5 means has history
        affordable = str(row.get("本金是否可买", "")) == "可以买"

        new_group = determine_group(
            code, name, has_history, has_big_line, ma5_up, deviation, affordable,
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
    df = pd.read_csv(path, dtype={"代码": str}, encoding="utf-8-sig")
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
    out[columns].to_csv(path, index=False, encoding="utf-8-sig")


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
        df = pd.read_csv(TRADES_FILE, dtype={"代码": str}, encoding="utf-8-sig")
        return normalize_trade_records(df)
    if LEGACY_TRADES_FILE.exists():
        df = pd.read_csv(LEGACY_TRADES_FILE, dtype={"代码": str}, encoding="utf-8-sig")
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
    recent_big = history.groupby("代码")["单日涨幅%"].max()
    out = watchlist.set_index("代码").copy()
    for code in out.index.intersection(latest.index):
        row = latest.loc[code]
        out.loc[code, "现价"] = row["收盘"]
        out.loc[code, "MA5"] = row["MA5"]
        out.loc[code, "MA10"] = row["MA10"]
        out.loc[code, "MA20"] = row["MA20"]
        out.loc[code, "MA5向上"] = bool(row["MA5向上"])
        out.loc[code, "最近大阳线%"] = recent_big.get(code, pd.NA)
    return out.reset_index()[WATCHLIST_COLUMNS]
