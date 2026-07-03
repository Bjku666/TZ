from __future__ import annotations

from pathlib import Path

from src.storage import backup_file


def backup_before_write(path: Path, label: str = "api") -> Path | None:
    return backup_file(path, label=label)

