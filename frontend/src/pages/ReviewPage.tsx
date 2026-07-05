import { ChevronLeft, ChevronRight, FileText, Save, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { money, pct, todayText } from "../api/adapters";
import { Badge, Button, Card, EmptyState, SectionTitle, StatTile } from "../components/common/Primitives";
import type { AccountState, Candidate, Position, ReportRecord, ReviewContext, SelectionItem, TradeLog } from "../types";

type ReportType = "daily" | "weekly" | "monthly";
type StepKey = "today" | "market" | "sector" | "stock" | "action";

const steps: Array<{ key: StepKey; label: string; title: string; index: string }> = [
  { key: "today", label: "今日复盘", title: "流水审计", index: "01" },
  { key: "market", label: "大盘多空", title: "系统环境", index: "02" },
  { key: "sector", label: "板块回踩", title: "辅助记录", index: "03" },
  { key: "stock", label: "持仓偏差", title: "个股诊断", index: "04" },
  { key: "action", label: "纠错自省", title: "总日报", index: "05" },
];

export function ReviewPage({
  initial,
  observation,
  buyReady,
  trades,
  positions,
  account,
  reviewContext,
  reports,
  busy,
  onSave,
}: {
  initial: SelectionItem[];
  observation: Candidate[];
  buyReady: Candidate[];
  trades: TradeLog[];
  positions: Position[];
  account: AccountState;
  reviewContext: ReviewContext | null;
  reports: Record<ReportType, ReportRecord[]>;
  busy: string | null;
  onSave: (payload: ReportRecord) => Promise<void>;
}) {
  const [active, setActive] = useState<StepKey>("today");
  const [type, setType] = useState<ReportType>("daily");
  const [date, setDate] = useState(todayText());
  const [market, setMarket] = useState("");
  const [sector, setSector] = useState("");
  const [stockReview, setStockReview] = useState("");
  const [sellAudit, setSellAudit] = useState("");
  const [profitExperience, setProfitExperience] = useState("");
  const [lossAnalysis, setLossAnalysis] = useState("");
  const [summary, setSummary] = useState("");
  const [tomorrowPlan, setTomorrowPlan] = useState("");
  const index = Math.max(0, steps.findIndex(step => step.key === active));
  const todayTrades = useMemo(() => trades.filter(item => item.date === date), [date, trades]);
  const todayBuys = todayTrades.filter(item => item.type === "BUY");
  const todaySells = todayTrades.filter(item => item.type === "SELL");
  const compliant = todayTrades.filter(item => item.rulesConclusion === "符合规则");
  const violations = todayTrades.filter(item => item.rulesConclusion !== "符合规则");
  const ruleExecutionRate = todayTrades.length ? (compliant.length / todayTrades.length) * 100 : 100;
  const avgWait = observation.length ? observation.reduce((sum, item) => sum + Number(item.waitingTradeDays || 0), 0) / observation.length : 0;
  const draft = buildDraft({
    date,
    todayBuys,
    todaySells,
    ruleExecutionRate,
    account,
    initialCount: initial.length,
    observationCount: observation.length,
    signalCount: buyReady.length,
    avgWait,
    market,
    sector,
    stockReview,
    sellAudit,
    profitExperience,
    lossAnalysis,
    summary,
    tomorrowPlan,
    positions,
  });

  async function save() {
    const payload: ReportRecord = {
      id: `${type}_${date}`,
      type,
      date,
      buyCount: todayBuys.length,
      sellCount: todaySells.length,
      ruleComplianceRate: Number(ruleExecutionRate.toFixed(2)),
      violations: violations.map(item => `${item.name} ${item.violationTags?.join("、") || item.rulesConclusion}`),
      realizedPnL: account.todayRealizedPnL || 0,
      portfolioRisk: positions.some(item => item.riskLevel === "danger") ? "存在待处理持仓" : "暂无高风险持仓",
      summary,
      tomorrowPlan,
      createdTime: new Date().toISOString(),
      accountSnapshot: account,
      todayTrades,
      currentPositions: positions,
      marketAnalysis: { marketConclusion: market || "暂无真实数据，请手动填写或等待数据源接入" },
      sectorAnalysis: {
        hotSectors: sector || "暂无真实数据，请手动填写或等待数据源接入",
        etfFlowNotes: sector || "暂无真实数据，请手动填写或等待数据源接入",
      },
      stockAnalysis: {
        selfDiagnostics: [],
        diagnosedHoldings: [],
      },
      actionAudit: {
        sellCompliant: sellAudit,
        profitExperience,
        lossAnalysis,
      },
      reflection: { summary, tomorrowPlan },
      summaryStats: {
        buyCount: todayBuys.length,
        sellCount: todaySells.length,
        tradeComplianceRate: Number(ruleExecutionRate.toFixed(2)),
        ruleComplianceRate: Number(ruleExecutionRate.toFixed(2)),
        realizedPnL: account.todayRealizedPnL || 0,
        portfolioRisk: positions.some(item => item.riskLevel === "danger") ? "存在待处理持仓" : "正常",
      },
    };
    await onSave(payload);
  }

  return (
    <div className="space-y-4">
      <Card className="rounded-xl p-4">
        <div className="mb-3 flex flex-col gap-3 border-b border-slate-800 pb-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-cyan-400" />
            <span className="text-xs font-black tracking-wider text-slate-200">盘后步进式闭环复盘系统</span>
          </div>
          <span className="w-fit rounded border border-slate-800 bg-slate-950 px-2.5 py-1 font-mono text-[10px] font-bold text-slate-400">
            复盘进度 {index + 1} / {steps.length}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
          {steps.map((step, stepIndex) => {
            const isActive = active === step.key;
            const complete = stepIndex < index;
            return (
              <button
                key={step.key}
                onClick={() => setActive(step.key)}
                className={`rounded-lg border p-3 text-left transition ${
                  isActive
                    ? "border-cyan-500/70 bg-cyan-950/25 shadow-md shadow-cyan-950/20"
                    : complete
                      ? "border-emerald-900/40 bg-slate-950/70 hover:border-slate-700"
                      : "border-slate-800/70 bg-slate-950/35 hover:border-slate-700"
                }`}
              >
                <div className="flex min-w-0 items-center gap-2">
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-[10px] font-black ${
                      isActive ? "bg-cyan-400 text-slate-950" : complete ? "border border-emerald-700/50 bg-emerald-950 text-emerald-300" : "border border-slate-800 bg-slate-900 text-slate-500"
                    }`}
                  >
                    {complete ? "✓" : step.index}
                  </span>
                  <div className="min-w-0">
                    <span className={`block truncate text-[11px] font-black ${isActive ? "text-cyan-300" : "text-slate-300"}`}>{step.label}</span>
                    <span className="block truncate text-[9px] text-slate-500">{step.title}</span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {active === "today" && (
        <Card className="rounded-xl p-4">
          <SectionTitle title="今日流水与合规审计" subtitle="只按当前视频原版规则快照审计交易，不恢复旧版增强规则。" />
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <StatTile label="买入次数" value={todayBuys.length} />
            <StatTile label="卖出次数" value={todaySells.length} />
            <StatTile label="规则执行率" value={pct(ruleExecutionRate)} tone={ruleExecutionRate >= 90 ? "green" : "amber"} />
            <StatTile label="已实现盈亏" value={money(account.todayRealizedPnL || 0)} tone={Number(account.todayRealizedPnL || 0) >= 0 ? "green" : "red"} />
            <StatTile label="当前持仓" value={positions.length} />
            <StatTile label="违规标签" value={violations.length} tone={violations.length ? "red" : "green"} />
          </div>
          <div className="mt-4">
            {todayTrades.length === 0 ? (
              <EmptyState title="今日暂无交易流水" detail="盘后仍可填写市场、板块和计划，但日报交易区会保持真实空态。" />
            ) : (
              <div className="overflow-auto rounded border border-slate-800">
                <table className="min-w-[840px] w-full text-left text-xs">
                  <thead className="bg-slate-950 text-[11px] text-slate-500">
                    <tr>
                      {["类型", "时间", "股票", "价格", "数量", "规则结论", "标签"].map(head => (
                        <th key={head} className="px-3 py-2 font-black">{head}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {todayTrades.map(trade => (
                      <tr key={trade.id} className="border-t border-slate-800 bg-slate-950/35">
                        <td className="px-3 py-2"><Badge tone={trade.type === "BUY" ? "red" : "green"}>{trade.type === "BUY" ? "买入" : "卖出"}</Badge></td>
                        <td className="px-3 py-2 font-mono">{trade.time}</td>
                        <td className="px-3 py-2 font-bold text-slate-100">{trade.name} <span className="font-mono text-slate-500">{trade.code}</span></td>
                        <td className="px-3 py-2 font-mono">{trade.price.toFixed(2)}</td>
                        <td className="px-3 py-2 font-mono">{trade.quantity}</td>
                        <td className="px-3 py-2"><Badge tone={trade.rulesConclusion === "符合规则" ? "green" : "amber"}>{trade.rulesConclusion}</Badge></td>
                        <td className="px-3 py-2 text-slate-500">{trade.violationTags?.join("、") || "无"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <ReviewFooter active={active} onChange={setActive} />
        </Card>
      )}

      {active === "market" && (
        <Card className="rounded-xl p-4">
          <SectionTitle title="上证、深证及创业板复盘硬指标" subtitle="市场环境只作辅助记录，不能改变视频原版信号。" />
          <textarea value={market} onChange={event => setMarket(event.target.value)} rows={10} placeholder="暂无真实数据，请手动填写或等待数据源接入" className="mt-4 w-full rounded border border-slate-800 bg-slate-950 p-3 text-xs leading-6 text-slate-200 outline-none focus:border-cyan-600" />
          {reviewContext?.marketSnapshot ? (
            <pre className="mt-3 max-h-56 overflow-auto rounded border border-slate-800 bg-slate-950 p-3 text-[11px] text-slate-500">{JSON.stringify(reviewContext.marketSnapshot, null, 2)}</pre>
          ) : (
            <div className="mt-3"><Badge tone="slate">暂无真实数据，请手动填写或等待数据源接入</Badge></div>
          )}
          <ReviewFooter active={active} onChange={setActive} />
        </Card>
      )}

      {active === "sector" && (
        <Card className="rounded-xl p-4">
          <SectionTitle title="行业板块趋势及资金辅助复盘" subtitle="保留记录入口，只展示真实来源或人工填写内容。" />
          <textarea value={sector} onChange={event => setSector(event.target.value)} rows={10} placeholder="暂无真实数据，请手动填写或等待数据源接入" className="mt-4 w-full rounded border border-slate-800 bg-slate-950 p-3 text-xs leading-6 text-slate-200 outline-none focus:border-cyan-600" />
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <StatTile label="正式候选数" value={initial.length} />
            <StatTile label="跨日观察数" value={observation.length} />
            <StatTile label="回踩信号数" value={buyReady.length} tone="green" />
          </div>
          <ReviewFooter active={active} onChange={setActive} />
        </Card>
      )}

      {active === "stock" && (
        <Card className="rounded-xl p-4">
          <SectionTitle title="持仓与今日交易自我诊断" subtitle="当前持仓、今日买入和今日卖出进入复盘；辅助记录只使用真实数据或手写内容。" />
          <div className="mt-4 grid gap-3 xl:grid-cols-2">
            {positions.length === 0 ? (
              <EmptyState title="暂无持仓诊断对象" />
            ) : (
              positions.map(position => (
                <div key={position.code} className="rounded border border-slate-800 bg-slate-950/60 p-3">
                  <div className="font-bold text-slate-100">{position.name} <span className="font-mono text-slate-500">{position.code}</span></div>
                  <div className="mt-2 text-xs leading-5 text-slate-500">{position.originalExitMessage || position.advice || "等待后端下一动作提示"}</div>
                </div>
              ))
            )}
          </div>
          <textarea value={stockReview} onChange={event => setStockReview(event.target.value)} rows={7} placeholder="记录个股候选周期、买卖动作与复盘结论" className="mt-4 w-full rounded border border-slate-800 bg-slate-950 p-3 text-xs leading-6 text-slate-200 outline-none focus:border-cyan-600" />
          <ReviewFooter active={active} onChange={setActive} />
        </Card>
      )}

      {active === "action" && (
        <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <Card className="rounded-xl p-4">
            <SectionTitle title="操作复盘与存档" subtitle="最后只写反思与明日计划，前四步会作为完整快照一起保存。" />
            <div className="mt-4 grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-[10px] font-bold text-slate-500">复盘时间维度</span>
                <select value={type} onChange={event => setType(event.target.value as ReportType)} className="mt-1 h-9 w-full rounded border border-slate-800 bg-slate-950 px-2 text-xs text-slate-200 outline-none focus:border-cyan-600">
                  <option value="daily">日报</option>
                  <option value="weekly">周报</option>
                  <option value="monthly">月报</option>
                </select>
              </label>
              <label className="block">
                <span className="text-[10px] font-bold text-slate-500">复盘参考日期</span>
                <input type="date" value={date} onChange={event => setDate(event.target.value)} className="mt-1 h-9 w-full rounded border border-slate-800 bg-slate-950 px-2 font-mono text-xs text-slate-200 outline-none focus:border-cyan-600" />
              </label>
            </div>
            <ReviewText title="卖出纪律" value={sellAudit} onChange={setSellAudit} />
            <ReviewText title="盈利经验" value={profitExperience} onChange={setProfitExperience} />
            <ReviewText title="亏损分析" value={lossAnalysis} onChange={setLossAnalysis} />
            <ReviewText title="纠错自省日报" value={summary} onChange={setSummary} rows={5} />
            <ReviewText title="明日计划" value={tomorrowPlan} onChange={setTomorrowPlan} rows={5} />
            <div className="mt-4 flex justify-end">
              <Button onClick={save} disabled={busy === "report"} variant="primary">
                <Save className="h-3.5 w-3.5" />
                {busy === "report" ? "保存中" : "保存并合成今日总日报"}
              </Button>
            </div>
          </Card>
          <Card className="rounded-xl p-4">
            <SectionTitle title="总日报草稿" subtitle="按当前真实数据和手写内容合成。" />
            <pre className="mt-4 max-h-[32rem] overflow-auto whitespace-pre-wrap rounded border border-slate-800 bg-slate-950 p-3 text-[11px] leading-5 text-slate-300">{draft}</pre>
            <div className="mt-4">
              <div className="mb-2 flex items-center gap-2 text-xs font-black text-slate-200">
                <FileText className="h-4 w-4 text-cyan-300" />
                历史复盘记录
              </div>
              {reports[type].length === 0 ? (
                <EmptyState title="暂无任何历史复盘记录" />
              ) : (
                <div className="space-y-2">
                  {reports[type].slice(0, 6).map(report => (
                    <div key={report.id} className="rounded border border-slate-800 bg-slate-950/60 p-3 text-xs">
                      <div className="font-bold text-slate-100">{report.date}</div>
                      <div className="mt-1 line-clamp-1 text-slate-500">{String(report.summary || "未填写心得")}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

function ReviewText({ title, value, onChange, rows = 3 }: { title: string; value: string; onChange: (value: string) => void; rows?: number }) {
  return (
    <label className="mt-4 block">
      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{title}</span>
      <textarea value={value} onChange={event => onChange(event.target.value)} rows={rows} className="mt-1 w-full rounded border border-slate-800 bg-slate-950 p-3 text-xs leading-6 text-slate-200 outline-none focus:border-cyan-600" />
    </label>
  );
}

function ReviewFooter({ active, onChange }: { active: StepKey; onChange: (step: StepKey) => void }) {
  const currentIndex = steps.findIndex(step => step.key === active);
  const previous = steps[currentIndex - 1];
  const next = steps[currentIndex + 1];
  return (
    <div className="mt-4 flex flex-col gap-3 border-t border-slate-900 pt-4 sm:flex-row sm:items-center sm:justify-between">
      {previous ? (
        <Button onClick={() => onChange(previous.key)} variant="ghost">
          <ChevronLeft className="h-4 w-4" />
          返回上一步：{previous.label}
        </Button>
      ) : (
        <span />
      )}
      {next && (
        <Button onClick={() => onChange(next.key)} variant="primary">
          进入下一步：{next.label}
          <ChevronRight className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}

function buildDraft({
  date,
  todayBuys,
  todaySells,
  ruleExecutionRate,
  account,
  initialCount,
  observationCount,
  signalCount,
  avgWait,
  market,
  sector,
  stockReview,
  sellAudit,
  profitExperience,
  lossAnalysis,
  summary,
  tomorrowPlan,
  positions,
}: {
  date: string;
  todayBuys: TradeLog[];
  todaySells: TradeLog[];
  ruleExecutionRate: number;
  account: AccountState;
  initialCount: number;
  observationCount: number;
  signalCount: number;
  avgWait: number;
  market: string;
  sector: string;
  stockReview: string;
  sellAudit: string;
  profitExperience: string;
  lossAnalysis: string;
  summary: string;
  tomorrowPlan: string;
  positions: Position[];
}) {
  const lines = [
    `【${date} 视频原版闭环复盘日报】`,
    "",
    "一、流水与合规审计",
    `- 买入 ${todayBuys.length} 次，卖出 ${todaySells.length} 次。`,
    `- 规则执行率：${ruleExecutionRate.toFixed(2)}%`,
    `- 今日已实现盈亏：${money(account.todayRealizedPnL || 0)} 元`,
    "",
    "二、视频原版流程复查",
    `- 正式候选数：${initialCount}`,
    `- 跨日观察数：${observationCount}`,
    `- 回踩信号数：${signalCount}`,
    `- 平均等待交易日：${avgWait.toFixed(1)}`,
    "",
    "三、大盘与板块辅助记录",
    `- 市场环境：${market || "暂无真实数据，请手动填写或等待数据源接入"}`,
    `- 板块观察：${sector || "暂无真实数据，请手动填写或等待数据源接入"}`,
    "",
    "四、自我诊断",
    positions.length
      ? positions.map(item => `- ${item.name}(${item.code})：${item.originalExitMessage || item.advice || "等待后端下一动作提示"}`).join("\n")
      : "- 暂无持仓诊断对象。",
    stockReview ? `- 手写个股复盘：${stockReview}` : "",
    "",
    "五、纠错自省",
    `- 卖出纪律：${sellAudit || "未填写"}`,
    `- 盈利经验：${profitExperience || "未填写"}`,
    `- 亏损分析：${lossAnalysis || "未填写"}`,
    `- 心得：${summary || "未填写"}`,
    "",
    "六、明日计划",
    tomorrowPlan || "没有纪律触发点时空仓等待，只执行后端视频原版信号。",
  ];
  return lines.filter(line => line !== "").join("\n");
}
