from __future__ import annotations

from pathlib import Path

from src.data import DATA_DIR
from src.storage import safe_write_text

REPORT_ROOT = DATA_DIR / "reports"


def report_dir(report_type: str) -> Path:
    mapping = {
        "daily": REPORT_ROOT / "daily",
        "weekly": REPORT_ROOT / "weekly",
        "monthly": REPORT_ROOT / "monthly",
    }
    path = mapping[report_type]
    path.mkdir(parents=True, exist_ok=True)
    return path


def report_path(report_type: str, key: str) -> Path:
    safe_key = key.replace("/", "-").replace(":", "-")
    return report_dir(report_type) / f"{safe_key}.md"


def load_report_note(report_type: str, key: str) -> str:
    path = report_path(report_type, key)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def save_report_note(report_type: str, key: str, content: str) -> Path:
    path = report_path(report_type, key)
    safe_write_text(path, content)
    return path


def report_markdown(title: str, metrics: dict[str, object], note: str) -> str:
    lines = [f"# {title}", ""]
    for key, value in metrics.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## 心得", "", note.strip()])
    return "\n".join(lines).strip() + "\n"
