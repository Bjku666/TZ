from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

from src.data import ROOT, clean_code

DATA_DIR = ROOT / "data"
ACCOUNT_FILE = DATA_DIR / "account_snapshots.csv"
POSITION_SNAPSHOT_FILE = DATA_DIR / "position_snapshots.csv"
TRADE_LOG_FILE = DATA_DIR / "trade_log.csv"

ACCOUNT_COLUMNS = [
    "snapshot_date",
    "account_mode",
    "initial_capital",
    "total_assets",
    "available_cash",
    "market_value",
    "daily_pnl",
    "total_pnl",
    "withdrawable_cash",
    "frozen_cash",
    "note",
]

POSITION_COLUMNS = [
    "snapshot_date",
    "account_mode",
    "code",
    "name",
    "position_qty",
    "available_qty",
    "cost_price",
    "current_price",
    "market_value",
    "floating_pnl",
    "floating_pnl_pct",
]

TRADE_FLOW_COLUMNS = [
    "trade_date",
    "trade_time",
    "account_mode",
    "code",
    "name",
    "side",
    "price",
    "quantity",
    "amount",
    "fee",
    "tax",
    "transfer_fee",
    "note",
]

ACCOUNT_ALIASES = {
    "snapshot_date": ["快照日期", "日期", "交易日期"],
    "account_mode": ["账户模式", "账户类型"],
    "initial_capital": ["初始本金", "本金"],
    "total_assets": ["总资产", "资产总值", "账户总资产"],
    "available_cash": ["可用资金", "可用金额", "资金余额"],
    "market_value": ["持仓市值", "股票市值", "证券市值"],
    "daily_pnl": ["当日盈亏", "今日盈亏"],
    "total_pnl": ["总盈亏", "累计盈亏"],
    "withdrawable_cash": ["可取金额", "可取资金"],
    "frozen_cash": ["冻结金额", "冻结资金"],
    "note": ["备注", "说明"],
}

POSITION_ALIASES = {
    "snapshot_date": ["快照日期", "日期"],
    "account_mode": ["账户模式", "账户类型"],
    "code": ["股票代码", "代码", "证券代码"],
    "name": ["股票名称", "名称", "证券名称", "证券简称"],
    "position_qty": ["持仓数量", "数量", "当前持仓", "证券数量"],
    "available_qty": ["可卖数量", "可用股份", "股份可用"],
    "cost_price": ["成本价", "持仓成本", "成本价格"],
    "current_price": ["当前价", "现价", "最新价", "市价"],
    "market_value": ["持仓市值", "市值", "证券市值"],
    "floating_pnl": ["浮动盈亏", "盈亏", "参考盈亏"],
    "floating_pnl_pct": ["盈亏比例", "收益率", "盈亏比"],
}

TRADE_ALIASES = {
    "trade_date": ["交易日期", "成交日期", "日期"],
    "trade_time": ["交易时间", "成交时间", "时间"],
    "account_mode": ["账户模式", "账户类型"],
    "code": ["股票代码", "代码", "证券代码"],
    "name": ["股票名称", "名称", "证券名称", "证券简称"],
    "side": ["买卖方向", "操作", "业务名称"],
    "price": ["成交价格", "成交价", "价格"],
    "quantity": ["成交数量", "数量", "成交股数"],
    "amount": ["成交金额", "发生金额", "金额"],
    "fee": ["手续费", "佣金"],
    "tax": ["印花税"],
    "transfer_fee": ["过户费"],
    "note": ["备注", "说明"],
}


def _normalized_name(value: object) -> str:
    return re.sub(r"[\s\n（）()_%％]", "", str(value)).lower()


def _find_column(columns: list[object], aliases: list[str]) -> object | None:
    normalized = {_normalized_name(column): column for column in columns}
    for alias in aliases:
        key = _normalized_name(alias)
        for candidate, original in normalized.items():
            if candidate == key or candidate.startswith(key):
                return original
    return None


def _normalize_frame(
    raw: pd.DataFrame,
    columns: list[str],
    aliases: dict[str, list[str]],
) -> pd.DataFrame:
    result: dict[str, pd.Series] = {}
    for target in columns:
        source = _find_column(list(raw.columns), aliases.get(target, [target]))
        result[target] = raw[source] if source is not None else pd.Series([pd.NA] * len(raw))
    return pd.DataFrame(result)


def archive_upload(file_bytes: bytes, filename: str, category: str) -> Path:
    """Save an uploaded file to the raw archive."""
    from src.data import ensure_data_dir, DATA_DIR
    raw_dir = DATA_DIR / "raw" / category
    raw_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    prefix = date.today().isoformat()
    if re.match(r"^\d{4}-\d{2}-\d{2}_", safe_name):
        archived_name = safe_name
    else:
        archived_name = f"{prefix}_{safe_name}"
    path = raw_dir / archived_name
    path.write_bytes(file_bytes)
    return path


def load_account_snapshots() -> pd.DataFrame:
    if not ACCOUNT_FILE.exists():
        return pd.DataFrame(columns=ACCOUNT_COLUMNS)
    frame = pd.read_csv(ACCOUNT_FILE)
    for column in ACCOUNT_COLUMNS:
        if column not in frame:
            frame[column] = pd.NA
    return frame[ACCOUNT_COLUMNS]


def save_account_snapshots(frame: pd.DataFrame) -> None:
    ACCOUNT_FILE.parent.mkdir(parents=True, exist_ok=True)
    frame[ACCOUNT_COLUMNS].to_csv(ACCOUNT_FILE, index=False, encoding="utf-8-sig")


def append_account_snapshots(frame: pd.DataFrame) -> None:
    existing = load_account_snapshots()
    combined = pd.concat([existing, frame[ACCOUNT_COLUMNS]], ignore_index=True)
    combined["snapshot_date"] = pd.to_datetime(combined["snapshot_date"], errors="coerce")
    combined = combined.dropna(subset=["snapshot_date", "account_mode"])
    combined = combined.sort_values("snapshot_date").drop_duplicates(
        ["snapshot_date", "account_mode"], keep="last"
    )
    combined["snapshot_date"] = combined["snapshot_date"].dt.date.astype(str)
    save_account_snapshots(combined)


def normalize_account_snapshot(
    raw: pd.DataFrame,
    account_mode: str,
    initial_capital: float,
) -> pd.DataFrame:
    frame = _normalize_frame(raw, ACCOUNT_COLUMNS, ACCOUNT_ALIASES)
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"], errors="coerce").fillna(
        pd.Timestamp.today().normalize()
    )
    frame["account_mode"] = frame["account_mode"].where(
        frame["account_mode"].isin(["模拟训练", "实盘记录"]), account_mode
    )
    frame["initial_capital"] = pd.to_numeric(frame["initial_capital"], errors="coerce").fillna(
        initial_capital
    )
    for column in ACCOUNT_COLUMNS[3:10]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["note"] = frame["note"].fillna("")
    frame["snapshot_date"] = frame["snapshot_date"].dt.date.astype(str)
    return frame[ACCOUNT_COLUMNS]


def latest_account_snapshot(account_mode: str) -> dict[str, object] | None:
    frame = load_account_snapshots()
    frame = frame[frame["account_mode"] == account_mode].copy()
    if frame.empty:
        return None
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"], errors="coerce")
    frame = frame.sort_values("snapshot_date")
    return frame.iloc[-1].to_dict()


def normalize_positions(raw: pd.DataFrame, account_mode: str) -> pd.DataFrame:
    frame = _normalize_frame(raw, POSITION_COLUMNS, POSITION_ALIASES)
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"], errors="coerce").fillna(
        pd.Timestamp.today().normalize()
    )
    frame["account_mode"] = frame["account_mode"].where(
        frame["account_mode"].isin(["模拟训练", "实盘记录"]), account_mode
    )
    frame["code"] = frame["code"].map(clean_code)
    frame["name"] = frame["name"].fillna("").astype(str).str.strip()
    for column in POSITION_COLUMNS[4:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[frame["code"].str.len() == 6].copy()
    frame["snapshot_date"] = frame["snapshot_date"].dt.date.astype(str)
    return frame[POSITION_COLUMNS]


def save_positions_snapshot(frame: pd.DataFrame) -> None:
    POSITION_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    frame[POSITION_COLUMNS].to_csv(POSITION_SNAPSHOT_FILE, index=False, encoding="utf-8-sig")


def load_positions_snapshot(account_mode: str | None = None) -> pd.DataFrame:
    if not POSITION_SNAPSHOT_FILE.exists():
        return pd.DataFrame(columns=POSITION_COLUMNS)
    frame = pd.read_csv(POSITION_SNAPSHOT_FILE, dtype={"code": str})
    if account_mode:
        frame = frame[frame["account_mode"] == account_mode]
    return frame


def normalize_trade_flow(raw: pd.DataFrame, account_mode: str) -> pd.DataFrame:
    frame = _normalize_frame(raw, TRADE_FLOW_COLUMNS, TRADE_ALIASES)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").fillna(
        pd.Timestamp.today().normalize()
    )
    frame["account_mode"] = frame["account_mode"].where(
        frame["account_mode"].isin(["模拟训练", "实盘记录"]), account_mode
    )
    frame["code"] = frame["code"].map(clean_code)
    frame["name"] = frame["name"].fillna("").astype(str).str.strip()
    for column in ["price", "quantity", "amount", "fee", "tax", "transfer_fee"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["trade_date"] = frame["trade_date"].dt.date.astype(str)
    frame["trade_time"] = frame["trade_time"].fillna("").astype(str)
    frame["note"] = frame["note"].fillna("")
    return frame[TRADE_FLOW_COLUMNS]


def save_trade_flow(frame: pd.DataFrame) -> None:
    TRADE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    frame[TRADE_FLOW_COLUMNS].to_csv(TRADE_LOG_FILE, index=False, encoding="utf-8-sig")
