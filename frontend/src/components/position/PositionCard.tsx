import { Badge, Card, Field } from "../common/Primitives";
import { compactMoney, money, pct, positionStatusLabel, price } from "../../api/adapters";
import { ExitDecisionPanel } from "./ExitDecisionPanel";
import type { Position } from "../../types";

export function PositionCard({
  position,
  onSell,
  onDefer,
}: {
  position: Position;
  onSell: (position: Position) => void;
  onDefer: (position: Position) => void;
}) {
  const pnlTone = Number(position.floatingPnL || 0) >= 0 ? "green" : "red";
  return (
    <Card className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-black text-slate-100">{position.name}</div>
          <div className="mt-1 font-mono text-xs text-slate-500">{position.code}</div>
        </div>
        <Badge tone={position.riskLevel === "danger" ? "red" : position.riskLevel === "warning" ? "amber" : "green"}>{positionStatusLabel(position)}</Badge>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Field label="实时价" value={price(position.currentPrice)} mono />
        <Field label="持仓均价" value={price(position.avgCost)} mono />
        <Field label="持仓数量" value={position.quantity} mono />
        <Field label="可卖数量" value={position.availableQuantity} mono tone={position.availableQuantity > 0 ? "green" : "amber"} />
        <Field label="持仓市值" value={compactMoney(position.marketValue)} mono />
        <Field label="浮动盈亏" value={`${money(position.floatingPnL)} / ${pct(position.floatingPnLPct)}`} mono tone={pnlTone} />
        <Field label="T+1状态" value={position.isT1Locked ? `锁定 ${position.t1LockedQuantity}` : "可卖"} tone={position.isT1Locked ? "amber" : "green"} />
        <Field label="买入日期" value={position.buyDate || "-"} mono />
      </div>
      <ExitDecisionPanel position={position} onSell={onSell} onDefer={onDefer} />
      {position.tradeLink && (
        <div className="rounded border border-slate-800 bg-slate-950/50 p-2 text-[11px] leading-5 text-slate-500">
          交易联动：共 {position.tradeLink.tradeCount || 0} 条流水
          {position.tradeLink.hasComplianceIssue && <span className="ml-2 text-amber-300">审计标签：{position.tradeLink.complianceTags?.join("、")}</span>}
        </div>
      )}
    </Card>
  );
}
