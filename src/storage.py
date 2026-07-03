from __future__ import annotations

import json
import os
import shutil
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BACKUP_DIR = DATA_DIR / "backups"
RUNTIME_DIR = DATA_DIR / "runtime"
QUOTE_SNAPSHOT_FILE = RUNTIME_DIR / "quote_snapshot.csv"
MARKET_CONTEXT_FILE = RUNTIME_DIR / "market_context.json"
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


@contextmanager
def file_write_lock(path: Path) -> Iterator[None]:
    ensure_storage_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    if fcntl is None:
        deadline = time.monotonic() + 10
        fd: int | None = None
        while fd is None:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode("utf-8"))
            except FileExistsError:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"等待文件锁超时: {lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            if fd is not None:
                os.close(fd)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
        return
    with lock_path.open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


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
    with file_write_lock(path):
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


def safe_write_text(path: Path, content: str, *, backup: bool = True) -> None:
    ensure_storage_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_write_lock(path):
        if backup:
            backup_file(path)
        tmp_path = path.with_name(f".{path.name}.tmp")
        tmp_path.write_text(content, encoding="utf-8")
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
    safe_write_text(LAST_REFRESH_FILE, json.dumps(info, ensure_ascii=False, indent=2), backup=False)


def load_market_context() -> dict[str, object]:
    ensure_storage_dirs()
    if not MARKET_CONTEXT_FILE.exists():
        return {}
    try:
        return json.loads(MARKET_CONTEXT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        backup_file(MARKET_CONTEXT_FILE, label="bad")
        return {}


def save_market_context(context: dict[str, object]) -> None:
    safe_write_text(MARKET_CONTEXT_FILE, json.dumps(context, ensure_ascii=False, indent=2), backup=False)
