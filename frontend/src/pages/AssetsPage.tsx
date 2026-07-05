import { Badge, Card, SectionTitle, StatTile } from "../components/common/Primitives";
import { money, pct } from "../api/adapters";
import type { AccountMode, AccountState } from "../types";

export function AssetsPage({ account, mode }: { account: AccountState; mode: AccountMode }) {
  const totalTone = Number(account.totalPnL || 0) >= 0 ? "green" : "red";
  return (
    <div className="space-y-4">
      <Card>
        <SectionTitle
          title="资产看板"
          subtitle="模拟训练和实盘记录相互独立；交易流水是资产计算的权威数据。"
          action={<Badge tone={mode === "real" ? "amber" : "cyan"}>{mode === "real" ? "实盘记录" : "模拟训练"}</Badge>}
        />
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
          <StatTile label="初始本金" value={money(account.initialCash)} />
          <StatTile label="可用现金" value={money(account.availableCash)} tone="green" />
          <StatTile label="持仓市值" value={money(account.holdingValue)} />
          <StatTile label="当前总资产" value={money(account.totalAssets)} tone="cyan" />
          <StatTile label="已实现盈亏" value={money(account.realizedPnL)} tone={Number(account.realizedPnL || 0) >= 0 ? "green" : "red"} />
          <StatTile label="浮动盈亏" value={money(account.floatingPnL)} tone={Number(account.floatingPnL || 0) >= 0 ? "green" : "red"} />
          <StatTile label="总盈亏" value={money(account.totalPnL)} tone={totalTone} />
          <StatTile label="总收益率" value={pct(account.totalReturnPct)} tone={totalTone} />
          <StatTile label="今日盈亏" value={money(account.todayPnL || 0)} tone={Number(account.todayPnL || 0) >= 0 ? "green" : "red"} />
          <StatTile label="今日已实现" value={money(account.todayRealizedPnL || 0)} tone={Number(account.todayRealizedPnL || 0) >= 0 ? "green" : "red"} />
          <StatTile label="费用累计" value="见交易流水" />
          <StatTile label="估值日期" value={account.valuationDate || account.asOfDate || "-"} />
        </div>
      </Card>
      <Card>
        <SectionTitle title="同花顺手工对账" subtitle="仅用于手工对账，不改变交易流水权威数据。" />
        <div className="mt-3 rounded border border-slate-800 bg-slate-950/60 p-4 text-xs leading-6 text-slate-500">
          当前对账模式：<span className="font-bold text-slate-300">{account.reconciliationMode ? "已启用" : "未启用"}</span>。
          如需调整对账口径，请到设置页录入券商账户侧的现金、市值和今日盈亏；系统仍以本地交易流水作为买卖记录事实来源。
        </div>
      </Card>
    </div>
  );
}
