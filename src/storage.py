from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BACKUP_DIR = DATA_DIR / "backups"
RUNTIME_DIR = DATA_DIR / "runtime"
QUOTE_SNAPSHOT_FILE = RUNTIME_DIR / "quote_snapshot.csv"
LAST_REFRESH_FILE = RUNTIME_DIR / "last_refresh.json"

QUOTE_SNAPSHOT_COLUMNS = [
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


def now_text() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")


def ensure_storage_dirs() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def backup_file(path: Path, *, label: str = "backup") -> Path | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    ensure_storage_dirs()
    try:
        relative = path.relative_to(DATA_DIR)
    except ValueError:
        relative = Path(path.name)
    stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S")
    backup_name = "__".join(relative.parts).replace("/", "__")
    target = BACKUP_DIR / f"{backup_name}.{label}.{stamp}{path.suffix}"
    shutil.copy2(path, target)
    return target


def safe_write_csv(df: pd.DataFrame, path: Path, *, columns: list[str] | None = None) -> None:
    ensure_storage_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_file(path)
    out = df.copy()
    if columns is not None:
        for column in columns:
            if column not in out:
                out[column] = pd.NA
        out = out[columns]
    tmp_path = path.with_name(f".{path.name}.tmp")
    out.to_csv(tmp_path, index=False, encoding="utf-8-sig")
    tmp_path.replace(path)


def load_quote_snapshot() -> pd.DataFrame:
    ensure_storage_dirs()
    if not QUOTE_SNAPSHOT_FILE.exists():
        return pd.DataFrame(columns=QUOTE_SNAPSHOT_COLUMNS)
    try:
        frame = pd.read_csv(QUOTE_SNAPSHOT_FILE, dtype={"代码": str}, encoding="utf-8-sig")
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        backup_file(QUOTE_SNAPSHOT_FILE, label="bad")
        return pd.DataFrame(columns=QUOTE_SNAPSHOT_COLUMNS)
    for column in QUOTE_SNAPSHOT_COLUMNS:
        if column not in frame:
            frame[column] = pd.NA
    return frame[QUOTE_SNAPSHOT_COLUMNS]


def save_quote_snapshot(quotes: pd.DataFrame, *, source: str = "", status: str = "", message: str = "") -> None:
    if quotes.empty:
        return
    ensure_storage_dirs()
    out = quotes.copy()
    refresh_time = now_text()
    for column in QUOTE_SNAPSHOT_COLUMNS:
        if column not in out:
            out[column] = pd.NA
    out["更新时间"] = out["更新时间"].fillna(refresh_time).replace("", refresh_time)
    out["来源"] = out["来源"].fillna(source).replace("", source)
    out["状态"] = out["状态"].fillna(status or "成功").replace("", status or "成功")
    safe_write_csv(out[QUOTE_SNAPSHOT_COLUMNS], QUOTE_SNAPSHOT_FILE, columns=QUOTE_SNAPSHOT_COLUMNS)
    save_last_refresh({
        "更新时间": refresh_time,
        "来源": source or str(out["来源"].dropna().iloc[0] if out["来源"].notna().any() else ""),
        "状态": status or str(out["状态"].dropna().iloc[0] if out["状态"].notna().any() else "成功"),
        "消息": message,
        "股票数": int(len(out)),
    })


def load_last_refresh() -> dict[str, object]:
    ensure_storage_dirs()
    if not LAST_REFRESH_FILE.exists():
        return {}
    try:
        return json.loads(LAST_REFRESH_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        backup_file(LAST_REFRESH_FILE, label="bad")
        return {}


def save_last_refresh(info: dict[str, object]) -> None:
    ensure_storage_dirs()
    tmp_path = LAST_REFRESH_FILE.with_name(f".{LAST_REFRESH_FILE.name}.tmp")
    tmp_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(LAST_REFRESH_FILE)
