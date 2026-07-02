from __future__ import annotations

import pandas as pd


def page_css() -> str:
    """Return the main page CSS with graphite + warm white professional theme."""
    return """
    <style>
    :root {
      --ink: #111827;
      --muted: #6B7280;
      --blue: #7C3AED;
      --blue-soft: #F5F3FF;
      --amber: #D97706;
      --amber-soft: #FFFBEB;
      --red: #DC2626;
      --red-soft: #FEF2F2;
      --green: #16A34A;
      --green-soft: #F0FDF4;
      --purple: #7C3AED;
      --purple-soft: #F5F3FF;
      --orange: #EA580C;
      --orange-soft: #FFF7ED;
      --gray: #9CA3AF;
      --bg: #F6F3EE;
      --card: #FFFFFF;
      --line: #E7E5E4;
    }

    .stApp { background: var(--bg); color: var(--ink); }
    .block-container { padding-top: 0.45rem !important; max-width: 1400px; }

    /* Sidebar */
    [data-testid="stSidebar"] {
      background: #18181B !important;
    }
    [data-testid="stSidebar"] * {
      color: #F9FAFB !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stNumberInput label {
      color: #D1D5DB !important;
    }
    [data-testid="stSidebar"] [data-baseweb="input"] input {
      color: #111827 !important;
      background: #F9FAFB !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] div[data-baseweb="select"] {
      background: #F9FAFB !important;
      color: #111827 !important;
      border-color: #D1D5DB !important;
    }
    /* Selectbox dropdown menu - make text visible on light background */
    [data-testid="stSidebar"] [data-baseweb="select"] * {
      color: #111827 !important;
    }
    /* Selected value text inside selectbox */
    [data-testid="stSidebar"] [data-baseweb="select"] div {
      color: #111827 !important;
    }
    /* Dropdown popover list items */
    [data-testid="stSidebar"] li[role="option"] {
      color: #111827 !important;
      background: #FFFFFF !important;
    }
    [data-testid="stSidebar"] li[role="option"]:hover {
      background: #F5F3FF !important;
    }
    /* The popover container */
    [data-testid="stSidebar"] [data-baseweb="popover"] {
      background: #FFFFFF !important;
      color: #111827 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="popover"] * {
      color: #111827 !important;
    }

    /* Radio navigation in sidebar */
    [data-testid="stSidebar"] .stRadio label {
      padding: 0.35rem 0.65rem;
      border-radius: 6px;
      color: #F9FAFB !important;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
      background: #27272A;
    }
    [data-testid="stSidebar"] .stRadio div[data-testid="stRadio"] label[data-selected="true"] {
      background: #A855F7 !important;
      color: #FFFFFF !important;
    }

    /* Cards */
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0.85rem;
      box-shadow: 0 1px 2px rgba(0,0,0,0.035);
      margin-bottom: 0.65rem;
    }
    .card h3 {
      margin-top: 0;
      font-size: 1.05rem;
      color: var(--ink);
    }

    /* Status label colors */
    .status-待买, .status-待买观察, .status-接近买点 {
      color: var(--blue) !important;
      font-weight: 600;
    }
    .status-继续观察, .status-重点观察 {
      color: var(--gray) !important;
    }
    .status-等回踩 {
      color: var(--amber) !important;
      font-weight: 600;
    }
    .status-偏高不追 {
      color: var(--orange) !important;
      font-weight: 600;
    }
    .status-远离不追, .status-跌破不买 {
      color: var(--red) !important;
      font-weight: 600;
    }
    .status-缺少历史K线, .status-历史K线数据不足, .status-本金买不起一手, .status-资金不足观察 {
      color: var(--purple) !important;
      font-weight: 600;
    }
    .status-淘汰 {
      color: var(--gray) !important;
    }
    .status-初筛 {
      color: var(--muted) !important;
    }

    /* Alert / Notification cards (not full-width banner) */
    .alert-card {
      border-radius: 10px;
      padding: 0.75rem 1rem;
      border: 1px solid;
      font-size: 0.9rem;
      margin-bottom: 0.75rem;
    }
    .alert-card.red {
      background: #FEF2F2;
      border-color: #FCA5A5;
      color: #991B1B;
    }
    .alert-card.blue {
      background: #F5F3FF;
      border-color: #C4B5FD;
      color: #5B21B6;
    }
    .alert-card.amber {
      background: #FFFBEB;
      border-color: #FCD34D;
      color: #92400E;
    }

    /* Remove the old full-width banner */
    .stAlert {
      border-radius: 10px !important;
      border-left-width: 0 !important;
    }

    /* Headings */
    h1, h2, h3 { letter-spacing: 0 !important; color: var(--ink); }
    h1 { font-size: 1.55rem !important; margin-bottom: 0.08rem !important; }
    h2 { font-size: 1.15rem !important; margin-top: 0 !important; }
    .subtitle { color: var(--muted); font-size: 0.9rem; margin-bottom: 0.75rem; }
    .page-goal {
      color: #4B5563;
      font-size: 0.86rem;
      background: #FFFFFF;
      border: 1px solid #E7E5E4;
      border-radius: 8px;
      padding: 0.45rem 0.65rem;
      margin: 0.35rem 0 0.65rem;
    }
    .eyebrow {
      color: var(--blue);
      font-size: 0.7rem;
      font-weight: 750;
      letter-spacing: 0.09rem;
      text-transform: uppercase;
      margin-bottom: 0.1rem;
    }

    /* Metrics */
    [data-testid="stMetric"] {
      background: var(--card);
      border: 1px solid var(--line);
      padding: 0.5rem 0.65rem;
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.03);
      min-height: 74px;
    }
    [data-testid="stMetricLabel"] { color: var(--muted); font-size: 0.8rem; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }

    /* Dataframe */
    [data-testid="stDataFrame"] {
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }

    /* Signal cards inside待买 */
    .signal {
      padding: 0.65rem 0.8rem;
      border: 1px solid var(--line);
      border-left-width: 4px;
      background: var(--card);
      border-radius: 10px;
      min-height: 70px;
      margin-bottom: 0.4rem;
    }
    .signal strong { display: block; margin-bottom: 0.15rem; }
    .signal.good { border-left-color: var(--blue); }
    .signal.wait { border-left-color: var(--amber); }
    .signal.stop { border-left-color: var(--red); }
    .signal.neutral { border-left-color: var(--gray); }
    .signal.purple { border-left-color: var(--purple); }

    /* System settings page */
    .stSlider label, .stNumberInput label { color: var(--ink); }
    .stSlider > div > div > div { background: var(--card); }

    /* Dataframe disabled text color fix */
    .stDataFrame td[data-testid="StyledDataFrameDataCell"][aria-disabled="true"] {
      color: var(--ink) !important;
    }

    /* Buttons */
    .stButton > button, .stDownloadButton > button {
      border-radius: 8px;
      font-weight: 600;
    }

    /* Disabled rows in data editor should use dark text */
    .stDataFrame [data-testid="cell"] input:disabled {
      color: #111827 !important;
      -webkit-text-fill-color: #111827 !important;
    }

    /* Tabs */
    div[data-baseweb="tab-list"] { gap: 0.25rem; }
    button[data-baseweb="tab"] { border-radius: 6px 6px 0 0; }

    /* Reminder tag inline style */
    .reminder-tag {
      display: inline-block;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
      font-size: 0.78rem;
      font-weight: 600;
      white-space: nowrap;
    }
    .reminder-tag.blue { background: #DBEAFE; color: #1E40AF; }
    .reminder-tag.amber { background: #FEF3C7; color: #92400E; }
    .reminder-tag.red { background: #FEE2E2; color: #991B1B; }
    .reminder-tag.purple { background: #EDE9FE; color: #5B21B6; }
    .reminder-tag.gray { background: #F3F4F6; color: #4B5563; }
    .reminder-tag.green { background: #DCFCE7; color: #166534; }
    .reminder-tag.orange { background: #FFEDD5; color: #9A3412; }

    /* Extra spacing */
    .section-gap { margin-top: 0.5rem; }
    .card-grid { display: flex; gap: 1rem; flex-wrap: wrap; }

    /* Current trading mode panel */
    .mode-panel {
      background: #FFFFFF;
      border: 1px solid #E7E5E4;
      border-radius: 8px;
      padding: 0.85rem;
      margin: 0.45rem 0 0.8rem;
    }
    .mode-panel h3 {
      margin: 0.1rem 0 0.25rem;
      font-size: 1.05rem;
      color: #111827;
    }
    .mode-panel p {
      color: #4B5563;
      margin: 0;
      font-size: 0.9rem;
    }
    .mode-kicker {
      color: #7C3AED;
      font-size: 0.72rem;
      font-weight: 750;
      letter-spacing: 0.08rem;
    }
    .mode-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0.65rem;
      margin-top: 0.85rem;
    }
    .mode-item {
      border-top: 1px solid #E7E5E4;
      padding-top: 0.6rem;
      min-width: 0;
    }
    .mode-item span {
      display: block;
      color: #6B7280;
      font-size: 0.76rem;
      margin-bottom: 0.18rem;
    }
    .mode-item b {
      display: block;
      color: #111827;
      font-size: 0.93rem;
      line-height: 1.25;
      margin-bottom: 0.18rem;
    }
    .mode-item small {
      display: block;
      color: #6B7280;
      line-height: 1.45;
    }
    @media (max-width: 900px) {
      .mode-grid { grid-template-columns: 1fr; }
    }

    .step-strip {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 0.5rem;
      margin: 0.25rem 0 0.85rem;
    }
    .step-card {
      background: #FFFFFF;
      border: 1px solid #E7E5E4;
      border-radius: 8px;
      padding: 0.6rem 0.65rem;
      min-height: 72px;
    }
    .step-card span {
      display: block;
      color: #7C3AED;
      font-size: 0.72rem;
      font-weight: 750;
      margin-bottom: 0.2rem;
    }
    .step-card b {
      display: block;
      color: #111827;
      font-size: 0.88rem;
      line-height: 1.25;
    }
    .holding-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 0.65rem;
      margin-bottom: 0.8rem;
    }
    .holding-card {
      background: #FFFFFF;
      border: 1px solid #E7E5E4;
      border-radius: 8px;
      padding: 0.8rem;
      box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    .holding-card h3 {
      margin: 0 0 0.45rem;
      font-size: 1rem;
    }
    .holding-card .mini-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.35rem 0.55rem;
      font-size: 0.84rem;
    }
    .holding-card span { color: #6B7280; }
    .holding-card b { color: #111827; font-weight: 650; }
    .compact-note {
      color: #6B7280;
      font-size: 0.82rem;
      line-height: 1.4;
    }
    @media (max-width: 1100px) {
      .step-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    }
    @media (max-width: 700px) {
      .step-strip { grid-template-columns: 1fr; }
    }
    </style>
    """


def status_color_css(status: str) -> str:
    """Return a CSS class name for a given status value."""
    mapping = {
        "待买": "status-待买",
        "待买观察": "status-待买",
        "重点观察": "status-重点观察",
        "接近买点": "status-接近买点",
        "继续观察": "status-继续观察",
        "观察": "status-继续观察",
        "等回踩": "status-等回踩",
        "偏高不追": "status-偏高不追",
        "远离不追": "status-远离不追",
        "跌破不买": "status-跌破不买",
        "跌破MA5": "status-跌破不买",
        "缺少历史K线": "status-缺少历史K线",
        "历史K线数据不足": "status-历史K线数据不足",
        "资金不足观察": "status-资金不足观察",
        "本金买不起一手": "status-本金买不起一手",
        "淘汰": "status-淘汰",
        "初筛": "status-初筛",
        "初筛通过": "status-初筛",
    }
    return mapping.get(status, "")


def reminder_tag(text: str, level: str = "gray") -> str:
    """Return an HTML inline tag for a reminder."""
    return f'<span class="reminder-tag {level}">{text}</span>'


def alert_card(text: str, level: str = "blue") -> str:
    """Return an HTML alert card."""
    return f'<div class="alert-card {level}">{text}</div>'


def card(html_content: str, title: str | None = None) -> str:
    """Wrap content in a styled card."""
    parts = ['<div class="card">']
    if title:
        parts.append(f"<h3>{title}</h3>")
    parts.append(html_content)
    parts.append("</div>")
    return "".join(parts)


def money_display(value: float | int | None) -> str:
    """Format a number as a human-readable money string."""
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        return "—"
    value = float(value)
    if abs(value) >= 1e8:
        return f"{value / 1e8:.1f}亿"
    if abs(value) >= 1e4:
        return f"¥{value / 1e4:.2f}万"
    return f"¥{value:,.2f}"


def percent_display(value: float | int | None) -> str:
    """Format a number as a percentage string."""
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except (TypeError, ValueError):
        return "—"
    return f"{float(value):+.2f}%"
