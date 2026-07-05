import {
  Activity,
  BarChart3,
  Briefcase,
  FileSpreadsheet,
  FileText,
  LineChart,
  RefreshCw,
  Settings,
  ShieldCheck,
  Trash2,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { shortTime } from "../api/adapters";
import { ModeSwitch } from "../components/common/ModeSwitch";
import type { AccountMode, ActivityEntry } from "../types";

export type PageKey = "dashboard" | "stockPool" | "intraday" | "positions" | "trades" | "assets" | "review" | "import" | "settings";

export const navItems: Array<{ key: PageKey; label: string; icon: typeof Activity }> = [
  { key: "dashboard", label: "今日看板", icon: BarChart3 },
  { key: "stockPool", label: "股票池 & 分组", icon: LineChart },
  { key: "intraday", label: "盘中低吸监控", icon: Activity },
  { key: "positions", label: "持仓监控", icon: Briefcase },
  { key: "trades", label: "交易记录审计", icon: FileText },
  { key: "assets", label: "资产看板", icon: Wallet },
  { key: "review", label: "复盘笔记归档", icon: ShieldCheck },
  { key: "import", label: "数据导入", icon: FileSpreadsheet },
  { key: "settings", label: "交易系统配置", icon: Settings },
];

export function Sidebar({
  active,
  onChange,
  mode,
  onModeChange,
  modeSwitching = false,
  activities,
  onClearActivities,
  collapsed = false,
}: {
  active: PageKey;
  onChange: (page: PageKey) => void;
  mode: AccountMode;
  onModeChange: (mode: AccountMode) => void;
  modeSwitching?: boolean;
  activities: ActivityEntry[];
  onClearActivities: () => void;
  collapsed?: boolean;
}) {
  return (
    <aside className={`${collapsed ? "w-[4.5rem]" : "w-72"} flex shrink-0 flex-col border-r border-slate-800 bg-slate-900`}>
      <div className="flex h-20 items-center gap-3 border-b border-slate-800 px-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-gradient-to-br from-orange-500 via-rose-600 to-red-700 shadow-lg shadow-rose-950/40">
          <TrendingUp className="h-5 w-5 text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="truncate text-sm font-black text-slate-100">强势回踩短线交易纪律系统</div>
            <div className="mt-1 flex items-center gap-1.5 truncate text-[10px] font-bold text-slate-500">
              <span className="h-2 w-2 rounded-full bg-orange-400"></span>
              视频原版五日线回踩工作台
            </div>
          </div>
        )}
      </div>
      {!collapsed && (
        <div className="border-b border-slate-800 px-3 py-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-black text-slate-600">账户模式</span>
            {modeSwitching && <span className="font-mono text-[10px] font-bold text-cyan-300">SYNC</span>}
          </div>
          <ModeSwitch value={mode} onChange={onModeChange} disabled={modeSwitching} />
        </div>
      )}
      <div className="px-3 pt-4 text-[10px] font-bold text-slate-600">纪律罗盘</div>
      <nav className="space-y-1 p-3">
        {navItems.map(item => {
          const Icon = item.icon;
          const selected = active === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onChange(item.key)}
              className={`flex h-10 w-full items-center gap-3 rounded border px-3 text-left text-xs font-bold transition ${
                selected
                  ? "border-blue-500 bg-blue-600 text-white shadow"
                  : "border-transparent text-slate-500 hover:border-slate-800 hover:bg-slate-900/70 hover:text-slate-200"
              }`}
              title={item.label}
            >
              <Icon className={`h-4 w-4 shrink-0 ${selected ? "text-white" : "text-slate-600"}`} />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </button>
          );
        })}
      </nav>
      {!collapsed && (
        <div className="mx-3 mb-3 mt-auto flex min-h-0 flex-1 flex-col rounded-lg border border-slate-800 bg-slate-900/45">
          <div className="flex items-center justify-between border-b border-slate-800 px-3 py-3">
            <div className="text-xs font-black text-slate-300">事件流日志</div>
            <button
              onClick={onClearActivities}
              className="inline-flex h-7 w-7 items-center justify-center rounded border border-slate-800 bg-slate-950 text-slate-500 transition hover:text-slate-200"
              title="清空事件流"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-3">
            {activities.length === 0 ? (
              <div className="flex h-full items-center justify-center text-center text-[11px] text-slate-600">暂无系统事件</div>
            ) : (
              <div className="space-y-2">
                {activities.slice(0, 16).map(entry => (
                  <div key={entry.id} className="rounded border border-slate-800 bg-slate-950/55 p-2">
                    <div className="flex items-start gap-2">
                      <RefreshCw className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${entry.kind === "danger" ? "text-rose-400" : entry.kind === "success" ? "text-emerald-300" : entry.kind === "warning" ? "text-amber-300" : "text-slate-500"}`} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-[11px] font-bold text-slate-300">{entry.title}</span>
                          <span className="shrink-0 font-mono text-[10px] text-slate-600">{shortTime(entry.time)}</span>
                        </div>
                        {entry.detail && <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-500">{entry.detail}</div>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
