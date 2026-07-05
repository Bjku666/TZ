import { Download, Loader2 } from "lucide-react";
import KLineChart from "../KLineChart";
import { Button, Card, SectionTitle } from "../common/Primitives";
import type { Candidate, HistoryJob, SelectionItem, TradeLog } from "../../types";

export function KLinePanel({
  code,
  name,
  candidate,
  selection,
  trades,
  historyJob,
  busy,
  onFetchOne,
  onFetchAll,
}: {
  code: string;
  name: string;
  candidate?: Candidate | null;
  selection?: SelectionItem | null;
  trades: TradeLog[];
  historyJob: HistoryJob | null;
  busy?: string | null;
  onFetchOne: (code: string) => void;
  onFetchAll: () => void;
}) {
  const stockTrades = trades.filter(item => item.code === code);
  return (
    <Card className="space-y-3">
      <SectionTitle
        title="K线与候选周期"
        subtitle="日K、MA5、MA10、MA20仅用于展示；买卖规则仍以后端视频原版状态为准。"
        action={
          <div className="flex gap-2">
            <Button onClick={() => onFetchOne(code)} disabled={!code || busy === `history:${code}`} variant="ghost">
              {busy === `history:${code}` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
              单股补K
            </Button>
            <Button onClick={onFetchAll} disabled={busy === "history" || historyJob?.status === "running"} variant="ghost">
              {historyJob?.status === "running" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
              全部补K
            </Button>
          </div>
        }
      />
      {historyJob && (
        <div className="rounded border border-slate-800 bg-slate-950/60 p-2 text-[11px] text-slate-400">
          后台补齐进度：
          <span className="ml-1 font-mono text-cyan-300">
            {historyJob.completed}/{historyJob.total}
          </span>
          <span className="ml-3">成功 {historyJob.fetched}</span>
          <span className="ml-3">失败 {historyJob.failed}</span>
          <span className="ml-3">跳过 {historyJob.skipped}</span>
          {historyJob.error && <span className="ml-3 text-rose-300">{historyJob.error}</span>}
        </div>
      )}
      <KLineChart
        code={code}
        name={name}
        selectionDate={selection?.selectionDate || candidate?.selectionDate}
        touchDate={candidate?.touchDetectedAt || candidate?.touchStartedAt || undefined}
        trades={stockTrades}
      />
    </Card>
  );
}
