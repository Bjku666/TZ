from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from backend.storage import sqlite_store, trade_repository
from src.data import TRADE_COLUMNS


def _trade(trade_id: str, code: str = "600000") -> dict[str, object]:
    return {
        "id": trade_id,
        "accountMode": "模拟训练",
        "code": code,
        "name": "测试股票",
        "type": "BUY",
        "date": "2026-07-03",
        "time": "09:35:00",
        "price": 10,
        "quantity": 100,
        "amount": 1000,
        "commission": 5,
        "stampDuty": 0,
        "transferFee": 0.01,
        "totalFee": 5.01,
        "reason": "测试",
        "remark": "",
        "snapshot": {},
        "rulesConclusion": "符合规则",
        "violationTags": [],
    }


class TradeRepositoryTests(TestCase):
    def test_append_delete_and_csv_mirror_use_sqlite_primary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "app.db"
            csv_path = root / "trades" / "trade_log.csv"

            def load_csv() -> pd.DataFrame:
                if not csv_path.exists():
                    return pd.DataFrame(columns=TRADE_COLUMNS)
                return pd.read_csv(csv_path, dtype={"代码": str}, encoding="utf-8-sig")

            def save_csv(frame: pd.DataFrame) -> None:
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                frame.to_csv(csv_path, index=False, encoding="utf-8-sig")

            with (
                patch.object(sqlite_store, "DB_PATH", db_path),
                patch.object(trade_repository, "load_csv_trades", load_csv),
                patch.object(trade_repository, "save_csv_trades", save_csv),
            ):
                sqlite_store.init_db()
                trade_repository.append_api_trade("simulation", "模拟训练", _trade("T000001", "600001"))
                trade_repository.append_api_trade("simulation", "模拟训练", _trade("T000002", "600002"))

                self.assertEqual(
                    [item["code"] for item in trade_repository.list_api_trades("simulation", "模拟训练")],
                    ["600001", "600002"],
                )

                trade_repository.delete_api_trade("simulation", "模拟训练", "T000001")
                rows = trade_repository.list_api_trades("simulation", "模拟训练")

                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["id"], "T000001")
                self.assertEqual(rows[0]["code"], "600002")
                mirrored = pd.read_csv(csv_path, dtype={"代码": str}, encoding="utf-8-sig")
                self.assertEqual(mirrored.iloc[0]["代码"], "600002")
