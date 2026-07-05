import { Clock3, RefreshCw } from "lucide-react";
import {
  currentClock,
  dataAgeLabel,
  isQuoteStale,
  marketPhaseLabels,
  modeLabel,
  money,
  pct,
  quoteSource,
} from "../api/adapters";
import { Badge, Button } from "../components/common/Primitives";
import type { AccountMode, AccountState, HealthPayload, MarketPhase, RuleConfig, SettingsPayload, WorkbenchPayload } from "../types";

export function TopStatusBar({
  health,
  mode,
  phase,
  rules,
  settings,
  account,
  payload,
  countdown,
  autoRefreshActive,
  refreshing,
  onRefresh,
}: {
  health: HealthPayload | null;
  mode: AccountMode;
  phase: MarketPhase;
  rules: RuleConfig | null;
  settings: SettingsPayload;
  account: AccountState;
  payload: WorkbenchPayload;
  countdown: number | null;
  autoRefreshActive: boolean;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const stale = isQuoteStale(payload, rules);
  const totalTone = Number(account.totalPnL || 0) >= 0 ? "text-emerald-300" : "text-rose-300";
  const todayTone = Number(account.todayPnL || 0) >= 0 ? "text-emerald-300" : "text-rose-300";
  const metrics = [
    { label: mode === "real" ? "实盘总资产" : "模拟总资产", value: money(account.totalAssets), tone: "text-slate-100" },
    { label: "总市值", value: money(account.holdingValue), tone: "text-amber-300" },
    { label: "可用资金", value: money(account.availableCash), tone: "text-slate-100" },
    { label: "当日参考盈亏", value: money(account.todayPnL || 0), tone: todayTone },
    { label: "账户累计盈亏", value: money(account.totalPnL), tone: totalTone },
    { label: "总收益率", value: pct(account.totalReturnPct), tone: totalTone },
  ];

  return (
    <header className="flex h-16 shrink-0 items-center gap-4 border-b border-slate-800 bg-slate-950 px-4">
      <div className="min-w-0 flex-1">
        <div className="grid max-w-[980px] grid-cols-3 rounded-lg border border-slate-800 bg-slate-900/65 px-2 py-2 shadow-sm xl:grid-cols-6">
          {metrics.map(metric => (
            <div key={metric.label} className="min-w-0 border-slate-800 px-2 xl:border-r last:border-r-0">
              <div className="truncate text-center text-[10px] font-bold text-slate-500">{metric.label}</div>
              <div className={`mt-0.5 truncate text-center font-mono text-sm font-black ${metric.tone}`}>{metric.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <div className="hidden text-right xl:block">
          <div className="inline-flex items-center gap-1 rounded-full border border-slate-800 bg-slate-900 px-3 py-1 font-mono text-sm font-black text-slate-100">
            <Clock3 className="h-3.5 w-3.5 text-amber-300" />
            {currentClock().split(" ").pop()}
          </div>
          <div className="mt-1 text-[10px] font-bold text-slate-500">
            {marketPhaseLabels[phase] || phase} · {quoteSource(settings, payload)} · {dataAgeLabel(payload)}
          </div>
        </div>
        <Badge tone={mode === "real" ? "red" : "cyan"}>{modeLabel(mode)}</Badge>
        <Badge tone={stale ? "red" : "green"}>{stale ? "数据过期" : "数据有效"}</Badge>
        <Badge tone={autoRefreshActive ? "cyan" : "slate"}>{autoRefreshActive ? `${countdown ?? "-"}s` : "暂停"}</Badge>
        <Button onClick={onRefresh} disabled={refreshing} variant="primary">
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
          刷新
        </Button>
      </div>
    </header>
  );
}
