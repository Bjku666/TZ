import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  CalendarDays,
  FileText,
  LineChart,
  NotebookPen,
  Save,
  ShieldCheck,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import type { CapitalPoint, Review, Trade, Workspace } from "./types";
import { apiPath, defaultStrategies, money, normalizeStrategyId, pct, request, reviewTypeLabel, signedMoney, today, tone } from "./lib";
import { Badge, Card, Empty, Mini, ProgressBar, SectionTitle, Stat } from "./ui";

type ReviewField = "planAndBasis" | "executionAndDeviation" | "resultAndEmotion" | "improvementAndNextPlan";
type ReviewView = "visual" | "daily" | "weekly";
type ReviewKind = "daily" | "weekly";

const dailyFields: Array<[ReviewField, string, string]> = [
  ["planAndBasis", "01 今日计划与交易依据", "原计划、触发证据、是否属于计划内机会"],
  ["executionAndDeviation", "02 执行偏差", "提前、滞后、追高、犹豫、补录或绕开纪律的动作"],
  ["resultAndEmotion", "03 结果归因与情绪", "行情结果、方法问题、执行问题和当时情绪分开写"],
  ["improvementAndNextPlan", "04 明日硬规则", "只保留明天能检查的时间、条件和动作"],
];

const mode3DailyFields: Array<[ReviewField, string, string]> = [
  ["planAndBasis", "01 今日计划与交易依据", "买入是否满足放量、缩量阴线、十日线条件，是否在14:50以后执行并分仓"],
  ["executionAndDeviation", "02 执行偏差", "是否提前买入、买了阳线/放量阴线/第一根阴线，是否追涨、补仓或计划外交易"],
  ["resultAndEmotion", "03 结果归因与情绪", "盈亏来自策略概率还是执行偏差，是否因为想多赚错过止盈或因亏损不愿止损"],
  ["improvementAndNextPlan", "04 下一交易日硬规则", "14:50以前不买入，未到十日线不买，次日10:00前完成主要处理"],
];

const weeklyFields: Array<[ReviewField, string, string]> = [
  ["planAndBasis", "01 本周核心模式", "本周最有效或最应避免的入场条件、持仓处理和退出节奏"],
  ["executionAndDeviation", "02 冲动偏差归因", "提前买、追高、犹豫、延迟卖出、补录失真等行为来源"],
  ["resultAndEmotion", "03 资金曲线与情绪节奏", "账户曲线在哪些节点变形，和情绪状态如何互相影响"],
  ["improvementAndNextPlan", "04 下周风控目标", "下周只保留 1-3 条硬规则，写完后照着执行"],
];

const tabs: Array<[ReviewView, string, string, typeof LineChart]> = [
  ["visual", "盈亏曲线与违纪归因", "资金曲线、净现金流、违规频次、摩擦成本", LineChart],
  ["daily", "每日盘后复盘日志", "计划依据、执行偏差、结果情绪、明日硬规则", CalendarDays],
  ["weekly", "周度总结与冲动偏差", "所选日期所在周统计，周末归档覆盖整周", BookOpen],
];

const emotionOptions = ["冷静", "紧张", "犹豫", "冲动", "后悔", "过度自信"];
const weekDayLabels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

function parseDate(value?: string) {
  const [year, month, day] = String(value || "").split("-").map(Number);
  return Number.isFinite(year) && Number.isFinite(month) && Number.isFinite(day)
    ? new Date(year, month - 1, day)
    : new Date();
}

function formatDate(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function shiftDate(value: string, days: number) {
  const base = parseDate(value);
  base.setDate(base.getDate() + days);
  return formatDate(base);
}

function weekRange(value: string) {
  const base = parseDate(value);
  const weekday = base.getDay() || 7;
  const start = new Date(base);
  start.setDate(base.getDate() - weekday + 1);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return { start: formatDate(start), end: formatDate(end) };
}

function splitEmotion(value: string) {
  const lines = String(value || "").split("\n");
  const emotionLine = [...lines].reverse().find((line) => line.trim().startsWith("情绪标签："));
  const body = lines.filter((line) => !line.trim().startsWith("情绪标签：")).join("\n").trim();
  const emotion = emotionLine?.replace("情绪标签：", "").trim() || "冷静";
  return { body, emotion: emotionOptions.includes(emotion) ? emotion : "冷静" };
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

function normalizeWorkspace(input: Workspace): Workspace {
  const raw = input as Workspace & Record<string, unknown>;
  const strategyId = normalizeStrategyId(typeof raw.strategyId === "string" ? raw.strategyId : undefined);
  const account = objectValue(raw.account);
  const capitalAnalysis = objectValue(raw.capitalAnalysis);
  const reviewSummary = objectValue(raw.reviewSummary);
  const trades = Array.isArray(raw.trades) ? raw.trades : [];
  const positions = Array.isArray(raw.positions) ? raw.positions : [];
  const reviews = Array.isArray(raw.reviews) ? raw.reviews : [];
  const initialCash = numberValue(account.initialCash);
  const totalAssets = numberValue(account.totalAssets) || initialCash;

  return {
    ...input,
    mode: raw.mode === "real" ? "real" : "simulation",
    strategyId,
    strategy: input.strategy || defaultStrategies.find((item) => item.id === strategyId) || defaultStrategies[0],
    strategies: input.strategies?.length ? input.strategies : defaultStrategies,
    account: {
      initialCash,
      availableCash: numberValue(account.availableCash),
      holdingValue: numberValue(account.holdingValue),
      totalAssets,
      realizedPnL: numberValue(account.realizedPnL),
      floatingPnL: numberValue(account.floatingPnL),
      totalPnL: numberValue(account.totalPnL),
      totalReturnPct: numberValue(account.totalReturnPct),
      todayPnL: numberValue(account.todayPnL),
      todayRealizedPnL: numberValue(account.todayRealizedPnL),
      asOfDate: textValue(account.asOfDate, today()),
      reconciliationMode: Boolean(account.reconciliationMode),
    },
    positions: positions.map((item, index) => {
      const position = objectValue(item);
      return {
      ...position,
      code: textValue(position.code, `position-${index}`),
      name: textValue(position.name, textValue(position.code, "未命名持仓")),
      } as Workspace["positions"][number];
    }),
    trades: trades.map((item, index) => {
      const trade = objectValue(item);
      return {
      ...trade,
      id: textValue(trade.id, `trade-${index}`),
      accountMode: raw.mode === "real" ? "real" : "simulation",
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
      strategySnapshot: objectValue(trade.strategySnapshot),
      } as Trade;
    }),
    reviewSummary: {
      tradeCount: numberValue(reviewSummary.tradeCount),
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
      mode3TradeCount: numberValue(reviewSummary.mode3TradeCount),
      nextDayExitRate: numberValue(reviewSummary.nextDayExitRate),
      exitBefore10Rate: numberValue(reviewSummary.exitBefore10Rate),
      targetProfitRate: numberValue(reviewSummary.targetProfitRate),
      averageHoldingTradingDays: numberValue(reviewSummary.averageHoldingTradingDays),
      overduePositionCount: numberValue(reviewSummary.overduePositionCount),
    },
    capitalAnalysis: {
      initialCash: numberValue(capitalAnalysis.initialCash),
      currentCash: numberValue(capitalAnalysis.currentCash),
      holdingValue: numberValue(capitalAnalysis.holdingValue),
      totalAssets: numberValue(capitalAnalysis.totalAssets) || totalAssets,
      cashChange: numberValue(capitalAnalysis.cashChange),
      assetChange: numberValue(capitalAnalysis.assetChange),
      assetChangePct: numberValue(capitalAnalysis.assetChangePct),
      realizedPnL: numberValue(capitalAnalysis.realizedPnL),
      floatingPnL: numberValue(capitalAnalysis.floatingPnL),
      totalFees: numberValue(capitalAnalysis.totalFees),
      netBuyAmount: numberValue(capitalAnalysis.netBuyAmount),
      capitalDeploymentPct: numberValue(capitalAnalysis.capitalDeploymentPct),
      cashRatioPct: numberValue(capitalAnalysis.cashRatioPct),
      positionCount: numberValue(capitalAnalysis.positionCount),
      daily: Array.isArray(capitalAnalysis.daily)
        ? capitalAnalysis.daily.map((item, index) => {
          const point = objectValue(item);
          return {
          date: textValue(point.date, index ? today() : textValue(account.asOfDate, today())),
          totalAssets: numberValue(point.totalAssets) || totalAssets,
          availableCash: numberValue(point.availableCash),
          holdingValue: numberValue(point.holdingValue),
          realizedPnL: numberValue(point.realizedPnL),
          floatingPnL: numberValue(point.floatingPnL),
          totalPnL: numberValue(point.totalPnL),
          tradeCount: numberValue(point.tradeCount),
          buyAmount: numberValue(point.buyAmount),
          sellAmount: numberValue(point.sellAmount),
          fees: numberValue(point.fees),
          };
        })
        : [],
    },
    reviews: reviews.map((item, index) => {
      const review = objectValue(item);
      return {
      ...review,
      id: textValue(review.id, `review-${index}`),
      accountMode: raw.mode === "real" ? "real" : "simulation",
      strategyId: normalizeStrategyId(textValue(review.strategyId, strategyId)),
      type: review.type === "weekly" || review.type === "monthly" ? review.type : "daily",
      date: textValue(review.date, today()),
      planAndBasis: textValue(review.planAndBasis),
      executionAndDeviation: textValue(review.executionAndDeviation),
      resultAndEmotion: textValue(review.resultAndEmotion),
      improvementAndNextPlan: textValue(review.improvementAndNextPlan),
      saved: Boolean(review.saved),
      } as Review;
    }),
  };
}

export function Reviews({ workspace: w, onMutate }: { workspace: Workspace; onMutate: (p: Promise<Workspace>) => void }) {
  const workspace = useMemo(() => normalizeWorkspace(w), [w]);
  const [view, setView] = useState<ReviewView>("visual");
  const [date, setDate] = useState(today());
  const [emotion, setEmotion] = useState("冷静");
  const reviewType: ReviewKind = view === "weekly" ? "weekly" : "daily";
  const range = weekRange(date);
  const reviewDate = view === "weekly" ? range.end : date;
  const existing = workspace.reviews.find((review) => review.type === reviewType && review.date === reviewDate);
  const [form, setForm] = useState<Record<ReviewField, string>>({
    planAndBasis: "",
    executionAndDeviation: "",
    resultAndEmotion: "",
    improvementAndNextPlan: "",
  });

  useEffect(() => {
    const parsed = reviewType === "daily" ? splitEmotion(existing?.resultAndEmotion || "") : null;
    setForm({
      planAndBasis: existing?.planAndBasis || "",
      executionAndDeviation: existing?.executionAndDeviation || "",
      resultAndEmotion: parsed?.body ?? existing?.resultAndEmotion ?? "",
      improvementAndNextPlan: existing?.improvementAndNextPlan || "",
    });
    if (parsed) setEmotion(parsed.emotion);
  }, [existing?.id, existing?.updatedAt, reviewType, reviewDate]);

  const selectedTrades = useMemo(() => {
    if (view === "weekly") return workspace.trades.filter((trade) => trade.date >= range.start && trade.date <= range.end);
    return workspace.trades.filter((trade) => trade.date === date);
  }, [workspace.trades, view, date, range.start, range.end]);
  const stats = useMemo(() => summarizeTrades(selectedTrades), [selectedTrades]);
  const allStats = useMemo(() => summarizeTrades(workspace.trades), [workspace.trades]);
  const violationStats = useMemo(() => collectViolationStats(workspace.trades), [workspace.trades]);
  const netFlows = useMemo(() => stockNetFlows(workspace.trades, workspace.positions.map((item) => item.code)), [workspace.trades, workspace.positions]);

  const patch = (key: ReviewField, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const moveDate = (days: number) => setDate((current) => shiftDate(current, days));
  const save = () => {
    const resultAndEmotion = reviewType === "daily"
      ? [form.resultAndEmotion.trim(), `情绪标签：${emotion}`].filter(Boolean).join("\n")
      : form.resultAndEmotion;
    onMutate(request(apiPath(workspace.mode, "/reviews", workspace.strategyId), {
      method: "POST",
      body: JSON.stringify({
        id: existing?.id || `${reviewType}-${reviewDate}`,
        accountMode: workspace.mode,
        strategyId: workspace.strategyId,
        type: reviewType,
        date: reviewDate,
        ...form,
        resultAndEmotion,
      }),
    }));
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-3 xl:grid-cols-3">
        {tabs.map(([key, label, desc, Icon]) => (
          <button
            key={key}
            onClick={() => setView(key)}
            className={`min-h-[86px] rounded-lg border p-4 text-left transition ${
              view === key
                ? "border-[var(--tz-accent-border)] bg-[var(--tz-accent-soft)] text-white shadow-sm shadow-black/20"
                : "border-[#27313b] bg-[#111821] text-[#8a94a3] hover:border-[#3a4654] hover:text-slate-100"
            }`}
          >
            <div className="flex items-center gap-2">
              <Icon size={17} className={view === key ? "mode-accent" : "text-[#707a88]"} />
              <b className="text-[13px] leading-5">{label}</b>
            </div>
            <div className="mt-2 text-[11px] leading-5 text-[#77808f]">{desc}</div>
          </button>
        ))}
      </div>

      {view !== "visual" && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Card className="flex flex-wrap items-center gap-3 px-4 py-3">
            <div className="flex items-center gap-2 font-black text-white">
              <CalendarDays size={16} className="mode-accent" />
              {view === "weekly" ? "选择周内任意日期" : "选择日复盘日期"}
            </div>
            <input type="date" className="input max-w-44" value={date} onChange={(event) => setDate(event.target.value)} />
            <button className="btn" onClick={() => setDate(today())}>今天</button>
            <button className="btn" onClick={() => moveDate(-1)}>前一天</button>
            <button className="btn" onClick={() => moveDate(1)}>后一天</button>
            <Badge tone={existing ? "green" : "indigo"}>{existing ? "编辑已有复盘" : "新建复盘"}</Badge>
          </Card>
          {view === "weekly" && (
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="slate">统计区间 {range.start} 至 {range.end}</Badge>
              <Badge tone="indigo">归档日 {reviewDate}</Badge>
            </div>
          )}
        </div>
      )}

      {view === "visual" && (
        <VisualDashboard
          workspace={workspace}
          stats={allStats}
          netFlows={netFlows}
          violationStats={violationStats}
          reviews={workspace.reviews}
        />
      )}

      {view === "daily" && (
        <DailyReview
          date={date}
          stats={stats}
          trades={selectedTrades}
          strategyId={workspace.strategyId}
          emotion={emotion}
          onEmotion={setEmotion}
          form={form}
          onPatch={patch}
          onSave={save}
        />
      )}

      {view === "weekly" && (
        <WeeklyReview
          date={reviewDate}
          range={range}
          stats={stats}
          trades={selectedTrades}
          violationStats={collectViolationStats(selectedTrades)}
          form={form}
          onPatch={patch}
          onSave={save}
        />
      )}

      {view !== "visual" && <HistoryList reviews={workspace.reviews.filter((review) => review.type !== "monthly")} />}
    </div>
  );
}

function VisualDashboard({
  workspace: w,
  stats,
  netFlows,
  violationStats,
  reviews,
}: {
  workspace: Workspace;
  stats: ReturnType<typeof summarizeTrades>;
  netFlows: Array<{ code: string; name: string; value: number }>;
  violationStats: Array<{ tag: string; count: number }>;
  reviews: Review[];
}) {
  const strategyAccount = w.strategyAccount || w.account;
  const strategyCapital = w.strategyCapitalAnalysis || w.capitalAnalysis;
  const violations = w.trades.filter((trade) => trade.rulesConclusion !== "符合规则");
  const violationFees = violations.reduce((sum, trade) => sum + trade.totalFee, 0);
  const averageFee = w.trades.length ? w.reviewSummary.totalFees / w.trades.length : 0;
  const estimatedFriction = violationFees + averageFee * violations.length;
  const isMode3 = w.strategyId === "mode3";
  const advice = violationStats.length
    ? `当前最高频偏差是【${violationStats[0].tag}】。下一阶段把这类动作压到 0，买入和卖出都回到【${w.strategy.name}】的规则框架。`
    : "当前交易模式暂无明显违纪类型。下一阶段重点是保持少交易，只记录计划内机会。";
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <Stat label="账户总资产" value={`¥${money(w.account.totalAssets)}`} sub={`账户本金 ¥${money(w.account.initialCash)}`} />
        <Stat label="当前模式盈亏" value={signedMoney(strategyAccount.totalPnL)} sub={pct(strategyAccount.totalReturnPct)} valueClass={tone(strategyAccount.totalPnL)} />
        <Stat label="模式已实现盈亏" value={signedMoney(strategyAccount.realizedPnL)} valueClass={tone(strategyAccount.realizedPnL)} />
        <Stat label="模式浮动盈亏" value={signedMoney(strategyAccount.floatingPnL)} valueClass={tone(strategyAccount.floatingPnL)} />
        <Stat label="纪律执行率" value={`${stats.complianceRate.toFixed(1)}%`} sub={`违规 ${stats.violations} / ${stats.count}`} valueClass={stats.complianceRate >= 90 ? "text-emerald-300" : "text-amber-300"} />
        <Stat label="当前模式费用" value={`¥${money(stats.fees)}`} sub={`${stats.buyCount}/${stats.sellCount} 买卖`} />
      </div>

      {isMode3 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
          <Stat label="模式三总交易" value={`${w.reviewSummary.mode3TradeCount || 0} 笔`} />
          <Stat label="次日完成退出" value={`${Number(w.reviewSummary.nextDayExitRate || 0).toFixed(1)}%`} />
          <Stat label="10:00前退出" value={`${Number(w.reviewSummary.exitBefore10Rate || 0).toFixed(1)}%`} />
          <Stat label="2%目标达到" value={`${Number(w.reviewSummary.targetProfitRate || 0).toFixed(1)}%`} />
          <Stat label="平均持仓日" value={`${Number(w.reviewSummary.averageHoldingTradingDays || 0).toFixed(1)} 天`} />
          <Stat label="超期持仓" value={`${w.reviewSummary.overduePositionCount || 0} 次`} valueClass={w.reviewSummary.overduePositionCount ? "text-rose-300" : "text-emerald-300"} />
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="p-5">
          <SectionTitle title="账户总资产净增长曲线" subtitle="资金曲线按模拟/实盘账户汇总；右侧指标和交易归因按当前交易模式统计。" action={<BarChart3 size={18} className="mode-accent" />} />
          <div className="mt-5">
            <EquityCurve points={w.capitalAnalysis.daily} fallbackValue={w.account.totalAssets} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            <Mini label="账户现金变化" value={signedMoney(w.capitalAnalysis.cashChange)} cls={tone(w.capitalAnalysis.cashChange)} />
            <Mini label="账户资金占用" value={`${w.capitalAnalysis.capitalDeploymentPct.toFixed(1)}%`} />
            <Mini label="账户现金比例" value={`${w.capitalAnalysis.cashRatioPct.toFixed(1)}%`} />
            <Mini label="模式完成周期" value={`${w.reviewSummary.completedCycles} 个`} />
          </div>
        </Card>

        <Card className="p-5">
          <SectionTitle title="当前模式个股盈亏结构" subtitle="只统计当前交易模式内已完成标的，红色为盈利，绿色为亏损。" />
          <div className="mt-5">
            <NetFlowBars items={netFlows} />
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_0.8fr]">
        <Card className="p-5">
          <div className="mb-4 flex items-center gap-2 font-black text-white">
            <AlertTriangle size={16} className="text-rose-300" />
            交易纪律违规归因分析与财务摩擦反馈
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-lg border border-[#27313b] bg-[#111821] p-4">
              <div className="mb-3 text-[11px] font-black text-[#8a94a3]">重复违纪行为频次</div>
              {!violationStats.length ? (
                <div className="text-xs text-[#8a94a3]">暂无违纪标签</div>
              ) : (
                <div className="space-y-3">
                  {violationStats.slice(0, 5).map((item) => (
                    <div key={item.tag}>
                      <div className="mb-1 flex justify-between gap-3 text-xs">
                        <span className="text-slate-300">{item.tag}</span>
                        <span className="font-mono font-black text-rose-300">{item.count} 次</span>
                      </div>
                      <ProgressBar value={(item.count / Math.max(1, violations.length)) * 100} tone="red" />
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="grid gap-3">
              <Mini label="违纪交易数" value={`${violations.length} 笔`} cls={violations.length ? "text-rose-300" : "text-emerald-300"} />
              <Mini label="违纪相关费用" value={`¥${money(violationFees)}`} cls="text-amber-300" />
              <Mini label="摩擦成本估算" value={`¥${money(estimatedFriction)}`} cls="text-rose-300" />
            </div>
            <div className="rounded-lg border border-indigo-900/70 bg-indigo-950/25 p-4 text-xs leading-6 text-indigo-100">
              <div className="mb-2 flex items-center gap-2 font-black text-indigo-200">
                <ShieldCheck size={15} />
                风控改进建议
              </div>
              {advice}
            </div>
          </div>
        </Card>

        <RecentReviews reviews={reviews.filter((review) => review.type !== "monthly")} />
      </div>
    </div>
  );
}

function DailyReview({
  date,
  stats,
  trades,
  strategyId,
  emotion,
  onEmotion,
  form,
  onPatch,
  onSave,
}: {
  date: string;
  stats: ReturnType<typeof summarizeTrades>;
  trades: Trade[];
  strategyId: Workspace["strategyId"];
  emotion: string;
  onEmotion: (value: string) => void;
  form: Record<ReviewField, string>;
  onPatch: (key: ReviewField, value: string) => void;
  onSave: () => void;
}) {
  return (
    <div className="space-y-6">
      <ReviewStats date={date} stats={stats} />
      <TradeAuditTable title="当日交易流水与纪律审计" trades={trades} />
      <ReviewForm
        title="每日盘后复盘日志"
        subtitle="计划依据、执行偏差、结果情绪、明日硬规则"
        fields={strategyId === "mode3" ? mode3DailyFields : dailyFields}
        date={date}
        stats={stats}
        emotion={emotion}
        onEmotion={onEmotion}
        form={form}
        onPatch={onPatch}
        onSave={onSave}
        showEmotion
      />
    </div>
  );
}

function WeeklyReview({
  date,
  range,
  stats,
  trades,
  violationStats,
  form,
  onPatch,
  onSave,
}: {
  date: string;
  range: { start: string; end: string };
  stats: ReturnType<typeof summarizeTrades>;
  trades: Trade[];
  violationStats: Array<{ tag: string; count: number }>;
  form: Record<ReviewField, string>;
  onPatch: (key: ReviewField, value: string) => void;
  onSave: () => void;
}) {
  const coreProblem = violationStats[0]?.tag || "暂无高频偏差";
  return (
    <div className="space-y-6">
      <Card className="p-5">
        <SectionTitle title="本周度多维纪律审计报告" subtitle="周复盘按所选日期所在自然周统计，统一归档到周日。" action={<Target size={18} className="text-yellow-300" />} />
        <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <Mini label="统计区间" value={`${range.start} / ${range.end}`} />
          <Mini label="归档日期" value={date} />
          <Mini label="区间合规率" value={`${stats.complianceRate.toFixed(2)}%`} cls={stats.complianceRate >= 90 ? "text-emerald-300" : "text-amber-300"} />
          <Mini label="区间交易笔数" value={`${stats.count} 笔`} />
          <Mini label="区间费用" value={`¥${money(stats.fees)}`} />
        </div>
        <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_0.9fr]">
          <WeeklyRhythm trades={trades} range={range} />
          <div className="rounded-lg border border-[#27313b] bg-[#111821] p-4 text-xs leading-6 text-[#cfd6df]">
            <b className="text-white">本周核心突破方向：</b>
            <span className="ml-2 text-[#9aa3af]">
              本周主要问题集中在【{coreProblem}】。下周目标是减少临盘反应，把买入和卖出动作压回当前交易模式规则。
            </span>
          </div>
        </div>
      </Card>

      <TradeAuditTable title="本周交易流水与纪律审计" trades={trades} />

      <ReviewForm
        title="周度总结与冲动偏差"
        subtitle="本周核心模式、冲动偏差、资金情绪、下周风控目标"
        fields={weeklyFields}
        date={date}
        stats={stats}
        form={form}
        onPatch={onPatch}
        onSave={onSave}
      />
    </div>
  );
}

function ReviewStats({ date, stats }: { date: string; stats: ReturnType<typeof summarizeTrades> }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
      <Stat label="复盘日期" value={date} />
      <Stat label="交易笔数" value={`${stats.count} 笔`} />
      <Stat label="买/卖" value={`${stats.buyCount}/${stats.sellCount}`} />
      <Stat label="费用" value={`¥${money(stats.fees)}`} />
      <Stat label="违规/偏差" value={`${stats.violations} 笔`} valueClass={stats.violations ? "text-amber-300" : "text-emerald-300"} />
      <Stat label="纪律执行率" value={`${stats.complianceRate.toFixed(1)}%`} valueClass={stats.complianceRate >= 90 ? "text-emerald-300" : "text-amber-300"} />
    </div>
  );
}

function ReviewForm({
  title,
  subtitle,
  fields,
  date,
  stats,
  emotion,
  onEmotion,
  form,
  onPatch,
  onSave,
  showEmotion = false,
}: {
  title: string;
  subtitle: string;
  fields: Array<[ReviewField, string, string]>;
  date: string;
  stats: ReturnType<typeof summarizeTrades>;
  emotion?: string;
  onEmotion?: (value: string) => void;
  form: Record<ReviewField, string>;
  onPatch: (key: ReviewField, value: string) => void;
  onSave: () => void;
  showEmotion?: boolean;
}) {
  return (
    <Card className="p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-[#27313b] pb-4">
        <div className="flex items-center gap-2 font-black text-white">
          <NotebookPen size={18} className="mode-accent" />
          <span>{title}</span>
          <span className="text-[11px] font-normal text-[#8a94a3]">{subtitle}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="slate">{date}</Badge>
          <Badge tone={stats.violations ? "amber" : "green"}>合规率 {stats.complianceRate.toFixed(1)}%</Badge>
          {showEmotion && (
            <select className="input max-w-36" value={emotion} onChange={(event) => onEmotion?.(event.target.value)}>
              {emotionOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          )}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {fields.map(([key, fieldTitle, hint]) => (
          <label key={key} className="rounded-lg border border-[#27313b] bg-[#111821] p-4">
            <b className="text-white">{fieldTitle}</b>
            <p className="mt-1 text-[11px] leading-5 text-[#8a94a3]">{hint}</p>
            <textarea rows={5} className="input mt-3 resize-none" value={form[key]} onChange={(event) => onPatch(key, event.target.value)} />
          </label>
        ))}
      </div>
      <button className="btn-primary mt-5 w-full justify-center py-3" onClick={onSave}>
        <Save size={15} />
        保存复盘
      </button>
    </Card>
  );
}

function TradeAuditTable({ title, trades }: { title: string; trades: Trade[] }) {
  return (
    <Card className="p-5">
      <SectionTitle title={title} subtitle="交易、费用、审计结论和违纪标签全部来自当前交易模式流水。" action={<FileText size={17} className="mode-accent" />} />
      <div className="mt-4 overflow-x-auto">
        {!trades.length ? (
          <Empty text="当前区间暂无交易流水。" />
        ) : (
          <table className="w-full min-w-[920px] text-left text-xs">
            <thead className="bg-[#111820] text-[#8a94a3]">
              <tr>
                {["日期 / 时间", "类型", "股票", "成交", "费用", "审计结论", "违纪标签", "动机 / 备注"].map((head) => (
                  <th key={head} className="px-4 py-3 font-black">{head}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => (
                <tr key={`${trade.accountMode}-${trade.strategyId}-${trade.id}`} className="border-t border-[#27313b] hover:bg-[#111821]">
                  <td className="px-4 py-3 font-mono text-slate-300">
                    <div>{trade.date}</div>
                    <div className="text-[10px] text-[#6f7886]">{trade.time}</div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={trade.type === "BUY" ? "green" : "red"}>{trade.type === "BUY" ? "买入" : "卖出"}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-black text-white">{trade.name}</div>
                    <div className="font-mono text-[10px] text-[#7b8492]">{trade.code}</div>
                  </td>
                  <td className="px-4 py-3 font-mono">
                    <div>¥{money(trade.amount)}</div>
                    <div className="text-[10px] text-[#7b8492]">{trade.price.toFixed(3)} x {trade.quantity}</div>
                  </td>
                  <td className="px-4 py-3 font-mono text-amber-200">¥{money(trade.totalFee)}</td>
                  <td className="px-4 py-3">
                    <Badge tone={trade.rulesConclusion === "符合规则" ? "green" : trade.rulesConclusion === "无法判断" ? "slate" : "amber"}>{trade.rulesConclusion}</Badge>
                  </td>
                  <td className="px-4 py-3 text-[#9aa3af]">{trade.violationTags.length ? trade.violationTags.join("、") : "无"}</td>
                  <td className="max-w-[260px] px-4 py-3 text-[#7b8492]">
                    <div className="line-clamp-2">{trade.reason || trade.remark || "未填写"}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Card>
  );
}

function WeeklyRhythm({ trades, range }: { trades: Trade[]; range: { start: string; end: string } }) {
  const buckets = weekDayLabels.map((label) => ({ label, count: 0, fees: 0, violations: 0 }));
  trades.forEach((trade) => {
    const date = parseDate(trade.date);
    const index = (date.getDay() || 7) - 1;
    buckets[index].count += 1;
    buckets[index].fees += trade.totalFee;
    if (trade.rulesConclusion !== "符合规则") buckets[index].violations += 1;
  });
  const max = Math.max(1, ...buckets.map((item) => item.count));
  return (
    <div className="rounded-lg border border-[#27313b] bg-[#111821] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-[11px] font-black text-[#8a94a3]">周内交易与冲动分布</div>
        <div className="font-mono text-[10px] text-[#667080]">{range.start} / {range.end}</div>
      </div>
      <div className="space-y-3">
        {buckets.map((item) => (
          <div key={item.label} className="grid grid-cols-[42px_1fr_74px] items-center gap-3 text-xs">
            <span className="font-black text-slate-300">{item.label}</span>
            <div className="h-7 rounded-md bg-[#0b1017]">
              <div className={`h-full rounded-md ${item.violations ? "bg-amber-500" : "bg-cyan-500"}`} style={{ width: `${Math.max(4, (item.count / max) * 100)}%` }} />
            </div>
            <span className="text-right font-mono text-[#8a94a3]">{item.count} 笔</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HistoryList({ reviews }: { reviews: Review[] }) {
  return (
    <RecentReviews reviews={reviews} expanded />
  );
}

function RecentReviews({ reviews, expanded = false }: { reviews: Review[]; expanded?: boolean }) {
  return (
    <Card className="p-5">
      <SectionTitle title={expanded ? "历史复盘" : "最近复盘归档"} subtitle="只保留每日与周度复盘，月复盘入口已移除。" />
      {!reviews.length ? (
        <div className="mt-3"><Empty text="当前交易模式暂无复盘。" /></div>
      ) : (
        <div className={`mt-3 grid gap-2 ${expanded ? "md:grid-cols-2 xl:grid-cols-3" : ""}`}>
          {reviews.slice(0, expanded ? 12 : 6).map((review) => (
            <article key={`${review.accountMode}-${review.strategyId}-${review.id}`} className="rounded-lg border border-[#27313b] bg-[#111821] p-3">
              <div className="font-mono text-xs text-indigo-300">{review.date} · {reviewTypeLabel(review.type)}</div>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#8a94a3]">{review.improvementAndNextPlan || review.executionAndDeviation || review.planAndBasis || "未填写"}</p>
            </article>
          ))}
        </div>
      )}
    </Card>
  );
}

function summarizeTrades(trades: Trade[]) {
  const violations = trades.filter((trade) => trade.rulesConclusion !== "符合规则").length;
  const count = trades.length;
  return {
    count,
    buyCount: trades.filter((trade) => trade.type === "BUY").length,
    sellCount: trades.filter((trade) => trade.type === "SELL").length,
    fees: trades.reduce((sum, trade) => sum + trade.totalFee, 0),
    violations,
    complianceRate: count ? ((count - violations) / count) * 100 : 100,
  };
}

function collectViolationStats(trades: Trade[]) {
  const counts = new Map<string, number>();
  trades.forEach((trade) => {
    if (trade.rulesConclusion === "符合规则") return;
    const tags = trade.violationTags.length ? trade.violationTags : [trade.rulesConclusion];
    tags.forEach((tag) => counts.set(tag, (counts.get(tag) || 0) + 1));
  });
  return [...counts.entries()].map(([tag, count]) => ({ tag, count })).sort((a, b) => b.count - a.count);
}

function stockNetFlows(trades: Trade[], openCodes: string[]) {
  const open = new Set(openCodes);
  const groups = new Map<string, { code: string; name: string; value: number }>();
  trades.forEach((trade) => {
    const current = groups.get(trade.code) || { code: trade.code, name: trade.name, value: 0 };
    current.value += trade.type === "BUY" ? -trade.amount - trade.totalFee : trade.amount - trade.totalFee;
    groups.set(trade.code, current);
  });
  return [...groups.values()]
    .filter((item) => Math.abs(item.value) > 0 && !open.has(item.code))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 6);
}

function EquityCurve({ points, fallbackValue }: { points: CapitalPoint[]; fallbackValue: number }) {
  const usable = points.length ? points : [{ date: today(), totalAssets: fallbackValue } as CapitalPoint];
  if (usable.length < 2) {
    return <Empty text="资金曲线需要至少两天数据。继续记录交易后会自动形成曲线。" />;
  }
  const values = usable.map((item) => item.totalAssets);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const polyline = usable.map((item, index) => {
    const x = 8 + (index / Math.max(1, usable.length - 1)) * 86;
    const y = 82 - ((item.totalAssets - min) / range) * 64;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
  const area = `8,88 ${polyline} 94,88`;
  const change = usable[usable.length - 1].totalAssets - usable[0].totalAssets;
  return (
    <div>
      <svg className="h-64 w-full" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="总资产净增长曲线">
        {[20, 40, 60, 80].map((y) => <line key={y} x1="8" x2="94" y1={y} y2={y} stroke="rgba(148,163,184,.12)" strokeWidth="0.3" />)}
        <polygon points={area} fill="rgba(40,168,214,.18)" />
        <polyline points={polyline} fill="none" stroke="var(--tz-accent)" strokeWidth="1.3" vectorEffect="non-scaling-stroke" />
        <line x1="8" x2="94" y1="88" y2="88" stroke="rgba(148,163,184,.35)" strokeWidth="0.5" />
        <line x1="8" x2="8" y1="12" y2="88" stroke="rgba(148,163,184,.35)" strokeWidth="0.5" />
      </svg>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 font-mono text-[10px] text-[#8a94a3]">
        <span>{usable[0].date}</span>
        <span className={`inline-flex items-center gap-1 font-black ${tone(change)}`}>
          {change >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          {signedMoney(change)}
        </span>
        <span>{usable[usable.length - 1].date}</span>
      </div>
    </div>
  );
}

function NetFlowBars({ items }: { items: Array<{ code: string; name: string; value: number }> }) {
  if (!items.length) {
    return <Empty text="暂无已完成标的的净现金流结构。卖出完成后这里会显示贡献或拖累。" />;
  }
  const max = Math.max(...items.map((item) => Math.abs(item.value)), 1);
  return (
    <div className="space-y-4">
      {items.map((item) => {
        const width = Math.max(8, Math.abs(item.value) / max * 100);
        const positive = item.value >= 0;
        return (
          <div key={item.code}>
            <div className="mb-1 flex items-center justify-between gap-3 text-xs">
              <span className="min-w-0 truncate text-slate-300">{item.name} <span className="font-mono text-[#667080]">{item.code}</span></span>
              <span className={`shrink-0 font-mono font-black ${positive ? "text-rose-300" : "text-emerald-300"}`}>{signedMoney(item.value)}</span>
            </div>
            <div className="h-8 rounded-md bg-[#0b1017]">
              <div className={`h-full rounded-md ${positive ? "bg-rose-500" : "bg-emerald-500"}`} style={{ width: `${width}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
