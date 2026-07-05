import { AlertCircle, RefreshCw } from "lucide-react";
import { compactMoney, dataAgeLabel, latestRefreshTime, marketPhaseLabels, quoteSource } from "../api/adapters";
import { Badge, Button, Card, EmptyState, SectionTitle, StatTile } from "../components/common/Primitives";
import type { MarketPhase, SettingsPayload, TurnoverChangeStock, WorkbenchPayload } from "../types";

export function IntradayPage({
  payload,
  settings,
  phase,
  autoRefreshActive,
  countdown,
  intervalSeconds,
  running,
  busy,
  preview,
  onRefresh,
  onPreview,
}: {
  payload: WorkbenchPayload;
  settings: SettingsPayload;
  phase: MarketPhase;
  autoRefreshActive: boolean;
  countdown: number | null;
  intervalSeconds: number | null;
  running: boolean;
  busy: string | null;
  preview: WorkbenchPayload["intradayPreview"];
  onRefresh: () => void;
  onPreview: () => void;
}) {
  const changes = preview?.changes || { newEntries: [], dropped: [], rankUp: [], rankDown: [] };
  return (
    <div className="space-y-4">
      <Card>
        <SectionTitle
          title="盘中监控"
          subtitle="实时前20只作预览，不会污染正式收盘批次。"
          action={
            <div className="flex gap-2">
              <Button onClick={onRefresh} disabled={busy === "refresh" || running} variant="primary">
                <RefreshCw className={`h-3.5 w-3.5 ${busy === "refresh" || running ? "animate-spin" : ""}`} />
                手动刷新
              </Button>
              <Button onClick={onPreview} disabled={busy === "preview"} variant="ghost">
                盘中前20预览
              </Button>
            </div>
          }
        />
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
          <StatTile label="自动刷新" value={autoRefreshActive ? "开启" : "暂停"} tone={autoRefreshActive ? "green" : "slate"} />
          <StatTile label="倒计时" value={autoRefreshActive ? `${countdown ?? "-"}秒` : "-"} tone="cyan" />
          <StatTile label="刷新频率" value={intervalSeconds ? `${intervalSeconds}秒` : "休止"} />
          <StatTile label="上次刷新" value={latestRefreshTime(payload)} />
          <StatTile label="接口耗时" value={payload.durationMs ? `${payload.durationMs}ms` : "-"} />
          <StatTile label="行情源" value={quoteSource(settings, payload)} />
          <StatTile label="数据年龄" value={dataAgeLabel(payload)} tone={payload.isStale ? "red" : "green"} />
        </div>
        {payload.isStale && (
          <div className="mt-3 flex items-center gap-2 rounded border border-rose-900 bg-rose-950/25 p-3 text-xs font-bold text-rose-300">
            <AlertCircle className="h-4 w-4" />
            当前行情数据已标记为过期或缓存，请不要把它当作新信号来源。
          </div>
        )}
        <div className="mt-3 text-xs text-slate-500">
          当前市场阶段：<span className="font-bold text-slate-300">{marketPhaseLabels[phase] || phase}</span>
        </div>
      </Card>

      <Card>
        <SectionTitle title="盘中前20预览" subtitle="展示新进、跌出、排名上升、排名下降；仅作盘中观察，不改变正式收盘批次。" />
        <div className="mt-4 grid gap-4 xl:grid-cols-4">
          <ChangeList title="新进实时前20" rows={changes.newEntries || []} tone="green" />
          <ChangeList title="跌出实时前20" rows={changes.dropped || []} tone="red" />
          <ChangeList title="排名上升" rows={changes.rankUp || []} tone="cyan" />
          <ChangeList title="排名下降" rows={changes.rankDown || []} tone="amber" />
        </div>
      </Card>
    </div>
  );
}

function ChangeList({ title, rows, tone }: { title: string; rows: TurnoverChangeStock[]; tone: "green" | "red" | "cyan" | "amber" }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950/50 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs font-black text-slate-200">{title}</div>
        <Badge tone={tone}>{rows.length}</Badge>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="暂无变化" />
      ) : (
        <div className="space-y-2">
          {rows.map(row => (
            <div key={`${title}_${row.code}_${row.rank || row.newRank || row.oldRank || ""}`} className="rounded border border-slate-800 bg-slate-900/50 p-2">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-xs font-bold text-slate-100">{row.name || row.code}</div>
                  <div className="font-mono text-[10px] text-slate-500">{row.code}</div>
                </div>
                <div className="font-mono text-xs font-black text-slate-200">
                  {row.oldRank ? `#${row.oldRank}` : ""}
                  {row.newRank ? ` → #${row.newRank}` : row.rank ? `#${row.rank}` : row.currentRank === null ? "跌出" : "-"}
                </div>
              </div>
              <div className="mt-1 font-mono text-[11px] text-slate-500">{compactMoney(row.volume)}</div>
              {row.exclusionReason && <div className="mt-1 text-[10px] text-amber-300">{row.exclusionReason}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
