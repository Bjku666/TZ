import { AlertCircle, CheckCircle2, FileText, RefreshCw, Trash2, WalletCards, XCircle } from "lucide-react";
import { shortTime } from "../api/adapters";
import { Button } from "../components/common/Primitives";
import type { ActivityEntry } from "../types";

const iconMap = {
  info: FileText,
  success: CheckCircle2,
  warning: AlertCircle,
  danger: XCircle,
  refresh: RefreshCw,
  trade: WalletCards,
  report: FileText,
};

const toneMap = {
  info: "border-slate-800 text-slate-400",
  success: "border-emerald-900/50 text-emerald-300",
  warning: "border-amber-900/50 text-amber-300",
  danger: "border-rose-900/60 text-rose-300",
  refresh: "border-cyan-900/50 text-cyan-300",
  trade: "border-cyan-900/50 text-cyan-300",
  report: "border-emerald-900/50 text-emerald-300",
};

export function ActivityStream({ entries, onClear }: { entries: ActivityEntry[]; onClear: () => void }) {
  return (
    <aside className="hidden w-80 shrink-0 border-l border-slate-800 bg-slate-950/95 xl:flex xl:flex-col">
      <div className="flex h-12 items-center justify-between border-b border-slate-800 px-3">
        <div>
          <div className="text-xs font-black text-slate-200">活动事件流</div>
          <div className="text-[10px] font-bold text-slate-500">真实操作与后端事件</div>
        </div>
        <Button onClick={onClear} variant="muted" className="h-7 px-2">
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-auto p-3">
        {entries.length === 0 ? (
          <div className="rounded border border-dashed border-slate-800 p-4 text-center text-xs text-slate-500">暂无真实事件</div>
        ) : (
          entries.map(entry => {
            const Icon = iconMap[entry.kind] || FileText;
            return (
              <div key={entry.id} className={`rounded border bg-slate-950/70 p-2 ${toneMap[entry.kind] || toneMap.info}`}>
                <div className="flex items-start gap-2">
                  <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${entry.kind === "refresh" ? "text-cyan-300" : ""}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="truncate text-[11px] font-black text-slate-200">{entry.title}</div>
                      <time className="shrink-0 font-mono text-[10px] text-slate-600">{shortTime(entry.time)}</time>
                    </div>
                    {entry.detail && <div className="mt-1 line-clamp-3 text-[11px] leading-4 text-slate-500">{entry.detail}</div>}
                    {entry.source && <div className="mt-1 truncate font-mono text-[10px] text-slate-600">{entry.source}</div>}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
