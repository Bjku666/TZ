from __future__ import annotations

import pandas as pd


def page_css() -> str:
    """Return the main page CSS with a focused discipline desk theme."""
    return """
    <style>
    :root {
      --ink: #111827;
      --muted: #64748B;
      --faint: #94A3B8;
      --nav: #0F172A;
      --nav-2: #111827;
      --nav-line: #243244;
      --blue: #2563EB;
      --blue-soft: #EFF6FF;
      --cyan: #0891B2;
      --cyan-soft: #ECFEFF;
      --amber: #D97706;
      --amber-soft: #FFFBEB;
      --red: #E11D48;
      --red-soft: #FFF1F2;
      --green: #059669;
      --green-soft: #ECFDF5;
      --purple: #7C3AED;
      --purple-soft: #F5F3FF;
      --orange: #EA580C;
      --orange-soft: #FFF7ED;
      --gray: #64748B;
      --bg: #F5F7FB;
      --card: #FFFFFF;
      --panel: #F8FAFC;
      --line: #DDE3EC;
      --line-strong: #CBD5E1;
      --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.05);
      --shadow-md: 0 10px 22px rgba(15, 23, 42, 0.07);
    }

    .stApp { background: var(--bg); color: var(--ink); }
    .block-container {
      padding-top: 0.55rem !important;
      padding-left: 1.25rem !important;
      padding-right: 1.25rem !important;
      max-width: 1440px;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
      background: var(--nav) !important;
      border-right: 1px solid var(--nav-line);
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
      color: #E5E7EB !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stNumberInput label {
      color: #CBD5E1 !important;
      font-size: 0.78rem;
      font-weight: 700;
    }
    [data-testid="stSidebar"] [data-baseweb="input"] input {
      color: #E5E7EB !important;
      background: #020617 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
      background: #020617 !important;
      color: #E5E7EB !important;
      border-color: var(--nav-line) !important;
      border-radius: 8px !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] svg {
      color: #E5E7EB !important;
      fill: #E5E7EB !important;
    }
    [data-testid="stSidebar"] hr {
      border-color: rgba(148, 163, 184, 0.2) !important;
      margin: 0.65rem 0 !important;
    }

    .sidebar-brand {
      border: 1px solid rgba(148, 163, 184, 0.25);
      border-radius: 10px;
      background: #111827;
      padding: 0.85rem 0.8rem;
      margin: 0.2rem 0 0.85rem;
    }
    .sidebar-brand .brand-row {
      display: flex;
      align-items: center;
      gap: 0.55rem;
      margin-bottom: 0.35rem;
    }
    .sidebar-brand .brand-mark {
      width: 1.9rem;
      height: 1.9rem;
      border-radius: 8px;
      background: #2563EB;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.18);
      position: relative;
      flex: 0 0 auto;
    }
    .sidebar-brand .brand-mark::after {
      content: "";
      position: absolute;
      left: 0.48rem;
      top: 0.45rem;
      width: 0.82rem;
      height: 0.82rem;
      border: 2px solid #FFFFFF;
      border-left: 0;
      border-bottom: 0;
      transform: rotate(45deg);
    }
    .sidebar-brand strong {
      display: block;
      color: #F8FAFC !important;
      font-size: 0.92rem;
      line-height: 1.2;
    }
    .sidebar-brand small {
      display: block;
      color: #94A3B8 !important;
      font-size: 0.72rem;
      line-height: 1.45;
    }
    .sidebar-brand .version-pill {
      display: inline-flex;
      align-items: center;
      border: 1px solid rgba(34, 211, 238, 0.28);
      background: rgba(8, 145, 178, 0.12);
      color: #A5F3FC !important;
      border-radius: 999px;
      padding: 0.12rem 0.48rem;
      font-size: 0.68rem;
      font-weight: 800;
      letter-spacing: 0.02rem;
      margin-top: 0.45rem;
    }

    /* Radio navigation in sidebar */
    [data-testid="stSidebar"] .stRadio > label {
      display: none;
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
      gap: 0.18rem;
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
      padding: 0.42rem 0.55rem !important;
      border-radius: 8px;
      border: 1px solid transparent;
      min-height: 34px;
      transition: background 120ms ease, border-color 120ms ease;
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {
      background: rgba(30, 41, 59, 0.8);
      border-color: rgba(148, 163, 184, 0.18);
    }
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:has(input:checked) {
      background: #2563EB !important;
      color: #FFFFFF !important;
      border-color: rgba(147, 197, 253, 0.45);
      box-shadow: 0 8px 18px rgba(37, 99, 235, 0.26);
    }
    .activity-log {
      border-top: 1px solid rgba(148, 163, 184, 0.18);
      margin-top: 0.8rem;
      padding-top: 0.75rem;
    }
    .sidebar-section-title {
      color: #94A3B8;
      font-size: 0.68rem;
      font-weight: 800;
      letter-spacing: 0.08rem;
      text-transform: uppercase;
      margin: 0.35rem 0 0.45rem;
    }
    .activity-log .activity-title {
      color: #94A3B8;
      font-size: 0.68rem;
      font-weight: 800;
      letter-spacing: 0.08rem;
      text-transform: uppercase;
      margin-bottom: 0.45rem;
    }
    .activity-log ul {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 0.35rem;
    }
    .activity-log li {
      color: #CBD5E1;
      background: #020617;
      border: 1px solid rgba(148, 163, 184, 0.14);
      border-radius: 7px;
      padding: 0.42rem 0.5rem;
      font-size: 0.72rem;
      line-height: 1.4;
    }
    .activity-log li.empty {
      color: #64748B;
      font-style: italic;
    }

    /* Cards */
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0.85rem;
      box-shadow: var(--shadow-sm);
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
    .status-缺少历史K线, .status-历史K线数据不足, .status-本金买不起一手, .status-资金不足观察, .status-未达规则 {
      color: var(--purple) !important;
      font-weight: 600;
    }
    .status-风险排除, .status-淘汰 {
      color: var(--gray) !important;
    }
    .status-初筛 {
      color: var(--muted) !important;
    }

    /* Alert / Notification cards (not full-width banner) */
    .alert-card {
      border-radius: 8px;
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
      background: #EFF6FF;
      border-color: #BFDBFE;
      color: #1D4ED8;
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
      color: #475569;
      font-size: 0.86rem;
      background: #FFFFFF;
      border: 1px solid var(--line);
      border-left: 4px solid var(--cyan);
      border-radius: 8px;
      padding: 0.5rem 0.7rem;
      margin: 0.35rem 0 0.65rem;
      box-shadow: var(--shadow-sm);
    }
    .eyebrow {
      color: var(--cyan);
      font-size: 0.7rem;
      font-weight: 750;
      letter-spacing: 0.09rem;
      text-transform: uppercase;
      margin-bottom: 0.1rem;
    }
    .version-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      border: 1px solid #BAE6FD;
      background: #F0F9FF;
      color: #0369A1;
      border-radius: 999px;
      padding: 0.16rem 0.55rem;
      font-size: 0.72rem;
      font-weight: 750;
      margin-left: 0.45rem;
      vertical-align: middle;
    }

    .dashboard-brief {
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(420px, 1fr);
      gap: 1rem;
      align-items: stretch;
      background: #FFFFFF;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 1rem;
      box-shadow: var(--shadow-md);
      margin: 0.75rem 0 0.85rem;
    }
    .dashboard-brief .brief-kicker {
      color: var(--cyan);
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.08rem;
      text-transform: uppercase;
      margin-bottom: 0.18rem;
    }
    .dashboard-brief h2 {
      margin: 0 0 0.35rem !important;
      font-size: 1.12rem !important;
      line-height: 1.25;
    }
    .dashboard-brief p {
      margin: 0;
      color: #64748B;
      font-size: 0.84rem;
      line-height: 1.55;
    }
    .brief-metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 0.55rem;
    }
    .brief-metric {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0.62rem 0.65rem;
      min-width: 0;
    }
    .brief-metric strong {
      display: block;
      color: #0F172A;
      font-size: 1.2rem;
      line-height: 1.1;
      font-weight: 800;
    }
    .brief-metric span {
      display: block;
      color: #64748B;
      font-size: 0.72rem;
      margin-top: 0.2rem;
      white-space: nowrap;
    }
    .brief-metric.hot {
      background: var(--cyan-soft);
      border-color: #A5F3FC;
    }
    .brief-metric.hot strong,
    .brief-metric.hot span {
      color: #0E7490;
    }
    .brief-metric.risk {
      background: var(--red-soft);
      border-color: #FECDD3;
    }
    .brief-metric.risk strong,
    .brief-metric.risk span {
      color: #BE123C;
    }
    @media (max-width: 1100px) {
      .dashboard-brief { grid-template-columns: 1fr; }
      .brief-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 620px) {
      .brief-metrics { grid-template-columns: 1fr; }
    }

    /* Metrics */
    [data-testid="stMetric"] {
      background: var(--card);
      border: 1px solid var(--line);
      padding: 0.5rem 0.65rem;
      border-radius: 8px;
      box-shadow: var(--shadow-sm);
      min-height: 74px;
    }
    [data-testid="stMetricLabel"] { color: var(--muted); font-size: 0.8rem; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }

    /* Dataframe */
    [data-testid="stDataFrame"] {
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #FFFFFF;
      box-shadow: var(--shadow-sm);
    }
    [data-testid="stDataFrame"] [role="gridcell"],
    [data-testid="stDataFrame"] [role="columnheader"] {
      font-size: 12px !important;
      line-height: 1.25 !important;
    }
    [data-testid="stDataFrame"] [role="columnheader"] {
      background: #F8FAFC !important;
      color: #334155 !important;
      font-weight: 700 !important;
    }

    /* Signal cards inside待买 */
    .signal {
      padding: 0.65rem 0.8rem;
      border: 1px solid var(--line);
      border-left-width: 4px;
      background: var(--card);
      border-radius: 8px;
      min-height: 70px;
      margin-bottom: 0.4rem;
      box-shadow: var(--shadow-sm);
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
    .stTextInput input,
    .stTextArea textarea,
    .stNumberInput input,
    .stDateInput input {
      border-radius: 8px !important;
      border-color: var(--line-strong) !important;
      background: #FFFFFF !important;
      color: var(--ink) !important;
    }
    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stNumberInput input:focus,
    .stDateInput input:focus {
      border-color: var(--cyan) !important;
      box-shadow: 0 0 0 1px rgba(8, 145, 178, 0.18) !important;
    }

    /* Dataframe disabled text color fix */
    .stDataFrame td[data-testid="StyledDataFrameDataCell"][aria-disabled="true"] {
      color: var(--ink) !important;
    }

    /* Buttons */
    .stButton > button, .stDownloadButton > button {
      border-radius: 8px;
      font-weight: 600;
      border-color: var(--line-strong);
      transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
      border-color: var(--cyan);
      box-shadow: 0 8px 18px rgba(8, 145, 178, 0.12);
      transform: translateY(-1px);
    }
    .stButton > button[kind="primary"],
    .stDownloadButton > button[kind="primary"] {
      background: var(--blue);
      border-color: var(--blue);
    }

    /* Disabled rows in data editor should use dark text */
    .stDataFrame [data-testid="cell"] input:disabled {
      color: #111827 !important;
      -webkit-text-fill-color: #111827 !important;
    }

    /* Tabs */
    div[data-baseweb="tab-list"] { gap: 0.25rem; }
    button[data-baseweb="tab"] {
      border-radius: 8px 8px 0 0;
      color: #64748B;
      font-weight: 700;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
      color: #0F172A;
      background: #FFFFFF;
      border-color: var(--line);
    }

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
    .reminder-tag.cyan { background: #CFFAFE; color: #0E7490; }
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
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 1rem;
      margin: 0.45rem 0 0.8rem;
      box-shadow: var(--shadow-md);
    }
    .mode-panel h3 {
      margin: 0.1rem 0 0.25rem;
      font-size: 1.05rem;
      color: #0F172A;
    }
    .mode-panel p {
      color: #64748B;
      margin: 0;
      font-size: 0.9rem;
    }
    .mode-kicker {
      color: var(--cyan);
      font-size: 0.72rem;
      font-weight: 750;
      letter-spacing: 0.08rem;
      text-transform: uppercase;
    }
    .mode-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0.65rem;
      margin-top: 0.85rem;
    }
    .mode-item {
      border: 1px solid var(--line);
      border-top: 3px solid #BAE6FD;
      background: var(--panel);
      border-radius: 8px;
      padding: 0.65rem;
      min-width: 0;
    }
    .mode-item span {
      display: block;
      color: #64748B;
      font-size: 0.76rem;
      margin-bottom: 0.18rem;
    }
    .mode-item b {
      display: block;
      color: #0F172A;
      font-size: 0.93rem;
      line-height: 1.25;
      margin-bottom: 0.18rem;
    }
    .mode-item small {
      display: block;
      color: #64748B;
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
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0.6rem 0.65rem;
      min-height: 72px;
      box-shadow: var(--shadow-sm);
    }
    .step-card span {
      display: block;
      color: var(--cyan);
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
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0.8rem;
      box-shadow: var(--shadow-sm);
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
    .holding-card span { color: #64748B; }
    .holding-card b { color: #0F172A; font-weight: 650; }
    .compact-note {
      color: #64748B;
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
        "未达规则": "status-未达规则",
        "风险排除": "status-风险排除",
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
