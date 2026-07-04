import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  AlertCircle,
  BarChart3,
  Briefcase,
  CheckCircle2,
  Clock3,
  Database,
  FileSpreadsheet,
  FileText,
  RefreshCw,
  Settings,
  Upload,
  Wallet,
  XCircle,
} from "lucide-react";
import type {
  AccountState,
  Candidate,
  Position,
  RuleConfig,
  SelectionBatch,
  SelectionItem,
  TradeLog,
  TurnoverChanges,
  WorkbenchPayload,
} from "./types";

type TabKey =
  | "initial"
  | "observation"
  | "buy"
  | "positions"
  | "trades"
  | "assets"
  | "review"
  | "import"
  | "settings";

const tabs: Array<{ key: TabKey; label: string; icon: typeof Activity }> = [
  { key: "initial", label: "今日初筛", icon: BarChart3 },
  { key: "observation", label: "跨日观察", icon: Clock3 },
  { key: "buy", label: "当前待买", icon: CheckCircle2 },
  { key: "positions", label: "持仓监控", icon: Briefcase },
  { key: "trades", label: "交易记录", icon: FileText },
  { key: "assets", label: "资产看板", icon: Wallet },
  { key: "review", label: "复盘报告", icon: Activity },
  { key: "import", label: "数据导入", icon: FileSpreadsheet },
  { key: "settings", label: "设置", icon: Settings },
];

const stateLabels: Record<string, string> = {
  INITIAL_SCREENED: "初筛入选",
  INITIAL_REJECTED: "初筛未通过",
  WAITING_ELIGIBLE_DATE: "等待最早可买日",
  OBSERVING: "跨日观察",
  IN_TOUCH_ZONE_OUTSIDE_WINDOW: "回踩区但不在买入时段",
  BUY_READY: "视频买点成立",
  BELOW_MA5: "低于回踩区",
  BOUGHT: "已买入",
  NEXT_DAY_OBSERVING: "次日早盘观察",
  MORNING_EXIT_DUE: "10点未涨停待卖",
  DEFERRED_TO_AFTERNOON: "已延迟至尾盘",
  AFTERNOON_EXIT_DUE: "尾盘待卖",
  LIMIT_UP_HOLD: "涨停持有",
  CLOSED: "已完成",
  INVALIDATED: "候选失效",
  CANCELLED: "已取消",
};

function money(value: unknown): string {
  const n = Number(value || 0);
  if (!Number.isFinite(n)) return "-";
  return n >= 100000000 ? `${(n / 100000000).toFixed(2)}亿` : n.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function pct(value: unknown): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}

async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: options?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || body.message || `请求失败 ${response.status}`);
  }
  return response.json();
}

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded border border-slate-800 bg-slate-950/55 p-4 ${className}`}>{children}</section>;
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0 rounded border border-slate-800 bg-slate-950/60 px-3 py-2">
      <div className="text-[11px] font-semibold text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm font-black text-slate-100">{value}</div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded border border-dashed border-slate-800 p-6 text-center text-sm text-slate-500">{text}</div>;
}

function Badge({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <span className={`inline-flex rounded px-2 py-1 text-[11px] font-bold ${ok ? "bg-emerald-950 text-emerald-300" : "bg-rose-950 text-rose-300"}`}>
      {children}
    </span>
  );
}

export default function App() {
  const [tab, setTab] = useState<TabKey>("initial");
  const [rules, setRules] = useState<RuleConfig | null>(null);
  const [official, setOfficial] = useState<SelectionBatch | null>(null);
  const [initialPool, setInitialPool] = useState<SelectionItem[]>([]);
  const [observationPool, setObservationPool] = useState<Candidate[]>([]);
  const [buyReadyPool, setBuyReadyPool] = useState<Candidate[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<TradeLog[]>([]);
  const [account, setAccount] = useState<AccountState | null>(null);
  const [changes, setChanges] = useState<TurnoverChanges | null>(null);
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const activeCandidates = useMemo(
    () => observationPool.filter(item => item.state !== "BUY_READY"),
    [observationPool],
  );

  async function loadAll() {
    setLoading(true);
    try {
      const [rulePayload, watchlist, portfolio, tradePayload, settingsPayload] = await Promise.all([
        api<{ config: RuleConfig }>("/api/rules"),
        api<WorkbenchPayload>("/api/selection/official/latest"),
        api<WorkbenchPayload>("/api/portfolio"),
        api<{ list: TradeLog[] }>("/api/trades"),
        api<Record<string, unknown>>("/api/settings"),
      ]);
      setRules(rulePayload.config);
      setOfficial(watchlist.officialSelection || null);
      setInitialPool(watchlist.initialPool || []);
      setObservationPool(watchlist.observationPool || []);
      setBuyReadyPool(watchlist.buyReadyPool || []);
      setPositions(portfolio.positions || []);
      setAccount(portfolio.accountState || null);
      setTrades(tradePayload.list || []);
      setSettings(settingsPayload);
      setDurationMs(watchlist.durationMs ?? null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function refreshQuotes() {
    setLoading(true);
    try {
      const payload = await api<WorkbenchPayload>("/api/watchlist/refresh-quotes");
      setOfficial(payload.officialSelection || official);
      setInitialPool(payload.initialPool || initialPool);
      setObservationPool(payload.observationPool || []);
      setBuyReadyPool(payload.buyReadyPool || []);
      setPositions(payload.positions || []);
      setAccount(payload.accountState || account);
      setDurationMs(payload.durationMs ?? null);
      setMessage(payload.message || "行情已刷新");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "行情刷新失败");
    } finally {
      setLoading(false);
    }
  }

  async function generateOfficial() {
    setLoading(true);
    try {
      const payload = await api<WorkbenchPayload>("/api/selection/official/generate", {
        method: "POST",
        body: JSON.stringify({}),
      });
      setOfficial(payload.officialSelection || null);
      setInitialPool(payload.initialPool || []);
      setObservationPool(payload.observationPool || []);
      setBuyReadyPool(payload.buyReadyPool || []);
      setMessage(payload.message || "正式批次已生成");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "正式批次生成失败");
    } finally {
      setLoading(false);
    }
  }

  async function previewTurnover() {
    setLoading(true);
    try {
      const payload = await api<{ message?: string; intradayPreview?: { changes: TurnoverChanges } }>("/api/selection/preview");
      setChanges(payload.intradayPreview?.changes || null);
      setMessage(payload.message || "盘中前20预览已更新");
      setTab("review");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "盘中预览失败");
    } finally {
      setLoading(false);
    }
  }

  async function confirmBuy(candidate: Candidate) {
    const price = Number(window.prompt("成交价", String(candidate.lastLivePrice || "")));
    const quantity = Number(window.prompt("买入数量，必须为100股整数倍", "100"));
    if (!price || !quantity) return;
    await api("/api/trades", {
      method: "POST",
      body: JSON.stringify({
        code: candidate.code,
        name: candidate.name,
        type: "BUY",
        price,
        quantity,
        reason: "视频原版MA5回踩人工确认买入",
        manualConfirmed: true,
      }),
    });
    setMessage("买入记录已保存");
    await loadAll();
  }

  async function recordSell(position: Position) {
    const price = Number(window.prompt("卖出成交价", String(position.currentPrice || "")));
    const quantity = Number(window.prompt("卖出数量", String(position.availableQuantity || position.quantity)));
    if (!price || !quantity) return;
    await api("/api/trades", {
      method: "POST",
      body: JSON.stringify({
        code: position.code,
        name: position.name,
        type: "SELL",
        price,
        quantity,
        reason: position.originalExitMessage || "视频原版隔日卖出人工记录",
      }),
    });
    setMessage("卖出记录已保存");
    await loadAll();
  }

  async function deferExit(position: Position) {
    await api(`/api/positions/${position.code}/defer-exit`, {
      method: "POST",
      body: JSON.stringify({ buyDate: position.buyDate, reason: "用户显式选择延迟至14:30后处理" }),
    });
    setMessage("已记录尾盘处理决策");
    await loadAll();
  }

  async function uploadImport(asOfficial: boolean) {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setMessage("请选择同花顺表格文件");
      return;
    }
    setLoading(true);
    try {
      const body = await file.arrayBuffer();
      const payload = await api<WorkbenchPayload>(
        `/api/selection/import?filename=${encodeURIComponent(file.name)}&asOfficial=${asOfficial ? "true" : "false"}&fetchHistory=false`,
        { method: "POST", body },
      );
      setOfficial(payload.officialSelection || official);
      setInitialPool(payload.initialPool || initialPool);
      setObservationPool(payload.observationPool || observationPool);
      setBuyReadyPool(payload.buyReadyPool || buyReadyPool);
      setMessage(payload.message || "导入完成");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导入失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/95">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-xl font-black tracking-normal">{rules?.strategyName || "视频原版五日线回踩隔日超短交易纪律系统"}</h1>
            <p className="mt-1 text-xs text-slate-400">
              原版信号、执行约束和工程口径分开记录；不连接券商，不自动下单。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={refreshQuotes} className="inline-flex items-center gap-2 rounded border border-cyan-700 bg-cyan-950 px-3 py-2 text-xs font-bold text-cyan-100">
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> 刷新行情
            </button>
            <button onClick={generateOfficial} className="inline-flex items-center gap-2 rounded border border-emerald-700 bg-emerald-950 px-3 py-2 text-xs font-bold text-emerald-100">
              <Database className="h-4 w-4" /> 生成正式批次
            </button>
            <button onClick={previewTurnover} className="inline-flex items-center gap-2 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-bold text-slate-100">
              <Activity className="h-4 w-4" /> 盘中前20预览
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-4 px-4 py-4 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="space-y-2">
          {tabs.map(item => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                onClick={() => setTab(item.key)}
                className={`flex w-full items-center gap-2 rounded border px-3 py-2 text-left text-sm font-bold ${
                  tab === item.key ? "border-cyan-600 bg-cyan-950 text-cyan-100" : "border-slate-800 bg-slate-900/60 text-slate-300"
                }`}
              >
                <Icon className="h-4 w-4" /> {item.label}
              </button>
            );
          })}
          <Card>
            <div className="text-xs font-bold text-slate-400">规则只读</div>
            <div className="mt-2 grid gap-2 text-xs text-slate-300">
              <div>成交额原始前{rules?.turnoverTopN || 20}</div>
              <div>回踩容差 ±{rules?.touchTolerancePct ?? 0.5}%</div>
              <div>{rules?.morningBuyWindow?.start || "09:30"}-{rules?.morningBuyWindow?.end || "10:00"}</div>
              <div>{rules?.afternoonBuyWindow?.start || "14:30"}-{rules?.afternoonBuyWindow?.end || "15:00"}</div>
              <div>行情新鲜度 {rules?.quoteFreshnessSeconds || 20} 秒</div>
            </div>
          </Card>
        </aside>

        <section className="space-y-4">
          {message && (
            <div className="rounded border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-200">
              {message}
            </div>
          )}
          <div className="grid gap-3 md:grid-cols-4">
            <Stat label="正式批次" value={official?.selectionDate || "未生成"} />
            <Stat label="初筛记录" value={initialPool.length} />
            <Stat label="跨日观察" value={activeCandidates.length} />
            <Stat label="当前待买" value={buyReadyPool.length} />
          </div>

          {tab === "initial" && (
            <Card>
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-black">今日初筛</h2>
                  <p className="mt-1 text-xs text-slate-400">
                    批次来源 {official?.source || "-"}，数据截止 {official?.dataAsOf || "-"}，过滤后不补位。
                  </p>
                </div>
                {durationMs !== null && <span className="text-xs text-slate-500">接口耗时 {durationMs} ms</span>}
              </div>
              <div className="grid gap-3">
                {initialPool.length === 0 && <Empty text="暂无正式收盘批次" />}
                {initialPool.map(item => (
                  <div key={item.id} className="grid gap-3 rounded border border-slate-800 bg-slate-900/45 p-3 md:grid-cols-[5rem_minmax(0,1fr)_7rem_7rem_7rem]">
                    <div className="text-xl font-black text-cyan-300">#{item.rawRank}</div>
                    <div className="min-w-0">
                      <div className="truncate font-black">{item.name} {item.code}</div>
                      <div className="mt-1 text-xs text-slate-400">成交额 {money(item.turnover)}</div>
                    </div>
                    <Stat label="收盘价" value={money(item.closePrice)} />
                    <Stat label="MA5" value={money(item.ma5Close)} />
                    <div className="flex flex-col gap-2">
                      <Badge ok={item.marketAllowed}>{item.marketAllowed ? "范围通过" : "范围排除"}</Badge>
                      <Badge ok={item.aboveMa5}>{item.aboveMa5 ? "站上MA5" : "未站上MA5"}</Badge>
                      {item.exclusionReason && <div className="text-xs text-rose-300">{item.exclusionReason}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {tab === "observation" && (
            <Card>
              <h2 className="mb-4 text-lg font-black">跨日观察</h2>
              <div className="grid gap-3">
                {activeCandidates.length === 0 && <Empty text="暂无活跃候选周期" />}
                {activeCandidates.map(item => (
                  <div key={item.id} className="rounded border border-slate-800 bg-slate-900/45 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-black">{item.name} {item.code}</div>
                        <div className="mt-1 text-xs text-slate-400">入选 {item.selectionDate}，最早可买 {item.eligibleFrom}</div>
                      </div>
                      <span className="rounded bg-slate-950 px-2 py-1 text-xs font-bold text-cyan-200">{stateLabels[item.state] || item.state}</span>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-5">
                      <Stat label="等待交易日" value={item.waitingTradeDays} />
                      <Stat label="当前价" value={money(item.lastLivePrice)} />
                      <Stat label="盘中MA5" value={money(item.lastMa5Live)} />
                      <Stat label="偏离率" value={pct(item.lastDeviation)} />
                      <Stat label="最近触线" value={item.touchDetectedAt || "-"} />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {tab === "buy" && (
            <Card>
              <h2 className="mb-4 text-lg font-black">当前待买</h2>
              <div className="grid gap-3">
                {buyReadyPool.length === 0 && <Empty text="暂无视频原版买点信号" />}
                {buyReadyPool.map(item => (
                  <div key={item.id} className="rounded border border-emerald-800 bg-emerald-950/20 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-black text-emerald-100">{item.name} {item.code}</div>
                        <div className="mt-1 text-xs text-emerald-300">视频原版信号成立，等待用户人工确认</div>
                      </div>
                      <button onClick={() => confirmBuy(item)} className="rounded bg-emerald-600 px-3 py-2 text-xs font-black text-white">
                        人工确认买入
                      </button>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-5">
                      <Stat label="当前价" value={money(item.lastLivePrice)} />
                      <Stat label="MA5" value={money(item.lastMa5Live)} />
                      <Stat label="偏离率" value={pct(item.lastDeviation)} />
                      <Stat label="触线时间" value={item.touchDetectedAt || "-"} />
                      <Stat label="最早可买" value={item.eligibleFrom} />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {tab === "positions" && (
            <Card>
              <h2 className="mb-4 text-lg font-black">持仓监控</h2>
              <div className="grid gap-3">
                {positions.length === 0 && <Empty text="暂无持仓" />}
                {positions.map(pos => (
                  <div key={pos.code} className="rounded border border-slate-800 bg-slate-900/45 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-black">{pos.name} {pos.code}</div>
                        <div className="mt-1 text-xs text-slate-400">买入 {pos.buyDate}，下一交易日 {pos.nextSellableTradeDate}</div>
                      </div>
                      <div className="flex gap-2">
                        <button onClick={() => deferExit(pos)} className="rounded border border-amber-700 px-3 py-2 text-xs font-bold text-amber-200">
                          延迟至尾盘
                        </button>
                        <button onClick={() => recordSell(pos)} className="rounded bg-rose-600 px-3 py-2 text-xs font-black text-white">
                          人工记录卖出
                        </button>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-6">
                      <Stat label="数量" value={pos.quantity} />
                      <Stat label="可卖" value={pos.availableQuantity} />
                      <Stat label="T+1锁定" value={pos.isT1Locked ? "是" : "否"} />
                      <Stat label="当前价" value={money(pos.currentPrice)} />
                      <Stat label="浮盈亏" value={money(pos.floatingPnL)} />
                      <Stat label="退出状态" value={stateLabels[pos.originalExitState || ""] || "-"} />
                    </div>
                    <div className="mt-3 rounded border border-slate-800 bg-slate-950/50 p-3 text-sm text-slate-200">
                      {pos.originalExitMessage || pos.advice}
                      {pos.executionBlocked && <div className="mt-1 text-amber-300">{pos.executionBlockReason}</div>}
                      {pos.programCompletionNote && <div className="mt-1 text-xs text-slate-500">{pos.programCompletionNote}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {tab === "trades" && (
            <Card>
              <h2 className="mb-4 text-lg font-black">交易记录</h2>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="text-xs text-slate-500">
                    <tr>
                      <th className="py-2">日期</th>
                      <th>代码</th>
                      <th>方向</th>
                      <th>价格</th>
                      <th>数量</th>
                      <th>费用</th>
                      <th>审计</th>
                      <th>标签</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map(trade => (
                      <tr key={trade.id} className="border-t border-slate-800">
                        <td className="py-2">{trade.date} {trade.time}</td>
                        <td>{trade.name} {trade.code}</td>
                        <td>{trade.type === "BUY" ? "买入" : "卖出"}</td>
                        <td>{money(trade.price)}</td>
                        <td>{trade.quantity}</td>
                        <td>{money(trade.totalFee)}</td>
                        <td>{trade.rulesConclusion}</td>
                        <td className="max-w-xs truncate">{trade.violationTags?.join("、") || "无"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {tab === "assets" && (
            <Card>
              <h2 className="mb-4 text-lg font-black">资产看板</h2>
              <div className="grid gap-3 md:grid-cols-4">
                <Stat label="初始本金" value={money(account?.initialCash)} />
                <Stat label="可用现金" value={money(account?.availableCash)} />
                <Stat label="持仓市值" value={money(account?.holdingValue)} />
                <Stat label="总资产" value={money(account?.totalAssets)} />
                <Stat label="已实现盈亏" value={money(account?.realizedPnL)} />
                <Stat label="浮动盈亏" value={money(account?.floatingPnL)} />
                <Stat label="总盈亏" value={money(account?.totalPnL)} />
                <Stat label="收益率" value={pct(account?.totalReturnPct)} />
              </div>
            </Card>
          )}

          {tab === "review" && (
            <Card>
              <h2 className="mb-4 text-lg font-black">复盘报告</h2>
              <div className="grid gap-3 md:grid-cols-4">
                <Stat label="正式候选数量" value={initialPool.filter(item => item.candidateCreated).length} />
                <Stat label="发生回踩数量" value={observationPool.filter(item => item.touchDetectedAt).length} />
                <Stat label="实际买入数量" value={trades.filter(item => item.type === "BUY").length} />
                <Stat label="规则执行率" value={`${trades.length ? Math.round((trades.filter(item => item.rulesConclusion === "符合规则").length / trades.length) * 100) : 100}%`} />
              </div>
              {changes && (
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {(["newEntries", "dropped", "rankUp", "rankDown"] as const).map(key => (
                    <div key={key} className="rounded border border-slate-800 bg-slate-900/45 p-3">
                      <div className="mb-2 text-sm font-black">{key}</div>
                      {(changes[key] || []).slice(0, 8).map(item => (
                        <div key={`${key}-${item.code}`} className="text-xs text-slate-300">
                          {item.name || ""} {item.code} {item.oldRank ? `#${item.oldRank}` : ""} {item.newRank ? `→ #${item.newRank}` : ""}
                        </div>
                      ))}
                      {(changes[key] || []).length === 0 && <div className="text-xs text-slate-500">无</div>}
                    </div>
                  ))}
                </div>
              )}
              <p className="mt-4 text-xs text-slate-500">统计用于流程复盘，不代表样本数量足以证明策略稳定盈利。</p>
            </Card>
          )}

          {tab === "import" && (
            <Card>
              <h2 className="mb-4 text-lg font-black">数据导入</h2>
              <div className="flex flex-col gap-3 md:flex-row md:items-center">
                <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm" />
                <button onClick={() => uploadImport(false)} className="inline-flex items-center gap-2 rounded border border-slate-700 px-3 py-2 text-sm font-bold">
                  <Upload className="h-4 w-4" /> 导入为预览
                </button>
                <button onClick={() => uploadImport(true)} className="inline-flex items-center gap-2 rounded border border-emerald-700 bg-emerald-950 px-3 py-2 text-sm font-bold text-emerald-100">
                  <CheckCircle2 className="h-4 w-4" /> 作为正式收盘批次
                </button>
              </div>
            </Card>
          )}

          {tab === "settings" && (
            <Card>
              <h2 className="mb-4 text-lg font-black">设置</h2>
              <div className="grid gap-3 md:grid-cols-3">
                <Stat label="账户模式" value={String(settings.currentMode || "simulation")} />
                <Stat label="初始本金" value={money(settings.activeInitialCash || settings.initialCash)} />
                <Stat label="行情源" value={String(settings.quote_source || settings.quoteSource || "自动切换")} />
                <Stat label="成交额规则" value={`固定前${rules?.turnoverTopN || 20}`} />
                <Stat label="回踩容差" value={`±${rules?.touchTolerancePct ?? 0.5}%`} />
                <Stat label="一手股数" value={rules?.lotSize || 100} />
              </div>
              <div className="mt-4 rounded border border-slate-800 bg-slate-950/45 p-3 text-xs leading-6 text-slate-400">
                市场信息仅供查看，不属于视频原版交易条件。MA5触线容差属于工程测量口径，策略版本升级前不在设置页静默修改。
              </div>
            </Card>
          )}
        </section>
      </main>
    </div>
  );
}
