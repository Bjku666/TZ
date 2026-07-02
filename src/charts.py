from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.history import load_cached_history
from src.rules import clean_code


def render_kline_chart(code: str, name: str | None = None) -> None:
    """Render a cached candlestick chart with MA5/MA10/MA20 overlays."""
    cleaned = clean_code(code)
    if not cleaned:
        st.info("请选择一只股票查看K线。")
        return

    history = load_cached_history(cleaned)
    if history is None or history.empty:
        st.info("暂无历史K线，请先补全。")
        return

    frame = history.copy()
    frame["日期"] = pd.to_datetime(frame.get("日期"), errors="coerce")
    for column in ["开盘", "最高", "最低", "收盘", "MA5", "MA10", "MA20"]:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["日期", "开盘", "最高", "最低", "收盘"]).sort_values("日期")
    if frame.empty:
        st.info("暂无有效历史K线，请先补全。")
        return

    for window in (5, 10, 20):
        column = f"MA{window}"
        if column not in frame or frame[column].isna().all():
            frame[column] = frame["收盘"].rolling(window).mean()

    title_name = str(name or "").strip()
    title = f"{title_name} {cleaned}" if title_name else cleaned
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=frame["日期"],
            open=frame["开盘"],
            high=frame["最高"],
            low=frame["最低"],
            close=frame["收盘"],
            name="K线",
            increasing_line_color="#DC2626",
            decreasing_line_color="#16A34A",
            increasing_fillcolor="#DC2626",
            decreasing_fillcolor="#16A34A",
        )
    )
    ma_colors = {"MA5": "#D97706", "MA10": "#2563EB", "MA20": "#7C3AED"}
    for column, color in ma_colors.items():
        fig.add_trace(
            go.Scatter(
                x=frame["日期"],
                y=frame[column],
                mode="lines",
                name=column,
                line=dict(width=1.5, color=color),
            )
        )
    fig.update_layout(
        title=title,
        height=420,
        margin=dict(l=10, r=10, t=42, b=10),
        xaxis_rangeslider_visible=False,
        yaxis_title="价格",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
    )
    st.plotly_chart(fig, width="stretch")
