import { useMemo, useState } from "react";
import { ClipboardList, Clock3, Eye, List, PanelsTopLeft, Plus, StickyNote, X } from "lucide-react";
import type { Position, Side, Trade, Workspace } from "./types";
import { apiPath, money, request, signedMoney, tone } from "./lib";
import { Badge, Card, Empty, Mini, SectionTitle, Stat } from "./ui";

export function Positions({
  workspace: w,
  onTrade,
  onMutate,
}: {
  workspace: Workspace;
  onTrade: (side: Side, code?: string) => void;
  onMutate: (p: Promise<Workspace>) => void;
}) {
  const [view, setView] = useState<"table" | "cards">("table");
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [note, setNote] = useState<Record<string, string>>({});
  const selected = w.positions.find((item) => item.code === selectedCode) || null;
  const lockedShares = w.positions.reduce((sum, item) => sum + item.t1LockedQuantity, 0);
  const availableValue = w.positions.reduce((sum, item) => sum + (item.availableQuantity / Math.max(1, item.quantity)) * item.marketValue, 0);
  const dueCount = w.positions.filter((item) => ["warning", "danger"].includes(item.actionPriority || "")).length;

  const saveNote = (code: string) => {
    const value = (note[code] || "").trim();
    if (!value) return;
    onMutate(request(apiPath(w.mode, `/positions/${code}/notes`, w.strategyId), { method: "POST", body: JSON.stringify({ note: value }) }));
    setNote((current) => ({ ...current, [code]: "" }));
  };

  const defer = (position: Position) => {
    const reason = w.strategyId === "mode3" ? "10:00前突破五日线，延长观察至当日尾盘" : "用户明确延后处理";
    onMutate(request(apiPath(w.mode, `/positions/${position.code}/defer-exit`, w.strategyId), { method: "POST", body: JSON.stringify({ reason }) }));
  };

  const cancelDefer = (position: Position) => {
    onMutate(request(apiPath(w.mode, `/positions/${position.code}/defer-exit`, w.strategyId), { method: "DELETE" }));
  };
  const startBuy = () => {
    if (w.strategyId === "mode3" && w.positions.length) {
      const ok = confirm("本模式原则上不做T、不进行常规补仓，请确认是否属于历史补录或特殊情况。");
      if (!ok) return;
    }
    onTrade("BUY");
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-end gap-3">
        <div className="flex rounded-lg border border-slate-800 bg-slate-950 p-1">
          <button onClick={() => setView("table")} className={`rounded-md px-3 py-2 text-xs font-black ${view === "table" ? "bg-slate-800 text-white" : "text-slate-500"}`}>
            <List size={14} className="mr-1 inline" />
            表格
          </button>
          <button onClick={() => setView("cards")} className={`rounded-md px-3 py-2 text-xs font-black ${view === "cards" ? "bg-slate-800 text-white" : "text-slate-500"}`}>
            <PanelsTopLeft size={14} className="mr-1 inline" />
            卡片
          </button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <Stat label="持仓数量" value={`${w.positions.length} 只`} />
        <Stat label="持仓市值" value={`¥${money(w.account.holdingValue)}`} />
        <Stat label="浮动盈亏" value={signedMoney(w.account.floatingPnL)} valueClass={tone(w.account.floatingPnL)} />
        <Stat label="可卖市值" value={`¥${money(availableValue)}`} />
        <Stat label="T+1 锁定" value={`${lockedShares} 股`} />
        <Stat label="今日待处理" value={`${dueCount} 只`} valueClass={dueCount ? "text-amber-300" : "text-cyan-300"} />
      </div>

      {!w.positions.length ? (
        <Empty text="当前账户没有持仓。请在真实成交后登记买入，系统会自动推导持仓。" />
      ) : (
        <div className="space-y-4">
          <Card className="overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#27313b] px-5 py-4">
              <div>
                <div className="text-[14px] font-black text-white">当前活动持仓账目明细</div>
                <p className="mt-1 text-[11px] leading-5 text-[#77808f]">持仓均价、偏离及决策状态均从对应交易流水按 A 股先进先出算法动态推导</p>
              </div>
              <button className="btn-primary" onClick={startBuy}>
                <Plus size={14} />
                {w.strategyId === "mode3" ? "补录/特殊买入" : "补录/加仓登记"}
              </button>
            </div>
            {view === "table" ? (
              <PositionTable positions={w.positions} selectedCode={selectedCode} onSelect={setSelectedCode} onTrade={onTrade} onDefer={defer} onCancelDefer={cancelDefer} />
            ) : (
              <div className="grid gap-3 p-4 lg:grid-cols-2">
                {w.positions.map((position) => (
                  <PositionCard
                    key={position.code}
                    position={position}
                    selected={selectedCode === position.code}
                    onSelect={() => setSelectedCode(position.code)}
                    onTrade={onTrade}
                    onDefer={() => defer(position)}
                    onCancelDefer={() => cancelDefer(position)}
                  />
                ))}
              </div>
            )}
          </Card>

          {selected && (
            <PositionDetail
              position={selected}
              trades={w.trades.filter((trade) => trade.code === selected.code)}
              note={note[selected.code] || ""}
              onNoteChange={(value) => setNote((current) => ({ ...current, [selected.code]: value }))}
              onSaveNote={() => saveNote(selected.code)}
              onTrade={onTrade}
              onDefer={() => defer(selected)}
              onCancelDefer={() => cancelDefer(selected)}
              onClose={() => setSelectedCode(null)}
            />
          )}
        </div>
      )}
    </div>
  );
}

function PositionTable({
  positions,
  selectedCode,
  onSelect,
  onTrade,
  onDefer,
  onCancelDefer,
}: {
  positions: Position[];
  selectedCode: string | null;
  onSelect: (code: string) => void;
  onTrade: (side: Side, code?: string) => void;
  onDefer: (position: Position) => void;
  onCancelDefer: (position: Position) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1080px] text-left text-xs">
        <thead className="bg-[#111820] text-[#8a94a3]">
          <tr>
            {["股票", "持仓量 / 可卖 / 锁定", "保本成本 / 现价", "持仓市值", "浮动盈亏（比例）", "参考线 / 偏离度", "买入日期 / 天数", "行动决策阶段", "操作区"].map((head) => (
              <th key={head} className="px-4 py-3 font-black">{head}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {positions.map((position) => (
            <tr
              key={position.code}
              onClick={() => onSelect(position.code)}
              className={`cursor-pointer border-t border-[#27313b] hover:bg-[#111821] ${selectedCode === position.code ? "bg-cyan-950/15" : ""}`}
            >
              <td className="px-4 py-3">
                <b className="text-white">{position.name}</b>
                <div className="font-mono text-[10px] text-[#77808f]">{position.code}</div>
              </td>
              <td className="px-4 py-3 font-mono">
                <span className="text-white">{position.quantity}</span>
                <span className="mx-1 text-[#6f7886]">/</span>
                <span className="text-emerald-300">{position.availableQuantity}</span>
                <span className="mx-1 text-[#6f7886]">/</span>
                <span className="text-rose-300">{position.t1LockedQuantity}</span>
              </td>
              <td className="px-4 py-3 font-mono">
                <div className="text-[#9aa3af]">¥{position.avgCost.toFixed(2)}</div>
                <div className="mt-1 text-white">¥{position.currentPrice.toFixed(2)}</div>
                {position.quoteUpdatedAt && <div className="mt-1 text-[10px] text-cyan-300">{position.quoteSource || "quote"} · {position.quoteUpdatedAt}</div>}
              </td>
              <td className="px-4 py-3 font-mono text-white">¥ {money(position.marketValue)}</td>
              <td className={`px-4 py-3 font-mono font-black ${tone(position.floatingPnL)}`}>
                <div>{signedMoney(position.floatingPnL)}</div>
                <div className="mt-1">{position.floatingPnLPct >= 0 ? "+" : ""}{position.floatingPnLPct.toFixed(2)}%</div>
              </td>
              <td className="px-4 py-3 font-mono">
                <div>{referenceLabel(position)} {formatPrice(referencePrice(position), 2)}</div>
                <div className={tone(referenceDistance(position))}>{formatPct(referenceDistance(position))}</div>
                {isMode3Position(position) && position.targetPrice ? <div className="mt-1 text-[10px] text-rose-300">目标 {formatPrice(position.targetPrice, 2)}</div> : null}
                {isMode3Position(position) && position.hardStopPrice ? <div className="mt-1 text-[10px] text-emerald-300">硬止损 {formatPrice(position.hardStopPrice, 2)}</div> : null}
              </td>
              <td className="px-4 py-3 font-mono">
                <div>{position.buyDate}</div>
                <div className="mt-1 text-[10px] text-[#77808f]">持股 {position.holdDays} 天</div>
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={position.status} />
                <div className="mt-1 font-mono text-[10px] text-[#77808f]">{position.nextActionTime || "-"}</div>
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2" onClick={(event) => event.stopPropagation()}>
                  <button className="btn-sell" disabled={!position.canExecuteSellNow} onClick={() => onTrade("SELL", position.code)}>记录卖出</button>
                  {canDefer(position) && <button className="rounded-md border border-amber-800/70 bg-amber-950/25 px-3 py-1.5 text-[11px] font-black text-amber-200" onClick={() => onDefer(position)}>{deferLabel(position)}</button>}
                  {canCancelDefer(position) && <button className="rounded-md border border-slate-700 px-3 py-1.5 text-[11px] font-black text-slate-300" onClick={() => onCancelDefer(position)}>{isMode3Position(position) ? "撤销延长" : "撤销"}</button>}
                  <button className="grid h-7 w-7 place-items-center rounded-md text-[#9aa3af] hover:bg-[#1d2430] hover:text-white" onClick={() => onSelect(position.code)} title="查看详情">
                    <Eye size={14} />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PositionCard({
  position,
  selected,
  onSelect,
  onTrade,
  onDefer,
  onCancelDefer,
}: {
  position: Position;
  selected: boolean;
  onSelect: () => void;
  onTrade: (side: Side, code?: string) => void;
  onDefer: () => void;
  onCancelDefer: () => void;
  key?: string;
}) {
  return (
    <button onClick={onSelect} className={`rounded-lg border p-4 text-left transition ${selected ? "border-cyan-800 bg-cyan-950/20" : "border-slate-800 bg-slate-950/40 hover:border-slate-700"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-black text-white">{position.name}</h3>
          <div className="mt-1 font-mono text-xs text-slate-500">{position.code} · 买入 {position.buyDate} · {position.holdDays} 个交易日</div>
        </div>
        <StatusBadge status={position.status} />
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
        <Mini label="数量/可卖" value={`${position.quantity}/${position.availableQuantity}`} />
        <Mini label="成本/现价" value={`${position.avgCost.toFixed(2)}/${position.currentPrice.toFixed(2)}`} />
        <Mini label="浮动盈亏" value={signedMoney(position.floatingPnL)} cls={tone(position.floatingPnL)} />
        <Mini label="T+1 锁定" value={position.t1LockedQuantity} />
        <Mini label="持仓市值" value={`¥${money(position.marketValue)}`} />
        <Mini label="收益率" value={`${position.floatingPnLPct.toFixed(2)}%`} cls={tone(position.floatingPnLPct)} />
        <Mini label={isMode3Position(position) ? "十日线参考" : "参考线"} value={formatPrice(referencePrice(position), 2)} />
        <Mini label={isMode3Position(position) ? "距十日线" : "偏离度"} value={formatPct(referenceDistance(position))} cls={tone(referenceDistance(position))} />
        {isMode3Position(position) && <Mini label="2%目标价" value={formatPrice(position.targetPrice, 2)} cls="text-rose-300" />}
      </div>
      <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-xs leading-5 text-slate-400">
        {position.advice || position.sellBlockedReason || "按原计划继续观察"}
        {position.nextActionTime && <div className="mt-1 font-mono text-cyan-300">下一节点：{position.nextActionTime}</div>}
      </div>
      <div className="mt-4 flex flex-wrap gap-2" onClick={(event) => event.stopPropagation()}>
        <button className="btn-sell" disabled={!position.canExecuteSellNow} onClick={() => onTrade("SELL", position.code)}>记录卖出</button>
        {canDefer(position) && <button className="btn" onClick={onDefer}>{deferLabel(position)}</button>}
        {canCancelDefer(position) && <button className="btn" onClick={onCancelDefer}>{isMode3Position(position) ? "撤销延长" : "撤销延后"}</button>}
      </div>
    </button>
  );
}

function PositionDetail({
  position,
  trades,
  note,
  onNoteChange,
  onSaveNote,
  onTrade,
  onDefer,
  onCancelDefer,
  onClose,
}: {
  position: Position | null;
  trades: Trade[];
  note: string;
  onNoteChange: (value: string) => void;
  onSaveNote: () => void;
  onTrade: (side: Side, code?: string) => void;
  onDefer?: () => void;
  onCancelDefer?: () => void;
  onClose: () => void;
}) {
  const sortedTrades = useMemo(() => [...trades].sort((a, b) => `${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`)), [trades]);
  if (!position) {
    return (
      <Card className="hidden p-5 xl:block">
        <Empty text="选择一只持仓查看详情。" />
      </Card>
    );
  }
  return (
    <Card className="p-5">
      <SectionTitle
        title="持仓详情"
        subtitle="基础信息、当前策略状态、交易时间线和用户备注。"
        action={<button className="icon-btn" onClick={onClose}><X size={16} /></button>}
      />
      <div className="mt-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-xl font-black text-white">{position.name}</h3>
          <p className="font-mono text-xs text-slate-500">{position.code}</p>
        </div>
        <StatusBadge status={position.status} />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <Mini label={position.quoteUpdatedAt ? "当前价格 / 行情" : "当前价格"} value={position.quoteUpdatedAt ? `${position.currentPrice.toFixed(3)} / ${position.quoteUpdatedAt}` : position.currentPrice.toFixed(3)} />
        <Mini label={isMode3Position(position) ? "十日线参考" : "参考线"} value={formatPrice(referencePrice(position), 3)} />
        <Mini label={isMode3Position(position) ? "距十日线" : "偏离度"} value={formatPct(referenceDistance(position))} cls={tone(referenceDistance(position))} />
        <Mini label="持仓数量" value={position.quantity} />
        <Mini label="可卖/锁定" value={`${position.availableQuantity}/${position.t1LockedQuantity}`} />
        <Mini label="平均成本" value={position.avgCost.toFixed(3)} />
        <Mini label="浮动盈亏" value={signedMoney(position.floatingPnL)} cls={tone(position.floatingPnL)} />
        {isMode3Position(position) && <Mini label="2%目标价" value={formatPrice(position.targetPrice, 3)} cls="text-rose-300" />}
        {isMode3Position(position) && <Mini label="十日线下1%" value={formatPrice(position.warningStopPrice, 3)} cls="text-amber-300" />}
        {isMode3Position(position) && <Mini label="硬止损价" value={formatPrice(position.hardStopPrice, 3)} cls="text-emerald-300" />}
        {isMode3Position(position) && <Mini label="延长观察" value={position.extendedObservation ? "已登记" : "未登记"} cls={position.extendedObservation ? "text-amber-300" : "text-slate-300"} />}
      </div>
      <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950/50 p-3">
        <div className="flex items-center gap-2 text-xs font-black text-slate-300">
          <Clock3 size={14} className="text-cyan-300" />
          当前策略状态
        </div>
        <p className="mt-2 text-xs leading-5 text-slate-500">{position.advice || position.sellBlockedReason || "正常观察。"}</p>
        <div className="mt-2 font-mono text-xs text-cyan-300">下一操作时间：{position.nextActionTime || "-"}</div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn-sell" disabled={!position.canExecuteSellNow} onClick={() => onTrade("SELL", position.code)}>记录卖出</button>
        {canDefer(position) && <button className="btn" onClick={onDefer}>{deferLabel(position)}</button>}
        {canCancelDefer(position) && <button className="btn" onClick={onCancelDefer}>{isMode3Position(position) ? "撤销延长" : "撤销延后"}</button>}
      </div>
      <div className="mt-5">
        <div className="mb-2 flex items-center gap-2 text-xs font-black text-slate-300">
          <StickyNote size={14} className="text-amber-300" />
          备注
        </div>
        <div className="flex gap-2">
          <input className="input" placeholder="添加持仓备注" value={note} onChange={(event) => onNoteChange(event.target.value)} />
          <button className="btn" onClick={onSaveNote}>保存</button>
        </div>
        {position.notes?.length ? (
          <ul className="mt-3 space-y-1 text-[11px] leading-5 text-slate-500">
            {position.notes.slice(-6).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
          </ul>
        ) : null}
      </div>
      <div className="mt-5">
        <div className="mb-2 flex items-center gap-2 text-xs font-black text-slate-300">
          <ClipboardList size={14} className="text-cyan-300" />
          交易时间线
        </div>
        {!sortedTrades.length ? (
          <Empty text="暂无交易时间线。" />
        ) : (
          <div className="space-y-2">
            {sortedTrades.map((trade) => (
              <div key={trade.id} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-xs">
                <div className="flex items-center justify-between gap-3">
                  <span className={trade.type === "BUY" ? "font-black text-emerald-300" : "font-black text-rose-300"}>{trade.type === "BUY" ? "买入" : "卖出"}</span>
                  <span className="font-mono text-slate-500">{trade.date} {trade.time}</span>
                </div>
                <div className="mt-1 font-mono text-slate-300">{trade.quantity} 股 @ {trade.price.toFixed(3)} · 费用 ¥{money(trade.totalFee)}</div>
                <div className="mt-1 text-slate-500">{trade.rulesConclusion} · {trade.violationTags.join("、") || "无违规标签"}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function StatusBadge({ status }: { status: string }) {
  const toneName = status.includes("待") || status.includes("必须") || status.includes("超期") ? "red" : status.includes("锁定") || status.includes("延") ? "amber" : "cyan";
  return <Badge tone={toneName}>{status}</Badge>;
}

function isMode3Position(position: Position) {
  return position.strategyId === "mode3" || position.referenceLine === "MA10";
}

function referenceLabel(position: Position) {
  return isMode3Position(position) ? "MA10" : position.referenceLine || "MA5";
}

function referencePrice(position: Position) {
  return Number(position.referencePrice ?? position.ma5 ?? position.currentPrice ?? 0);
}

function referenceDistance(position: Position) {
  return Number(position.distanceToReferencePct ?? position.deviation5 ?? 0);
}

function formatPrice(value: number | null | undefined, digits = 2) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? `¥${parsed.toFixed(digits)}` : "-";
}

function formatPct(value: number | null | undefined) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "-";
  return `${parsed >= 0 ? "+" : ""}${parsed.toFixed(2)}%`;
}

function deferLabel(position: Position) {
  return isMode3Position(position) ? "突破五日线，延长至尾盘" : "延后处理";
}

function canDefer(position: Position) {
  return position.actionType === "MORNING_EXIT_DUE";
}

function canCancelDefer(position: Position) {
  return position.actionType === "DEFERRED_TO_AFTERNOON" || position.actionType === "AFTERNOON_EXIT_DUE" || position.actionType === "EXTENDED_AFTER_MA5_BREAK" || position.actionType === "SAME_DAY_FINAL_EXIT_DUE" || position.actionType === "MANUAL_REVIEW_DEFERRED" || position.status.includes("延");
}
