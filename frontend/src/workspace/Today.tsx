import { AlertTriangle, CheckCircle2, Clock3, FileText, Minus, Plus, Settings, ShieldCheck, Wallet } from "lucide-react";
import type { Action, Side, Workspace } from "./types";
import { money, pct, signedMoney, tone } from "./lib";
import { Badge, CapitalSplit, Card, Empty, Mini, TradeTable, Stat } from "./ui";

export function Today({
  workspace: w,
  onTrade,
  onSettings,
  onReviews,
  onPositions,
}: {
  workspace: Workspace;
  onTrade: (side: Side, code?: string) => void;
  onSettings: () => void;
  onReviews: () => void;
  onPositions: () => void;
}) {
  const account = w.account;
  const strategyAccount = w.strategyAccount || w.account;
  const capital = w.capitalAnalysis;
  const strategyCapital = w.strategyCapitalAnalysis || w.capitalAnalysis;
  const accountPositionCount = w.accountPositions?.length ?? w.positions.length;
  const todayTrades = w.trades.filter((item) => item.date === account.asOfDate);
  const todayBuys = todayTrades.filter((item) => item.type === "BUY");
  const todaySells = todayTrades.filter((item) => item.type === "SELL");
  const todayFees = todayTrades.reduce((sum, item) => sum + item.totalFee, 0);
  const compliant = todayTrades.filter((item) => item.rulesConclusion === "符合规则").length;
  const violations = todayTrades.filter((item) => item.rulesConclusion !== "符合规则");
  const t1Count = w.positions.filter((item) => item.t1LockedQuantity > 0).length;
  const todayComplianceRate = todayTrades.length ? (compliant / todayTrades.length) * 100 : null;
  const todayCashImpact = todayTrades.reduce((sum, item) => {
    return item.type === "BUY" ? sum - item.amount - item.totalFee : sum + item.amount - item.totalFee;
  }, 0);
  const auditTitle = violations.length ? "存在纪律偏差" : todayTrades.length ? "纪律执行完美!" : "今日无新交易";
  const auditMessage = violations.length
    ? "今日有交易需要补充原因并纳入复盘。"
    : todayTrades.length
      ? `今日成交未触发当前交易模式的重大偏差，请继续按【${w.strategy.name}】执行。`
      : "今天没有新增成交，纪律面板只保留账户累计结果，不把历史盈亏算作今日操作。";

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <Stat label="当前总资产" value={`¥ ${money(account.totalAssets)}`} sub={`相对本金 ${pct(account.totalReturnPct)}`} valueClass={tone(account.totalPnL)} />
        <Stat label="可用现金余额" value={`¥ ${money(account.availableCash)}`} sub={`现金比重 ${capital.cashRatioPct.toFixed(1)}%`} valueClass="text-cyan-300" />
        <Stat label="今日总盈亏" value={signedMoney(account.todayPnL)} sub={`已实现/浮动 ${signedMoney(account.todayRealizedPnL)} / ${signedMoney(account.floatingPnL)}`} valueClass={tone(account.todayPnL)} />
        <Stat label="账户持仓与市值" value={`¥ ${money(account.holdingValue)}`} sub={`${accountPositionCount} 只账户持仓 / 本模式 T+1 ${t1Count} 只`} />
        <Stat label="当前模式流水" value={`${todayTrades.length} 笔登记`} sub={`买 ${todayBuys.length} / 卖 ${todaySells.length} / 费 ¥${money(todayFees)}`} />
        <Stat
          label="今日纪律执行"
          value={todayComplianceRate === null ? "今日无交易" : `${todayComplianceRate.toFixed(1)}%`}
          sub={todayTrades.length ? `符合/偏差 ${compliant} / ${violations.length}` : `${account.asOfDate} 无新增成交`}
          valueClass={todayComplianceRate === null ? "text-slate-200" : todayComplianceRate >= 90 ? "text-emerald-300" : "text-amber-300"}
        />
      </div>

      <Card className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-2 text-[12px] font-black text-[#8a94a3]">交易纪律快速通道:</span>
          <button className="btn-buy" onClick={() => onTrade("BUY")}>
            <Plus size={14} />
            快速登记买入 (BUY)
          </button>
          <button className="btn-sell" onClick={() => onTrade("SELL")}>
            <Minus size={14} />
            快速登记卖出 (SELL)
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={onSettings}>
            <Wallet size={14} />
            本金与手续费公式设置
          </button>
          <button className="btn" onClick={onReviews}>
            <ShieldCheck size={14} />
            纪律违规检查详情
          </button>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_350px]">
        <div className="space-y-4">
          <BlockTitle title={`今日待办核心纪律卡片 (${w.pendingActions.length})`} />
          {!w.pendingActions.length ? (
            <Card className="p-4">
              <Empty text="当前账户没有必须处理的行动。没有信号时，保持空仓也是纪律。" />
            </Card>
          ) : (
            <div className="space-y-3">
              {w.pendingActions.map((action) => (
                <PendingActionCard key={action.id} action={action} onTrade={onTrade} onPositions={onPositions} />
              ))}
            </div>
          )}

          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-[#27313b] px-5 py-3">
              <div className="flex items-center gap-2 text-[13px] font-black text-white">
                <FileText size={16} className="mode-accent" />
                今日成交记录流水 ({todayTrades.length})
              </div>
              <span className="font-mono text-[10px] text-[#77808f]">{account.asOfDate}</span>
            </div>
            <div className="p-4">
              <TradeTable rows={todayTrades} />
            </div>
          </Card>
        </div>

        <Card className="self-start p-5">
          <div className="flex items-center justify-between">
            <BlockTitle title="今日纪律审计警报" compact />
            <span className="text-[11px] font-black text-rose-300">{violations.length} 个触发</span>
          </div>

          <div className="mt-8 grid place-items-center text-center">
            <div className={`grid h-10 w-10 place-items-center rounded-full border ${violations.length ? "border-amber-700 bg-amber-950/35 text-amber-300" : "border-emerald-700 bg-emerald-950/35 text-emerald-300"}`}>
              {violations.length ? <AlertTriangle size={22} /> : <CheckCircle2 size={22} />}
            </div>
            <div className="mt-4 text-[13px] font-black text-white">{auditTitle}</div>
            <p className="mt-2 max-w-[240px] text-[11px] leading-5 text-[#77808f]">
              {auditMessage}
            </p>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <AuditMetric
              label="今日资金影响"
              value={signedMoney(todayCashImpact)}
              detail={todayTrades.length ? `成交 ${todayTrades.length} 笔 / 费用 ¥${money(todayFees)}` : "无新增成交"}
              cls={tone(todayCashImpact)}
            />
            <AuditMetric
              label="累计资产差额"
              value={signedMoney(strategyAccount.totalPnL)}
              extra={pct(strategyAccount.totalReturnPct)}
              detail={`当前模式 / 本金 ¥${money(strategyAccount.initialCash)}`}
              cls={tone(strategyAccount.totalPnL)}
            />
            <AuditMetric
              label="当前模式净买入"
              value={`¥ ${money(strategyCapital.netBuyAmount)}`}
              detail={w.positions.length ? `${w.positions.length} 只持仓` : "当前空仓"}
            />
            <AuditMetric
              label="当前模式费用"
              value={`¥ ${money(strategyCapital.totalFees)}`}
              detail={`${w.trades.length} 笔历史成交`}
            />
          </div>
          <div className="mt-4">
            <CapitalSplit cashPct={capital.cashRatioPct} holdingPct={capital.capitalDeploymentPct} />
          </div>

          <div className="mt-6 rounded-lg border border-orange-900/60 bg-orange-950/20 p-4 text-[11px] leading-6 text-orange-200">
            <div className="mb-2 flex items-center gap-2 font-black text-orange-300">
              <Settings size={14} />
              {w.strategy.name}交易规则
            </div>
            <p>1. {w.strategy.buyRuleSummary}</p>
            <p>2. {w.strategy.positionRuleSummary}</p>
            <p>3. {w.strategy.reviewFocus}</p>
          </div>
        </Card>
      </div>
    </div>
  );
}

function BlockTitle({ title, compact = false }: { title: string; compact?: boolean }) {
  return (
    <div className={`flex items-center gap-2 ${compact ? "" : "text-[14px]"} font-black text-white`}>
      <span className="notice-dot h-2.5 w-2.5 rounded-full" />
      {title}
    </div>
  );
}

function AuditMetric({
  label,
  value,
  detail,
  extra,
  cls = "text-white",
}: {
  label: string;
  value: string | number;
  detail: string;
  extra?: string | number;
  cls?: string;
}) {
  return (
    <div className="min-h-[84px] rounded-md border border-[#27313b] bg-[#111821] p-3">
      <div className="text-[10px] leading-4 text-[#768191]">{label}</div>
      <div className={`mt-2 break-words font-mono text-[16px] font-black leading-5 ${cls}`}>{value}</div>
      {extra !== undefined && <div className={`mt-1 font-mono text-[16px] font-black leading-5 ${cls}`}>{extra}</div>}
      <div className="mt-2 text-[10px] leading-4 text-[#687080]">{detail}</div>
    </div>
  );
}

function PendingActionCard({
  action,
  onTrade,
  onPositions,
}: {
  action: Action;
  onTrade: (side: Side, code?: string) => void;
  onPositions: () => void;
  key?: string;
}) {
  const toneClass =
    action.priority === "danger"
      ? "border-rose-700/80 bg-rose-950/35"
      : action.priority === "warning"
        ? "border-amber-800/80 bg-amber-950/25"
        : "border-[#27313b] bg-[#151a22]";
  const canSell = ["MORNING_EXIT_DUE", "AFTERNOON_EXIT_DUE", "DEFERRED_TO_AFTERNOON"].includes(action.type);
  return (
    <article className={`rounded-lg border p-4 ${toneClass}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <b className="text-white">
            {action.name} <span className="font-mono text-xs text-[#9aa3af]">({action.code})</span>
          </b>
          <p className="mt-1 text-xs font-bold text-slate-300">{action.title}</p>
        </div>
        {action.nextActionTime && (
          <Badge tone={action.priority === "danger" ? "red" : action.priority === "warning" ? "amber" : "slate"}>
            <Clock3 size={11} className="mr-1" />
            {action.nextActionTime}
          </Badge>
        )}
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-300">{action.message}</p>
      {action.position && (
        <div className="mt-3 grid grid-cols-3 gap-2">
          <Mini label="可卖数量" value={action.position.availableQuantity} />
          <Mini label="当前盈亏" value={signedMoney(action.position.floatingPnL)} cls={tone(action.position.floatingPnL)} />
          <Mini label="下一节点" value={action.position.nextActionTime || "-"} />
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {canSell ? <button className="btn-sell" onClick={() => onTrade("SELL", action.code)}>记录卖出</button> : null}
        <button className="btn" onClick={onPositions}>查看持仓</button>
      </div>
    </article>
  );
}
