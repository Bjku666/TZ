from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import market, portfolio, review, rules, settings, trades, watchlist
from backend.storage.sqlite_store import init_db
from src.data import ensure_data_dir

APP_NAME = "强势回踩短线交易纪律系统 API"
APP_VERSION = "0.1.4"
API_CONTRACT_VERSION = "trade-link-v8"
BUILD_TIME = os.environ.get("TZ_BUILD_TIME") or datetime.now(timezone.utc).isoformat()


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            timeout=1,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def create_app() -> FastAPI:
    ensure_data_dir()
    init_db()
    app = FastAPI(title=APP_NAME, version=APP_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(settings.router)
    app.include_router(watchlist.router)
    app.include_router(market.router)
    app.include_router(trades.router)
    app.include_router(portfolio.router)
    app.include_router(review.router)
    app.include_router(rules.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "version": APP_VERSION,
            "contract": API_CONTRACT_VERSION,
            "gitCommit": _git_commit(),
            "buildTime": BUILD_TIME,
            "serverTime": datetime.now().astimezone().isoformat(),
            "timezone": "Asia/Shanghai",
        }

    return app


app = create_app()
