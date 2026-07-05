import { AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import { candidateToStock, compactMoney, dateTime, pct, price, selectionToStock, stateLabels, stateTone } from "../../api/adapters";
import { Badge, Card, Field, SectionTitle } from "../common/Primitives";
import { CandidateTimeline } from "./CandidateTimeline";
import type { Candidate, CandidateEvent, SelectionItem } from "../../types";

export function StockDetailPanel({
  candidate,
  selection,
  events,
}: {
  candidate?: Candidate | null;
  selection?: SelectionItem | null;
  events: CandidateEvent[];
}) {
  if (!candidate && !selection) {
    return (
      <Card>
        <SectionTitle title="股票详情" subtitle="选择左侧股票后查看后端候选状态、事件时间线和K线。" />
      </Card>
    );
  }

  const stock = candidate ? candidateToStock(candidate, candidate.state === "BUY_READY" ? "待买" : "观察") : selection ? selectionToStock(selection) : null;
  if (!stock) return null;
  const signalKnown = stock.signalQualified !== undefined;
  const executionKnown = stock.executionAllowed !== undefined;

  return (
    <Card className="space-y-4">
      <SectionTitle
        title={
          <span>
            {stock.name}
            <span className="ml-2 font-mono text-xs text-slate-500">{stock.code}</span>
          </span>
        }
        subtitle={candidate ? "当前候选周期详情" : "正式初筛批次详情"}
        action={<Badge tone={candidate ? stateTone[candidate.state] || "slate" : selection?.candidateCreated ? "cyan" : "slate"}>{candidate ? stateLabels[candidate.state] || candidate.state : selection?.candidateCreated ? "已转入观察" : "批次项目"}</Badge>}
      />

      <div className="grid grid-cols-2 gap-3">
        <Field label="当前价/收盘价" value={price(candidate?.lastLivePrice ?? selection?.closePrice)} mono />
        <Field label="涨跌幅" value="暂无真实数据" />
        <Field label="成交额" value={selection ? compactMoney(selection.turnover) : "-"} mono />
        <Field label="原始排名" value={selection?.rawRank ? `#${selection.rawRank}` : "-"} mono />
        <Field label="入选批次" value={candidate?.sourceBatchId || selection?.batchId || "-"} mono />
        <Field label="入选日期" value={candidate?.selectionDate || selection?.selectionDate || "-"} mono />
        <Field label="最早可交易日" value={candidate?.eligibleFrom || "-"} mono />
        <Field label="等待交易日数" value={candidate?.waitingTradeDays ?? "-"} mono />
        <Field label="入选日收盘" value={price(candidate?.lastClose ?? selection?.closePrice)} mono />
        <Field label="入选日MA5" value={price(candidate?.lastMa5Close ?? selection?.ma5Close)} mono />
        <Field label="盘中MA5 live" value={price(candidate?.lastMa5Live)} mono tone="cyan" />
        <Field label="当前偏离率" value={candidate ? pct(candidate.lastDeviation) : pct(stock.deviation5)} mono tone={Number(candidate?.lastDeviation || stock.deviation5) >= 0 ? "red" : "green"} />
        <Field label="最近触线时间" value={dateTime(candidate?.touchDetectedAt || candidate?.touchStartedAt)} mono />
        <Field label="报价时间" value={dateTime(candidate?.updatedAt)} mono />
        <Field label="数据年龄" value="以后端刷新结果为准" />
        <Field label="K线缓存状态" value="图表加载后显示" />
      </div>

      <div className="grid grid-cols-1 gap-2">
        <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
          <div className="mb-2 text-[11px] font-black text-slate-400">信号与执行拆分</div>
          <div className="grid grid-cols-2 gap-2">
            <Badge tone={stock.signalQualified ? "green" : signalKnown ? "red" : "slate"}>
              {stock.signalQualified ? <CheckCircle2 className="mr-1 h-3 w-3" /> : signalKnown ? <XCircle className="mr-1 h-3 w-3" /> : <AlertCircle className="mr-1 h-3 w-3" />}
              signalQualified: {signalKnown ? (stock.signalQualified ? "true" : "false") : "unknown"}
            </Badge>
            <Badge tone={stock.executionAllowed ? "green" : executionKnown ? "red" : "slate"}>
              {stock.executionAllowed ? <CheckCircle2 className="mr-1 h-3 w-3" /> : executionKnown ? <XCircle className="mr-1 h-3 w-3" /> : <AlertCircle className="mr-1 h-3 w-3" />}
              executionAllowed: {executionKnown ? (stock.executionAllowed ? "true" : "false") : "unknown"}
            </Badge>
          </div>
          <div className="mt-2 text-[11px] leading-5 text-slate-500">
            {stock.executionBlockReasons?.length ? stock.executionBlockReasons.join("；") : stock.signalReason || "无后端阻断原因"}
          </div>
        </div>
      </div>

      <div>
        <div className="mb-2 text-[11px] font-black text-slate-400">候选事件时间线</div>
        <CandidateTimeline events={events} />
      </div>
    </Card>
  );
}
