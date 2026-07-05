import { CheckCircle2, CircleDollarSign, XCircle } from "lucide-react";
import type { ReactNode } from "react";
import { candidateToStock, compactMoney, dateTime, pct, price, selectionToStock, stateLabels, stateTone } from "../../api/adapters";
import { Badge, Button, EmptyState } from "../common/Primitives";
import type { Candidate, SelectionItem } from "../../types";

export type StockPoolTab = "initial" | "observation" | "buy";

export function StockTable({
  tab,
  initial,
  candidates,
  selectedCode,
  onSelectInitial,
  onSelectCandidate,
  onBuy,
}: {
  tab: StockPoolTab;
  initial: SelectionItem[];
  candidates: Candidate[];
  selectedCode?: string;
  onSelectInitial: (item: SelectionItem) => void;
  onSelectCandidate: (item: Candidate) => void;
  onBuy: (item: Candidate) => void;
}) {
  if (tab === "initial") {
    if (initial.length === 0) return <EmptyState title="暂无正式初筛批次" detail="请在收盘后生成正式批次，或明确导入正式收盘榜单。" />;
    return (
      <div className="overflow-auto rounded border border-slate-800">
        <table className="min-w-[1180px] w-full text-left text-xs">
          <thead className="sticky top-0 z-10 bg-slate-950 text-[11px] uppercase text-slate-500">
            <tr>
              <Th>股票名称</Th>
              <Th>股票代码</Th>
              <Th>原始排名</Th>
              <Th>成交额</Th>
              <Th>入选日期</Th>
              <Th>收盘价</Th>
              <Th>入选日MA5</Th>
              <Th>站上MA5</Th>
              <Th>跨日观察</Th>
              <Th>排除原因</Th>
              <Th>数据源</Th>
              <Th>数据截止</Th>
            </tr>
          </thead>
          <tbody>
            {initial.map(item => {
              const selected = selectedCode === item.code;
              return (
                <tr
                  key={item.id || `${item.batchId}:${item.code}`}
                  onClick={() => onSelectInitial(item)}
                  className={`cursor-pointer border-t border-slate-800/70 hover:bg-slate-900/60 ${selected ? "bg-cyan-950/20" : "bg-slate-950/30"}`}
                >
                  <Td strong>{item.name}</Td>
                  <Td mono>{item.code}</Td>
                  <Td mono>#{item.rawRank || "-"}</Td>
                  <Td mono>{compactMoney(item.turnover)}</Td>
                  <Td mono>{item.selectionDate || "-"}</Td>
                  <Td mono>{price(item.closePrice)}</Td>
                  <Td mono>{price(item.ma5Close)}</Td>
                  <Td>
                    <Badge tone={item.aboveMa5 ? "green" : "red"}>{item.aboveMa5 ? "是" : "否"}</Badge>
                  </Td>
                  <Td>
                    <Badge tone={item.candidateCreated ? "cyan" : "slate"}>{item.candidateCreated ? "已转入" : "未转入"}</Badge>
                  </Td>
                  <Td className="max-w-[15rem] truncate">{item.exclusionReason || "-"}</Td>
                  <Td>{item.source || "-"}</Td>
                  <Td mono>{item.dataAsOf || "-"}</Td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  if (candidates.length === 0) {
    return (
      <EmptyState
        title={tab === "buy" ? "暂无当前待买" : "暂无跨日观察候选"}
        detail={tab === "buy" ? "只有后端确认视频原版买点成立时才会显示在这里。" : "正式批次中站上入选日MA5的股票会进入跨日观察。"}
      />
    );
  }

  if (tab === "observation") {
    return (
      <div className="overflow-auto rounded border border-slate-800">
        <table className="min-w-[1220px] w-full text-left text-xs">
          <thead className="sticky top-0 z-10 bg-slate-950 text-[11px] uppercase text-slate-500">
            <tr>
              <Th>股票</Th>
              <Th>入选日期</Th>
              <Th>原始批次</Th>
              <Th>最早可买</Th>
              <Th>等待日</Th>
              <Th>当前价</Th>
              <Th>MA5 live</Th>
              <Th>偏离率</Th>
              <Th>候选状态</Th>
              <Th>最近回踩</Th>
              <Th>行情更新</Th>
              <Th>执行状态</Th>
            </tr>
          </thead>
          <tbody>
            {candidates.map(item => {
              const selected = selectedCode === item.code;
              const stock = candidateToStock(item, "观察");
              return (
                <tr
                  key={item.id}
                  onClick={() => onSelectCandidate(item)}
                  className={`cursor-pointer border-t border-slate-800/70 hover:bg-slate-900/60 ${selected ? "bg-cyan-950/20" : "bg-slate-950/30"}`}
                >
                  <Td strong>
                    {item.name}
                    <span className="ml-2 font-mono text-slate-500">{item.code}</span>
                  </Td>
                  <Td mono>{item.selectionDate}</Td>
                  <Td mono>{item.sourceBatchId || "-"}</Td>
                  <Td mono>{item.eligibleFrom || "-"}</Td>
                  <Td mono>{item.waitingTradeDays}</Td>
                  <Td mono>{price(item.lastLivePrice)}</Td>
                  <Td mono>{price(item.lastMa5Live)}</Td>
                  <Td mono className={Number(item.lastDeviation || 0) >= 0 ? "text-rose-300" : "text-emerald-300"}>
                    {pct(item.lastDeviation)}
                  </Td>
                  <Td>
                    <Badge tone={stateTone[item.state] || "slate"}>{stateLabels[item.state] || item.state}</Badge>
                  </Td>
                  <Td mono>{dateTime(item.touchDetectedAt || item.touchStartedAt)}</Td>
                  <Td mono>{dateTime(item.updatedAt)}</Td>
                  <Td className="max-w-[15rem] truncate">{stock.executionBlockReasons?.join("；") || stock.signalReason || "-"}</Td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="overflow-auto rounded border border-slate-800">
      <table className="min-w-[1180px] w-full text-left text-xs">
        <thead className="sticky top-0 z-10 bg-slate-950 text-[11px] uppercase text-slate-500">
          <tr>
            <Th>股票</Th>
            <Th>当前价</Th>
            <Th>MA5 live</Th>
            <Th>偏离率</Th>
            <Th>进入回踩区</Th>
            <Th>买入窗口</Th>
            <Th>原版信号</Th>
            <Th>执行状态</Th>
            <Th>资金</Th>
            <Th>阻断原因</Th>
            <Th>人工确认</Th>
          </tr>
        </thead>
        <tbody>
          {candidates.map(item => {
            const stock = candidateToStock(item, "待买");
            const selected = selectedCode === item.code;
            return (
              <tr
                key={item.id}
                onClick={() => onSelectCandidate(item)}
                className={`cursor-pointer border-t border-slate-800/70 hover:bg-slate-900/60 ${selected ? "bg-cyan-950/20" : "bg-slate-950/30"}`}
              >
                <Td strong>
                  {item.name}
                  <span className="ml-2 font-mono text-slate-500">{item.code}</span>
                </Td>
                <Td mono>{price(item.lastLivePrice)}</Td>
                <Td mono>{price(item.lastMa5Live)}</Td>
                <Td mono className={Number(item.lastDeviation || 0) >= 0 ? "text-rose-300" : "text-emerald-300"}>
                  {pct(item.lastDeviation)}
                </Td>
                <Td mono>{dateTime(item.touchDetectedAt || item.touchStartedAt)}</Td>
                <Td>
                  <Badge tone={item.state === "BUY_READY" ? "green" : "amber"}>{item.state === "BUY_READY" ? "当前允许" : "等待窗口"}</Badge>
                </Td>
                <Td>
                  <Badge tone={stock.signalQualified ? "green" : "slate"}>
                    {stock.signalQualified ? <CheckCircle2 className="mr-1 h-3 w-3" /> : <XCircle className="mr-1 h-3 w-3" />}
                    {stock.signalQualified === undefined ? "未知" : stock.signalQualified ? "signalQualified" : "未成立"}
                  </Badge>
                </Td>
                <Td>
                  <Badge tone={stock.executionAllowed ? "green" : "red"}>{stock.executionAllowed ? "executionAllowed" : "受阻"}</Badge>
                </Td>
                <Td>
                  <Badge tone="cyan">
                    <CircleDollarSign className="mr-1 h-3 w-3" />
                    后端校验
                  </Badge>
                </Td>
                <Td className="max-w-[15rem] truncate">{stock.executionBlockReasons?.join("；") || "无"}</Td>
                <Td>
                  <Button
                    onClick={event => {
                      event.stopPropagation();
                      onBuy(item);
                    }}
                    disabled={!stock.executionAllowed}
                    variant="primary"
                  >
                    确认买入
                  </Button>
                </Td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children }: { children: ReactNode }) {
  return <th className="whitespace-nowrap px-3 py-2 font-black">{children}</th>;
}

function Td({
  children,
  mono = false,
  strong = false,
  className = "",
}: {
  children: ReactNode;
  mono?: boolean;
  strong?: boolean;
  className?: string;
}) {
  return <td className={`whitespace-nowrap px-3 py-2 ${mono ? "font-mono" : ""} ${strong ? "font-bold text-slate-100" : "text-slate-300"} ${className}`}>{children}</td>;
}
