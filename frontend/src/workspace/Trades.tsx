import { useMemo, useState } from "react";
import { Download, Minus, Plus, RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import type { Side, Trade, Workspace } from "./types";
import { apiPath, defaultStrategies, money, normalizeStrategyId, request, signedMoney, today, tone } from "./lib";
import { Badge, Card, Stat, TradeTable } from "./ui";

type ConclusionFilter = "ALL" | "符合规则" | "部分不符" | "违规交易" | "无法判断";

export function Trades({
  workspace: w,
  onTrade,
  onEdit,
  onMutate,
}: {
  workspace: Workspace;
  onTrade: (side: Side) => void;
  onEdit: (t: Trade) => void;
  onMutate: (p: Promise<Workspace>) => void;
}) {
  const workspace = useMemo(() => normalizeTradeWorkspace(w), [w]);
  const [query, setQuery] = useState("");
  const [side, setSide] = useState<"ALL" | Side>("ALL");
  const [conclusion, setConclusion] = useState<ConclusionFilter>("ALL");
  const [tradeDate, setTradeDate] = useState("");
  const [backfillOnly, setBackfillOnly] = useState(false);
  const [manualFeeOnly, setManualFeeOnly] = useState(false);
  const [remarkOnly, setRemarkOnly] = useState(false);

  const rows = useMemo(() => {
    return workspace.trades.filter((trade) => {
      const keyword = `${trade.code}${trade.name}${trade.reason || ""}${trade.remark || ""}`;
      if (query && !keyword.includes(query)) return false;
      if (side !== "ALL" && trade.type !== side) return false;
      if (conclusion !== "ALL" && trade.rulesConclusion !== conclusion) return false;
      if (tradeDate && trade.date !== tradeDate) return false;
      if (backfillOnly && !trade.historicalBackfill) return false;
      if (manualFeeOnly && !trade.manualFeeOverride) return false;
      if (remarkOnly && !trade.remark && !trade.reason) return false;
      return true;
    });
  }, [workspace.trades, query, side, conclusion, tradeDate, backfillOnly, manualFeeOnly, remarkOnly]);

  const buyCount = workspace.trades.filter((item) => item.type === "BUY").length;
  const sellCount = workspace.trades.filter((item) => item.type === "SELL").length;
  const turnover = workspace.trades.reduce((sum, item) => sum + item.amount, 0);
  const compliant = workspace.trades.filter((item) => item.rulesConclusion === "符合规则").length;

  const reset = () => {
    setQuery("");
    setSide("ALL");
    setConclusion("ALL");
    setTradeDate("");
    setBackfillOnly(false);
    setManualFeeOnly(false);
    setRemarkOnly(false);
  };

  const exportCsv = () => {
    const header = ["日期", "时间", "方向", "代码", "名称", "价格", "数量", "成交金额", "费用", "纪律结论", "原因", "备注"];
    const body = rows.map((trade) => [
      trade.date,
      trade.time,
      trade.type === "BUY" ? "买入" : "卖出",
      trade.code,
      trade.name,
      trade.price,
      trade.quantity,
      trade.amount,
      trade.totalFee,
      trade.rulesConclusion,
      trade.reason,
      trade.remark,
    ]);
    const csv = [header, ...body]
      .map((line) => line.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `tz-${workspace.mode}-${workspace.strategyId}-trades-${today()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const deleteTrade = (trade: Trade) => {
    const impact = [
      `交易：${trade.date} ${trade.time} ${trade.name} ${trade.type === "BUY" ? "买入" : "卖出"} ${trade.quantity} 股`,
      `成交金额：¥${money(trade.amount)}，费用：¥${money(trade.totalFee)}`,
      "删除后会重新计算当前账户的现金、持仓、资产和复盘统计。",
    ].join("\n");
    if (confirm(`${impact}\n\n确认删除？`)) {
      onMutate(request(apiPath(workspace.mode, `/trades/${trade.id}`, workspace.strategyId), { method: "DELETE" }));
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-7">
        <Stat label="总交易笔数" value={workspace.reviewSummary.tradeCount} />
        <Stat label="买入笔数" value={buyCount} />
        <Stat label="卖出笔数" value={sellCount} />
        <Stat label="总成交金额" value={`¥${money(turnover)}`} />
        <Stat label="总手续费" value={`¥${money(workspace.reviewSummary.totalFees)}`} />
        <Stat label="符合规则比例" value={`${(workspace.trades.length ? (compliant / workspace.trades.length) * 100 : 100).toFixed(1)}%`} />
        <Stat label="累计盈亏" value={signedMoney(workspace.account.totalPnL)} valueClass={tone(workspace.account.totalPnL)} />
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#27313b] pb-4">
          <input className="input max-w-[448px]" placeholder="按股票名称或 6 位代码查询..." value={query} onChange={(event) => setQuery(event.target.value)} />
          <div className="flex flex-wrap gap-2">
            <button className="btn" onClick={() => onMutate(request(apiPath(workspace.mode, "/trades/recalculate-fees", workspace.strategyId), { method: "POST", body: "{}" }))}>
              <RefreshCw size={14} />
              重算手续费
            </button>
            <button className="btn-primary" onClick={exportCsv}>
              <Download size={14} />
              导出成交流水 ({workspace.strategy.name})
            </button>
            <button className="btn-buy" onClick={() => onTrade("BUY")}>
              <Plus size={14} />
              新建买入
            </button>
            <button className="btn-sell" onClick={() => onTrade("SELL")}>
              <Minus size={14} />
              新建卖出
            </button>
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_16rem]">
          <select className="input" value={side} onChange={(event) => setSide(event.target.value as "ALL" | Side)}>
            <option value="ALL">全部类型 (ALL)</option>
            <option value="BUY">买入</option>
            <option value="SELL">卖出</option>
          </select>
          <select className="input" value={conclusion} onChange={(event) => setConclusion(event.target.value as ConclusionFilter)}>
            <option value="ALL">全部审计评级 (ALL)</option>
            <option value="符合规则">符合规则</option>
            <option value="部分不符">部分不符</option>
            <option value="违规交易">违规交易</option>
            <option value="无法判断">无法判断</option>
          </select>
          <select className="input" value={backfillOnly ? "BACKFILL" : "ALL"} onChange={(event) => setBackfillOnly(event.target.value === "BACKFILL")}>
            <option value="ALL">全部来源 (ALL)</option>
            <option value="BACKFILL">历史补录</option>
          </select>
          <button className="btn" onClick={reset}>
            <RotateCcw size={14} />
            重置所有筛选
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <label className="flex min-w-64 items-center gap-2 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-400">
            <span className="shrink-0 font-black text-[#8a94a3]">指定交易日期</span>
            <input type="date" className="input h-8 max-w-40 py-1" value={tradeDate} onChange={(event) => setTradeDate(event.target.value)} />
          </label>
          <button className="btn" onClick={() => setTradeDate("")}>全部日期</button>
          <label className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-400">
            <input type="checkbox" checked={manualFeeOnly} onChange={(event) => setManualFeeOnly(event.target.checked)} />
            手工费用
          </label>
          <label className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-400">
            <input type="checkbox" checked={remarkOnly} onChange={(event) => setRemarkOnly(event.target.checked)} />
            有原因/备注
          </label>
          <Badge tone="slate">当前结果 {rows.length} 笔</Badge>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <TradeTable
          rows={rows}
          actions={(trade) => (
            <div className="flex gap-2">
              <button className="text-cyan-300" onClick={() => onEdit(trade)}>编辑</button>
              <button className="text-rose-400" onClick={() => deleteTrade(trade)}>
                <Trash2 size={14} />
              </button>
            </div>
          )}
        />
      </Card>
    </div>
  );
}

function numberValue(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function textValue(value: unknown, fallback = "") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function objectValue(value: unknown) {
  return value && typeof value === "object" ? value as Record<string, unknown> : {};
}

function normalizeTradeWorkspace(input: Workspace): Workspace {
  const raw = input as Workspace & Record<string, unknown>;
  const mode = raw.mode === "real" ? "real" : "simulation";
  const strategyId = normalizeStrategyId(typeof raw.strategyId === "string" ? raw.strategyId : undefined);
  const account = objectValue(raw.account);
  const reviewSummary = objectValue(raw.reviewSummary);
  const trades = Array.isArray(raw.trades) ? raw.trades : [];

  return {
    ...input,
    mode,
    strategyId,
    strategy: input.strategy || defaultStrategies.find((item) => item.id === strategyId) || defaultStrategies[0],
    strategies: input.strategies?.length ? input.strategies : defaultStrategies,
    account: {
      ...(input.account || {}),
      initialCash: numberValue(account.initialCash),
      availableCash: numberValue(account.availableCash),
      holdingValue: numberValue(account.holdingValue),
      totalAssets: numberValue(account.totalAssets),
      realizedPnL: numberValue(account.realizedPnL),
      floatingPnL: numberValue(account.floatingPnL),
      totalPnL: numberValue(account.totalPnL),
      totalReturnPct: numberValue(account.totalReturnPct),
      todayPnL: numberValue(account.todayPnL),
      todayRealizedPnL: numberValue(account.todayRealizedPnL),
      asOfDate: textValue(account.asOfDate, today()),
      reconciliationMode: Boolean(account.reconciliationMode),
    },
    reviewSummary: {
      ...(input.reviewSummary || {}),
      tradeCount: numberValue(reviewSummary.tradeCount) || trades.length,
      completedCycles: numberValue(reviewSummary.completedCycles),
      winRate: numberValue(reviewSummary.winRate),
      averageWin: numberValue(reviewSummary.averageWin),
      averageLoss: numberValue(reviewSummary.averageLoss),
      profitLossRatio: numberValue(reviewSummary.profitLossRatio),
      totalPnL: numberValue(reviewSummary.totalPnL),
      totalReturnPct: numberValue(reviewSummary.totalReturnPct),
      maxSingleWin: numberValue(reviewSummary.maxSingleWin),
      maxSingleLoss: numberValue(reviewSummary.maxSingleLoss),
      totalFees: numberValue(reviewSummary.totalFees),
      complianceRate: numberValue(reviewSummary.complianceRate),
      violationCount: numberValue(reviewSummary.violationCount),
    },
    trades: trades.map((item, index) => {
      const trade = objectValue(item);
      return {
        ...trade,
        id: textValue(trade.id, `trade-${index}`),
        accountMode: mode,
        strategyId: normalizeStrategyId(textValue(trade.strategyId, strategyId)),
        code: textValue(trade.code, "未知代码"),
        name: textValue(trade.name, textValue(trade.code, "未命名股票")),
        type: trade.type === "SELL" ? "SELL" : "BUY",
        date: textValue(trade.date, today()),
        time: textValue(trade.time, ""),
        price: numberValue(trade.price),
        quantity: numberValue(trade.quantity),
        amount: numberValue(trade.amount),
        commission: numberValue(trade.commission),
        stampDuty: numberValue(trade.stampDuty),
        transferFee: numberValue(trade.transferFee),
        totalFee: numberValue(trade.totalFee),
        reason: textValue(trade.reason),
        remark: textValue(trade.remark),
        rulesConclusion: textValue(trade.rulesConclusion, "无法判断"),
        violationTags: Array.isArray(trade.violationTags) ? trade.violationTags.filter(Boolean).map(String) : [],
        historicalBackfill: Boolean(trade.historicalBackfill),
        manualFeeOverride: Boolean(trade.manualFeeOverride),
      } as Trade;
    }),
  };
}
