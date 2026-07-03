from __future__ import annotations

import json
from datetime import date, time
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import src.data as _data
from src.data import (
    HOLDING_COLUMNS,
    TRADE_COLUMNS,
    WATCHLIST_COLUMNS,
    assign_pool_batch,
    ensure_data_dir,
    load_holdings,
    load_trades,
    load_watchlist,
    read_tabular,
    save_holdings,
    save_trades,
    save_watchlist,
    standardize_candidates,
)

enrich_watchlist = _data.enrich_watchlist

from src.account import (
    ACCOUNT_COLUMNS,
    append_account_snapshots,
    archive_upload,
    latest_account_snapshot,
    normalize_account_snapshot,
    normalize_positions,
    normalize_trade_flow,
    load_positions_snapshot,
    save_positions_snapshot,
    save_trade_flow,
)
from src.rules import (
    OBSERVATION_STAGES,
    PIPELINE_STAGES,
    evaluate_stock,
    holding_advice,
    ma5_deviation,
    normalize_stage,
    screening_result,
    stage_to_group,
)
from src.charts import render_kline_chart
from src.history import (
    compute_all_reminders,
    diagnose_history,
    fetch_and_cache,
    load_cached_history,
    save_history_cache as history_save_cache,
)
from src.realtime import (
    QUOTE_SOURCE_OPTIONS,
    china_now,
    fetch_auto_stock_pool,
    fetch_realtime_quotes,
    is_a_share_trading_time,
    merge_quotes_into_holdings,
    merge_quotes_into_watchlist,
)
from src.storage import load_last_refresh, load_quote_snapshot, save_quote_snapshot
from src.portfolio import (
    account_state_from_trades,
    asset_curve_from_trades,
    build_positions_from_trades,
    calculate_trade_fees,
    closed_trades_from_flow,
    max_drawdown,
    portfolio_to_legacy_holdings,
)
from src.reports import load_report_note, report_markdown, save_report_note
from src.settings import fee_prefix_for_mode, load_settings, save_settings
from src.ui_style import page_css, money_display, percent_display

APP_NAME = "强势回踩短线交易纪律系统"
APP_VERSION = "v2.1 Discipline Desk"

st.set_page_config(
    page_title=APP_NAME,
    page_icon=":material/show_chart:",
    layout="wide",
    initial_sidebar_state="auto",
)

ensure_data_dir()

# ── Auto-dismiss alert JS ──


# ── Page CSS ──
st.markdown(page_css(), unsafe_allow_html=True)


# ── Cached data loaders ──
def initial_watchlist() -> pd.DataFrame:
    return load_watchlist()


@st.cache_data(show_spinner=False)
def cached_history_diagnostics(codes: tuple[str, ...]) -> dict[str, dict[str, object]]:
    return {code: diagnose_history(code) for code in codes}


@st.cache_data(ttl=45, show_spinner=False)
def cached_realtime_quotes(
    codes: tuple[str, ...],
    source: str = "自动切换",
    refresh_token: int = 0,
) -> pd.DataFrame:
    del refresh_token
    return fetch_realtime_quotes(list(codes), source=source)


# ── Helpers ──
def number_or(value: object, default: float = 0) -> float:
    numeric = pd.to_numeric(value, errors="coerce")
    return float(numeric) if pd.notna(numeric) else float(default)


class InMemoryUpload:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def normalize_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column in out:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def prepare_holdings_view(holdings: pd.DataFrame) -> pd.DataFrame:
    display = normalize_numeric_columns(
        holdings,
        ["买入价", "数量", "当前价", "MA5", "跌破MA5天数"],
    )
    if display.empty:
        return display
    display["市值"] = display["当前价"] * display["数量"]
    display["成本"] = display["买入价"] * display["数量"]
    display["盈亏"] = display["市值"] - display["成本"]
    display["盈亏%"] = (display["盈亏"] / display["成本"] * 100).round(2)
    display["纪律建议"] = display.apply(
        lambda row: holding_advice(
            row.get("当前价"),
            row.get("MA5"),
            row.get("数量"),
            row.get("跌破MA5天数", 0),
            row.get("可卖数量", row.get("数量")),
            row.get("持仓天数"),
        ),
        axis=1,
    )
    return display


def account_summary(
    holdings: pd.DataFrame,
    initial_capital: float,
    snapshot: dict[str, object] | None = None,
) -> dict[str, float]:
    display = prepare_holdings_view(holdings)
    open_cost = float(display["成本"].sum()) if not display.empty else 0.0
    market_value = float(display["市值"].sum()) if not display.empty else 0.0
    floating_pnl = float(display["盈亏"].sum()) if not display.empty else 0.0

    snapshot_cash = pd.to_numeric(snapshot.get("available_cash") if snapshot else None, errors="coerce")
    if pd.notna(snapshot_cash):
        available = float(snapshot_cash)
    else:
        available = max(float(initial_capital) - open_cost, 0.0)

    snapshot_assets = pd.to_numeric(snapshot.get("total_assets") if snapshot else None, errors="coerce")
    equity = float(snapshot_assets) if pd.notna(snapshot_assets) else available + market_value

    return {
        "initial_capital": float(initial_capital),
        "available_cash": available,
        "open_cost": open_cost,
        "market_value": market_value,
        "floating_pnl": floating_pnl,
        "equity": equity,
    }


def page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="eyebrow">STRONG PULLBACK · DISCIPLINE DESK'
        f'<span class="version-badge">{APP_VERSION}</span></div>',
        unsafe_allow_html=True,
    )
    st.title(title)
    st.markdown(f'<div class="page-goal">本页目标：{subtitle}</div>', unsafe_allow_html=True)


def log_activity(message: str) -> None:
    """Add a compact event to the sidebar activity stream."""
    timestamp = china_now().strftime("%H:%M:%S")
    entries = list(st.session_state.get("activity_log", []))
    st.session_state.activity_log = [f"{timestamp}｜{message}", *entries][:8]


def render_activity_log() -> None:
    logs = list(st.session_state.get("activity_log", []))
    if logs:
        items = "".join(f"<li>{escape(str(log))}</li>" for log in logs[:6])
    else:
        items = '<li class="empty">暂无系统事件</li>'
    st.markdown(
        f"""
        <div class="activity-log">
          <div class="activity-title">事件流</div>
          <ul>{items}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def filter_stock_search(df: pd.DataFrame, query: str) -> pd.DataFrame:
    query = str(query or "").strip()
    if df.empty or not query:
        return df
    mask = pd.Series(False, index=df.index)
    for column in ["代码", "名称"]:
        if column in df:
            mask = mask | df[column].astype(str).str.contains(
                query,
                case=False,
                na=False,
                regex=False,
            )
    return df[mask].copy()


def render_dashboard_brief(
    today_key: str,
    quote_status: str,
    funds_source: str,
    today_buy_watch: int,
    missing_history: int,
    risk_holding_count: int,
    unreviewed_trades: int,
) -> None:
    risk_class = "brief-metric risk" if risk_holding_count else "brief-metric"
    st.markdown(
        f"""
        <section class="dashboard-brief">
          <div>
            <div class="brief-kicker">TODAY DISCIPLINE · {escape(today_key)}</div>
            <h2>只处理待补数据、待买确认、持仓风险和复盘归档。</h2>
            <p>{escape(quote_status)} · {escape(funds_source)} · 交易动作仍以手动确认为准。</p>
          </div>
          <div class="brief-metrics">
            <div class="brief-metric hot"><strong>{today_buy_watch}</strong><span>待买确认</span></div>
            <div class="brief-metric"><strong>{missing_history}</strong><span>缺K线</span></div>
            <div class="{risk_class}"><strong>{risk_holding_count}</strong><span>风险持仓</span></div>
            <div class="brief-metric"><strong>{unreviewed_trades}</strong><span>未复盘交易</span></div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_trading_mode_panel(available_cash_value: float) -> None:
    st.markdown(
        f"""
        <section class="mode-panel">
          <div>
            <div class="mode-kicker">Active Playbook</div>
            <h3>主板成交额前排强势股的 5 日线回踩低吸模式</h3>
            <p>只在强势确认后等待 MA5 附近回踩；进入待买也必须经过资金、时间和风控校验。</p>
          </div>
          <div class="mode-grid">
            <div class="mode-item">
              <span>股票范围</span>
              <b>沪深主板 A 股</b>
              <small>600/601/603/605/000/001/002；排除 ST、创业板、科创板、北交所、京东方A。</small>
            </div>
            <div class="mode-item">
              <span>强势确认</span>
              <b>近 10-20 日有 ≥5% 阳线</b>
              <small>最近 20 个交易日内出现过单日涨幅 ≥5% 且收盘高于开盘的阳线。</small>
            </div>
            <div class="mode-item">
              <span>买点区间</span>
              <b>距 MA5 0%-2%</b>
              <small>0%-2%待买观察，2%-5%继续观察，5%-7%偏高不追，>7%远离不追，<0%跌破MA5。</small>
            </div>
            <div class="mode-item">
              <span>买入时间</span>
              <b>9:35-10:00 / 14:30-14:55</b>
              <small>盘中确认回踩不破；不在 9:30、午盘中段和尾盘最后几分钟临时追。</small>
            </div>
            <div class="mode-item">
              <span>资金约束</span>
              <b>当前可用 {money_display(available_cash_value)}</b>
              <small>一手金额 = 当前价 x 100；资金不参与漏斗分层，只在交易记录时校验现金。</small>
            </div>
            <div class="mode-item">
              <span>卖出纪律</span>
              <b>5 日线管理仓位</b>
              <small>次日 10 点前不强就走；远离 MA5 止盈；14:50 跌破看减仓/退出，3 日不回清仓。</small>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


_TABLE_RENDER_COUNTER = 0


def next_table_key() -> str:
    global _TABLE_RENDER_COUNTER
    _TABLE_RENDER_COUNTER += 1
    return f"table_more_cols_{_TABLE_RENDER_COUNTER}"


def format_amount_cell(value: object) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return ""
    return money_display(float(numeric))


def format_percent_cell(value: object) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return ""
    return f"{float(numeric):.2f}%"


def compact_display_frame(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()
    amount_columns = {
        "成交额",
        "一手金额",
        "当前本金",
        "当前可用资金",
        "金额",
        "成交金额",
        "手续费",
        "印花税",
        "过户费",
        "总费用",
        "市值",
        "成本",
        "总成本",
        "总市值",
        "盈亏",
        "浮动盈亏",
        "实现盈亏",
        "收益金额",
        "当前现金",
        "持仓市值",
        "当前总资产",
    }
    percent_columns = [col for col in display.columns if col.endswith("%") or col in {"MA5偏离率%", "涨跌幅%"}]
    price_columns = {"现价", "MA5", "MA10", "MA20", "买入价", "当前价", "价格", "平均成本", "匹配成本", "卖出价", "买入均价"}

    for column in display.columns:
        if column in amount_columns:
            display[column] = display[column].map(format_amount_cell)
        elif column in percent_columns:
            display[column] = display[column].map(format_percent_cell)
        elif column in price_columns:
            display[column] = pd.to_numeric(display[column], errors="coerce").map(
                lambda value: "" if pd.isna(value) else f"{float(value):.3f}"
            )
    return display


def render_table(df: pd.DataFrame, height: int = 360) -> None:
    config = {
        "评分": st.column_config.ProgressColumn(min_value=0, max_value=10, format="%d / 10"),
        "提醒": st.column_config.TextColumn(width="small"),
        "筛选原因": st.column_config.TextColumn(width="small"),
        "明日计划": st.column_config.TextColumn(width="small"),
        "规则快照": st.column_config.TextColumn(width="small"),
        "偏离点": st.column_config.TextColumn(width="small"),
    }
    display = compact_display_frame(df)
    st.dataframe(
        display,
        width="stretch",
        height=height,
        hide_index=True,
        column_config={k: v for k, v in config.items() if k in df.columns},
        row_height=30,
    )



def goto_page(target: str) -> None:
    st.session_state.pending_page_navigation = target


def navigate_now(target: str) -> None:
    goto_page(target)
    st.rerun()


def nav_button(label: str, target: str, *, key: str, use_container_width: bool = True) -> None:
    if st.button(label, key=key, use_container_width=use_container_width):
        navigate_now(target)


def render_return_home(current_page: str) -> None:
    if current_page != "今日看板" and st.button("返回今日看板", key=f"back_home_{current_page}"):
        navigate_now("今日看板")


def trigger_global_refresh() -> None:
    st.session_state.manual_quote_refresh = int(st.session_state.get("manual_quote_refresh", 0)) + 1
    st.session_state.force_quote_refresh = True
    st.session_state.reminder_computed = False
    log_activity("手动刷新行情并重新计算规则")
    st.cache_data.clear()
    st.rerun()


def schedule_auto_refresh(enabled: bool, interval_seconds: int) -> None:
    del enabled, interval_seconds
    return


def trade_history_context(code: str, trade_date: object, trade_price: object) -> dict[str, object]:
    history = load_cached_history(str(code))
    result: dict[str, object] = {
        "has_history": False,
        "MA5": pd.NA,
        "MA5向上": pd.NA,
        "最近大阳线%": pd.NA,
        "MA5偏离率%": pd.NA,
    }
    if history is None or history.empty:
        return result

    history = history.copy()
    history["日期"] = pd.to_datetime(history["日期"], errors="coerce")
    trade_day = pd.to_datetime(trade_date, errors="coerce")
    if pd.isna(trade_day):
        return result

    history = history[history["日期"] <= trade_day].sort_values("日期")
    if history.empty:
        return result

    latest = history.iloc[-1]
    recent = history.tail(20)
    price = pd.to_numeric(trade_price, errors="coerce")
    ma5 = pd.to_numeric(latest.get("MA5"), errors="coerce")
    result["has_history"] = True
    result["MA5"] = ma5
    result["MA5向上"] = bool(latest.get("MA5向上", False))
    if "单日涨幅%" in recent.columns:
        max_up = pd.to_numeric(recent["单日涨幅%"], errors="coerce").max()
        result["最近大阳线%"] = round(float(max_up), 2) if pd.notna(max_up) else pd.NA
    result["MA5偏离率%"] = ma5_deviation(price, ma5)
    return result


def audit_trades_against_rules(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()

    audited = normalize_numeric_columns(trades.copy(), ["价格", "数量", "金额"])
    audited["日期_dt"] = pd.to_datetime(audited["日期"], errors="coerce")
    audited = audited.sort_values(["日期_dt", "代码", "类型"]).reset_index(drop=True)
    positions: dict[str, dict[str, float]] = {}
    rows: list[dict[str, object]] = []

    for _, row in audited.iterrows():
        code = str(row.get("代码", ""))
        name = str(row.get("名称", ""))
        side = str(row.get("类型", ""))
        price = number_or(row.get("价格"), 0)
        qty = number_or(row.get("数量"), 0)
        fee = number_or(row.get("手续费"), 0)
        tax = number_or(row.get("印花税"), 0)
        transfer_fee = number_or(row.get("过户费"), 0)
        total_fee = number_or(row.get("总费用"), fee + tax + transfer_fee)
        saved_conclusion = str(row.get("规则结论", "") or "").strip()
        saved_tags = str(row.get("违规标签", "") or "").strip()
        context = trade_history_context(code, row.get("日期"), price)
        ma5 = context.get("MA5")
        deviation = context.get("MA5偏离率%")
        max_big_line = context.get("最近大阳线%")
        conclusion = "待补充"
        issues: list[str] = []
        basis: list[str] = []
        matched_cost = pd.NA
        realized_pnl = pd.NA
        realized_pnl_pct = pd.NA

        if side == "买入":
            passed, reason = screening_result(code, name)
            if not passed:
                issues.append(reason)
            if not context["has_history"]:
                issues.append("缺少历史K线，无法审计买点")
            else:
                if pd.isna(max_big_line) or float(max_big_line) < 5:
                    issues.append("买入前近20日缺少5%强势阳线")
                if deviation is None or pd.isna(deviation):
                    issues.append("无法计算买入价与MA5偏离")
                elif float(deviation) < 0:
                    issues.append("买入价低于MA5，属于跌破后买入")
                elif float(deviation) > 2:
                    issues.append("买入价距离MA5超过2%，未到待买区")
                else:
                    basis.append("回踩MA5 0%-2%区间")
            if saved_conclusion:
                conclusion = saved_conclusion
                if saved_tags and saved_tags != "无":
                    issues = [saved_tags]
            elif not issues:
                conclusion = "符合规则"
            elif len(issues) <= 2:
                conclusion = "部分符合"
            else:
                conclusion = "违反规则"

            pos = positions.setdefault(code, {"qty": 0.0, "amount": 0.0})
            pos["qty"] += qty
            pos["amount"] += price * qty + total_fee

        elif side == "卖出":
            pos = positions.setdefault(code, {"qty": 0.0, "amount": 0.0})
            if pos["qty"] > 0:
                matched_cost = pos["amount"] / pos["qty"]
                realized_pnl = (price - matched_cost) * qty - total_fee
                realized_pnl_pct = (price - matched_cost) / matched_cost * 100 if matched_cost else pd.NA
            if not context["has_history"]:
                issues.append("缺少历史K线，无法审计卖点")
            else:
                if deviation is None or pd.isna(deviation):
                    issues.append("无法计算卖出价与MA5偏离")
                elif float(deviation) < 0:
                    basis.append("跌破MA5风控卖出")
                elif float(deviation) > 7:
                    basis.append("远离MA5止盈卖出")
                elif pd.notna(realized_pnl) and float(realized_pnl) > 0:
                    basis.append("盈利退出，但未触发远离MA5止盈")
                    issues.append("卖出依据需备注：未见跌破或远离MA5")
                else:
                    issues.append("卖出时未跌破MA5，也未远离MA5")

            if not issues:
                conclusion = "符合规则"
            elif basis:
                conclusion = "部分符合"
            else:
                conclusion = "违反规则"

            reduce_qty = min(qty, pos["qty"])
            if pos["qty"] > 0 and reduce_qty > 0:
                avg_cost = pos["amount"] / pos["qty"]
                pos["qty"] -= reduce_qty
                pos["amount"] -= avg_cost * reduce_qty
        else:
            issues.append("未知交易类型")
            conclusion = "待补充"

        time_text = str(row.get("时间", "") or "").strip()
        if not time_text:
            time_audit = "未记录成交时间，无法判断是否在9:35-10:00或14:30-14:55"
        elif trade_time_allowed(time_text):
            time_audit = "计划时间内"
        else:
            time_audit = "非计划时间"

        rows.append({
            **row.drop(labels=["日期_dt"], errors="ignore").to_dict(),
            "MA5": ma5,
            "MA5偏离率%": deviation,
            "最近大阳线%": max_big_line,
            "匹配成本": matched_cost,
            "实现盈亏": realized_pnl,
            "实现盈亏%": realized_pnl_pct,
            "规则结论": conclusion,
            "规则依据": "；".join(basis) if basis else "",
            "偏离点": "；".join(issues) if issues else "无",
            "时间审计": time_audit,
        })

    return pd.DataFrame(rows)


def render_trade_audit_report(audited: pd.DataFrame, title: str, mask: pd.Series) -> None:
    subset = audited[mask].copy()
    if subset.empty:
        st.info(f"{title}没有买入卖出记录，暂不生成规则分析。")
        return

    buys = subset[subset["类型"] == "买入"]
    sells = subset[subset["类型"] == "卖出"]
    compliant = subset["规则结论"].fillna("").astype(str).str.contains("符合规则|符合", regex=True)
    realized = pd.to_numeric(sells.get("实现盈亏", pd.Series(dtype=float)), errors="coerce").sum()

    metric_cols = st.columns(5)
    metric_cols[0].metric("交易次数", len(subset))
    metric_cols[1].metric("买入次数", len(buys))
    metric_cols[2].metric("卖出次数", len(sells))
    metric_cols[3].metric("已实现盈亏", f"¥{realized:,.2f}")
    metric_cols[4].metric("规则符合率", f"{(compliant.mean() * 100 if len(subset) else 0):.1f}%")

    deviations = subset[subset["偏离点"].fillna("无") != "无"]
    if not deviations.empty:
        st.caption("主要偏离点")
        for text, count in deviations["偏离点"].value_counts().head(3).items():
            st.write(f"- {text}：{count}次")

    render_columns(
        subset,
        ["日期", "类型", "代码", "名称", "价格", "数量", "金额", "MA5", "MA5偏离率%",
         "规则结论", "规则依据", "偏离点", "时间审计", "实现盈亏", "实现盈亏%"],
        420,
    )


REMINDER_COLUMNS = [
    "MA5",
    "MA10",
    "MA20",
    "MA5向上",
    "最近大阳线%",
    "MA5偏离率%",
    "一手金额",
    "当前本金",
    "当前可用资金",
    "资金可买",
    "本金是否可买",
    "history_status",
    "history_rows",
    "history_last_date",
    "history_error",
    "提醒",
    "规则状态",
]


def text_contains(df: pd.DataFrame, column: str, pattern: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    return df[column].fillna("").astype(str).str.contains(pattern, na=False)


def is_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "是", "yes", "y"}


def select_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if column in df.columns]


def render_columns(
    df: pd.DataFrame,
    columns: list[str],
    height: int = 340,
    *,
    show_toggle: bool = True,
) -> None:
    if df.empty:
        render_table(df[select_columns(df, columns)], height)
        return
    table_columns = select_columns(df, columns)
    if show_toggle:
        show_more = st.toggle("展开更多列", value=False, key=next_table_key())
        if show_more:
            table_columns = list(df.columns)
    render_table(df[table_columns], height)


STOCK_TABLE_COLUMNS = [
    "代码", "名称", "涨跌幅%", "现价", "成交额", "成交额排名", "MA5", "MA10", "MA20",
    "MA5偏离率%", "最近大阳线%", "MA5向上", "一手金额", "本金是否可买", "分组", "流程阶段", "提醒",
]

HOLDING_TABLE_COLUMNS = [
    "代码", "名称", "数量", "平均成本", "当前价", "市值", "浮动盈亏", "浮动盈亏%",
    "MA5", "MA5偏离率%", "持仓天数", "操作提醒",
]


def workbench_column_config(df: pd.DataFrame) -> dict[str, object]:
    config: dict[str, object] = {
        "代码": st.column_config.TextColumn(width="small"),
        "名称": st.column_config.TextColumn(width="small"),
        "分组": st.column_config.TextColumn(width="small"),
        "流程阶段": st.column_config.TextColumn(width="small"),
        "提醒": st.column_config.TextColumn(width="medium"),
        "操作提醒": st.column_config.TextColumn(width="medium"),
        "本金是否可买": st.column_config.TextColumn(width="small"),
        "MA5向上": st.column_config.CheckboxColumn(width="small"),
    }
    price_cols = {"现价", "当前价", "MA5", "MA10", "MA20", "平均成本"}
    amount_cols = {"成交额", "一手金额", "市值", "浮动盈亏"}
    percent_cols = {"涨跌幅%", "MA5偏离率%", "最近大阳线%", "浮动盈亏%"}
    integer_cols = {"成交额排名", "数量", "持仓天数"}
    for column in df.columns:
        if column in price_cols:
            config[column] = st.column_config.NumberColumn(format="%.3f", width="small")
        elif column in amount_cols:
            config[column] = st.column_config.NumberColumn(format="¥%.2f", width="small")
        elif column in percent_cols:
            config[column] = st.column_config.NumberColumn(format="%.2f%%", width="small")
        elif column in integer_cols:
            config[column] = st.column_config.NumberColumn(format="%d", width="small")
    return {column: value for column, value in config.items() if column in df.columns}


def color_positive_red(value: object) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric) or float(numeric) == 0:
        return ""
    color = "#DC2626" if float(numeric) > 0 else "#16A34A"
    return f"color: {color}; font-weight: 650"


def style_workbench_frame(df: pd.DataFrame):
    style = df.style
    color_columns = [column for column in ["涨跌幅%", "MA5偏离率%", "浮动盈亏", "浮动盈亏%"] if column in df.columns]
    if color_columns:
        style = style.map(color_positive_red, subset=color_columns)
    formatters = {}
    for column in df.columns:
        if column in {"现价", "当前价", "MA5", "MA10", "MA20", "平均成本"}:
            formatters[column] = "{:.3f}"
        elif column in {"涨跌幅%", "MA5偏离率%", "最近大阳线%", "浮动盈亏%"}:
            formatters[column] = "{:.2f}%"
        elif column in {"成交额", "一手金额", "市值", "浮动盈亏"}:
            formatters[column] = "¥{:,.2f}"
    return style.format(formatters, na_rep="")


def selected_rows_from_event(event: object) -> list[int]:
    if event is None:
        return []
    selection = event.get("selection", {}) if isinstance(event, dict) else getattr(event, "selection", {})
    if selection is None:
        return []
    if isinstance(selection, dict):
        return list(selection.get("rows", []) or [])
    return list(getattr(selection, "rows", []) or [])


def render_workbench_table(
    df: pd.DataFrame,
    columns: list[str],
    *,
    key: str,
    height: int = 480,
) -> pd.Series | None:
    table_columns = select_columns(df, columns)
    display = df[table_columns].copy() if table_columns else df.copy()
    if display.empty:
        st.dataframe(display, width="stretch", height=180, hide_index=True, row_height=26, key=f"{key}_empty")
        return None

    numeric_columns = [
        "涨跌幅%", "现价", "成交额", "成交额排名", "MA5", "MA10", "MA20", "MA5偏离率%",
        "最近大阳线%", "一手金额", "数量", "平均成本", "当前价", "市值", "浮动盈亏",
        "浮动盈亏%", "持仓天数",
    ]
    for column in numeric_columns:
        if column in display:
            display[column] = pd.to_numeric(display[column], errors="coerce")
    if "MA5向上" in display:
        display["MA5向上"] = display["MA5向上"].map(is_truthy)

    event = st.dataframe(
        style_workbench_frame(display),
        width="stretch",
        height=height,
        hide_index=True,
        row_height=26,
        column_config=workbench_column_config(display),
        on_select="rerun",
        selection_mode="single-row",
        key=key,
    )
    selected_rows = selected_rows_from_event(event)
    if selected_rows:
        selected_index = selected_rows[0]
        if 0 <= selected_index < len(display):
            return display.iloc[selected_index]
    return None


def render_kline_for_selection(selected: pd.Series | None) -> None:
    if selected is None:
        st.caption("单击表格中的股票查看K线。")
        return
    render_kline_chart(str(selected.get("代码", "")), str(selected.get("名称", "")))


def history_action_advice(status: str) -> str:
    mapping = {
        "已有缓存": "可参与MA规则判断",
        "缺少历史K线": "点击补K线",
        "自动获取失败": "稍后重试或手动导入",
        "数据不足": "可能是新股/次新股，暂不参与MA20/完整规则判断",
        "缓存过旧": "点击强制刷新",
        "自动获取成功": "已更新，重新计算规则",
    }
    return mapping.get(str(status or ""), "检查数据后重试")


def count_risk_positions(positions: pd.DataFrame) -> int:
    if positions.empty:
        return 0
    deviation = pd.to_numeric(positions.get("MA5偏离率%", pd.Series(dtype=float)), errors="coerce")
    reminders = positions.get("操作提醒", pd.Series([""] * len(positions))).fillna("").astype(str)
    risk_text = reminders.str.contains("跌破|减仓|清仓|卖出|风险", regex=True)
    return int(deviation.lt(0).fillna(False).sum() + (risk_text & ~deviation.lt(0).fillna(False)).sum())


def observation_result(row: pd.Series) -> tuple[bool, str]:
    has_history = pd.notna(row.get("MA5"))
    has_big_line = number_or(row.get("最近大阳线%"), 0) >= 5
    deviation = ma5_deviation(row.get("现价"), row.get("MA5"))
    passed, reason = screening_result(str(row.get("代码", "")), str(row.get("名称", "")))
    if not passed:
        return False, reason
    if not has_history:
        return False, "缺少历史K线，待补充"
    if not has_big_line:
        return False, "缺少5%阳线启动信号"
    if deviation is None:
        return False, "无法计算MA5偏离率"
    if deviation < 0:
        return False, "当前价在MA5下方"
    return True, "近20日有5%阳线启动信号"


def capital_result(row: pd.Series) -> tuple[bool, str]:
    deviation = ma5_deviation(row.get("现价"), row.get("MA5"))
    if deviation is None:
        return False, "无法计算MA5偏离率"
    if deviation < 0:
        return False, "当前价在MA5下方"
    if deviation > 2:
        return False, "等待回踩到MA5 0%-2%"
    return True, "待买观察，盘中手动确认"


def build_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["观察通过"] = False
    out["待买通过"] = False
    out["流程阶段"] = "初筛通过"
    out["分组"] = "初筛"
    out["筛选原因"] = ""

    for index, row in out.iterrows():
        result = evaluate_stock(row.to_dict())
        out.loc[index, "流程阶段"] = result["stage"]
        out.loc[index, "状态"] = result["stage"]
        out.loc[index, "分组"] = result["group"]
        out.loc[index, "筛选原因"] = result["reason"]
        if result["reminder"]:
            out.loc[index, "提醒"] = result["reminder"]
        was_pinned = str(row.get("is_pinned", "")).strip().lower() in {"true", "1", "是", "yes", "y"}
        if was_pinned or result["group"] in {"观察", "待买", "持仓"}:
            out.loc[index, "is_pinned"] = True
        out.loc[index, "观察通过"] = result["group"] in {"观察", "待买"}
        out.loc[index, "待买通过"] = bool(result["can_buy"])

    return out


def pipeline_views(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    source = df.copy()
    if "流程阶段" not in source:
        source["流程阶段"] = source.get("状态", "初筛通过")
    source["流程阶段"] = source["流程阶段"].map(normalize_stage)
    source["分组"] = source["流程阶段"].map(stage_to_group)
    views = {stage: source[source["流程阶段"] == stage].copy() for stage in PIPELINE_STAGES}
    stage_text = source.get("流程阶段", pd.Series("", index=source.index)).fillna("").astype(str)
    observe_mask = stage_text.isin(OBSERVATION_STAGES | {"待买观察"})
    volume_break = source.get("放量跌破MA5", pd.Series(False, index=source.index)).map(is_truthy)
    buy_mask = stage_text.eq("待买观察") & ~volume_break
    views["初筛"] = source.copy()
    views["观察"] = source[observe_mask].copy()
    views["持仓"] = source[source["分组"] == "持仓"].copy()
    views["待买"] = source[buy_mask].copy()
    views["待买观察"] = views["待买"].copy()
    views["观察未待买"] = source[observe_mask & ~buy_mask].copy()
    views["未达规则"] = source[stage_text.isin(["未达规则", "风险排除", "跌破MA5", "淘汰"])].copy()
    views["淘汰分组"] = source[source["分组"] == "淘汰"].copy()
    return views


def apply_reminder_columns(target: pd.DataFrame, reminder_data: pd.DataFrame) -> pd.DataFrame:
    for col in REMINDER_COLUMNS:
        if col in reminder_data.columns and len(reminder_data) == len(target):
            target[col] = reminder_data[col].values
    if "资金可买" in reminder_data.columns and len(reminder_data) == len(target):
        target["本金是否可买"] = reminder_data["资金可买"].values
    return target


def prepare_current_stock_batch(
    incoming: pd.DataFrame,
    existing: pd.DataFrame | None = None,
    limit: int = 30,
    source: str = "手动生成",
) -> pd.DataFrame:
    """Use the latest import/generation as the current time batch, not an accumulation."""
    batch = incoming.copy()
    if batch.empty:
        return batch.reindex(columns=WATCHLIST_COLUMNS)

    rank = pd.to_numeric(batch.get("成交额排名"), errors="coerce")
    turnover = pd.to_numeric(batch.get("成交额"), errors="coerce")
    batch["_rank_sort"] = rank.fillna(999999)
    batch["_turnover_sort"] = turnover.fillna(-1)
    batch = (
        batch.sort_values(["_rank_sort", "_turnover_sort"], ascending=[True, False])
        .head(limit)
        .drop(columns=["_rank_sort", "_turnover_sort"])
        .copy()
    )

    if existing is not None and not existing.empty:
        keep_columns = ["明日计划", "备注"]
        existing_index = existing.set_index("代码")
        for index, row in batch.iterrows():
            code = str(row.get("代码", ""))
            if code not in existing_index.index:
                continue
            for column in keep_columns:
                value = existing_index.loc[code].get(column, pd.NA)
                if pd.notna(value) and str(value).strip():
                    batch.loc[index, column] = value

    for column in WATCHLIST_COLUMNS:
        if column not in batch:
            batch[column] = False if column in {"MA5向上", "放量跌破MA5"} else pd.NA
    batch["状态"] = "初筛通过"
    batch["流程阶段"] = "初筛通过"
    batch["分组"] = "初筛"
    batch["is_pinned"] = False
    batch = assign_pool_batch(batch, source)
    return batch[WATCHLIST_COLUMNS].reset_index(drop=True)


def fetch_history_for_codes(
    codes: list[str],
    *,
    only_missing: bool = True,
    statuses_to_fetch: set[str] | None = None,
) -> dict[str, object]:
    cleaned_codes = [str(code) for code in codes if str(code).strip()]
    if only_missing:
        allowed_statuses = statuses_to_fetch or {"缺少历史K线", "数据不足", "自动获取失败", "缓存过旧"}
        cleaned_codes = [
            code for code in cleaned_codes
            if diagnose_history(code)["history_status"] in allowed_statuses
        ]
    summary: dict[str, object] = {
        "fetched": 0,
        "failed": 0,
        "insufficient": 0,
        "failed_codes": [],
        "history_parts": [],
        "statuses": {},
    }
    if not cleaned_codes:
        return summary

    progress = st.progress(0, text="正在补全历史K线...")
    for i, code in enumerate(cleaned_codes):
        progress.progress((i + 1) / len(cleaned_codes), text=f"正在获取 {code} 历史K线...")
        try:
            result = fetch_and_cache(str(code))
        except Exception as exc:
            result = {"success": False, "status": "自动获取失败", "error": str(exc), "data": None}

        if result.get("success") and result.get("data") is not None:
            summary["fetched"] = int(summary["fetched"]) + 1
            summary["history_parts"].append(result["data"])
            summary["statuses"][code] = {"status": "自动获取成功", "error": ""}
        else:
            status = str(result.get("status") or "自动获取失败")
            if status == "数据不足":
                summary["insufficient"] = int(summary["insufficient"]) + 1
            else:
                summary["failed"] = int(summary["failed"]) + 1
            summary["failed_codes"].append(code)
            summary["statuses"][code] = {
                "status": status,
                "error": str(result.get("error") or "自动获取失败"),
            }
    progress.empty()

    if summary["history_parts"]:
        combined = pd.concat(summary["history_parts"], ignore_index=True)
        history_save_cache(combined)
    st.session_state.history_fetch_failures = int(summary["failed"]) + int(summary["insufficient"])
    st.session_state.history_failed_codes = summary["failed_codes"]
    st.session_state.history_fetch_statuses = summary["statuses"]
    return summary


def _run_analysis(uploaded, incoming: pd.DataFrame, fetch_missing: bool = False) -> None:
    """Run stock pool analysis with optional history fetching."""
    archive_upload(uploaded.getvalue(), uploaded.name, "stock_pool")
    merged = prepare_current_stock_batch(
        incoming,
        existing=st.session_state.watchlist,
        limit=30,
        source=f"数据导入:{uploaded.name}",
    )
    if merged.empty:
        st.error("当前批次没有识别到有效股票代码。")
        return

    if fetch_missing and st.session_state.settings.get("history_source", "本地缓存 + AKShare") != "仅本地缓存":
        fetch_history_for_codes(merged["代码"].dropna().astype(str).tolist(), only_missing=True)
    elif fetch_missing:
        st.info("当前历史K线数据源设置为“仅本地缓存”，未联网补历史K线。")

    reminder_data = compute_all_reminders(merged, available_cash)
    merged = apply_reminder_columns(merged, reminder_data)
    analyzed = build_pipeline(enrich_watchlist(
        merged,
        available_cash,
        max_position_ratio=max_position_ratio,
    ))
    for column in ["分组", "流程阶段", "筛选原因", "提醒", "规则状态"]:
        if column in analyzed.columns:
            merged[column] = analyzed[column].values
    merged["状态"] = analyzed["流程阶段"].values
    st.session_state.watchlist = merged[WATCHLIST_COLUMNS]
    save_watchlist(st.session_state.watchlist)
    analyzed.to_csv("data/processed/latest_analysis.csv", index=False, encoding="utf-8-sig")
    st.cache_data.clear()
    st.session_state.reminder_computed = True
    st.session_state.last_reminder_cash = available_cash
    summary = pipeline_views(analyzed)
    log_activity(
        f"股票池分析完成：待买{len(summary['待买'])}，"
        f"观察{len(summary['观察'])}，"
        f"未达规则{len(summary['未达规则'])}"
    )
    st.success(
        f"分析完成。初筛 {len(summary['初筛'])}，观察 {len(summary['观察'])}，"
        f"待买观察 {len(summary['待买'])}，未达规则 {len(summary['未达规则'])}。"
    )


def scan_turnover_changes_for_watchlist(current: pd.DataFrame, limit: int = 30) -> dict[str, object]:
    live_pool = fetch_auto_stock_pool(limit, source="自动切换")
    if live_pool.empty:
        return {
            "success": False,
            "message": live_pool.attrs.get("message", "行情源未返回实时成交额前30"),
            "new": pd.DataFrame(),
            "dropped": pd.DataFrame(),
            "rank_changed": pd.DataFrame(),
        }

    current_codes = set(current.get("代码", pd.Series(dtype=str)).dropna().astype(str).map(_data.clean_code))
    live_codes = set(live_pool.get("代码", pd.Series(dtype=str)).dropna().astype(str).map(_data.clean_code))
    current_rank_source = current.get("pool_rank_at_generation", current.get("成交额排名", pd.Series(dtype=object)))
    current_rank = {
        _data.clean_code(code): pd.to_numeric(rank, errors="coerce")
        for code, rank in zip(current.get("代码", pd.Series(dtype=str)), current_rank_source)
    }
    live_rank = {
        _data.clean_code(row.get("代码")): pd.to_numeric(row.get("成交额排名"), errors="coerce")
        for _, row in live_pool.iterrows()
    }

    live_index = live_pool.assign(代码=live_pool["代码"].map(_data.clean_code)).set_index("代码", drop=False)
    current_index = current.assign(代码=current["代码"].map(_data.clean_code)).set_index("代码", drop=False) if not current.empty else pd.DataFrame()

    new = live_index.loc[[code for code in live_index.index if code in live_codes - current_codes]].copy()
    dropped = current_index.loc[[code for code in current_index.index if code in current_codes - live_codes]].copy() if not current_index.empty else pd.DataFrame()
    changed_rows: list[dict[str, object]] = []
    for code in sorted(current_codes & live_codes, key=lambda item: live_rank.get(item, 999999)):
        old_rank = current_rank.get(code)
        new_rank = live_rank.get(code)
        if pd.isna(old_rank) or pd.isna(new_rank) or int(old_rank) == int(new_rank):
            continue
        changed_rows.append({
            "代码": code,
            "名称": live_index.loc[code].get("名称", ""),
            "生成排名": int(old_rank),
            "实时排名": int(new_rank),
            "方向": "上升" if int(new_rank) < int(old_rank) else "下降",
        })

    return {
        "success": True,
        "message": f"扫描完成：新进 {len(new)}，跌出 {len(dropped)}，排名变化 {len(changed_rows)}。当前初筛池未替换。",
        "new": new.reset_index(drop=True),
        "dropped": dropped.reset_index(drop=True),
        "rank_changed": pd.DataFrame(changed_rows),
    }


def _recompute_reminders(
    current_watchlist: pd.DataFrame | None = None,
    current_cash: float | None = None,
) -> None:
    """Recompute reminder fields for the current watchlist."""
    target = st.session_state.watchlist.copy() if current_watchlist is None else current_watchlist.copy()
    cash = available_cash if current_cash is None else current_cash
    reminder_data = compute_all_reminders(target, cash)
    target = apply_reminder_columns(target, reminder_data)
    enriched = enrich_watchlist(
        target,
        cash,
        max_position_ratio=float(st.session_state.settings.get("max_position_pct", 100)) / 100,
    )
    analyzed = build_pipeline(enriched)
    for column in ["分组", "流程阶段", "筛选原因", "提醒", "规则状态"]:
        if column in analyzed.columns:
            target[column] = analyzed[column].values
    target["状态"] = analyzed["流程阶段"].values
    st.session_state.watchlist = target[WATCHLIST_COLUMNS]
    save_watchlist(st.session_state.watchlist)
    st.cache_data.clear()
    st.session_state.reminder_computed = True
    st.session_state.last_reminder_cash = cash


def lookup_trade_context(
    code: str,
    side: str,
    watchlist_df: pd.DataFrame | None,
    positions_df: pd.DataFrame | None,
) -> dict[str, object]:
    cleaned = _data.clean_code(code)
    context: dict[str, object] = {
        "代码": cleaned,
        "名称": "",
        "当前价": pd.NA,
        "MA5": pd.NA,
        "流程阶段": "",
        "是否待买观察": False,
        "一手金额": pd.NA,
        "持仓数量": 0,
        "平均成本": pd.NA,
        "source": "",
    }
    if not cleaned:
        return context

    pool = watchlist_df if watchlist_df is not None else st.session_state.watchlist
    if pool is not None and not pool.empty and "代码" in pool:
        matches = pool[pool["代码"].astype(str).map(_data.clean_code) == cleaned]
        if not matches.empty:
            row = matches.iloc[-1].to_dict()
            context.update({
                "名称": row.get("名称", ""),
                "当前价": row.get("现价", row.get("当前价", pd.NA)),
                "MA5": row.get("MA5", pd.NA),
                "流程阶段": row.get("流程阶段", row.get("状态", "")),
                "是否待买观察": normalize_stage(row.get("流程阶段", row.get("状态", ""))) == "待买观察",
                "一手金额": row.get("一手金额", pd.NA),
                "source": "当前股票池",
            })

    positions = positions_df if positions_df is not None else pd.DataFrame()
    if positions is not None and not positions.empty and "代码" in positions:
        matches = positions[positions["代码"].astype(str).map(_data.clean_code) == cleaned]
        if not matches.empty:
            row = matches.iloc[-1].to_dict()
            if side == "卖出" or not str(context.get("名称", "")).strip():
                context.update({
                    "名称": row.get("名称", context.get("名称", "")),
                    "当前价": row.get("当前价", context.get("当前价", pd.NA)),
                    "MA5": row.get("MA5", context.get("MA5", pd.NA)),
                    "source": "当前持仓",
                })
            context.update({
                "持仓数量": int(number_or(row.get("数量"), 0)),
                "平均成本": row.get("平均成本", pd.NA),
            })

    if pd.isna(pd.to_numeric(context.get("当前价"), errors="coerce")):
        history = load_cached_history(cleaned)
        if history is not None and not history.empty:
            latest = history.iloc[-1]
            context["当前价"] = latest.get("收盘", context["当前价"])
            context["MA5"] = latest.get("MA5", context["MA5"])
            if not context["source"]:
                context["source"] = "历史缓存"

    price = pd.to_numeric(context.get("当前价"), errors="coerce")
    if pd.notna(price):
        context["一手金额"] = float(price) * 100
    return context


def trade_time_allowed(trade_time: str) -> bool:
    text = str(trade_time or "").strip().replace("：", ":")
    try:
        hour_text, minute_text = text.split(":")[:2]
        current = time(int(hour_text), int(minute_text))
    except (ValueError, TypeError):
        return False
    return time(9, 35) <= current <= time(10, 0) or time(14, 30) <= current <= time(14, 55)


def rule_snapshot_for_trade(
    code: str,
    name: str,
    side: str,
    trade_time: str,
    price: float,
    amount: float,
    cash: float,
    watchlist_df: pd.DataFrame,
) -> tuple[str, str, str]:
    if side != "买入":
        return "", "", ""

    cleaned = _data.clean_code(code)
    row: dict[str, object] = {}
    if not watchlist_df.empty and "代码" in watchlist_df:
        matches = watchlist_df[watchlist_df["代码"].astype(str).map(_data.clean_code) == cleaned]
        if not matches.empty:
            row = matches.iloc[-1].to_dict()

    passed, screen_reason = screening_result(cleaned, name or row.get("名称", ""))
    rank = pd.to_numeric(row.get("成交额排名"), errors="coerce")
    rank_ok = pd.notna(rank) and float(rank) <= 30
    big_line = number_or(row.get("最近大阳线%"), 0) >= 5
    ma5_up = is_truthy(row.get("MA5向上"))
    deviation = row.get("MA5偏离率%")
    if not pd.notna(pd.to_numeric(deviation, errors="coerce")):
        deviation = ma5_deviation(price, row.get("MA5"))
    deviation_ok = deviation is not None and pd.notna(deviation) and 0 <= float(deviation) <= 2
    principal_ok = amount <= cash
    time_ok = trade_time_allowed(trade_time)
    stage = str(row.get("流程阶段", row.get("状态", "")) or "")
    group_name = str(row.get("分组") or stage_to_group(stage))

    tags: list[str] = []
    if not passed:
        if "主板" in screen_reason:
            tags.append("非主板")
        elif "ST" in screen_reason:
            tags.append("ST")
        elif "京东方" in screen_reason:
            tags.append("京东方A")
        else:
            tags.append("其他")
    if not big_line:
        tags.append("无5%阳线")
    if not ma5_up:
        tags.append("MA5未向上")
    if deviation is None or pd.isna(deviation):
        tags.append("未回踩MA5")
    else:
        deviation_f = float(deviation)
        if deviation_f < 0:
            tags.append("跌破MA5仍买")
        elif deviation_f > 5:
            tags.append("远离MA5追高")
        elif deviation_f > 2:
            tags.append("未回踩MA5")
    if not principal_ok:
        tags.append("本金不足仍买")
    if not time_ok:
        tags.append("非计划时间买入")

    unique_tags = list(dict.fromkeys(tags))
    severe = {"非主板", "ST", "京东方A", "无5%阳线", "MA5未向上", "跌破MA5仍买", "远离MA5追高", "本金不足仍买"}
    if not unique_tags:
        conclusion = "符合规则"
    elif severe.intersection(unique_tags) or len(unique_tags) >= 3:
        conclusion = "违反规则"
    else:
        conclusion = "部分符合"

    def snapshot_value(value: object) -> object:
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        if hasattr(value, "item"):
            try:
                return value.item()
            except (TypeError, ValueError):
                return value
        return value

    snapshot = {
        "是否主板": passed,
        "是否成交额前30": rank_ok,
        "是否有5%阳线": big_line,
        "是否MA5向上": ma5_up,
        "是否MA5偏离率0%-2%": deviation_ok,
        "是否本金可买": principal_ok,
        "是否在允许交易时间": time_ok,
        "买入时分组": group_name,
        "买入时状态": stage or "未在当前股票池",
        "买入时流程阶段": stage or "未在当前股票池",
        "买入时MA5": snapshot_value(row.get("MA5", pd.NA)),
        "买入时MA5偏离率%": snapshot_value(deviation),
        "买入时最近20日最大涨幅%": snapshot_value(row.get("最近大阳线%", pd.NA)),
        "买入时MA5向上": ma5_up,
        "买入时资金足够": principal_ok,
    }
    return json.dumps(snapshot, ensure_ascii=False), conclusion, "；".join(unique_tags) if unique_tags else "无"


def save_trade_record(existing_trades: pd.DataFrame, new_trade: pd.DataFrame) -> None:
    trades = pd.concat([existing_trades, new_trade], ignore_index=True)
    save_trades(trades)
    st.session_state.trades = load_trades()
    positions = build_positions_from_trades(
        st.session_state.trades,
        watchlist=st.session_state.watchlist,
        legacy_holdings=st.session_state.holdings,
    )
    st.session_state.holdings = portfolio_to_legacy_holdings(positions)
    save_holdings(st.session_state.holdings)
    log_activity("交易流水已保存，持仓和资产已重算")


def render_trade_form(existing_trades: pd.DataFrame) -> None:
    st.divider()
    st.markdown("#### 添加交易记录")
    positions_for_form = build_positions_from_trades(
        existing_trades,
        watchlist=st.session_state.watchlist,
        legacy_holdings=st.session_state.holdings,
    )
    row1 = st.columns([1, 1, 0.9])
    with row1[0]:
        trade_code = st.text_input("股票代码", key="trade_ticket_code", placeholder="例如 600460")
    with row1[2]:
        trade_type = st.selectbox("买卖方向", ["买入", "卖出"], key="trade_ticket_side")

    context = lookup_trade_context(trade_code, trade_type, watchlist, positions_for_form)
    token = f"{context.get('代码', '')}-{trade_type}"
    if token and token != st.session_state.get("trade_ticket_last_token"):
        if str(context.get("名称", "")).strip():
            st.session_state.trade_ticket_name = str(context.get("名称", ""))
        price_value = pd.to_numeric(context.get("当前价"), errors="coerce")
        if pd.notna(price_value):
            st.session_state.trade_ticket_price = float(price_value)
        if trade_type == "卖出" and number_or(context.get("持仓数量"), 0) > 0:
            st.session_state.trade_ticket_qty = int(number_or(context.get("持仓数量"), 0))
        elif "trade_ticket_qty" not in st.session_state:
            st.session_state.trade_ticket_qty = 100
        st.session_state.trade_ticket_last_token = token

    with row1[1]:
        trade_name = st.text_input("股票名称", key="trade_ticket_name")

    if context.get("source"):
        stage_text = str(context.get("流程阶段") or "未分层")
        pending_text = "是" if context.get("是否待买观察") else "否"
        st.caption(
            f"自动匹配：{context['source']} · 当前价 {context.get('当前价', '—')} · "
            f"MA5 {context.get('MA5', '—')} · 状态 {stage_text} · 待买观察 {pending_text} · "
            f"一手金额 {format_amount_cell(context.get('一手金额'))}"
        )

    row2 = st.columns([1, 1, 1])
    with row2[0]:
        trade_price = st.number_input("价格", min_value=0.0, step=0.001, format="%.3f", key="trade_ticket_price")
    with row2[1]:
        max_qty = int(number_or(context.get("持仓数量"), 0)) if trade_type == "卖出" else None
        trade_qty = st.number_input(
            "数量",
            min_value=0,
            max_value=max_qty if max_qty and trade_type == "卖出" else None,
            step=100,
            key="trade_ticket_qty",
        )
    amount = round(float(trade_price) * float(trade_qty), 2)
    with row2[2]:
        st.metric("成交金额", money_display(amount))

    row3 = st.columns([1, 1, 2])
    with row3[0]:
        trade_date = st.date_input("交易日期", date.today(), key="trade_ticket_date")
    with row3[1]:
        trade_time_text = st.text_input("交易时间", value=st.session_state.get("trade_ticket_time", ""), key="trade_ticket_time", placeholder="例如 09:45")
    with row3[2]:
        trade_reason = st.text_input("买入/卖出原因", key="trade_ticket_reason")

    auto_fee = bool(st.session_state.settings.get("auto_calculate_fees", True))
    fee_values = calculate_trade_fees(trade_type, trade_price, trade_qty, st.session_state.settings)
    row4 = st.columns(3)
    with row4[0]:
        if auto_fee:
            trade_fee = st.number_input(
                "手续费",
                min_value=0.0,
                value=float(fee_values["commission"]),
                step=0.01,
                format="%.2f",
                key=f"trade_ticket_fee_auto_{trade_type}_{amount}_{trade_qty}",
                disabled=True,
            )
        else:
            trade_fee = st.number_input(
                "手续费",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                key="trade_ticket_fee_manual",
            )
    with row4[1]:
        if trade_type == "买入":
            trade_tax = 0.0
            st.number_input("印花税", value=0.0, disabled=True, key="trade_ticket_tax_disabled")
        else:
            if auto_fee:
                trade_tax = st.number_input(
                    "印花税",
                    min_value=0.0,
                    value=float(fee_values["stamp_tax"]),
                    step=0.01,
                    format="%.2f",
                    key=f"trade_ticket_tax_auto_{amount}_{trade_qty}",
                    disabled=True,
                )
            else:
                trade_tax = st.number_input(
                    "印花税",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="trade_ticket_tax_manual",
                )
    with row4[2]:
        if auto_fee:
            trade_transfer_fee = st.number_input(
                "过户费",
                min_value=0.0,
                value=float(fee_values["transfer_fee"]),
                step=0.01,
                format="%.2f",
                key=f"trade_ticket_transfer_auto_{trade_type}_{amount}_{trade_qty}",
                disabled=True,
            )
        else:
            trade_transfer_fee = st.number_input(
                "过户费",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                key="trade_ticket_transfer_manual",
            )

    trade_note = st.text_area("心得备注", key="trade_ticket_note", height=90)

    total_fee = round(float(trade_fee) + float(trade_tax) + float(trade_transfer_fee), 2)
    st.caption(f"费用合计 {money_display(total_fee)}；买入不收印花税，卖出按成交金额自动计算印花税。")

    if trade_type == "卖出" and trade_qty > number_or(context.get("持仓数量"), 0):
        st.error("卖出数量大于当前持仓，不能保存。")

    if st.button("保存交易记录", type="primary", key="save_trade_ticket"):
        if not _data.clean_code(trade_code):
            st.error("请填写有效股票代码。")
            return
        if trade_price <= 0 or trade_qty <= 0:
            st.error("价格和数量必须大于0。")
            return
        if trade_type == "卖出" and trade_qty > number_or(context.get("持仓数量"), 0):
            st.error("卖出数量大于当前持仓，不能保存。")
            return
        if trade_type == "买入" and amount + total_fee > available_cash:
            st.warning("买入金额加费用超过当前可用现金，系统仍会记录，但规则审计会标记本金不足。")

        snapshot, conclusion, violation_tags = rule_snapshot_for_trade(
            trade_code,
            trade_name,
            trade_type,
            trade_time_text,
            float(trade_price),
            float(amount + total_fee),
            available_cash,
            watchlist,
        )
        new_trade = pd.DataFrame([{
            "代码": trade_code,
            "名称": trade_name,
            "类型": trade_type,
            "日期": trade_date.isoformat(),
            "时间": trade_time_text,
            "价格": trade_price,
            "数量": trade_qty,
            "金额": amount,
            "手续费": trade_fee,
            "印花税": 0.0 if trade_type == "买入" else trade_tax,
            "过户费": trade_transfer_fee,
            "总费用": total_fee,
            "原因": trade_reason,
            "备注": trade_note,
            "规则快照": snapshot,
            "规则结论": conclusion,
            "违规标签": violation_tags,
        }])
        save_trade_record(existing_trades, new_trade)
        st.success("交易记录已保存，持仓、资产和复盘已自动更新")
        st.rerun()


def render_trade_editor(trades: pd.DataFrame) -> None:
    st.markdown("#### 交易流水编辑")
    st.caption("持仓、现金、资产、复盘都由这里的买入/卖出记录自动推导。可以直接新增、修改或删除行。")
    editable = trades.copy()
    for column in TRADE_COLUMNS:
        if column not in editable:
            editable[column] = pd.NA
    edited = st.data_editor(
        editable[TRADE_COLUMNS],
        num_rows="dynamic",
        width="stretch",
        height=360,
        column_config={
            "类型": st.column_config.SelectboxColumn(options=["买入", "卖出"]),
            "价格": st.column_config.NumberColumn(format="%.3f", step=0.001),
            "数量": st.column_config.NumberColumn(step=100),
            "金额": st.column_config.NumberColumn(format="¥%.2f"),
            "手续费": st.column_config.NumberColumn(format="¥%.2f", step=0.01),
            "印花税": st.column_config.NumberColumn(format="¥%.2f", step=0.01),
            "过户费": st.column_config.NumberColumn(format="¥%.2f", step=0.01),
            "总费用": st.column_config.NumberColumn(format="¥%.2f", step=0.01),
            "规则快照": st.column_config.TextColumn(width="small"),
            "违规标签": st.column_config.TextColumn(width="small"),
        },
        key="trade_log_editor",
    )
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("保存交易记录", type="primary", use_container_width=True):
            save_trades(edited)
            st.session_state.trades = load_trades()
            st.session_state.holdings = portfolio_to_legacy_holdings(
                build_positions_from_trades(
                    st.session_state.trades,
                    watchlist=st.session_state.watchlist,
                    legacy_holdings=st.session_state.holdings,
                )
            )
            save_holdings(st.session_state.holdings)
            st.success("交易记录已保存，持仓/资产/复盘已联动更新")
            st.rerun()
    with col2:
        st.caption("卖出数量请不要超过当前持仓；系统会按移动平均成本法计算实现盈亏。")


# ── Initialize session state ──
if "watchlist" not in st.session_state:
    st.session_state.watchlist = initial_watchlist()
if "holdings" not in st.session_state:
    st.session_state.holdings = load_holdings()
if "trades" not in st.session_state:
    st.session_state.trades = load_trades()
if "settings" not in st.session_state:
    st.session_state.settings = load_settings()
if "reminder_computed" not in st.session_state:
    st.session_state.reminder_computed = False
if "manual_quote_refresh" not in st.session_state:
    st.session_state.manual_quote_refresh = 0
if "activity_log" not in st.session_state:
    st.session_state.activity_log = []
if "page_navigation" not in st.session_state:
    st.session_state.page_navigation = "今日看板"
pending_page_navigation = st.session_state.get("pending_page_navigation")
if pending_page_navigation:
    st.session_state.page_navigation = pending_page_navigation
    del st.session_state["pending_page_navigation"]
elif st.session_state.get("page_navigation") == "待买观察":
    st.session_state.page_navigation = "待买"
elif st.session_state.get("page_navigation") in {"交易复盘", "报告中心"}:
    st.session_state.page_navigation = "复盘报告"

# ── Sidebar ──
with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-brand">
          <div class="brand-row">
            <span class="brand-mark"></span>
            <div>
              <strong>{APP_NAME}</strong>
              <small>主板前排 · MA5 回踩 · 纪律工作台</small>
            </div>
          </div>
          <small>不连接券商，不自动下单，只做规则约束与复盘存证。</small>
          <span class="version-pill">{APP_VERSION}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    settings = st.session_state.settings.copy()
    mode_index = 0 if settings.get("account_mode", "模拟训练") == "模拟训练" else 1
    account_mode = st.selectbox(
        "账户模式",
        ["模拟训练", "实盘记录"],
        index=mode_index,
    )

    settings.update({
        "account_mode": account_mode,
    })
    if settings != st.session_state.settings:
        st.session_state.settings = settings
        save_settings(settings)
        st.rerun()

    st.divider()
    if st.button("刷新行情 / 重新计算", key="sidebar_global_refresh", use_container_width=True):
        trigger_global_refresh()
    st.divider()
    st.markdown('<div class="sidebar-section-title">纪律罗盘</div>', unsafe_allow_html=True)
    page = st.radio(
        "导航",
        ["今日看板", "数据导入", "股票分组", "盘中观察", "待买", "交易记录", "持仓监控", "资产看板", "复盘报告", "系统设置"],
        label_visibility="collapsed",
        key="page_navigation",
    )
    render_activity_log()

page = st.session_state.get("page_navigation", "今日看板")
settings = st.session_state.settings.copy()
initial_capital = (
    settings.get("simulation_capital", 10000)
    if account_mode == "模拟训练"
    else settings.get("live_capital", 5000)
)

# ── Realtime quote refresh ──
market_now = china_now()
trading_now = is_a_share_trading_time(market_now)
force_quote_refresh = bool(st.session_state.get("force_quote_refresh", False))
if "force_quote_refresh" in st.session_state:
    del st.session_state["force_quote_refresh"]

quote_codes = sorted(
    set(st.session_state.watchlist["代码"].dropna().astype(str))
    | set(st.session_state.holdings["代码"].dropna().astype(str))
)
quote_snapshot = load_quote_snapshot()
last_refresh = load_last_refresh()
quote_status = "暂无行情快照，使用本地数据"
if not quote_snapshot.empty:
    st.session_state.watchlist = merge_quotes_into_watchlist(
        st.session_state.watchlist,
        quote_snapshot,
    )[WATCHLIST_COLUMNS]
    st.session_state.holdings = merge_quotes_into_holdings(
        st.session_state.holdings,
        quote_snapshot,
    )[HOLDING_COLUMNS]
    snapshot_times = quote_snapshot["更新时间"].dropna().astype(str)
    snapshot_sources = quote_snapshot["来源"].dropna().astype(str)
    snapshot_states = quote_snapshot["状态"].dropna().astype(str)
    refresh_time = str(last_refresh.get("更新时间") or (snapshot_times.max() if not snapshot_times.empty else ""))
    refresh_source = str(last_refresh.get("来源") or (snapshot_sources.iloc[0] if not snapshot_sources.empty else "行情快照"))
    refresh_state = str(last_refresh.get("状态") or (snapshot_states.iloc[0] if not snapshot_states.empty else "缓存"))
    quote_status = f"行情快照 {refresh_time}｜{refresh_source}｜{refresh_state}"

if quote_codes and force_quote_refresh:
    quotes = cached_realtime_quotes(
        tuple(quote_codes),
        settings.get("quote_source", "自动切换"),
        int(st.session_state.get("manual_quote_refresh", 0)),
    )
    if not quotes.empty:
        quote_message = quotes.attrs.get("message") or quotes.attrs.get("source") or "行情已更新"
        quote_source = quotes.attrs.get("source") or settings.get("quote_source", "自动切换")
        quote_state = "部分成功" if "未获取" in str(quote_message) else "成功"
        quotes_for_snapshot = quotes.copy()
        if not quote_snapshot.empty:
            fresh_codes = set(quotes_for_snapshot["代码"].dropna().astype(str))
            active_codes = set(quote_codes)
            snapshot_codes = quote_snapshot["代码"].astype(str)
            cached_fallback = quote_snapshot[
                snapshot_codes.isin(active_codes) & ~snapshot_codes.isin(fresh_codes)
            ].copy()
            if not cached_fallback.empty:
                cached_fallback["状态"] = "缓存兜底"
                quotes_for_snapshot = pd.concat([quotes_for_snapshot, cached_fallback], ignore_index=True)
        save_quote_snapshot(
            quotes_for_snapshot,
            source=str(quote_source),
            status=quote_state,
            message=str(quote_message),
        )
        st.session_state.watchlist = merge_quotes_into_watchlist(
            st.session_state.watchlist,
            quotes,
        )[WATCHLIST_COLUMNS]
        st.session_state.holdings = merge_quotes_into_holdings(
            st.session_state.holdings,
            quotes,
        )[HOLDING_COLUMNS]
        save_watchlist(st.session_state.watchlist)
        save_holdings(st.session_state.holdings)
        st.session_state.reminder_computed = False
        st.session_state.last_quote_time = market_now.strftime("%H:%M:%S")
        quote_status = f"{quote_message} · {st.session_state.last_quote_time}"
    else:
        quote_error = quotes.attrs.get("message", "未知原因")
        if not quote_snapshot.empty:
            quote_status = f"行情抓取失败，使用快照缓存：{quote_error}"
        else:
            quote_status = f"行情抓取失败，且暂无快照缓存：{quote_error}"
elif st.session_state.get("last_quote_time"):
    quote_status = f"最近行情更新 {st.session_state.last_quote_time}"

# ── Portfolio / account from trade log ──
portfolio_positions = build_positions_from_trades(
    st.session_state.trades,
    watchlist=st.session_state.watchlist,
    legacy_holdings=st.session_state.holdings,
)
if not portfolio_positions.empty:
    st.session_state.holdings = portfolio_to_legacy_holdings(portfolio_positions)
    save_holdings(st.session_state.holdings)

portfolio_account = account_state_from_trades(
    st.session_state.trades,
    portfolio_positions,
    float(initial_capital),
    account_mode,
)
account = {
    "available_cash": float(portfolio_account["当前现金"]),
    "equity": float(portfolio_account["当前总资产"]),
    "market_value": float(portfolio_account["持仓市值"]),
    "floating_pnl": float(portfolio_account["浮动盈亏"]),
}
available_cash = account["available_cash"]
funds_source = "交易流水自动计算"

max_position_ratio = float(settings.get("max_position_pct", 100)) / 100

# ── Enrich watchlist ──
watchlist = enrich_watchlist(
    st.session_state.watchlist,
    available_cash,
    max_position_ratio=max_position_ratio,
)

# Compute reminders if not done yet or cash changed
cash_changed = st.session_state.get("last_reminder_cash") != available_cash
if cash_changed or not st.session_state.reminder_computed or "提醒" not in watchlist.columns:
    reminder_data = compute_all_reminders(watchlist, available_cash)
    watchlist = apply_reminder_columns(watchlist, reminder_data)
    st.session_state.watchlist = watchlist[WATCHLIST_COLUMNS]
    st.session_state.reminder_computed = True
    st.session_state.last_reminder_cash = available_cash

# Pipeline views
watchlist = build_pipeline(watchlist)
held_codes = set(portfolio_positions["代码"].dropna().astype(str)) if not portfolio_positions.empty else set()
if held_codes and "代码" in watchlist:
    held_mask = watchlist["代码"].astype(str).isin(held_codes)
    watchlist.loc[held_mask, "is_pinned"] = True
watchlist_changed = False
for column in ["状态", "分组", "流程阶段", "筛选原因", "提醒", "规则状态", "is_pinned"]:
    if column in watchlist.columns and column in st.session_state.watchlist.columns:
        old_values = st.session_state.watchlist[column].reset_index(drop=True).fillna("")
        new_values = watchlist[column].reset_index(drop=True).fillna("")
        if not old_values.equals(new_values):
            st.session_state.watchlist[column] = watchlist[column].values
            watchlist_changed = True
if watchlist_changed:
    save_watchlist(st.session_state.watchlist)
views = pipeline_views(watchlist)
if held_codes:
    for view_name in list(views.keys()):
        views[view_name] = views[view_name][
            ~views[view_name]["代码"].astype(str).isin(held_codes)
        ].copy()
counts = {name: len(frame) for name, frame in views.items()}

valid_pages = {"今日看板", "数据导入", "股票分组", "盘中观察", "待买", "交易记录", "持仓监控", "资产看板", "复盘报告", "系统设置"}
if page not in valid_pages:
    page = "今日看板"
    st.session_state.page_navigation = page

# ══════════════════════════════════════════════════════════════════
# PAGE: 今日看板
# ══════════════════════════════════════════════════════════════════
if page == "今日看板":
    page_header(APP_NAME, "今天只确认该补什么、看什么、买不买、记不记。")

    missing_history = int((watchlist.get("history_status", pd.Series("", index=watchlist.index)) == "缺少历史K线").sum())
    today_buy_watch = len(views["待买观察"])
    risk_holding_count = count_risk_positions(portfolio_positions)
    today_key = date.today().isoformat()
    trades_today = st.session_state.trades[
        pd.to_datetime(st.session_state.trades.get("日期", pd.Series(dtype=str)), errors="coerce")
        == pd.Timestamp(date.today())
    ] if not st.session_state.trades.empty else pd.DataFrame()
    unreviewed_trades = len(trades_today) if len(trades_today) and not load_report_note("daily", today_key) else 0

    top_cols = st.columns([1, 3])
    with top_cols[0]:
        if st.button("刷新行情 / 重新计算", type="primary", use_container_width=True):
            trigger_global_refresh()
    top_cols[1].caption(f"{quote_status} · {funds_source} · 页面切换不自动联网，盘中手动轻刷新。")

    render_dashboard_brief(
        today_key,
        quote_status,
        funds_source,
        today_buy_watch,
        missing_history,
        risk_holding_count,
        unreviewed_trades,
    )

    st.markdown("#### 账户状态")
    account_cols = st.columns(4)
    account_cols[0].metric("可用现金", money_display(available_cash))
    account_cols[1].metric("账户权益", money_display(account["equity"]))
    account_cols[2].metric("持仓市值", money_display(account["market_value"]))
    account_cols[3].metric("浮动盈亏", money_display(account["floating_pnl"]))

    st.markdown("#### 今日动作")
    action_cols = st.columns(6)
    action_cols[0].metric("初筛数量", counts.get("初筛", 0))
    action_cols[1].metric("观察数量", counts.get("观察", 0))
    action_cols[2].metric("待买数量", counts.get("待买", 0))
    action_cols[3].metric("持仓数量", len(portfolio_positions))
    action_cols[4].metric("缺K线数量", missing_history)
    action_cols[5].metric("风险持仓数量", risk_holding_count)

    st.markdown("#### 今日待处理事项")
    todo_frame = pd.DataFrame([
        {"事项": "需要补K线", "数量": missing_history, "处理入口": "数据导入"},
        {"事项": "待买确认", "数量": today_buy_watch, "处理入口": "待买"},
        {"事项": "持仓风险", "数量": risk_holding_count, "处理入口": "持仓监控"},
        {"事项": "今日未复盘交易", "数量": unreviewed_trades, "处理入口": "复盘报告"},
    ])
    st.dataframe(todo_frame, width="stretch", hide_index=True, height=170, row_height=28)

    st.markdown("#### 快捷按钮")
    quick_cols = st.columns(7)
    with quick_cols[0]:
        if st.button("刷新行情", key="dash_refresh_quotes", use_container_width=True):
            trigger_global_refresh()
    with quick_cols[1]:
        nav_button("生成股票池", "数据导入", key="dash_step_import")
    with quick_cols[2]:
        nav_button("补K线", "数据导入", key="dash_step_history")
    with quick_cols[3]:
        nav_button("去观察", "股票分组", key="dash_step_focus")
    with quick_cols[4]:
        nav_button("去待买", "待买", key="dash_step_buy")
    with quick_cols[5]:
        nav_button("记录交易", "交易记录", key="dash_step_trade")
    with quick_cols[6]:
        nav_button("写复盘", "复盘报告", key="dash_step_review")

    with st.expander("查看强势回踩交易规则", expanded=False):
        render_trading_mode_panel(available_cash)

    refresh_mode = settings.get("quote_refresh_mode", "手动")
    if refresh_mode != "手动":
        seconds = 30 if refresh_mode == "30秒" else int(settings.get("quote_refresh_seconds", 60))
        schedule_auto_refresh(page == "今日看板" and trading_now, seconds)

# ══════════════════════════════════════════════════════════════════
# PAGE: 数据导入
# ══════════════════════════════════════════════════════════════════
elif page == "数据导入":
    page_header("数据导入", "上传或自动生成股票池，补齐历史K线。")

    st.markdown("#### 自动生成今日股票池")
    st.caption("固定生成当前时点沪深主板成交额前30：600/601/603/605/000/001/002，排除 ST、创业板、科创板、北交所、京东方A。每次生成都会替换当前初筛池，旧批次只归档不累积。")
    auto_cols = st.columns([1, 1, 2])
    with auto_cols[0]:
        st.metric("股票数量", "30")
        auto_pool_size = 30
    with auto_cols[1]:
        auto_fetch_history = st.checkbox("生成后补历史K线", value=True)
    with auto_cols[2]:
        st.write("")
        st.write("")
        if st.button("自动生成今日股票池", type="primary", use_container_width=True):
            with st.spinner("正在获取全市场行情并生成股票池..."):
                auto_pool = fetch_auto_stock_pool(int(auto_pool_size), source="自动切换")
            if auto_pool.empty:
                error_msg = auto_pool.attrs.get("message", "行情源没有返回数据")
                st.error(f"自动股票池生成失败：{error_msg}。请手动上传同花顺股票池。")
            else:
                st.info(
                    f"自动股票池来源：{auto_pool.attrs.get('source', '自动切换')} · "
                    f"{auto_pool.attrs.get('message', '已生成')}"
                )
                settings["auto_pool_size"] = 30
                st.session_state.settings = settings
                save_settings(settings)
                auto_name = f"{date.today().isoformat()}_自动股票池.csv"
                auto_bytes = auto_pool.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                uploaded_auto = InMemoryUpload(auto_name, auto_bytes)
                _run_analysis(uploaded_auto, standardize_candidates(auto_pool), fetch_missing=auto_fetch_history)
                st.rerun()

    st.markdown("#### 扫描新进成交额前30")
    scan_cols = st.columns([1, 3])
    with scan_cols[0]:
        if st.button("扫描新进前30", use_container_width=True):
            with st.spinner("正在扫描实时成交额前30..."):
                st.session_state.turnover_scan_result = scan_turnover_changes_for_watchlist(st.session_state.watchlist, 30)
    with scan_cols[1]:
        result = st.session_state.get("turnover_scan_result")
        if result:
            if result.get("success"):
                st.success(str(result.get("message", "扫描完成")))
                metric_cols = st.columns(3)
                metric_cols[0].metric("新进", len(result.get("new", pd.DataFrame())))
                metric_cols[1].metric("跌出", len(result.get("dropped", pd.DataFrame())))
                metric_cols[2].metric("排名变化", len(result.get("rank_changed", pd.DataFrame())))
            else:
                st.warning(str(result.get("message", "扫描失败")))

    result = st.session_state.get("turnover_scan_result")
    if result and result.get("success"):
        tabs = st.tabs(["新进前30", "跌出前30", "排名变化"])
        with tabs[0]:
            new_frame = result.get("new", pd.DataFrame())
            if isinstance(new_frame, pd.DataFrame) and not new_frame.empty:
                render_table(new_frame[["代码", "名称", "现价", "涨跌幅%", "成交额", "成交额排名"]], 220)
            else:
                st.caption("暂无新进。")
        with tabs[1]:
            dropped_frame = result.get("dropped", pd.DataFrame())
            if isinstance(dropped_frame, pd.DataFrame) and not dropped_frame.empty:
                display_cols = [col for col in ["代码", "名称", "pool_rank_at_generation", "成交额排名", "is_pinned", "流程阶段"] if col in dropped_frame.columns]
                render_table(dropped_frame[display_cols], 220)
            else:
                st.caption("暂无跌出。")
        with tabs[2]:
            changed_frame = result.get("rank_changed", pd.DataFrame())
            if isinstance(changed_frame, pd.DataFrame) and not changed_frame.empty:
                render_table(changed_frame, 220)
            else:
                st.caption("暂无排名变化。")

    st.divider()

    # ── 上传股票池 ──
    st.markdown("#### 上传同花顺股票池")
    st.caption("从同花顺导出的强势回踩初筛30只股票 Excel / CSV，直接上传这里。")
    uploaded = st.file_uploader("选择同花顺导出的 Excel / CSV", type=["xlsx", "xls", "csv"])
    if uploaded:
        try:
            incoming = standardize_candidates(read_tabular(uploaded, uploaded.name))
            st.success(f"✅ 识别到 {len(incoming)} 只有效股票")

            info_cols = st.columns(3)
            info_cols[0].metric("文件名", uploaded.name)
            info_cols[1].metric("股票数量", len(incoming))
            detected = [c for c in ["代码", "名称", "现价", "涨跌幅%", "成交额"] if c in incoming.columns]
            info_cols[2].metric("识别字段", f"{len(detected)}/{len(['代码','名称','现价','涨跌幅%','成交额'])}")

            render_table(incoming[["代码", "名称", "现价", "涨跌幅%", "成交额", "成交额排名"]], 300)

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("一键分析股票池", type="primary", use_container_width=True):
                    _run_analysis(uploaded, incoming, fetch_missing=False)
                    st.rerun()
            with btn_col2:
                if st.button("一键分析并补全历史K线", type="primary", use_container_width=True):
                    _run_analysis(uploaded, incoming, fetch_missing=True)
                    st.rerun()

        except Exception as exc:
            st.error(f"文件未能识别：{exc}")
    else:
        if not st.session_state.watchlist.empty:
            st.info("已上传过股票池，当前数据来自本地缓存。")
        else:
            st.info("请上传同花顺导出的股票池 Excel / CSV 文件开始分析。")

    st.divider()

    # ── 历史K线状态 ──
    st.markdown("#### 历史K线诊断")
    codes_list = watchlist["代码"].dropna().astype(str).unique()
    total_stocks = len(codes_list)
    diagnostics = cached_history_diagnostics(tuple(sorted(codes_list)))
    with_history = sum(1 for item in diagnostics.values() if item.get("history_status") == "已有缓存")
    missing_count = sum(1 for item in diagnostics.values() if item.get("history_status") == "缺少历史K线")
    failed_count = len(st.session_state.get("history_failed_codes", []))
    insufficient_count = sum(1 for item in diagnostics.values() if item.get("history_status") == "数据不足")
    stale_count = sum(1 for item in diagnostics.values() if item.get("history_status") == "缓存过旧")

    hist_cols = st.columns(6)
    hist_cols[0].metric("股票总数", total_stocks)
    hist_cols[1].metric("已有历史K线", with_history)
    hist_cols[2].metric("缺少历史K线", missing_count)
    hist_cols[3].metric("获取失败", failed_count)
    hist_cols[4].metric("数据不足", insufficient_count)
    hist_cols[5].metric("缓存过旧", stale_count)

    diag_rows = []
    fetch_statuses = st.session_state.get("history_fetch_statuses", {})
    for code in codes_list:
        row = diagnostics.get(str(code), diagnose_history(str(code))).copy()
        if str(code) in fetch_statuses:
            row["history_status"] = fetch_statuses[str(code)].get("status", row["history_status"])
            row["history_error"] = fetch_statuses[str(code)].get("error", row["history_error"])
        name_match = watchlist[watchlist["代码"].astype(str) == str(code)]
        diag_rows.append({
            "代码": str(code),
            "名称": name_match.iloc[0].get("名称", "") if not name_match.empty else "",
            "状态": row.get("history_status", ""),
            "历史行数": row.get("history_rows", 0),
            "最后日期": row.get("history_last_date", ""),
            "失败原因": row.get("history_error", ""),
            "操作建议": history_action_advice(str(row.get("history_status", ""))),
        })
    diag_frame = pd.DataFrame(diag_rows)
    if not diag_frame.empty:
        render_columns(
            diag_frame,
            ["代码", "名称", "状态", "历史行数", "最后日期", "失败原因", "操作建议"],
            260,
        )

    hist_actions = st.columns(3)
    with hist_actions[0]:
        if st.button("只补缺失股票", type="primary", use_container_width=True):
            if settings.get("history_source", "本地缓存 + AKShare") == "仅本地缓存":
                st.warning("当前历史K线数据源为“仅本地缓存”。如需自动补历史K线，请在系统设置中改为“本地缓存 + AKShare”。")
            else:
                summary = fetch_history_for_codes(list(codes_list), only_missing=True, statuses_to_fetch={"缺少历史K线"})
                _recompute_reminders()
                st.success(
                    f"补全完成：成功 {summary['fetched']} 只，失败 {summary['failed']} 只，数据不足 {summary['insufficient']} 只。"
                )
                st.rerun()
    with hist_actions[1]:
        if st.button("重新获取失败股票", use_container_width=True):
            failed_codes = st.session_state.get("history_failed_codes", [])
            if not failed_codes:
                st.info("当前没有失败股票需要重试。")
            elif settings.get("history_source", "本地缓存 + AKShare") == "仅本地缓存":
                st.warning("当前历史K线数据源为“仅本地缓存”。")
            else:
                summary = fetch_history_for_codes(list(failed_codes), only_missing=False)
                _recompute_reminders()
                st.success(
                    f"重试完成：成功 {summary['fetched']} 只，失败 {summary['failed']} 只，数据不足 {summary['insufficient']} 只。"
                )
                st.rerun()
    with hist_actions[2]:
        if st.button("强制重抓当前股票池全部K线", use_container_width=True):
            if settings.get("history_source", "本地缓存 + AKShare") == "仅本地缓存":
                st.warning("当前历史K线数据源为“仅本地缓存”。")
            else:
                summary = fetch_history_for_codes(list(codes_list), only_missing=False)
                _recompute_reminders()
                st.success(
                    f"强制重抓完成：成功 {summary['fetched']} 只，失败 {summary['failed']} 只，数据不足 {summary['insufficient']} 只。"
                )
                st.rerun()

    st.divider()

    # ── 导出结果 ──
    st.markdown("#### 导出结果")
    export_cols = st.columns(3)
    with export_cols[0]:
        if Path("data/processed/latest_analysis.csv").exists():
            with open("data/processed/latest_analysis.csv", "rb") as f:
                st.download_button(
                    "下载最新分析结果 CSV",
                    f.read(),
                    file_name=f"强势回踩_分析结果_{date.today().isoformat()}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
    with export_cols[1]:
        watch_buy = views["待买"]
        if not watch_buy.empty:
            csv_data = watch_buy.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "下载待买 CSV",
                csv_data,
                file_name=f"强势回踩_待买_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with export_cols[2]:
        watch_obs = views["观察"]
        if not watch_obs.empty:
            csv_data = watch_obs.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                "下载观察池 CSV",
                csv_data,
                file_name=f"强势回踩_观察池_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
            )



# ══════════════════════════════════════════════════════════════════
# PAGE: 股票分组
# ══════════════════════════════════════════════════════════════════
elif page == "股票分组":
    page_header("股票分组", "按初筛、观察、待买三组盯盘，持仓单独进入持仓监控。")

    search_cols = st.columns([2, 3])
    with search_cols[0]:
        stock_search_query = st.text_input(
            "搜索股票",
            value="",
            placeholder="输入代码或名称",
            key="stock_group_search",
        )
    search_cols[1].caption("搜索只影响当前页面展示，不修改股票池分组和规则计算结果。")

    group_tabs = st.tabs([
        f"初筛（{counts.get('初筛', 0)}）",
        f"观察（{counts.get('观察', 0)}）",
        f"待买（{counts.get('待买', 0)}）",
    ])

    tab_specs = [
        ("初筛", views["初筛"], STOCK_TABLE_COLUMNS, "stock_group_initial"),
        ("观察", views["观察"], STOCK_TABLE_COLUMNS, "stock_group_observe"),
        ("待买", views["待买"], STOCK_TABLE_COLUMNS, "stock_group_buy"),
    ]
    for tab, (label, frame, columns, key) in zip(group_tabs, tab_specs):
        with tab:
            visible_frame = filter_stock_search(frame, stock_search_query)
            if frame.empty:
                st.info(f"暂无{label}股票。")
            elif visible_frame.empty:
                st.info("没有匹配当前搜索条件的股票。")
            selected = render_workbench_table(visible_frame, columns, key=key, height=500)
            render_kline_for_selection(selected)


# ══════════════════════════════════════════════════════════════════
# PAGE: 盘中观察
# ══════════════════════════════════════════════════════════════════
elif page == "盘中观察":
    page_header("盘中观察", "盘中确认回踩是否成立，只做规则提醒和手动确认。")

    refresh_cols = st.columns([1, 1, 3])
    with refresh_cols[0]:
        if st.button("刷新行情", type="primary", use_container_width=True):
            trigger_global_refresh()
    with refresh_cols[1]:
        nav_button("去待买确认", "待买", key="intraday_go_buy")
    refresh_cols[2].caption(
        f"{quote_status} · 数据源：{settings.get('quote_source', '自动切换')} · "
        "开源行情源稳定性不如商业终端，异常时请以同花顺/券商软件为准。"
    )

    intraday_parts = []
    if not views["待买观察"].empty:
        intraday_parts.append(views["待买"].assign(盯盘阶段="待买观察"))
    if not views["观察未待买"].empty:
        intraday_parts.append(views["观察未待买"].assign(盯盘阶段="观察"))

    if intraday_parts:
        intraday = pd.concat(intraday_parts, ignore_index=True)
        intraday["距MA5绝对值"] = pd.to_numeric(intraday["MA5偏离率%"], errors="coerce").abs()
        intraday = intraday.sort_values(["盯盘阶段", "距MA5绝对值"], ascending=[True, True])

        metric_cols = st.columns(5)
        metric_cols[0].metric("待买观察", len(views["待买观察"]))
        metric_cols[1].metric("观察", len(views["观察"]))
        metric_cols[2].metric("继续观察", len(views["继续观察"]))
        metric_cols[3].metric("偏高不追", len(views["偏高不追"]))
        metric_cols[4].metric("未达规则", len(views["未达规则"]))

        selected_intraday = render_workbench_table(
            intraday,
            ["盯盘阶段", *STOCK_TABLE_COLUMNS],
            key="intraday_workbench_table",
            height=560,
        )
        render_kline_for_selection(selected_intraday)
    else:
        st.info("暂无观察池或待买观察股票。请先生成/导入股票池并分析。")

    refresh_mode = settings.get("quote_refresh_mode", "手动")
    if refresh_mode != "手动":
        seconds = 30 if refresh_mode == "30秒" else int(settings.get("quote_refresh_seconds", 60))
        schedule_auto_refresh(trading_now, seconds)


# ══════════════════════════════════════════════════════════════════
# PAGE: 待买
# ══════════════════════════════════════════════════════════════════
elif page == "待买":
    page_header("待买", "盘中手动确认待买观察是否仍满足规则。")

    buy_candidates = views["待买"]
    if not buy_candidates.empty:
        selected_buy_row = render_workbench_table(
            buy_candidates,
            STOCK_TABLE_COLUMNS,
            key="buy_page_workbench_table",
            height=420,
        )
        render_kline_for_selection(selected_buy_row)
        st.divider()
        st.markdown("#### 买入操作")
        st.caption("确认后只写入交易流水，持仓和资产由流水自动生成。")
        default_buy_code = str(selected_buy_row.get("代码")) if selected_buy_row is not None else None
        buy_codes = buy_candidates["代码"].astype(str).tolist()
        default_index = buy_codes.index(default_buy_code) if default_buy_code in buy_codes else 0
        buy_code = st.selectbox("选择股票", buy_codes, index=default_index)
        if buy_code:
            selected = buy_candidates[buy_candidates["代码"] == buy_code].iloc[0]
            if str(selected.get("本金是否可买", "")) != "可以买":
                lot_cost = number_or(selected.get("一手金额"), 0)
                st.warning(
                    f"{selected['名称']} 一手金额 ¥{lot_cost:,.2f}，"
                    f"当前可用现金 ¥{available_cash:,.2f}，暂时不能记录交易。"
                )
            with st.form("buy_form"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    buy_price = st.number_input(
                        "买入价",
                        value=float(selected["现价"]),
                        step=0.001,
                        format="%.3f",
                    )
                with col2:
                    buy_qty = st.number_input("买入数量（股）", min_value=100, step=100, value=100)
                with col3:
                    buy_date = st.date_input("买入日期", date.today())
                with col4:
                    buy_time = st.text_input("买入时间", value="", placeholder="例如 09:45")
                buy_fee_values = calculate_trade_fees("买入", buy_price, buy_qty, settings)
                st.caption(
                    f"预估费用：手续费 {money_display(buy_fee_values['commission'])}，"
                    f"印花税 {money_display(0)}，过户费 {money_display(buy_fee_values['transfer_fee'])}"
                )

                if st.form_submit_button("盘中手动确认", type="primary"):
                    buy_qty = int(buy_qty)
                    buy_amount = round(float(buy_price) * buy_qty, 2)
                    buy_fee_values = calculate_trade_fees("买入", buy_price, buy_qty, settings)
                    total_cost = buy_amount + buy_fee_values["total_fee"]
                    if total_cost > available_cash:
                        st.error(f"买入金额加费用 {money_display(total_cost)} 超过当前可用现金 {money_display(available_cash)}")
                    else:
                        code = str(selected["代码"])
                        name = str(selected["名称"])
                        note = "待买确认：强势股回踩 MA5 不破"
                        snapshot, conclusion, violation_tags = rule_snapshot_for_trade(
                            code,
                            name,
                            "买入",
                            buy_time,
                            float(buy_price),
                            float(total_cost),
                            available_cash,
                            watchlist,
                        )
                        new_trade = pd.DataFrame([{
                            "代码": code,
                            "名称": name,
                            "类型": "买入",
                            "日期": buy_date.isoformat(),
                            "时间": buy_time,
                            "价格": float(buy_price),
                            "数量": buy_qty,
                            "金额": buy_amount,
                            "手续费": buy_fee_values["commission"],
                            "印花税": 0.0,
                            "过户费": buy_fee_values["transfer_fee"],
                            "总费用": buy_fee_values["total_fee"],
                            "原因": "待买观察确认",
                            "备注": note,
                            "规则快照": snapshot,
                            "规则结论": conclusion,
                            "违规标签": violation_tags,
                        }])
                        save_trade_record(load_trades(), new_trade)
                        st.session_state.buy_success_message = (
                            f"已买入 {name}（{buy_qty}股 @ {float(buy_price):.3f}），"
                            "持仓已由交易流水自动生成。"
                        )
                        st.session_state.pending_page_navigation = "持仓监控"
                        st.rerun()
    else:
        st.info("暂无待买股票。请先在「数据导入」上传股票池并点击分析。")

    st.divider()
    watch_pool = views["观察未待买"]
    if not watch_pool.empty:
        with st.expander(f"继续观察（{len(watch_pool)}只）"):
            render_columns(
                watch_pool,
                ["代码", "名称", "现价", "涨跌幅%", "MA5偏离率%",
                 "一手金额", "流程阶段", "提醒"],
                300,
            )


# ══════════════════════════════════════════════════════════════════
# PAGE: 交易记录
# ══════════════════════════════════════════════════════════════════
elif page == "交易记录":
    page_header("交易记录", "记录真实/模拟买卖，系统自动更新资产和持仓。")

    flow = st.session_state.trades.copy()
    trade_positions = build_positions_from_trades(
        flow,
        watchlist=st.session_state.watchlist,
        legacy_holdings=st.session_state.holdings,
    )
    trade_account = account_state_from_trades(flow, trade_positions, float(initial_capital), account_mode)

    kpi_cols = st.columns(5)
    kpi_cols[0].metric("当前现金", money_display(float(trade_account["当前现金"])))
    kpi_cols[1].metric("持仓市值", money_display(float(trade_account["持仓市值"])))
    kpi_cols[2].metric("总资产", money_display(float(trade_account["当前总资产"])))
    kpi_cols[3].metric("已实现盈亏", f"¥{float(trade_account['已实现盈亏']):,.2f}")
    kpi_cols[4].metric("总收益率", f"{float(trade_account['总收益率%']):+.2f}%")

    render_trade_form(st.session_state.trades)
    with st.expander("交易流水明细编辑", expanded=False):
        render_trade_editor(flow)

    st.divider()
    st.markdown("#### 由交易记录自动生成的当前持仓")
    if trade_positions.empty:
        st.info("还没有未平仓持仓。录入买入记录后，这里会自动出现。")
    else:
        render_columns(
            trade_positions,
            ["代码", "名称", "数量", "平均成本", "当前价", "市值", "浮动盈亏",
             "浮动盈亏%", "MA5", "MA5偏离率%", "持仓天数", "操作提醒"],
            420,
        )


# ══════════════════════════════════════════════════════════════════
# PAGE: 持仓监控
# ══════════════════════════════════════════════════════════════════
elif page == "持仓监控":
    page_header("持仓监控", "检查是否跌破MA5或远离MA5。")

    buy_success_message = st.session_state.get("buy_success_message")
    if buy_success_message:
        st.success(buy_success_message)
        del st.session_state["buy_success_message"]
    price_update_message = st.session_state.get("holding_price_update_message")
    if price_update_message:
        level, message = price_update_message
        if level == "success":
            st.success(message)
        else:
            st.warning(message)
        del st.session_state["holding_price_update_message"]

    if not st.session_state.holdings.empty:
        display_holdings = st.session_state.holdings.copy()
        for numeric_column in ["买入价", "数量", "当前价", "MA5", "跌破MA5天数"]:
            if numeric_column in display_holdings.columns:
                display_holdings[numeric_column] = pd.to_numeric(
                    display_holdings[numeric_column],
                    errors="coerce",
                )
        display_holdings["市值"] = display_holdings["当前价"] * display_holdings["数量"]
        display_holdings["成本"] = display_holdings["买入价"] * display_holdings["数量"]
        display_holdings["盈亏"] = display_holdings["市值"] - display_holdings["成本"]
        display_holdings["盈亏%"] = (display_holdings["盈亏"] / display_holdings["成本"] * 100).round(2)
        display_holdings["MA5偏离率%"] = display_holdings.apply(
            lambda row: ma5_deviation(row.get("当前价"), row.get("MA5")),
            axis=1,
        )
        display_holdings["纪律建议"] = display_holdings.apply(
            lambda row: holding_advice(
                row.get("当前价"),
                row.get("MA5"),
                row.get("数量"),
                row.get("跌破MA5天数", 0),
                row.get("可卖数量", row.get("数量")),
                row.get("持仓天数"),
            ),
            axis=1,
        )

        total_cost = display_holdings["成本"].sum()
        total_value = display_holdings["市值"].sum()
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("持仓数量", len(st.session_state.holdings))
        col2.metric("总成本", f"¥{total_cost:,.2f}")
        col3.metric("总市值", f"¥{total_value:,.2f}")
        col4.metric("总盈亏", f"¥{total_pnl:,.2f}", f"{total_pnl_pct:.2f}%")

        st.divider()
        card_html = ['<div class="holding-grid">']
        for _, row in display_holdings.iterrows():
            card_html.append(
                f"""
                <div class="holding-card">
                  <h3>{row.get('名称', '')} / {row.get('代码', '')}</h3>
                  <div class="mini-grid">
                    <span>数量</span><b>{int(number_or(row.get('数量'), 0))}</b>
                    <span>平均成本</span><b>{number_or(row.get('买入价'), 0):.3f}</b>
                    <span>当前价</span><b>{number_or(row.get('当前价'), 0):.3f}</b>
                    <span>市值</span><b>{money_display(row.get('市值'))}</b>
                    <span>浮动盈亏</span><b>{money_display(row.get('盈亏'))}</b>
                    <span>MA5偏离率</span><b>{percent_display(row.get('MA5偏离率%'))}</b>
                  </div>
                  <p class="compact-note">{row.get('纪律建议', '')}</p>
                </div>
                """
            )
        card_html.append("</div>")
        st.markdown("".join(card_html), unsafe_allow_html=True)

        holding_workbench = display_holdings.rename(
            columns={"买入价": "平均成本", "盈亏": "浮动盈亏", "盈亏%": "浮动盈亏%", "纪律建议": "操作提醒"}
        )
        selected_holding_monitor = render_workbench_table(
            holding_workbench,
            HOLDING_TABLE_COLUMNS,
            key="holding_monitor_workbench_table",
            height=300,
        )
        render_kline_for_selection(selected_holding_monitor)

        st.divider()
        st.markdown("#### 卖出操作")
        sell_code = st.selectbox("选择卖出股票", display_holdings["代码"].tolist(), key="sell_code")
        if sell_code:
            sell_holding = display_holdings[display_holdings["代码"] == sell_code].iloc[0]
            with st.form("sell_form"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    sell_price = st.number_input(
                        "卖出价",
                        value=float(sell_holding["当前价"]),
                        step=0.001,
                        format="%.3f",
                    )
                with col2:
                    sell_qty = st.number_input(
                        "卖出数量",
                        min_value=100,
                        max_value=int(sell_holding["数量"]),
                        step=100,
                        value=int(sell_holding["数量"]),
                    )
                with col3:
                    sell_date = st.date_input("卖出日期", date.today())
                with col4:
                    sell_time = st.text_input("卖出时间", value="", placeholder="例如 14:45")
                sell_reason = st.text_input("卖出原因", value=str(sell_holding.get("纪律建议", "")))
                sell_fee_values = calculate_trade_fees("卖出", sell_price, sell_qty, settings)
                st.caption(
                    f"预估费用：手续费 {money_display(sell_fee_values['commission'])}，"
                    f"印花税 {money_display(sell_fee_values['stamp_tax'])}，过户费 {money_display(sell_fee_values['transfer_fee'])}"
                )

                if st.form_submit_button("确认卖出", type="primary"):
                    if int(sell_qty) > int(sell_holding["数量"]):
                        st.error("卖出数量大于当前持仓，不能保存。")
                        st.stop()
                    new_trade = pd.DataFrame([{
                        "代码": sell_holding["代码"],
                        "名称": sell_holding["名称"],
                        "类型": "卖出",
                        "日期": sell_date.isoformat(),
                        "时间": sell_time,
                        "价格": sell_price,
                        "数量": int(sell_qty),
                        "金额": round(float(sell_price) * int(sell_qty), 2),
                        "手续费": sell_fee_values["commission"],
                        "印花税": sell_fee_values["stamp_tax"],
                        "过户费": sell_fee_values["transfer_fee"],
                        "总费用": sell_fee_values["total_fee"],
                        "原因": sell_reason,
                        "备注": "",
                    }])
                    save_trade_record(load_trades(), new_trade)
                    st.success(
                        f"已卖出 {sell_holding['名称']}（{int(sell_qty)}股 @ {float(sell_price):.3f}）"
                    )
                    st.rerun()
    else:
        st.info("当前没有持仓记录。请在「待买」页面买入股票。")

    if st.button("手动修正持仓", type="secondary"):
        st.session_state.show_manual_holding_editor = not st.session_state.get("show_manual_holding_editor", False)
    if st.session_state.get("show_manual_holding_editor", False):
        st.caption("默认持仓由交易流水生成；这里只用于券商数据和流水暂时不一致时修正。")
        manual_holdings = st.data_editor(
            st.session_state.holdings,
            num_rows="dynamic",
            width="stretch",
            height=240,
            key="manual_holding_editor",
        )
        if st.button("保存手动修正", type="primary"):
            save_holdings(manual_holdings)
            st.session_state.holdings = load_holdings()
            st.success("手动持仓已保存。后续新增交易仍会继续按流水推导。")
            st.rerun()

    st.divider()
    st.markdown("#### 更新当前价")
    if st.button("更新所有持仓当前价", type="secondary"):
        updated = st.session_state.holdings.copy()
        holding_codes = updated["代码"].dropna().astype(str).tolist()
        fresh_quotes = fetch_realtime_quotes(
            holding_codes,
            source=settings.get("quote_source", "自动切换"),
        )
        if not fresh_quotes.empty:
            updated = merge_quotes_into_holdings(updated, fresh_quotes)[HOLDING_COLUMNS]
            st.session_state.holding_price_update_message = (
                "success",
                f"当前价已更新：{fresh_quotes.attrs.get('message', '行情已更新')}",
            )
        else:
            for i, row in updated.iterrows():
                code = row["代码"]
                stock_data = watchlist[watchlist["代码"] == code]
                if not stock_data.empty:
                    updated.at[i, "当前价"] = float(stock_data.iloc[0]["现价"])
            st.session_state.holding_price_update_message = (
                "warning",
                "外部行情获取失败，已尽量使用股票池缓存价格。"
                f"原因：{fresh_quotes.attrs.get('message', '未知原因')}",
            )
        st.session_state.holdings = updated
        save_holdings(updated)
        st.rerun()

    st.divider()
    st.markdown("#### 交易统计")
    trades_for_holdings = audit_trades_against_rules(st.session_state.trades)
    if trades_for_holdings.empty:
        st.info("暂无买入卖出记录。")
    else:
        today = pd.Timestamp(date.today())
        trades_for_holdings["日期_dt"] = pd.to_datetime(trades_for_holdings["日期"], errors="coerce")
        today_trades = trades_for_holdings[trades_for_holdings["日期_dt"] == today]
        buy_amount = pd.to_numeric(trades_for_holdings.loc[trades_for_holdings["类型"] == "买入", "金额"], errors="coerce").sum()
        sell_amount = pd.to_numeric(trades_for_holdings.loc[trades_for_holdings["类型"] == "卖出", "金额"], errors="coerce").sum()
        realized_total = pd.to_numeric(trades_for_holdings["实现盈亏"], errors="coerce").sum()
        stat_cols = st.columns(4)
        stat_cols[0].metric("累计买入", f"¥{buy_amount:,.2f}")
        stat_cols[1].metric("累计卖出", f"¥{sell_amount:,.2f}")
        stat_cols[2].metric("已实现盈亏", f"¥{realized_total:,.2f}")
        stat_cols[3].metric("今日交易", len(today_trades))
        render_columns(
            trades_for_holdings.tail(12),
            ["日期", "类型", "代码", "名称", "价格", "数量", "金额", "规则结论", "偏离点", "实现盈亏"],
            360,
        )


# ══════════════════════════════════════════════════════════════════
# PAGE: 资产看板
# ══════════════════════════════════════════════════════════════════
elif page == "资产看板":
    page_header("资产看板", "查看交易流水推导出的现金、仓位和收益。")

    positions_view = build_positions_from_trades(
        st.session_state.trades,
        watchlist=st.session_state.watchlist,
        legacy_holdings=st.session_state.holdings,
    )
    account_view = account_state_from_trades(
        st.session_state.trades,
        positions_view,
        float(initial_capital),
        account_mode,
    )
    exposure = (
        float(account_view["持仓市值"]) / float(account_view["当前总资产"]) * 100
        if float(account_view["当前总资产"]) else 0
    )
    asset_cols = st.columns(5)
    asset_cols[0].metric("初始本金", money_display(float(account_view["初始本金"])))
    asset_cols[1].metric("当前现金", money_display(float(account_view["当前现金"])))
    asset_cols[2].metric("持仓市值", money_display(float(account_view["持仓市值"])))
    asset_cols[3].metric("当前总资产", money_display(float(account_view["当前总资产"])))
    asset_cols[4].metric("风险暴露", f"{exposure:.1f}%")

    pnl_cols = st.columns(5)
    pnl_cols[0].metric("已实现盈亏", f"¥{float(account_view['已实现盈亏']):,.2f}")
    pnl_cols[1].metric("浮动盈亏", f"¥{float(account_view['浮动盈亏']):,.2f}")
    pnl_cols[2].metric("总盈亏", f"¥{float(account_view['总盈亏']):,.2f}")
    pnl_cols[3].metric("总收益率", f"{float(account_view['总收益率%']):+.2f}%")
    pnl_cols[4].metric("当前持仓数量", len(positions_view))

    curve = asset_curve_from_trades(st.session_state.trades, float(initial_capital))
    if curve.empty:
        st.info("交易记录不足，资产曲线将在记录买卖后生成。")
    else:
        curve = curve.copy()
        curve["总资产估算"] = float(initial_capital) - curve["累计投入"] + float(account_view["持仓市值"])
        dd = max_drawdown(curve["总资产估算"])
        st.metric("最大回撤估算", f"{dd:.2f}%")
        fig = px.line(curve, x="日期", y="总资产估算", markers=True)
        fig.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis_title="总资产估算",
            xaxis_title="",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#FFFFFF",
        )
        st.plotly_chart(fig, width="stretch")

        bar = px.bar(curve, x="日期", y="当日交易金额")
        bar.update_layout(
            height=260,
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis_title="当日现金流",
            xaxis_title="",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#FFFFFF",
        )
        st.plotly_chart(bar, width="stretch")

    st.markdown("#### 当前持仓")
    if positions_view.empty:
        st.info("暂无持仓。")
    else:
        render_columns(
            positions_view,
            ["代码", "名称", "数量", "平均成本", "当前价", "市值", "浮动盈亏", "浮动盈亏%",
             "MA5", "MA5偏离率%", "持仓天数", "操作提醒"],
            420,
        )


# ══════════════════════════════════════════════════════════════════
# PAGE: 复盘报告
# ══════════════════════════════════════════════════════════════════
elif page == "复盘报告":
    page_header("复盘报告", "复盘交易证据，保存今日、周、月记录。")

    trades = st.session_state.trades
    audited_trades = audit_trades_against_rules(trades)
    if not audited_trades.empty:
        audited_trades["日期_dt"] = pd.to_datetime(audited_trades["日期"], errors="coerce")

    report_tabs = st.tabs(["今日复盘", "周复盘", "月复盘", "全部交易审计", "复盘笔记"])

    with report_tabs[0]:
        selected_day = st.date_input("复盘日期", date.today(), key="review_daily_date")
        day_key = selected_day.isoformat()
        day_trades = (
            audited_trades[audited_trades["日期_dt"] == pd.Timestamp(selected_day)].copy()
            if not audited_trades.empty else pd.DataFrame()
        )
        buy_count = int((day_trades.get("类型", pd.Series(dtype=str)) == "买入").sum()) if not day_trades.empty else 0
        sell_count = int((day_trades.get("类型", pd.Series(dtype=str)) == "卖出").sum()) if not day_trades.empty else 0
        compliant = day_trades.get("规则结论", pd.Series(dtype=str)).fillna("").astype(str).str.contains("符合规则|符合", regex=True) if not day_trades.empty else pd.Series(dtype=bool)
        violation_rows = day_trades[day_trades.get("偏离点", pd.Series(dtype=str)).fillna("无") != "无"] if not day_trades.empty else pd.DataFrame()
        day_sells = day_trades[day_trades.get("类型", pd.Series(dtype=str)) == "卖出"] if not day_trades.empty else pd.DataFrame()
        day_realized = pd.to_numeric(day_sells.get("实现盈亏", pd.Series(dtype=float)), errors="coerce").fillna(0).sum() if not day_sells.empty else 0
        risk_holding_count = count_risk_positions(portfolio_positions)

        metric_cols = st.columns(6)
        metric_cols[0].metric("今日买入次数", buy_count)
        metric_cols[1].metric("今日卖出次数", sell_count)
        metric_cols[2].metric("今日规则符合率", f"{(compliant.mean() * 100 if len(compliant) else 0):.1f}%")
        metric_cols[3].metric("今日违规点", len(violation_rows))
        metric_cols[4].metric("今日已实现盈亏", money_display(float(day_realized)))
        metric_cols[5].metric("今日持仓风险", risk_holding_count)

        if day_trades.empty:
            st.info("当日没有买入卖出记录，可以只保存观察心得和明日计划。")
        else:
            render_columns(
                day_trades,
                ["日期", "时间", "类型", "代码", "名称", "价格", "数量", "规则结论", "偏离点", "实现盈亏"],
                320,
            )
            if not violation_rows.empty:
                st.caption("今日违规点")
                for text, count in violation_rows["偏离点"].value_counts().head(5).items():
                    st.write(f"- {text}：{count}次")

        saved_daily = load_report_note("daily", day_key)
        default_daily = "" if saved_daily.startswith("# ") else saved_daily
        today_note = st.text_area("今日心得", value=default_daily, height=110, key="review_today_note")
        tomorrow_plan = st.text_area("明日计划", height=90, key="review_tomorrow_plan")
        if st.button("保存今日复盘", type="primary", key="save_review_daily"):
            metrics = {
                "今日买入次数": buy_count,
                "今日卖出次数": sell_count,
                "今日规则符合率": f"{(compliant.mean() * 100 if len(compliant) else 0):.1f}%",
                "今日违规点": len(violation_rows),
                "今日已实现盈亏": money_display(float(day_realized)),
                "今日持仓风险": risk_holding_count,
            }
            note = f"## 今日心得\n\n{today_note.strip()}\n\n## 明日计划\n\n{tomorrow_plan.strip()}"
            save_report_note("daily", day_key, report_markdown(f"{day_key} 日报", metrics, note))
            st.success("今日复盘已保存")

    with report_tabs[1]:
        if audited_trades.empty:
            st.info("暂无可生成周复盘的交易记录。")
        else:
            week_values = audited_trades["日期_dt"].dropna().dt.to_period("W").astype(str).sort_values().unique().tolist()
            selected_week = st.selectbox("周复盘周期", week_values[::-1], key="review_week_period")
            week_mask = audited_trades["日期_dt"].dt.to_period("W").astype(str) == selected_week
            render_trade_audit_report(audited_trades, f"{selected_week} 周复盘", week_mask)

    with report_tabs[2]:
        if audited_trades.empty:
            st.info("暂无可生成月复盘的交易记录。")
        else:
            month_values = audited_trades["日期_dt"].dropna().dt.to_period("M").astype(str).sort_values().unique().tolist()
            selected_month = st.selectbox("月复盘月份", month_values[::-1], key="review_month_period")
            month_mask = audited_trades["日期_dt"].dt.to_period("M").astype(str) == selected_month
            render_trade_audit_report(audited_trades, f"{selected_month} 月复盘", month_mask)

    with report_tabs[3]:
        if audited_trades.empty:
            st.info("暂无交易记录。")
        else:
            render_columns(
                audited_trades,
                ["日期", "时间", "类型", "代码", "名称", "价格", "数量", "金额", "MA5", "MA5偏离率%",
                 "最近大阳线%", "规则结论", "规则依据", "偏离点", "时间审计", "实现盈亏", "实现盈亏%"],
                540,
            )
        nav_button("去记录交易", "交易记录", key="review_go_trade", use_container_width=False)

    with report_tabs[4]:
        note_cols = st.columns(3)
        with note_cols[0]:
            note_day = st.date_input("日报日期", date.today(), key="note_daily_date").isoformat()
            daily_text = st.text_area("日报笔记", value=load_report_note("daily", note_day), height=240, key="note_daily_text")
            if st.button("保存日报笔记", type="primary", key="save_daily_note"):
                save_report_note("daily", note_day, daily_text)
                st.success("日报笔记已保存")
        with note_cols[1]:
            current_week = str(pd.Timestamp(date.today()).to_period("W"))
            week_key = st.text_input("周报周期", value=current_week, key="note_week_key")
            weekly_text = st.text_area("周报笔记", value=load_report_note("weekly", week_key), height=240, key="note_weekly_text")
            if st.button("保存周报笔记", type="primary", key="save_weekly_note"):
                save_report_note("weekly", week_key, weekly_text)
                st.success("周报笔记已保存")
        with note_cols[2]:
            month_key = st.text_input("月报月份", value=pd.Timestamp(date.today()).to_period("M").strftime("%Y-%m"), key="note_month_key")
            monthly_text = st.text_area("月报笔记", value=load_report_note("monthly", month_key), height=240, key="note_monthly_text")
            if st.button("保存月报笔记", type="primary", key="save_monthly_note"):
                save_report_note("monthly", month_key, monthly_text)
                st.success("月报笔记已保存")


# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# PAGE: 系统设置
# ══════════════════════════════════════════════════════════════════
elif page == "系统设置":
    page_header("系统设置", "配置交易费用、数据源和基础风控参数。")

    settings = st.session_state.settings.copy()
    with st.form("settings_form"):
        st.markdown("#### 交易参数")
        col1, col2 = st.columns(2)
        with col1:
            lot_size = st.number_input("最小交易单位（股）", min_value=100, step=100, value=int(settings.get("lot_size", 100)))
        with col2:
            max_pos_pct = st.slider("单笔最大仓位（%）", 10, 100, int(settings.get("max_position_pct", 100)))

        st.divider()
        st.markdown("#### 交易费用设置")
        fee_col1, fee_col2, fee_col3 = st.columns(3)
        with fee_col1:
            commission_rate = st.number_input(
                "佣金费率",
                min_value=0.0,
                value=float(settings.get("commission_rate", 0.00025)),
                step=0.00001,
                format="%.5f",
            )
            use_min_commission = st.checkbox("启用最低佣金", value=bool(settings.get("use_min_commission", True)))
        with fee_col2:
            min_commission = st.number_input(
                "最低佣金",
                min_value=0.0,
                value=float(settings.get("min_commission", 5.0)),
                step=0.5,
                format="%.2f",
            )
            auto_calculate_fees = st.checkbox("自动计算费用", value=bool(settings.get("auto_calculate_fees", True)))
        with fee_col3:
            stamp_tax_rate = st.number_input(
                "印花税率（仅卖出）",
                min_value=0.0,
                value=float(settings.get("stamp_tax_rate", 0.0005)),
                step=0.00001,
                format="%.5f",
            )
            transfer_fee_rate = st.number_input(
                "过户费率（双向）",
                min_value=0.0,
                value=float(settings.get("transfer_fee_rate", 0.00001)),
                step=0.00001,
                format="%.5f",
            )

        st.divider()
        st.markdown("#### 风控设置")
        col3, col4 = st.columns(2)
        with col3:
            allow_high = st.checkbox("允许高价股（单手金额>本金）", value=settings.get("allow_high_price", False))
        with col4:
            allow_unaffordable = st.checkbox("资金不足仍显示候选（仅交易时检查现金）", value=settings.get("allow_unaffordable_watchlist", False))

        st.divider()
        st.markdown("#### 数据源设置")
        ds_col1, ds_col2, ds_col3 = st.columns(3)
        with ds_col1:
            history_source = st.selectbox(
                "历史K线数据源",
                ["本地缓存 + AKShare", "仅本地缓存"],
                index=0 if settings.get("history_source", "本地缓存 + AKShare") == "本地缓存 + AKShare" else 1,
            )
        with ds_col2:
            current_quote_source = settings.get("quote_source", "自动切换")
            if current_quote_source not in QUOTE_SOURCE_OPTIONS:
                current_quote_source = "自动切换"
            quote_source = st.selectbox(
                "盘中行情数据源",
                QUOTE_SOURCE_OPTIONS,
                index=QUOTE_SOURCE_OPTIONS.index(current_quote_source),
            )
        with ds_col3:
            refresh_mode = st.selectbox(
                "刷新频率",
                ["手动", "30秒", "60秒"],
                index=["手动", "30秒", "60秒"].index(
                    settings.get("quote_refresh_mode", "手动")
                    if settings.get("quote_refresh_mode", "手动") in ["手动", "30秒", "60秒"]
                    else "手动"
                ),
            )
            st.caption("自动切换顺序：东方财富 → AKShare → 新浪行情。当前以手动轻刷新为主，页面切换不自动联网。")

        st.divider()
        st.markdown("#### 数据管理")
        st.caption("操作不可撤销，请谨慎使用。")
        col5, col6 = st.columns(2)
        with col5:
            if st.form_submit_button("清除缓存数据", type="secondary", use_container_width=True):
                st.cache_data.clear()
                st.session_state.reminder_computed = False
                st.success("缓存已清除")
        with col6:
            if st.form_submit_button("重置所有数据", type="secondary", use_container_width=True):
                for f in ["data/watchlist.csv", "data/holdings.csv", "data/trades.csv", "data/trades/trade_log.csv", "data/settings.json"]:
                    Path(f).unlink(missing_ok=True)
                st.cache_data.clear()
                st.session_state.clear()
                st.success("所有数据已重置，页面将重新加载")
                st.rerun()

        if st.form_submit_button("保存设置", type="primary", use_container_width=True):
            active_fee_prefix = fee_prefix_for_mode(account_mode)
            settings.update({
                "lot_size": lot_size,
                "max_position_pct": max_pos_pct,
                "allow_high_price": allow_high,
                "allow_unaffordable_watchlist": allow_unaffordable,
                "history_source": history_source,
                "quote_source": quote_source,
                "quote_refresh_mode": refresh_mode,
                "quote_refresh_seconds": 30 if refresh_mode == "30秒" else 60,
                "commission_rate": commission_rate,
                "min_commission": min_commission,
                "stamp_tax_rate": stamp_tax_rate,
                "transfer_fee_rate": transfer_fee_rate,
                f"{active_fee_prefix}_commission_rate": commission_rate,
                f"{active_fee_prefix}_min_commission": min_commission,
                f"{active_fee_prefix}_stamp_tax_rate": stamp_tax_rate,
                f"{active_fee_prefix}_transfer_fee_rate": transfer_fee_rate,
                "use_min_commission": use_min_commission,
                "auto_calculate_fees": auto_calculate_fees,
            })
            st.session_state.settings = settings
            save_settings(settings)
            st.success("设置已保存")
            st.rerun()
