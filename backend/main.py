from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.workspace import router as workspace_router
from backend.storage.account_store import init_account_storage

APP_VERSION = "3.0.0"
API_CONTRACT = "account-workspace-v3"


def create_app() -> FastAPI:
    init_account_storage()
    app = FastAPI(title="TZ 五日线回踩交易纪律工作台", version=APP_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(workspace_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "version": APP_VERSION,
            "contract": API_CONTRACT,
            "serverTime": datetime.now(timezone.utc).isoformat(),
        }

    return app


app = create_app()
