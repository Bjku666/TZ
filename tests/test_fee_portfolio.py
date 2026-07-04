from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from backend.main import create_app
from backend.services import portfolio_service
from src.data import HOLDING_COLUMNS, TRADE_COLUMNS, WATCHLIST_COLUMNS
from src.portfolio import account_state_from_trades, build_positions_from_trades, calculate_trade_fees
from src.settings import mode_fee_settings, normalize_settings


def _trade_row(
    code: str,
    name: str,
    side: str,
    trade_date: str,
    price: float,
    quantity: int = 100,
    total_fee: float = 0.0,
) -> dict[str, object]:
    amount = round(price * quantity, 2)
    return {
        "账户模式": "模拟训练",
        "代码": code,
        "名称": name,
        "类型": side,
        "日期": trade_date,
        "时间": "14:50:00",
        "价格": price,
        "数量": quantity,
        "金额": amount,
        "手续费": 0.0,
        "印花税": 0.0,
        "过户费": 0.0,
        "总费用": total_fee,
        "原因": "测试",
        "备注": "",
        "规则快照": "{}",
        "规则结论": "符合规则",
        "违规标签": "[]",
    }


def _acceptance_trades() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _trade_row("600460", "士兰微", "买入", "2026-07-02", 50.0),
            _trade_row("600460", "士兰微", "卖出", "2026-07-03", 48.69),
            _trade_row("600176", "中国巨石", "买入", "2026-07-03", 71.45),
        ],
        columns=TRADE_COLUMNS,
    )


def _watchlist(china_jushi_price: float = 70.9) -> pd.DataFrame:
    rows = pd.DataFrame(
        [
            {"代码": "600460", "名称": "士兰微", "现价": 48.69, "MA5": 50.0},
            {"代码": "600176", "名称": "中国巨石", "现价": china_jushi_price, "MA5": 70.0},
        ]
    )
    for column in WATCHLIST_COLUMNS:
        if column not in rows:
            rows[column] = pd.NA
    return rows[WATCHLIST_COLUMNS]


class FeePortfolioTests(TestCase):
    def test_recalculate_fees_route_is_mounted_as_post(self) -> None:
        schema = create_app().openapi()

        self.assertIn("/api/trades/recalculate-fees", schema["paths"])
        self.assertIn("post", schema["paths"]["/api/trades/recalculate-fees"])

    def test_simulation_zero_fee_acceptance_account_assets(self) -> None:
        trades = _acceptance_trades()
        positions = build_positions_from_trades(
            trades,
            _watchlist(),
            pd.DataFrame(columns=HOLDING_COLUMNS),
            as_of_date="2026-07-03",
        )
        state = account_state_from_trades(trades, positions, 10000, "模拟训练")

        self.assertEqual(round(float(state["当前现金"]), 2), 2724.00)
        self.assertEqual(round(float(state["持仓市值"]), 2), 7090.00)
        self.assertEqual(round(float(state["当前总资产"]), 2), 9814.00)
        self.assertEqual(round(float(state["总盈亏"]), 2), -186.00)
        self.assertEqual(round(float(state["总收益率%"]), 2), -1.86)

    def test_real_a_share_fee_calculation(self) -> None:
        settings = {
            "commission_rate": 0.00025,
            "min_commission": 5.0,
            "stamp_tax_rate": 0.0005,
            "transfer_fee_rate": 0.00001,
        }

        buy_fees = calculate_trade_fees("买入", 10, 1000, settings)
        sell_fees = calculate_trade_fees("卖出", 10, 1000, settings)

        self.assertEqual(buy_fees["commission"], 5.00)
        self.assertEqual(buy_fees["stamp_tax"], 0.00)
        self.assertEqual(buy_fees["transfer_fee"], 0.10)
        self.assertEqual(buy_fees["total_fee"], 5.10)
        self.assertEqual(sell_fees["commission"], 5.00)
        self.assertEqual(sell_fees["stamp_tax"], 5.00)
        self.assertEqual(sell_fees["transfer_fee"], 0.10)
        self.assertEqual(sell_fees["total_fee"], 10.10)

    def test_simulation_defaults_zero_but_saved_simulation_fees_are_editable(self) -> None:
        defaults = normalize_settings({})
        default_fees = mode_fee_settings(defaults, "simulation")

        edited = normalize_settings(
            {
                "simulation_fee_profile": "real_a_share",
                "simulation_commission_rate": 0.0003,
                "simulation_min_commission": 5.0,
                "simulation_stamp_tax_rate": 0.0005,
                "simulation_transfer_fee_rate": 0.00001,
            }
        )
        edited_fees = mode_fee_settings(edited, "simulation")

        self.assertEqual(default_fees["commission_rate"], 0.00031)
        self.assertEqual(default_fees["min_commission"], 0)
        self.assertEqual(default_fees["stamp_tax_rate"], 0.0005)
        self.assertEqual(default_fees["transfer_fee_rate"], 0.00001)
        self.assertEqual(edited_fees["commission_rate"], 0.0003)
        self.assertEqual(edited_fees["min_commission"], 5.0)
        self.assertEqual(edited_fees["stamp_tax_rate"], 0.0005)
        self.assertEqual(edited_fees["transfer_fee_rate"], 0.00001)

    def test_portfolio_snapshot_defaults_to_last_trade_date_and_matches_ths_today_pnl(self) -> None:
        trades = _acceptance_trades()
        watchlist = _watchlist(china_jushi_price=72.1872)
        shilan_history = pd.DataFrame(
            [
                {"日期": "2026-07-01", "收盘": 50.0},
                {"日期": "2026-07-02", "收盘": 51.8499},
            ]
        )

        with (
            patch.object(portfolio_service.trade_repository, "load_trade_frame", return_value=trades),
            patch.object(portfolio_service, "load_watchlist", return_value=watchlist),
            patch.object(portfolio_service, "load_holdings", return_value=pd.DataFrame(columns=HOLDING_COLUMNS)),
            patch.object(portfolio_service, "load_quote_snapshot", return_value=pd.DataFrame()),
            patch.object(portfolio_service, "load_last_refresh", return_value={}),
            patch.object(portfolio_service, "load_cached_history", return_value=shilan_history),
            patch.object(portfolio_service, "get_settings", return_value={"thsReconciliation": {"enabled": False}}),
            patch.object(
                portfolio_service,
                "_reference_from_quote_archives",
                return_value=(pd.Timestamp("2026-07-02 19:55:57"), 50.5),
            ),
            patch.object(portfolio_service, "initial_cash", return_value=10000),
        ):
            snapshot = portfolio_service.portfolio_snapshot("simulation")

        self.assertEqual(snapshot["asOfDate"], "2026-07-03")
        self.assertEqual(snapshot["accountState"]["asOfDate"], "2026-07-03")
        self.assertEqual(snapshot["accountState"]["availableCash"], 2724.00)
        self.assertEqual(snapshot["accountState"]["holdingValue"], 7218.72)
        self.assertEqual(snapshot["accountState"]["totalPnL"], -57.28)
        self.assertEqual(snapshot["accountState"]["todayPnL"], -242.27)

    def test_today_pnl_prefers_newer_quote_archive_over_stale_history(self) -> None:
        trades = _acceptance_trades()
        stale_history = pd.DataFrame(
            [
                {"日期": "2026-06-30", "收盘": 54.66},
                {"日期": "2026-07-01", "收盘": 53.15},
            ]
        )

        with (
            patch.object(portfolio_service.trade_repository, "load_trade_frame", return_value=trades),
            patch.object(portfolio_service, "load_watchlist", return_value=_watchlist(china_jushi_price=70.9)),
            patch.object(portfolio_service, "load_holdings", return_value=pd.DataFrame(columns=HOLDING_COLUMNS)),
            patch.object(portfolio_service, "load_quote_snapshot", return_value=pd.DataFrame()),
            patch.object(portfolio_service, "load_last_refresh", return_value={}),
            patch.object(portfolio_service, "load_cached_history", return_value=stale_history),
            patch.object(portfolio_service, "get_settings", return_value={"thsReconciliation": {"enabled": False}}),
            patch.object(
                portfolio_service,
                "_reference_from_quote_archives",
                return_value=(pd.Timestamp("2026-07-02 19:55:57"), 50.5),
            ),
            patch.object(portfolio_service, "initial_cash", return_value=10000),
        ):
            snapshot = portfolio_service.portfolio_snapshot("simulation", as_of_date="2026-07-03")

        self.assertEqual(snapshot["accountState"]["totalPnL"], -186.00)
        self.assertEqual(snapshot["accountState"]["todayPnL"], -236.00)

    def test_ths_reconciliation_converts_broker_capital_to_discipline_capital(self) -> None:
        trades = _acceptance_trades()
        reconciliation_settings = {
            "thsReconciliation": {
                "enabled": True,
                "accountCapital": 200000,
                "totalAssets": 199806.13,
                "availableCash": 192716.13,
                "holdingValue": 7090,
                "holdingPnL": -57.28,
                "todayPnL": -242.27,
            }
        }

        with (
            patch.object(portfolio_service.trade_repository, "load_trade_frame", return_value=trades),
            patch.object(portfolio_service, "load_watchlist", return_value=_watchlist()),
            patch.object(portfolio_service, "load_holdings", return_value=pd.DataFrame(columns=HOLDING_COLUMNS)),
            patch.object(portfolio_service, "load_quote_snapshot", return_value=pd.DataFrame()),
            patch.object(portfolio_service, "load_last_refresh", return_value={}),
            patch.object(portfolio_service, "load_cached_history", return_value=pd.DataFrame()),
            patch.object(portfolio_service, "initial_cash", return_value=10000),
            patch.object(portfolio_service, "get_settings", return_value=reconciliation_settings),
        ):
            snapshot = portfolio_service.portfolio_snapshot("simulation")

        account = snapshot["accountState"]
        self.assertEqual(snapshot["asOfDate"], "2026-07-03")
        self.assertEqual(account["totalAssets"], 9806.13)
        self.assertEqual(account["holdingValue"], 7090.00)
        self.assertEqual(account["availableCash"], 2716.13)
        self.assertEqual(account["holdingPnL"], -57.28)
        self.assertEqual(account["todayPnL"], -242.27)
        self.assertEqual(account["accountPnL"], -193.87)
        self.assertEqual(account["totalPnL"], -193.87)
        self.assertEqual(account["totalReturnPct"], -1.94)
        position = snapshot["positions"][0]
        self.assertEqual(position["avgCost"], 71.473)
        self.assertEqual(position["currentPrice"], 70.900)
        self.assertEqual(position["marketValue"], 7090.00)
        self.assertEqual(position["floatingPnL"], -57.28)
