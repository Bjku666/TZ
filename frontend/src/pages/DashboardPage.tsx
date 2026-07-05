import { BarChart3, Briefcase, CheckCircle2, Download, Eye, FileText, Lightbulb, RefreshCw, ShieldCheck, Upload } from "lucide-react";
import { dashboardStats, marketPhaseLabels, money, pct, positionStatusLabel, price, stateLabels } from "../api/adapters";
import { Badge, Button, Card, EmptyState, Field, StatTile } from "../components/common/Primitives";
import type { Candidate, MarketPhase, Position, SelectionBatch, SelectionItem, Stock, TradeLog, AccountState } from "../types";
import type { PageKey } from "../layout/Sidebar";

export function DashboardPage({
  official,
  initial,
  observation,
  buyReady,
  positions,
  trades,
  stocks,
  account,
  phase,
  busy,
  onGenerate,
  onRefresh,
  onBackfill,
  onNavigate,
}: {
  official: SelectionBatch | null;
  initial: SelectionItem[];
  observation: Candidate[];
  buyReady: Candidate[];
  positions: Position[];
  trades: TradeLog[];
  stocks: Stock[];
  account: AccountState;
  phase: MarketPhase;
  busy: string | null;
  onGenerate: () => void;
  onRefresh: () => void;
  onBackfill: () => void;
  onNavigate: (page: PageKey) => void;
}) {
  const stats = dashboardStats(official, initial, observation, buyReady, positions, trades, stocks);
  const marketOpen = phase === "trading";
  const pendingExit = positions.filter(item => ["MORNING_EXIT_DUE", "AFTERNOON_EXIT_DUE", "LIMIT_UP_OPENED_EXIT_DUE"].includes(String(item.originalExitState)));
  const compactPositions = positions.slice(0, 3);

  return (
    <div className="space-y-4">
      <Card className="rounded-xl p-4">
        <div className="grid gap-4 xl:grid-cols-[1.35fr_0.95fr]">
          <div className="flex min-w-0 items-start gap-3">
            <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded bg-cyan-950/70 text-cyan-300">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm font-black text-slate-100">欢迎使用强势回踩短线交易纪律系统</h2>
              <p className="mt-2 text-xs leading-6 text-slate-400">
                本系统围绕视频原版五日线回踩隔日超短纪律：正式前20、跨日观察、盘中MA5回踩、人工确认买入、隔日卖出提醒。
              </p>
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/55 p-3">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-black text-cyan-300">
                <Briefcase className="h-4 w-4" />
                盘前第一步
              </div>
              <Button onClick={onGenerate} disabled={busy === "generate"} variant="primary">
                <BarChart3 className="h-3.5 w-3.5" />
                构建今日正式初筛
              </Button>
            </div>
            <div className="text-[11px] leading-5 text-slate-500">
              当前批次：{official?.selectionDate || "暂无"}；只允许收盘后正式生成，盘中请使用前20预览。
            </div>
          </div>
        </div>
      </Card>

      <Card className="rounded-xl p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${marketOpen ? "bg-cyan-400" : "bg-slate-500"}`} />
              <h3 className="text-sm font-black text-slate-100">{marketPhaseLabels[phase] || phase}</h3>
            </div>
            <div className="mt-3 space-y-2 text-xs leading-6 text-slate-400">
              <p><Lightbulb className="mr-1 inline h-4 w-4 text-amber-300" />正式初筛必须来自后端正式批次；实时前20仅预览，不污染收盘批次。</p>
              <p><Lightbulb className="mr-1 inline h-4 w-4 text-amber-300" />候选从下一交易日起跨日等待，买点由后端 MA5 live 与买入窗口共同确认。</p>
            </div>
          </div>
          <div className="hidden text-right xl:block">
            <div className="text-[11px] font-bold text-slate-500">收盘写快照与复盘</div>
            <div className="mt-1 font-mono text-sm font-black text-cyan-300">{account.asOfDate || "-"}</div>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-3">
        <BigStat title="正式前20" value={stats.initialCount} detail={`最近批次 ${stats.officialDate}`} />
        <BigStat title="观察" value={stats.observationCount} detail="跨日等待MA5回踩" />
        <BigStat title="待买观察" value={stats.buyReadyCount} detail="后端确认视频买点" accent />
      </div>

      <Card className="rounded-xl p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-black text-slate-100">待买观察简表</h3>
            <Badge tone="cyan">{buyReady.length} 只</Badge>
          </div>
          <Button onClick={() => onNavigate("stockPool")} variant="ghost">
            <Eye className="h-3.5 w-3.5" />
            查看待买
          </Button>
        </div>
        {buyReady.length === 0 ? (
          <EmptyState title="暂无待买观察" detail="刷新行情后，这里只显示后端进入 BUY_READY 的候选。" />
        ) : (
          <div className="grid gap-3 xl:grid-cols-2">
            {buyReady.slice(0, 4).map(item => (
              <div key={item.id} className="rounded-lg border border-cyan-500/25 bg-slate-950/70 p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-black text-slate-100">{item.name} <span className="font-mono text-xs text-slate-500">{item.code}</span></div>
                    <div className="mt-2 flex flex-wrap gap-2 font-mono text-[11px]">
                      <span>现价 <b className="text-slate-100">{price(item.lastLivePrice)}</b></span>
                      <span className="text-cyan-300">MA5 {price(item.lastMa5Live)}</span>
                      <span className="text-amber-300">偏离 {pct(item.lastDeviation)}</span>
                    </div>
                  </div>
                  <Badge tone="green">{stateLabels[item.state] || item.state}</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="rounded-xl p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Briefcase className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-black text-slate-100">当前持仓精简监控</h3>
            <Badge tone={pendingExit.length ? "red" : "slate"}>{pendingExit.length ? `${pendingExit.length} 个待处理` : `${positions.length} 只`}</Badge>
          </div>
          <Button onClick={() => onNavigate("positions")} variant="success">
            查看完整持仓卡
          </Button>
        </div>
        {compactPositions.length === 0 ? (
          <EmptyState title="暂无持仓" detail="买入保存后，这里会出现 T+1、隔日卖出和延迟处理状态。" />
        ) : (
          <div className="space-y-3">
            {compactPositions.map((position, index) => (
              <div key={`${position.code}_${position.buyDate}`} className="rounded-lg border border-l-2 border-slate-800 border-l-amber-500/80 bg-slate-950/50 p-3">
                <div className="grid gap-3 xl:grid-cols-[250px_1fr_330px] xl:items-center">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-slate-700 bg-slate-950 text-[10px] font-black">{index + 1}</span>
                    <div className="min-w-0">
                      <div className="truncate text-sm font-black text-slate-100">{position.name}</div>
                      <div className="mt-1 font-mono text-[11px] text-slate-500">{position.code} 持有 {position.holdDays} 天</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                    <Field label="现价" value={price(position.currentPrice)} mono />
                    <Field label="MA5 / 偏离" value={`${price(position.ma5)} / ${pct(position.deviation5)}`} mono tone="cyan" />
                    <Field label="浮盈亏" value={`${money(position.floatingPnL)} (${pct(position.floatingPnLPct)})`} mono tone={position.floatingPnL >= 0 ? "green" : "red"} />
                    <Field label="可卖 / T+1" value={`${position.availableQuantity} / ${position.t1LockedQuantity}`} mono />
                  </div>
                  <div className="rounded border border-slate-800 bg-slate-900/60 p-2">
                    <Badge tone={position.riskLevel === "danger" ? "red" : position.riskLevel === "warning" ? "amber" : "green"}>
                      {positionStatusLabel(position)}
                    </Badge>
                    <div className="mt-1 line-clamp-2 text-[11px] leading-5 text-slate-400">{position.originalExitMessage || position.advice || "等待后端下一动作提示"}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="rounded-xl p-4">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-black uppercase tracking-widest text-cyan-400">ACTIVE PLAYBOOK</span>
          <span className="h-px flex-1 bg-slate-800" />
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <StatTile label="全市场原始前20" value="先取前20，过滤后不补位" tone="cyan" />
          <StatTile label="买入窗口" value="09:30-10:00 / 14:30-15:00" />
          <StatTile label="MA5 live" value="前4日收盘 + 实时价" />
          <StatTile label="隔日卖出" value="10点未涨停提示卖出" tone="amber" />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-7">
          <Button onClick={onGenerate} disabled={busy === "generate"} variant="primary"><BarChart3 className="h-3.5 w-3.5" />正式批次</Button>
          <Button onClick={onRefresh} disabled={busy === "refresh"} variant="ghost"><RefreshCw className="h-3.5 w-3.5" />刷新行情</Button>
          <Button onClick={() => onNavigate("stockPool")} variant="ghost"><Eye className="h-3.5 w-3.5" />待买池</Button>
          <Button onClick={() => onNavigate("positions")} variant="ghost"><Briefcase className="h-3.5 w-3.5" />持仓卡</Button>
          <Button onClick={onBackfill} disabled={busy === "history"} variant="ghost"><Download className="h-3.5 w-3.5" />补K线</Button>
          <Button onClick={() => onNavigate("import")} variant="ghost"><Upload className="h-3.5 w-3.5" />同花顺</Button>
          <Button onClick={() => onNavigate("review")} variant="ghost"><FileText className="h-3.5 w-3.5" />复盘</Button>
        </div>
      </Card>
    </div>
  );
}

function BigStat({ title, value, detail, accent = false }: { title: string; value: number; detail: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl border bg-slate-900 p-4 ${accent ? "border-l-4 border-cyan-400 border-slate-800" : "border-slate-800"}`}>
      <div className="text-xs font-bold text-slate-400">{title}</div>
      <div className={`mt-2 font-mono text-4xl font-black ${accent ? "text-cyan-300" : "text-slate-100"}`}>{value}</div>
      <div className="mt-2 text-xs font-semibold text-slate-500">{detail}</div>
    </div>
  );
}
