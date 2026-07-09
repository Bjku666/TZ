import React from "react";
import {
  Activity,
  Bell,
  BookOpen,
  BriefcaseBusiness,
  ChevronLeft,
  Clock3,
  Database,
  History,
  Layers,
  Loader2,
  RefreshCw,
  Settings,
  TrendingUp,
  X,
} from "lucide-react";
import type { CapitalPoint, Mode, Page, StrategyId, StrategyMode, Trade } from "./types";
import { modeLabel, money, nowTime, pct, tone } from "./lib";

type IconType = typeof Activity;
type Tone = "slate" | "cyan" | "green" | "amber" | "red" | "orange" | "indigo";

const nav: Array<[Page, string, IconType, string]> = [
  ["today", "今日执行", Activity, "今日待办行动与风险提醒"],
  ["positions", "当前持仓", BriefcaseBusiness, "持仓列表与延迟卖出处理"],
  ["trades", "交易记录", History, "全账本交易流水与纪律审计"],
  ["reviews", "复盘分析", BookOpen, "资金曲线、日复盘、周复盘与违规统计"],
];

const pageMeta: Record<Page, { title: string; subtitle: string }> = {
  today: {
    title: "今日执行 & 行动指南",
    subtitle: "实盘记录模式：对接您同花顺的实际成交流水，严格执行实盘纪律审计与违纪警报",
  },
  positions: {
    title: "当前持仓 & 延迟管理",
    subtitle: "持仓均价、偏离及决策状态均从对应交易流水按 A 股先进先出算法动态推导",
  },
  trades: {
    title: "全历史交易审计账本",
    subtitle: "实盘记录模式：对接您同花顺的实际成交流水，严格执行实盘纪律审计与违纪警报",
  },
  reviews: {
    title: "复盘分析 & 资金纪律",
    subtitle: "按计划、执行、结果、改进四段复盘，并保留资金变化与盈亏结构",
  },
};

const toneMap: Record<Tone, string> = {
  slate: "border-[#303948] bg-[#151a22] text-[#a9b2c0]",
  cyan: "border-cyan-800 bg-cyan-950/35 text-cyan-200",
  green: "border-emerald-800 bg-emerald-950/35 text-emerald-200",
  amber: "border-amber-800 bg-amber-950/35 text-amber-200",
  red: "border-rose-800 bg-rose-950/40 text-rose-200",
  orange: "border-orange-800 bg-orange-950/35 text-orange-200",
  indigo: "border-indigo-800 bg-indigo-950/35 text-indigo-200",
};

export function Sidebar({
  mode,
  strategyId,
  strategies,
  page,
  quoteUpdatedAt,
  onMode,
  onStrategy,
  onPage,
}: {
  mode: Mode;
  strategyId: StrategyId;
  strategies: StrategyMode[];
  page: Page;
  quoteUpdatedAt?: string;
  onMode: (mode: Mode) => void;
  onStrategy: (strategyId: StrategyId) => void;
  onPage: (page: Page) => void;
}) {
  const live = Boolean(quoteUpdatedAt && !quoteUpdatedAt.includes("未连接") && !quoteUpdatedAt.includes("失败"));
  return (
    <aside className="hidden w-[230px] shrink-0 border-r border-[#27313b] bg-[#080d0d] md:flex md:flex-col">
      <div className="flex h-[76px] items-center gap-3 border-b border-[#27313b] px-5">
        <div className="brand-mark">
          <TrendingUp size={18} strokeWidth={2.7} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[15px] font-black leading-4 text-white">Workstation</div>
          <div className="mt-1 font-mono text-[8px] uppercase tracking-[0.28em] text-[#687080]">CONSOLE V1.4</div>
        </div>
        <ChevronLeft size={15} className="text-[#687080]" />
      </div>

      <div className="border-b border-[#27313b] px-5 py-4">
        <div className="mb-3 font-mono text-[9px] font-bold uppercase tracking-[0.24em] text-[#687080]">当前交易账本 / ACCOUNT</div>
        <ModeSwitch mode={mode} onMode={onMode} />
      </div>

      <div className="border-b border-[#27313b] px-5 py-4">
        <div className="mb-3 flex items-center gap-2 font-mono text-[9px] font-bold uppercase tracking-[0.24em] text-[#687080]">
          <Layers size={12} />
          交易模式 / STRATEGY
        </div>
        <StrategySwitch strategyId={strategyId} strategies={strategies} onStrategy={onStrategy} />
      </div>

      <nav className="flex-1 space-y-2 px-3 py-4">
        {nav.map(([key, label, Icon, sub]) => {
          const active = page === key;
          return (
            <button
              key={key}
              onClick={() => onPage(key)}
              className={`flex h-[42px] w-full items-center gap-3 rounded-md border px-3 text-left transition ${
                active
                  ? "nav-item-active"
                  : "border-transparent text-[#7a838f] hover:bg-[#111820] hover:text-slate-200"
              }`}
            >
              <Icon size={16} className={active ? "mode-accent" : "text-[#707a88]"} />
              <span className="min-w-0">
                <b className="block truncate text-[13px] leading-4">{label}</b>
                <small className="block truncate text-[10px] leading-4 text-[#697381]">{sub}</small>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="border-t border-[#27313b] p-3">
        <div className="rounded-md border border-[#27313b] bg-[#111820] p-3 font-mono text-[10px] leading-5 text-[#77808f]">
          <div className="flex justify-between">
            <span>行情状态:</span>
            <span className={`truncate pl-2 text-right font-black ${live ? "text-emerald-300" : "text-slate-400"}`}>● {quoteUpdatedAt || "加载中"}</span>
          </div>
          <div className="flex justify-between">
            <span>对账引擎:</span>
            <span className="text-slate-200">LOCAL_SYNC</span>
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between font-mono text-[10px] text-[#5e6672]">
          <span>TZ CORE v2.4.1</span>
          <span className="inline-flex items-center gap-1 text-emerald-400">
            <Database size={11} />
            LOCAL_ON
          </span>
        </div>
      </div>
    </aside>
  );
}

export function MobileNav({ page, onPage }: { page: Page; onPage: (page: Page) => void }) {
  return (
    <nav className="grid grid-cols-4 border-t border-[#27313b] bg-[#080d0d] md:hidden">
      {nav.map(([key, label, Icon]) => (
        <button
          key={key}
          onClick={() => onPage(key)}
          className={`flex h-16 flex-col items-center justify-center gap-1 text-[10px] font-bold ${page === key ? "mobile-nav-active" : "text-slate-500"}`}
        >
          <Icon size={18} />
          {label}
        </button>
      ))}
    </nav>
  );
}

export function Header({
  page,
  mode,
  strategyId,
  strategy,
  strategies,
  phase,
  quoteUpdatedAt,
  unread,
  loading,
  onMode,
  onStrategy,
  onRefresh,
  onSettings,
  onNotices,
}: {
  page: Page;
  mode: Mode;
  strategyId: StrategyId;
  strategy: StrategyMode;
  strategies: StrategyMode[];
  phase: string;
  quoteUpdatedAt?: string;
  unread: number;
  loading: boolean;
  onMode: (mode: Mode) => void;
  onStrategy: (strategyId: StrategyId) => void;
  onRefresh: () => void;
  onSettings: () => void;
  onNotices: () => void;
}) {
  const meta = pageMeta[page];
  const now = new Date();
  const dateText = `${now.getFullYear()}年${String(now.getMonth() + 1).padStart(2, "0")}月${String(now.getDate()).padStart(2, "0")}日 ${now.toLocaleDateString("zh-CN", { weekday: "long" })}`;
  const phaseLabel = phase || "连接中";
  const phaseTone = phaseToneClass(phaseLabel);
  return (
    <header className="flex min-h-[72px] shrink-0 items-center justify-between gap-4 border-b border-[#27313b] bg-[#0c1118] px-4 md:px-6">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="truncate text-[16px] font-black leading-5 text-white">{meta.title}</h1>
          <span className="hidden h-4 w-px bg-[#303948] sm:block" />
          <span className="hidden text-xs text-[#747d8d] sm:inline">{dateText}</span>
          <Badge tone={phaseBadgeTone(phaseLabel)}>
            <span className={`mr-1 h-1.5 w-1.5 rounded-full ${phaseTone.dot}`} />
            {phaseLabel}
          </Badge>
        </div>
        <p className="mt-1 truncate text-[11px] leading-4 text-[#77808f]">
          {modeLabel(mode)} · {strategy.name} · {strategy.ruleStatus} · {meta.subtitle.replace("实盘记录模式：", "").replace("对接您同花顺的实际成交流水，", "")}
          {quoteUpdatedAt ? ` · ${quoteUpdatedAt}` : ""}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <div className="hidden items-center gap-2 rounded-md border border-[#27313b] bg-[#111821] px-3 py-2 lg:flex">
          <Clock3 size={14} className="text-cyan-300" />
          <span className="font-mono text-xs font-black text-white">{nowTime()}</span>
          <span className="h-4 w-px bg-[#303948]" />
          <span className={`rounded-[4px] border px-2 py-0.5 text-[10px] font-black ${phaseTone.pill}`}>
            {phaseLabel}
          </span>
        </div>
        <div className="hidden sm:block md:hidden">
          <ModeSwitch mode={mode} onMode={onMode} compact />
        </div>
        <div className="hidden lg:block xl:hidden">
          <StrategySwitch strategyId={strategyId} strategies={strategies} onStrategy={onStrategy} compact />
        </div>
        <select className="input h-9 max-w-[116px] py-1 text-xs md:hidden" value={strategyId} onChange={(event) => onStrategy(event.target.value as StrategyId)} title="切换交易模式">
          {strategies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <button className="icon-btn" onClick={onRefresh} title="刷新账户工作区">
          {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
        </button>
        <button className="icon-btn relative" onClick={onNotices} title="通知中心">
          <Bell size={15} />
          {unread > 0 && <i className="notice-dot absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full px-1 text-[9px] font-black text-white">{unread}</i>}
        </button>
        <button className="icon-btn" onClick={onSettings} title="设置">
          <Settings size={15} />
        </button>
      </div>
    </header>
  );
}

function phaseBadgeTone(phase: string): Tone {
  if (phase === "交易中") return "green";
  if (phase === "连接中") return "cyan";
  if (phase === "休市") return "slate";
  return "amber";
}

function phaseToneClass(phase: string) {
  if (phase === "交易中") {
    return { dot: "bg-emerald-300", pill: "border-emerald-800 bg-emerald-950/35 text-emerald-300" };
  }
  if (phase === "连接中") {
    return { dot: "bg-cyan-300", pill: "border-cyan-800 bg-cyan-950/35 text-cyan-300" };
  }
  if (phase === "休市") {
    return { dot: "bg-slate-400", pill: "border-slate-700 bg-slate-900/55 text-slate-300" };
  }
  return { dot: "bg-amber-300", pill: "border-amber-800 bg-amber-950/35 text-amber-300" };
}

export function ModeSwitch({ mode, onMode, compact = false }: { mode: Mode; onMode: (mode: Mode) => void; compact?: boolean }) {
  return (
    <div className={`grid h-[34px] grid-cols-2 rounded-[7px] border border-[#303948] bg-[#111820] p-1 ${compact ? "w-[210px]" : "w-full"}`}>
      <button onClick={() => onMode("simulation")} className={`rounded-[5px] text-[12px] font-black ${mode === "simulation" ? "mode-switch-option-active" : "text-[#9aa3af]"}`}>
        模拟训练
      </button>
      <button onClick={() => onMode("real")} className={`rounded-[5px] text-[12px] font-black ${mode === "real" ? "mode-switch-option-active" : "text-[#9aa3af]"}`}>
        实盘记录
      </button>
    </div>
  );
}

export function StrategySwitch({
  strategyId,
  strategies,
  onStrategy,
  compact = false,
}: {
  strategyId: StrategyId;
  strategies: StrategyMode[];
  onStrategy: (strategyId: StrategyId) => void;
  compact?: boolean;
}) {
  if (compact) {
    return (
      <select className="input h-9 w-[142px] py-1 text-xs" value={strategyId} onChange={(event) => onStrategy(event.target.value as StrategyId)} title="切换交易模式">
        {strategies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    );
  }

  return (
    <div className="space-y-2">
      {strategies.map((item) => {
        const active = item.id === strategyId;
        return (
          <button
            key={item.id}
            onClick={() => onStrategy(item.id)}
            className={`w-full rounded-md border px-3 py-2 text-left transition ${
              active
                ? "border-[var(--tz-accent-border)] bg-[var(--tz-accent-soft)] text-white"
                : "border-[#27313b] bg-[#111820] text-[#8a94a3] hover:border-[#3a4654] hover:text-slate-100"
            }`}
          >
            <span className="flex items-center justify-between gap-2">
              <b className="truncate text-[12px] leading-4">{item.name}</b>
              <small className={`shrink-0 rounded-[4px] border px-1.5 py-0.5 text-[9px] font-black ${item.placeholder ? "border-amber-800 bg-amber-950/35 text-amber-200" : "border-emerald-800 bg-emerald-950/35 text-emerald-200"}`}>
                {item.ruleStatus}
              </small>
            </span>
            <small className="mt-1 block truncate text-[10px] leading-4 text-[#697381]">{item.description}</small>
          </button>
        );
      })}
    </div>
  );
}

export function Loading() {
  return (
    <div className="grid h-72 place-items-center rounded-lg border border-[#27313b] bg-[#121821] text-sm text-[#77808f]">
      <span className="flex items-center gap-2">
        <Loader2 className="animate-spin" size={18} />
        正在加载当前工作区……
      </span>
    </div>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-[#27313b] bg-[#151a22] shadow-sm shadow-black/20 ${className}`}>{children}</section>;
}

export function SectionTitle({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 className="text-[14px] font-black leading-5 text-white">{title}</h3>
        {subtitle && <p className="mt-1 text-[11px] leading-5 text-[#77808f]">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Badge({ children, tone = "slate" }: { children: React.ReactNode; tone?: Tone }) {
  return <span className={`inline-flex items-center rounded-[5px] border px-2 py-0.5 text-[10px] font-black leading-4 ${toneMap[tone]}`}>{children}</span>;
}

export function Stat({ label, value, sub, valueClass = "text-white" }: { label: string; value: string | number; sub?: string; valueClass?: string }) {
  return (
    <Card className="min-h-[82px] p-4">
      <div className="text-[10px] font-black uppercase tracking-wider text-[#768191]">{label}</div>
      <div className={`mt-2 break-words font-mono text-[20px] font-black leading-6 ${valueClass}`}>{value}</div>
      {sub && <div className="mt-2 text-[10px] leading-4 text-[#7b8492]">{sub}</div>}
    </Card>
  );
}

export function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-[#303948] p-6 text-center text-xs text-[#77808f]">{text}</div>;
}

export function Mini({ label, value, cls = "text-white" }: { label: string; value: string | number; cls?: string }) {
  return (
    <div className="rounded-md border border-[#27313b] bg-[#111821] p-3">
      <div className="text-[10px] leading-4 text-[#768191]">{label}</div>
      <div className={`mt-1 break-words font-mono text-[13px] font-black leading-5 ${cls}`}>{value}</div>
    </div>
  );
}

export function ProgressBar({ value, tone = "cyan" }: { value: number; tone?: Tone }) {
  const width = Math.max(0, Math.min(100, Number(value || 0)));
  const color = tone === "red" ? "bg-rose-500" : tone === "green" ? "bg-emerald-500" : tone === "orange" ? "bg-orange-500" : tone === "amber" ? "bg-amber-500" : "bg-cyan-500";
  return (
    <div className="h-2 overflow-hidden rounded-full bg-[#0b1017]">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${width}%` }} />
    </div>
  );
}

export function CapitalSplit({ cashPct, holdingPct }: { cashPct: number; holdingPct: number }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-[10px] font-bold text-[#77808f]">
        <span>现金 {cashPct.toFixed(1)}%</span>
        <span>持仓 {holdingPct.toFixed(1)}%</span>
      </div>
      <div className="flex h-2 overflow-hidden rounded-full bg-[#0b1017]">
        <div className="bg-cyan-500" style={{ width: `${Math.max(0, Math.min(100, cashPct))}%` }} />
        <div className="bg-orange-500" style={{ width: `${Math.max(0, Math.min(100, holdingPct))}%` }} />
      </div>
    </div>
  );
}

export function Sparkline({ points, field = "totalAssets" }: { points: CapitalPoint[]; field?: keyof CapitalPoint }) {
  const series = points.map((item) => Number(item[field] || 0));
  if (series.length < 2) {
    return <div className="grid h-24 place-items-center rounded-lg border border-dashed border-[#303948] text-xs text-[#687080]">暂无资金曲线</div>;
  }
  const min = Math.min(...series);
  const max = Math.max(...series);
  const range = max - min || 1;
  const path = series
    .map((value, index) => {
      const x = (index / Math.max(1, series.length - 1)) * 100;
      const y = 30 - ((value - min) / range) * 26;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <svg className="h-24 w-full overflow-visible" viewBox="0 0 100 32" preserveAspectRatio="none" role="img" aria-label="资金变化曲线">
      <polyline fill="none" stroke="rgba(34,211,238,.9)" strokeWidth="1.8" points={path} vectorEffect="non-scaling-stroke" />
      <line x1="0" x2="100" y1="30" y2="30" stroke="rgba(148,163,184,.18)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function TradeTable({ rows, actions }: { rows: Trade[]; actions?: (trade: Trade) => React.ReactNode }) {
  if (!rows.length) return <Empty text="暂无符合条件的交易记录。" />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[980px] text-left text-xs">
        <thead className="bg-[#111820] text-[#8a94a3]">
          <tr>
            {["日期 / 时间", "类型", "股票", "价格", "数量（股）", "成交金额", "佣/税/规费", "审计结论", "动机 / 违纪原因", "操作"].map((h) => (
              <th key={h} className="px-4 py-3 font-black">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const t = normalizeTableTrade(row, index);
            return (
              <tr key={`${t.accountMode}-${t.strategyId}-${t.id}`} className="border-t border-[#27313b] hover:bg-[#111821]">
                <td className="px-4 py-3 font-mono text-slate-300">
                  <div>{t.date}</div>
                  <div className="text-[10px] text-[#6f7886]">{t.time}</div>
                </td>
                <td className="px-4 py-3">
                  <Badge tone={t.type === "BUY" ? "green" : "red"}>{t.type === "BUY" ? "买入" : "卖出"}</Badge>
                </td>
                <td className="px-4 py-3">
                  <b className="text-white">{t.name}</b>
                  <div className="font-mono text-[10px] text-[#77808f]">{t.code}</div>
                </td>
                <td className="px-4 py-3 font-mono">¥ {t.price.toFixed(2)}</td>
                <td className="px-4 py-3 font-mono">{t.quantity}</td>
                <td className="px-4 py-3 font-mono text-white">¥ {money(t.amount)}</td>
                <td className="px-4 py-3 font-mono text-[#9aa3af]">¥ {money(t.totalFee)}</td>
                <td className="px-4 py-3">
                  <Badge tone={t.rulesConclusion === "符合规则" ? "green" : t.rulesConclusion === "违规交易" ? "red" : "amber"}>{t.rulesConclusion}</Badge>
                </td>
                <td className="max-w-72 px-4 py-3 text-[#9aa3af]">
                  <div className="line-clamp-2">{t.reason || t.violationTags.join("、") || t.remark || "无"}</div>
                </td>
                <td className="px-4 py-3">{actions?.(t)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function normalizeTableTrade(row: Trade, index: number): Trade {
  const item = row as Trade & Record<string, unknown>;
  const numberValue = (value: unknown) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const textValue = (value: unknown, fallback = "") => typeof value === "string" && value.trim() ? value : fallback;
  return {
    ...row,
    id: textValue(item.id, `trade-${index}`),
    accountMode: item.accountMode === "real" ? "real" : "simulation",
    strategyId: item.strategyId || "ma5_pullback",
    code: textValue(item.code, "未知代码"),
    name: textValue(item.name, textValue(item.code, "未命名股票")),
    type: item.type === "SELL" ? "SELL" : "BUY",
    date: textValue(item.date, "未记录日期"),
    time: textValue(item.time, ""),
    price: numberValue(item.price),
    quantity: numberValue(item.quantity),
    amount: numberValue(item.amount),
    commission: numberValue(item.commission),
    stampDuty: numberValue(item.stampDuty),
    transferFee: numberValue(item.transferFee),
    totalFee: numberValue(item.totalFee),
    reason: textValue(item.reason),
    remark: textValue(item.remark),
    rulesConclusion: textValue(item.rulesConclusion, "无法判断"),
    violationTags: Array.isArray(item.violationTags) ? item.violationTags.filter(Boolean).map(String) : [],
    historicalBackfill: Boolean(item.historicalBackfill),
    manualFeeOverride: Boolean(item.manualFeeOverride),
  };
}

export function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <Field label={label}>
      <input type="number" step="any" className="input" value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </Field>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-[12px] font-medium text-[#9aa3af]">
      {label}
      <div className="mt-2">{children}</div>
    </label>
  );
}

export function Modal({ title, onClose, children, wide = false }: { title: string; onClose: () => void; children: React.ReactNode; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-4 backdrop-blur-[2px]" onMouseDown={onClose}>
      <div
        className={`max-h-[92vh] w-full overflow-hidden rounded-xl border border-[#25324a] bg-[#121722] shadow-2xl ${wide ? "max-w-[512px]" : "max-w-xl"}`}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#25324a] bg-[#0f1d3a] px-6 py-4">
          <h2 className="font-black text-white">{title}</h2>
          <button className="icon-btn border-0 bg-transparent" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div className="max-h-[calc(92vh-64px)] overflow-y-auto p-6">{children}</div>
      </div>
    </div>
  );
}

export { money, pct, tone };
