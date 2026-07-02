from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import src.data as _data
from src.data import (
    HOLDING_COLUMNS,
    TRADE_COLUMNS,
    WATCHLIST_COLUMNS,
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
    PIPELINE_STAGES,
    holding_advice,
    ma5_deviation,
    score_stock,
    screening_result,
    stock_stage_result,
)
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
from src.settings import load_settings, save_settings
from src.ui_style import page_css, money_display, percent_display

st.set_page_config(
    page_title="强势回踩系统",
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
        '<div class="eyebrow">STRONG PULLBACK · DISCIPLINE DESK</div>',
        unsafe_allow_html=True,
    )
    st.title(title)
    st.markdown(f'<div class="page-goal">本页目标：{subtitle}</div>', unsafe_allow_html=True)


def render_trading_mode_panel() -> None:
    st.markdown(
        f"""
        <section class="mode-panel">
          <div>
            <div class="mode-kicker">当前交易模式</div>
            <h3>主板成交额前排强势股的 5 日线回踩低吸模式</h3>
            <p>强势先入观察，贴近 5 日线才进待买；本金不足可以提示，但确认买入时必须拦截。</p>
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
              <small>同时看 MA5 向上、股价在 MA5 上方、成交额前排。</small>
            </div>
            <div class="mode-item">
              <span>买点区间</span>
              <b>距 MA5 0%-2%</b>
              <small>2%-5%继续观察，5%-7%偏高，>7%远离不追，<0%跌破不买。</small>
            </div>
            <div class="mode-item">
              <span>买入时间</span>
              <b>9:35-10:00 / 14:30-14:55</b>
              <small>盘中确认回踩不破；不在 9:30、午盘中段和尾盘最后几分钟临时追。</small>
            </div>
            <div class="mode-item">
              <span>资金约束</span>
              <b>当前本金 {money_display(available_cash)}</b>
              <small>一手金额 = 当前价 x 100；待买阶段标注资金状态，确认买入时校验现金。</small>
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


def schedule_auto_refresh(enabled: bool, interval_seconds: int) -> None:
    if not enabled:
        return
    st.html(
        f"""
        <script>
          setTimeout(function() {{
            window.parent.location.reload();
          }}, {int(interval_seconds) * 1000});
        </script>
        """,
        unsafe_allow_javascript=True,
    )


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
                if not bool(context.get("MA5向上", False)):
                    issues.append("买入时MA5未向上")
                if deviation is None or pd.isna(deviation):
                    issues.append("无法计算买入价与MA5偏离")
                elif float(deviation) < 0:
                    issues.append("买入价低于MA5，属于跌破后买入")
                elif float(deviation) > 2:
                    issues.append("买入价距离MA5超过2%，没有等回踩")
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


def observation_result(row: pd.Series) -> tuple[bool, str]:
    deviation = ma5_deviation(row.get("现价"), row.get("MA5"))
    has_history = pd.notna(row.get("MA5"))
    has_big_line = number_or(row.get("最近大阳线%"), 0) >= 5
    passed, reason = screening_result(str(row.get("代码", "")), str(row.get("名称", "")))
    if not passed:
        return False, reason
    if not has_history:
        return False, "缺少历史K线，待补充"
    if not has_big_line:
        return False, "缺少5%阳线启动信号"
    if deviation is None:
        return False, "无法计算MA5偏离率"
    return True, "进入观察池，盘中等待贴近MA5"


def capital_result(row: pd.Series) -> tuple[bool, str]:
    deviation = ma5_deviation(row.get("现价"), row.get("MA5"))
    ma5_up = is_truthy(row.get("MA5向上"))
    if not ma5_up:
        return False, "观察中：MA5未向上"
    if deviation is None:
        return False, "观察中：无法计算MA5偏离率"
    if deviation < 0:
        return False, "观察中：当前价在MA5下方"
    if deviation > 2:
        return False, "观察中：等待回踩到MA5 0%-2%"
    if str(row.get("本金是否可买", "")) != "可以买":
        return True, "符合待买形态，但当前本金不足"
    if is_truthy(row.get("是否超过单笔比例", False)):
        return True, "符合待买形态，但超过单笔仓位"
    return True, "符合待买形态和本金约束"


def build_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["观察通过"] = False
    out["待买通过"] = False
    out["流程阶段"] = "初筛通过"
    out["筛选原因"] = ""

    for index, row in out.iterrows():
        stage, reason, reminder = stock_stage_result(row.to_dict())
        out.loc[index, "流程阶段"] = stage
        out.loc[index, "状态"] = stage
        out.loc[index, "筛选原因"] = reason
        if reminder:
            out.loc[index, "提醒"] = reminder
        out.loc[index, "观察通过"] = stage in {"重点观察", "等回踩", "待买观察", "资金不足观察"}
        out.loc[index, "待买通过"] = stage == "待买观察"

    return out


def pipeline_views(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    views = {stage: df[df["流程阶段"] == stage].copy() for stage in PIPELINE_STAGES}
    views["初筛"] = df.copy()
    views["观察"] = df[df["流程阶段"].isin(["重点观察", "等回踩", "待买观察", "资金不足观察"])].copy()
    views["待买"] = views["待买观察"]
    views["观察未待买"] = df[df["流程阶段"].isin(["重点观察", "等回踩", "资金不足观察"])].copy()
    views["未达规则"] = df[df["流程阶段"].isin(["缺少历史K线", "淘汰"])].copy()
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
    return batch[WATCHLIST_COLUMNS].reset_index(drop=True)


def fetch_history_for_codes(codes: list[str], *, only_missing: bool = True) -> dict[str, object]:
    cleaned_codes = [str(code) for code in codes if str(code).strip()]
    if only_missing:
        cleaned_codes = [
            code for code in cleaned_codes
            if diagnose_history(code)["history_status"] in {"缺少历史K线", "数据不足", "自动获取失败"}
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
    for column in ["流程阶段", "筛选原因", "提醒", "规则状态"]:
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
    st.success(
        f"分析完成。初筛通过 {len(summary['初筛通过'])}，重点观察 {len(summary['重点观察'])}，"
        f"等回踩 {len(summary['等回踩'])}，待买观察 {len(summary['待买观察'])}，"
        f"资金不足 {len(summary['资金不足观察'])}，缺少历史K线 {len(summary['缺少历史K线'])}，"
        f"淘汰 {len(summary['淘汰'])}。"
    )


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
    for column in ["流程阶段", "筛选原因", "提醒", "规则状态"]:
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
                "是否待买观察": row.get("流程阶段", row.get("状态", "")) == "待买观察",
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
    if not ma5_up:
        tags.append("其他")
    if not principal_ok:
        tags.append("本金不足仍买")
    if not time_ok:
        tags.append("非计划时间买入")

    unique_tags = list(dict.fromkeys(tags))
    severe = {"非主板", "ST", "京东方A", "无5%阳线", "跌破MA5仍买", "远离MA5追高", "本金不足仍买"}
    if not unique_tags:
        conclusion = "符合规则"
    elif severe.intersection(unique_tags) or len(unique_tags) >= 3:
        conclusion = "违反规则"
    else:
        conclusion = "部分符合"

    snapshot = {
        "是否主板": passed,
        "是否成交额前30": rank_ok,
        "是否有5%阳线": big_line,
        "是否MA5向上": ma5_up,
        "是否MA5偏离率0%-2%": deviation_ok,
        "是否本金可买": principal_ok,
        "是否在允许交易时间": time_ok,
        "买入时状态": stage or "未在当前股票池",
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
if "page_navigation" not in st.session_state:
    st.session_state.page_navigation = "今日看板"
pending_page_navigation = st.session_state.get("pending_page_navigation")
if pending_page_navigation:
    st.session_state.page_navigation = pending_page_navigation
    del st.session_state["pending_page_navigation"]
elif st.session_state.get("page_navigation") == "待买观察":
    st.session_state.page_navigation = "待买"

# ── Sidebar ──
with st.sidebar:
    st.markdown("## 强势回踩")

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
    page = st.radio(
        "导航",
        ["今日看板", "数据导入", "股票分组", "盘中观察", "待买", "交易记录", "持仓监控", "资产看板", "交易复盘", "报告中心", "系统设置"],
        label_visibility="collapsed",
        key="page_navigation",
    )

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
quote_status = "非交易时段，使用本地缓存"
if quote_codes and (trading_now or force_quote_refresh):
    quotes = cached_realtime_quotes(
        tuple(quote_codes),
        settings.get("quote_source", "自动切换"),
        int(st.session_state.get("manual_quote_refresh", 0)),
    )
    if not quotes.empty:
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
        quote_message = quotes.attrs.get("message") or quotes.attrs.get("source") or "行情已更新"
        quote_status = f"{quote_message} · {st.session_state.last_quote_time}"
    else:
        quote_error = quotes.attrs.get("message", "未知原因")
        quote_status = f"行情抓取失败，使用本地缓存：{quote_error}"
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
for column in ["状态", "流程阶段", "筛选原因", "提醒", "规则状态"]:
    if column in watchlist.columns and column in st.session_state.watchlist.columns:
        st.session_state.watchlist[column] = watchlist[column].values
save_watchlist(st.session_state.watchlist)
views = pipeline_views(watchlist)
held_codes = set(st.session_state.holdings["代码"].dropna().astype(str))
if held_codes:
    for view_name in ["重点观察", "等回踩", "待买观察", "资金不足观察", "观察", "待买", "观察未待买"]:
        views[view_name] = views[view_name][
            ~views[view_name]["代码"].astype(str).isin(held_codes)
        ].copy()
counts = {name: len(frame) for name, frame in views.items()}

valid_pages = {"今日看板", "数据导入", "股票分组", "盘中观察", "待买", "交易记录", "持仓监控", "资产看板", "交易复盘", "报告中心", "系统设置"}
if page not in valid_pages:
    page = "今日看板"
    st.session_state.page_navigation = page

# ══════════════════════════════════════════════════════════════════
# PAGE: 今日看板
# ══════════════════════════════════════════════════════════════════
if page == "今日看板":
    page_header("强势回踩系统", "今天只确认该补什么、看什么、买不买、记不记。")

    missing_history = len(views["缺少历史K线"])
    today_buy_watch = len(views["待买观察"])

    st.markdown("#### 账户状态 KPI")
    kpi_cols = st.columns(4)
    kpi_cols[0].metric("账户模式", account_mode)
    kpi_cols[1].metric("可用现金", money_display(available_cash))
    kpi_cols[2].metric("账户权益", money_display(account["equity"]))
    kpi_cols[3].metric("持仓市值", money_display(account["market_value"]))
    kpi_cols_2 = st.columns(4)
    kpi_cols_2[0].metric("浮动盈亏", money_display(account["floating_pnl"]))
    kpi_cols_2[1].metric("今日待买观察", today_buy_watch)
    kpi_cols_2[2].metric("当前持仓", len(portfolio_positions))
    kpi_cols_2[3].metric("缺少历史K线", missing_history)

    stage_cols = st.columns(7)
    for i, stage in enumerate(["初筛通过", "重点观察", "等回踩", "待买观察", "资金不足观察", "缺少历史K线", "淘汰"]):
        label = "资金不足" if stage == "资金不足观察" else stage
        stage_cols[i].metric(label, counts.get(stage, 0))

    st.markdown("#### 今日操作步骤")
    st.markdown(
        """
        <div class="step-strip">
          <div class="step-card"><span>01</span><b>生成/上传股票池</b></div>
          <div class="step-card"><span>02</span><b>补全历史K线</b></div>
          <div class="step-card"><span>03</span><b>查看重点观察</b></div>
          <div class="step-card"><span>04</span><b>盘中确认</b></div>
          <div class="step-card"><span>05</span><b>记录交易</b></div>
          <div class="step-card"><span>06</span><b>收盘复盘</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    step_buttons = st.columns(6)
    with step_buttons[0]:
        nav_button("股票池", "数据导入", key="dash_step_import")
    with step_buttons[1]:
        nav_button("补K线", "数据导入", key="dash_step_history")
    with step_buttons[2]:
        nav_button("重点观察", "股票分组", key="dash_step_focus")
    with step_buttons[3]:
        nav_button("盘中确认", "盘中观察", key="dash_step_intraday")
    with step_buttons[4]:
        nav_button("记录交易", "交易记录", key="dash_step_trade")
    with step_buttons[5]:
        nav_button("收盘复盘", "交易复盘", key="dash_step_review")

    refresh_cols = st.columns([1, 4])
    with refresh_cols[0]:
        if st.button("刷新行情", use_container_width=True):
            st.session_state.manual_quote_refresh += 1
            st.session_state.force_quote_refresh = True
            st.rerun()
    refresh_cols[1].caption(
        f"{quote_status} · {funds_source} · "
        f"{'交易时段自动刷新' if trading_now else '非交易时段不自动刷新'}"
    )

    st.markdown("#### 今日重点")
    focus = views["待买观察"].copy()
    near = pd.concat(
        [views["重点观察"], views["资金不足观察"]],
        ignore_index=True,
    ) if not views["重点观察"].empty or not views["资金不足观察"].empty else pd.DataFrame()
    risk = views["淘汰"].copy()

    table_cols = st.columns(3)
    with table_cols[0]:
        st.markdown("##### 今日待买观察")
        if focus.empty:
            st.info("暂无。")
        else:
            render_columns(
                focus,
                ["代码", "名称", "现价", "涨跌幅%", "MA5偏离率%", "一手金额", "流程阶段", "提醒"],
                260,
            )
    with table_cols[1]:
        st.markdown("##### 今日接近但未达标")
        if near.empty:
            st.info("暂无。")
        else:
            render_columns(
                near,
                ["代码", "名称", "现价", "涨跌幅%", "MA5偏离率%", "一手金额", "流程阶段", "提醒"],
                260,
            )
    with table_cols[2]:
        st.markdown("##### 今日风险排除")
        if risk.empty:
            st.info("暂无。")
        else:
            render_columns(
                risk,
                ["代码", "名称", "现价", "涨跌幅%", "MA5偏离率%", "流程阶段", "提醒"],
                260,
            )

    with st.expander("查看强势回踩交易规则", expanded=False):
        render_trading_mode_panel()

    refresh_mode = settings.get("quote_refresh_mode", "60秒")
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

    hist_cols = st.columns(5)
    hist_cols[0].metric("股票总数", total_stocks)
    hist_cols[1].metric("已有历史K线", with_history)
    hist_cols[2].metric("缺少历史K线", missing_count)
    hist_cols[3].metric("获取失败", failed_count)
    hist_cols[4].metric("数据不足", insufficient_count)

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
            "history_status": row.get("history_status", ""),
            "history_rows": row.get("history_rows", 0),
            "history_last_date": row.get("history_last_date", ""),
            "history_error": row.get("history_error", ""),
        })
    diag_frame = pd.DataFrame(diag_rows)
    if not diag_frame.empty:
        render_columns(
            diag_frame,
            ["代码", "名称", "history_status", "history_rows", "history_last_date", "history_error"],
            260,
        )

    hist_actions = st.columns(2)
    with hist_actions[0]:
        if st.button("只补缺失股票", type="primary", use_container_width=True):
            if settings.get("history_source", "本地缓存 + AKShare") == "仅本地缓存":
                st.warning("当前历史K线数据源为“仅本地缓存”。如需自动补历史K线，请在系统设置中改为“本地缓存 + AKShare”。")
            else:
                summary = fetch_history_for_codes(list(codes_list), only_missing=True)
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
    page_header("股票分组", "确认哪些股票进入待买观察，哪些只是等待。")

    group_count_cols = st.columns(7)
    for i, stage in enumerate(["初筛通过", "重点观察", "等回踩", "待买观察", "资金不足观察", "缺少历史K线", "淘汰"]):
        label = "资金不足" if stage == "资金不足观察" else stage
        group_count_cols[i].metric(label, counts.get(stage, 0))

    st.divider()

    group_specs = [
        (
            "待买观察",
            views["待买观察"],
            ["代码", "名称", "现价", "涨跌幅%", "成交额排名", "MA5偏离率%", "一手金额", "流程阶段", "提醒"],
            True,
        ),
        (
            "重点观察",
            views["重点观察"],
            ["代码", "名称", "现价", "涨跌幅%", "成交额排名", "MA5偏离率%", "一手金额", "流程阶段", "提醒"],
            True,
        ),
        (
            "等回踩",
            views["等回踩"],
            ["代码", "名称", "现价", "涨跌幅%", "成交额排名", "MA5偏离率%", "一手金额", "流程阶段", "提醒"],
            True,
        ),
        (
            "资金不足观察",
            views["资金不足观察"],
            ["代码", "名称", "现价", "涨跌幅%", "成交额排名", "MA5偏离率%", "一手金额", "流程阶段", "提醒"],
            False,
        ),
        (
            "缺少历史K线",
            views["缺少历史K线"],
            ["代码", "名称", "现价", "涨跌幅%", "成交额排名", "history_status", "history_rows", "history_last_date", "history_error", "提醒"],
            False,
        ),
        (
            "初筛通过",
            views["初筛通过"],
            ["代码", "名称", "现价", "涨跌幅%", "成交额排名", "MA5偏离率%", "一手金额", "流程阶段", "提醒"],
            False,
        ),
        (
            "淘汰",
            views["淘汰"],
            ["代码", "名称", "现价", "涨跌幅%", "成交额排名", "MA5偏离率%", "流程阶段", "筛选原因", "提醒"],
            False,
        ),
    ]
    for group, group_df, columns, expanded in group_specs:
        if not group_df.empty:
            with st.expander(f"{group}（{len(group_df)}只）", expanded=expanded):
                render_columns(group_df, columns, 340)
        else:
            st.info(f"暂无{group}股票。")


# ══════════════════════════════════════════════════════════════════
# PAGE: 盘中观察
# ══════════════════════════════════════════════════════════════════
elif page == "盘中观察":
    page_header("盘中观察", "盘中确认回踩是否成立，只做规则提醒和手动确认。")

    refresh_cols = st.columns([1, 1, 3])
    with refresh_cols[0]:
        if st.button("刷新行情", type="primary", use_container_width=True):
            st.session_state.manual_quote_refresh += 1
            st.session_state.force_quote_refresh = True
            st.rerun()
    with refresh_cols[1]:
        nav_button("去待买确认", "待买", key="intraday_go_buy")
    refresh_cols[2].caption(
        f"{quote_status} · 数据源：{settings.get('quote_source', '自动切换')} · "
        "开源行情源稳定性不如商业终端，异常时请以同花顺/券商软件为准。"
    )

    intraday_parts = []
    if not views["待买观察"].empty:
        intraday_parts.append(views["待买"].assign(盯盘阶段="待买观察"))
    if not views["重点观察"].empty:
        intraday_parts.append(views["重点观察"].assign(盯盘阶段="重点观察"))
    if not views["等回踩"].empty:
        intraday_parts.append(views["等回踩"].assign(盯盘阶段="等回踩"))
    if not views["资金不足观察"].empty:
        intraday_parts.append(views["资金不足观察"].assign(盯盘阶段="资金不足"))

    if intraday_parts:
        intraday = pd.concat(intraday_parts, ignore_index=True)
        intraday["距MA5绝对值"] = pd.to_numeric(intraday["MA5偏离率%"], errors="coerce").abs()
        intraday = intraday.sort_values(["盯盘阶段", "距MA5绝对值"], ascending=[True, True])

        metric_cols = st.columns(5)
        metric_cols[0].metric("待买观察", len(views["待买观察"]))
        metric_cols[1].metric("重点观察", len(views["重点观察"]))
        metric_cols[2].metric("等回踩", len(views["等回踩"]))
        metric_cols[3].metric("跌破MA5", int(pd.to_numeric(intraday["MA5偏离率%"], errors="coerce").lt(0).sum()))
        metric_cols[4].metric("资金不足", len(views["资金不足观察"]))

        render_columns(
            intraday,
            ["盯盘阶段", "代码", "名称", "现价", "涨跌幅%", "成交额排名", "MA5偏离率%",
             "一手金额", "流程阶段", "提醒"],
            560,
        )
    else:
        st.info("暂无观察池或待买观察股票。请先生成/导入股票池并分析。")

    refresh_mode = settings.get("quote_refresh_mode", "60秒")
    if refresh_mode != "手动":
        seconds = 30 if refresh_mode == "30秒" else int(settings.get("quote_refresh_seconds", 60))
        schedule_auto_refresh(trading_now, seconds)


# ══════════════════════════════════════════════════════════════════
# PAGE: 待买
# ══════════════════════════════════════════════════════════════════
elif page == "待买":
    page_header("待买", "确认待买观察是否真的满足买入条件。")

    buy_candidates = views["待买"]
    if not buy_candidates.empty:
        render_columns(
            buy_candidates,
            ["代码", "名称", "现价", "涨跌幅%", "成交额排名", "MA5偏离率%",
             "一手金额", "流程阶段", "提醒"],
            500,
        )
        st.divider()
        st.markdown("#### 买入操作")
        st.caption("确认后只写入交易流水，持仓和资产由流水自动生成。")
        buy_code = st.selectbox("选择股票", buy_candidates["代码"].tolist())
        if buy_code:
            selected = buy_candidates[buy_candidates["代码"] == buy_code].iloc[0]
            if str(selected.get("本金是否可买", "")) != "可以买":
                lot_cost = number_or(selected.get("一手金额"), 0)
                st.warning(
                    f"{selected['名称']} 一手金额 ¥{lot_cost:,.2f}，"
                    f"当前可用现金 ¥{available_cash:,.2f}，暂时不能确认买入。"
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

                if st.form_submit_button("确认买入", type="primary"):
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

        render_table(
            display_holdings[
                ["代码", "名称", "买入日期", "买入价", "数量", "当前价", "MA5",
                 "市值", "盈亏", "盈亏%", "MA5偏离率%", "纪律建议"]
            ],
            240,
        )

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
# PAGE: 交易复盘
# ══════════════════════════════════════════════════════════════════
elif page == "交易复盘":
    page_header("交易复盘", "验证每笔交易是否遵守规则。")

    trades = st.session_state.trades
    audited_trades = audit_trades_against_rules(trades)
    if not audited_trades.empty:
        audited_trades["日期_dt"] = pd.to_datetime(audited_trades["日期"], errors="coerce")
        buy_trades = audited_trades[audited_trades["类型"] == "买入"]
        sell_trades = audited_trades[audited_trades["类型"] == "卖出"]
        total_buy = pd.to_numeric(buy_trades["金额"], errors="coerce").sum() if not buy_trades.empty else 0
        total_sell = pd.to_numeric(sell_trades["金额"], errors="coerce").sum() if not sell_trades.empty else 0
        realized_total = pd.to_numeric(audited_trades["实现盈亏"], errors="coerce").sum()
        compliant = audited_trades["规则结论"].fillna("").astype(str).str.contains("符合规则|符合", regex=True)

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("总交易次数", len(audited_trades))
        col2.metric("买入次数", len(buy_trades))
        col3.metric("卖出次数", len(sell_trades))
        col4.metric("净投入", f"¥{total_buy - total_sell:,.2f}")
        col5.metric("规则符合率", f"{(compliant.mean() * 100 if len(audited_trades) else 0):.1f}%")

        st.divider()
        tabs = st.tabs(["规则审计", "日报", "周报", "月报", "补录交易"])

        with tabs[0]:
            render_columns(
                audited_trades,
                ["日期", "类型", "代码", "名称", "价格", "数量", "金额", "MA5", "MA5偏离率%",
                 "最近大阳线%", "规则结论", "规则依据", "偏离点", "时间审计", "实现盈亏", "实现盈亏%"],
                520,
            )

        with tabs[1]:
            selected_day = st.date_input("日报日期", date.today(), key="daily_report_date")
            selected_day_ts = pd.Timestamp(selected_day)
            render_trade_audit_report(
                audited_trades,
                f"{selected_day.isoformat()} 日报",
                audited_trades["日期_dt"] == selected_day_ts,
            )

        with tabs[2]:
            week_values = (
                audited_trades["日期_dt"]
                .dropna()
                .dt.to_period("W")
                .astype(str)
                .sort_values()
                .unique()
                .tolist()
            )
            if week_values:
                selected_week = st.selectbox("周报周期", week_values[::-1], key="weekly_report_period")
                render_trade_audit_report(
                    audited_trades,
                    f"{selected_week} 周报",
                    audited_trades["日期_dt"].dt.to_period("W").astype(str) == selected_week,
                )
            else:
                st.info("暂无可生成周报的交易记录。")

        with tabs[3]:
            month_values = (
                audited_trades["日期_dt"]
                .dropna()
                .dt.to_period("M")
                .astype(str)
                .sort_values()
                .unique()
                .tolist()
            )
            if month_values:
                selected_month = st.selectbox("月报周期", month_values[::-1], key="monthly_report_period")
                render_trade_audit_report(
                    audited_trades,
                    f"{selected_month} 月报",
                    audited_trades["日期_dt"].dt.to_period("M").astype(str) == selected_month,
                )
            else:
                st.info("暂无可生成月报的交易记录。")

        with tabs[4]:
            render_trade_form(trades)
    else:
        st.info("暂无交易记录。买入股票时会自动生成记录；当日没有买入卖出时不会生成日报分析。")
        render_trade_form(trades)

    st.divider()
    st.markdown("#### 持仓关联复盘")
    holdings_view = prepare_holdings_view(st.session_state.holdings)
    if holdings_view.empty:
        st.info("当前没有持仓。")
    else:
        render_columns(
            holdings_view,
            ["代码", "名称", "买入日期", "买入价", "数量", "当前价", "MA5", "盈亏", "盈亏%", "纪律建议"],
            320,
        )


# ══════════════════════════════════════════════════════════════════
# PAGE: 报告中心
# ══════════════════════════════════════════════════════════════════
elif page == "报告中心":
    page_header("报告中心", "保存日报、周报、月报和手写心得。")

    audited = audit_trades_against_rules(st.session_state.trades)
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
    if not audited.empty:
        audited["日期_dt"] = pd.to_datetime(audited["日期"], errors="coerce")

    report_tabs = st.tabs(["日报", "周报", "月报"])

    with report_tabs[0]:
        selected_day = st.date_input("日期", date.today(), key="report_center_day")
        key = selected_day.isoformat()
        if audited.empty:
            day_trades = pd.DataFrame()
        else:
            day_trades = audited[audited["日期_dt"] == pd.Timestamp(selected_day)].copy()
        buy_count = int((day_trades.get("类型", pd.Series(dtype=str)) == "买入").sum()) if not day_trades.empty else 0
        sell_count = int((day_trades.get("类型", pd.Series(dtype=str)) == "卖出").sum()) if not day_trades.empty else 0
        compliant_count = int(day_trades.get("规则结论", pd.Series(dtype=str)).fillna("").str.contains("符合").sum()) if not day_trades.empty else 0
        violation_count = len(day_trades) - compliant_count if not day_trades.empty else 0
        day_realized = pd.to_numeric(
            day_trades.loc[day_trades.get("类型", pd.Series(dtype=str)) == "卖出", "实现盈亏"],
            errors="coerce",
        ).fillna(0).sum() if not day_trades.empty and "实现盈亏" in day_trades else 0
        metrics = {
            "今日资产": money_display(float(account_view["当前总资产"])),
            "今日盈亏": money_display(float(day_realized)),
            "今日买入": buy_count,
            "今日卖出": sell_count,
            "当前持仓": len(positions_view),
            "规则内交易数": compliant_count,
            "违规交易数": violation_count,
        }
        cols = st.columns(4)
        cols[0].metric("今日资产", metrics["今日资产"])
        cols[1].metric("今日盈亏", metrics["今日盈亏"])
        cols[2].metric("今日买入/卖出", f"{buy_count}/{sell_count}")
        cols[3].metric("违规交易", violation_count)
        if day_trades.empty:
            st.info("当日没有买入卖出记录，不生成交易分析；可以记录今日观察和执行心得。")
        else:
            render_columns(day_trades, ["日期", "类型", "代码", "名称", "价格", "数量", "规则结论", "偏离点"], 320)
        saved = load_report_note("daily", key)
        today_note = st.text_area("今日心得", value=saved if saved and not saved.startswith("# ") else "", height=120, key="daily_note")
        tomorrow_plan = st.text_area("明日计划", height=100, key="daily_plan")
        if st.button("保存日报", type="primary"):
            note = f"## 今日心得\n\n{today_note.strip()}\n\n## 明日计划\n\n{tomorrow_plan.strip()}"
            save_report_note("daily", key, report_markdown(f"{key} 日报", metrics, note))
            st.success("日报已保存")

    with report_tabs[1]:
        if audited.empty:
            st.info("暂无可生成周报的交易记录。")
            week_key = pd.Timestamp(date.today()).to_period("W").strftime("%Y-%m-%d")
            week_note = st.text_area("本周心得 / 下周计划", value=load_report_note("weekly", week_key), height=180)
            if st.button("保存周报", type="primary"):
                save_report_note("weekly", week_key, report_markdown(f"{week_key} 周报", {"交易次数": 0}, week_note))
                st.success("周报已保存")
        else:
            weeks = audited["日期_dt"].dropna().dt.to_period("W").astype(str).sort_values().unique().tolist()
            selected_week = st.selectbox("周期", weeks[::-1], key="report_center_week")
            week_mask = audited["日期_dt"].dt.to_period("W").astype(str) == selected_week
            week_trades = audited[week_mask].copy()
            compliant = week_trades["规则结论"].fillna("").str.contains("符合")
            sells = week_trades[week_trades["类型"] == "卖出"]
            realized = pd.to_numeric(sells.get("实现盈亏", pd.Series(dtype=float)), errors="coerce").dropna()
            win_rate = (realized.gt(0).mean() * 100) if len(realized) else 0
            profits = realized[realized > 0]
            losses = realized[realized < 0]
            week_return = realized.sum() / float(initial_capital) * 100 if initial_capital else 0
            metrics = {
                "周收益率": f"{week_return:.2f}%",
                "交易次数": len(week_trades),
                "胜率": f"{win_rate:.1f}%",
                "平均盈利": money_display(float(profits.mean()) if len(profits) else 0),
                "平均亏损": money_display(float(losses.mean()) if len(losses) else 0),
                "最大亏损": money_display(float(losses.min()) if len(losses) else 0),
                "规则执行率": f"{(compliant.mean() * 100 if len(week_trades) else 0):.1f}%",
            }
            metric_cols = st.columns(4)
            metric_cols[0].metric("周收益率", metrics["周收益率"])
            metric_cols[1].metric("交易次数", metrics["交易次数"])
            metric_cols[2].metric("胜率", metrics["胜率"])
            metric_cols[3].metric("规则执行率", metrics["规则执行率"])
            render_columns(week_trades, ["日期", "类型", "代码", "名称", "价格", "数量", "规则结论", "偏离点", "实现盈亏"], 360)
            saved = load_report_note("weekly", selected_week)
            week_errors = st.text_area("本周错误", value=saved if saved and not saved.startswith("# ") else "", height=100, key="weekly_errors")
            next_improve = st.text_area("下周改进", height=100, key="weekly_next")
            if st.button("保存周报", type="primary"):
                note = f"## 本周错误\n\n{week_errors.strip()}\n\n## 下周改进\n\n{next_improve.strip()}"
                save_report_note("weekly", selected_week, report_markdown(f"{selected_week} 周报", metrics, note))
                st.success("周报已保存")

    with report_tabs[2]:
        if audited.empty:
            st.info("暂无可生成月报的交易记录。")
        else:
            months = audited["日期_dt"].dropna().dt.to_period("M").astype(str).sort_values().unique().tolist()
            selected_month = st.selectbox("月份", months[::-1], key="report_center_month")
            month_mask = audited["日期_dt"].dt.to_period("M").astype(str) == selected_month
            month_trades = audited[month_mask].copy()
            compliant = month_trades["规则结论"].fillna("").str.contains("符合")
            sells = month_trades[month_trades["类型"] == "卖出"]
            realized = pd.to_numeric(sells.get("实现盈亏", pd.Series(dtype=float)), errors="coerce").dropna()
            win_rate = realized.gt(0).mean() * 100 if len(realized) else 0
            best = realized.max() if len(realized) else 0
            worst = realized.min() if len(realized) else 0
            month_return = realized.sum() / float(initial_capital) * 100 if initial_capital else 0
            month_curve = asset_curve_from_trades(month_trades, float(initial_capital))
            month_dd = max_drawdown(month_curve["现金"]) if not month_curve.empty and "现金" in month_curve else 0
            metrics = {
                "月收益率": f"{month_return:.2f}%",
                "最大回撤": f"{month_dd:.2f}%",
                "交易次数": len(month_trades),
                "胜率": f"{win_rate:.1f}%",
                "规则执行率": f"{(compliant.mean() * 100 if len(month_trades) else 0):.1f}%",
                "最赚钱交易": money_display(float(best)),
                "最亏钱交易": money_display(float(worst)),
            }
            metric_cols = st.columns(4)
            metric_cols[0].metric("月收益率", metrics["月收益率"])
            metric_cols[1].metric("最大回撤", metrics["最大回撤"])
            metric_cols[2].metric("交易次数", metrics["交易次数"])
            metric_cols[3].metric("胜率", metrics["胜率"])
            render_columns(month_trades, ["日期", "类型", "代码", "名称", "价格", "数量", "规则结论", "偏离点", "实现盈亏"], 360)
            saved = load_report_note("monthly", selected_month)
            month_note = st.text_area("本月心得", value=saved if saved and not saved.startswith("# ") else "", height=100, key="monthly_note")
            next_month_plan = st.text_area("下月计划", height=100, key="monthly_plan")
            if st.button("保存月报", type="primary"):
                note = f"## 本月心得\n\n{month_note.strip()}\n\n## 下月计划\n\n{next_month_plan.strip()}"
                save_report_note("monthly", selected_month, report_markdown(f"{selected_month} 月报", metrics, note))
                st.success("月报已保存")


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
            allow_unaffordable = st.checkbox("允许资金不足股票入池", value=settings.get("allow_unaffordable_watchlist", False))

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
                    settings.get("quote_refresh_mode", "60秒")
                    if settings.get("quote_refresh_mode", "60秒") in ["手动", "30秒", "60秒"]
                    else "60秒"
                ),
            )
            st.caption("自动切换顺序：东方财富 → AKShare → 新浪行情。开源/网页行情源稳定性不如商业行情终端，如行情异常，请以同花顺/券商软件为准。")

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
                "use_min_commission": use_min_commission,
                "auto_calculate_fees": auto_calculate_fees,
            })
            st.session_state.settings = settings
            save_settings(settings)
            st.success("设置已保存")
            st.rerun()
