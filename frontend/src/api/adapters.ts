import type {
  AccountState,
  ActivityEntry,
  Candidate,
  CandidateEvent,
  CandidateState,
  HealthPayload,
  IntradayPreview,
  MarketPhase,
  Position,
  RuleConfig,
  SelectionBatch,
  SelectionItem,
  SettingsPayload,
  Stock,
  TradeLog,
  TurnoverChanges,
  WorkbenchPayload,
} from "../types";

export const stateLabels: Record<string, string> = {
  INITIAL_SCREENED: "初筛入选",
  INITIAL_REJECTED: "初筛未通过",
  WAITING_ELIGIBLE_DATE: "等待最早可买日",
  OBSERVING: "跨日观察",
  IN_TOUCH_ZONE_OUTSIDE_WINDOW: "回踩区，等待买入窗口",
  BUY_READY: "视频买点成立",
  BELOW_MA5: "低于回踩区",
  BOUGHT: "已买入",
  NEXT_DAY_OBSERVING: "次日早盘观察",
  MORNING_EXIT_DUE: "10点未涨停待卖",
  DEFERRED_TO_AFTERNOON: "已延迟至尾盘",
  AFTERNOON_EXIT_DUE: "14:30后待卖",
  LIMIT_UP_HOLD: "10点时涨停持有",
  LIMIT_UP_OPENED_EXIT_DUE: "涨停打开待处理",
  CLOSED: "已完成",
  INVALIDATED: "候选失效",
  CANCELLED: "已取消",
};

export const stateTone: Record<string, "green" | "red" | "cyan" | "amber" | "slate"> = {
  INITIAL_SCREENED: "cyan",
  INITIAL_REJECTED: "slate",
  WAITING_ELIGIBLE_DATE: "amber",
  OBSERVING: "cyan",
  IN_TOUCH_ZONE_OUTSIDE_WINDOW: "amber",
  BUY_READY: "green",
  BELOW_MA5: "red",
  BOUGHT: "green",
  NEXT_DAY_OBSERVING: "amber",
  MORNING_EXIT_DUE: "red",
  DEFERRED_TO_AFTERNOON: "amber",
  AFTERNOON_EXIT_DUE: "red",
  LIMIT_UP_HOLD: "green",
  LIMIT_UP_OPENED_EXIT_DUE: "red",
  CLOSED: "slate",
  INVALIDATED: "slate",
  CANCELLED: "slate",
};

export const marketPhaseLabels: Record<string, string> = {
  pre_market: "盘前",
  trading: "交易中",
  lunch_break: "午间休市",
  after_close: "收盘后",
  weekend: "周末",
  holiday: "休市",
  unknown: "未知",
};

export function compactMoney(value?: number | null): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  if (Math.abs(n) >= 100000000) return `${(n / 100000000).toFixed(2)}亿`;
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}万`;
  return n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function money(value?: number | null): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  return n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function price(value?: number | null): string {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return "-";
  return n.toFixed(2);
}

export function pct(value?: number | null, withSign = true): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  return `${withSign && n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}

export function dateTime(value?: string | null): string {
  if (!value) return "-";
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return String(value);
  return new Date(parsed).toLocaleString("zh-CN", { hour12: false });
}

export function shortTime(value?: string | null): string {
  if (!value) return "--:--:--";
  const parsed = Date.parse(value);
  if (Number.isFinite(parsed)) {
    return new Date(parsed).toLocaleTimeString("zh-CN", { hour12: false });
  }
  return String(value).slice(0, 8);
}

export function todayText(): string {
  const local = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

export function currentClock(): string {
  return new Date().toLocaleString("zh-CN", { hour12: false });
}

export function resolveMode(settings: SettingsPayload): "simulation" | "real" {
  return settings.currentMode === "real" ? "real" : "simulation";
}

export function modeLabel(mode: "simulation" | "real"): string {
  return mode === "real" ? "实盘记录" : "模拟训练";
}

export function quoteSource(settings: SettingsPayload, payload?: WorkbenchPayload | null): string {
  return String(payload?.source || settings.quoteSource || settings.quote_source || "自动切换");
}

export function detectMarketPhase(now = new Date()): MarketPhase {
  const day = now.getDay();
  if (day === 0 || day === 6) return "weekend";
  const minutes = now.getHours() * 60 + now.getMinutes();
  if (minutes < 9 * 60 + 30) return "pre_market";
  if (minutes <= 11 * 60 + 30) return "trading";
  if (minutes < 13 * 60) return "lunch_break";
  if (minutes <= 15 * 60) return "trading";
  return "after_close";
}

export function autoRefreshSeconds(phase: MarketPhase): number | null {
  if (phase !== "trading") return null;
  const now = new Date();
  const minutes = now.getHours() * 60 + now.getMinutes();
  const morning = minutes >= 9 * 60 + 30 && minutes <= 10 * 60;
  const afternoon = minutes >= 14 * 60 + 30 && minutes <= 15 * 60;
  return morning || afternoon ? 12 : 45;
}

function candidateSignal(candidate: Candidate): {
  signalQualified: boolean | null;
  executionAllowed: boolean | null;
  executionBlockReasons: string[];
  signalReason: string;
} {
  if (typeof candidate.signalQualified === "boolean" || typeof candidate.executionAllowed === "boolean") {
    return {
      signalQualified: candidate.signalQualified ?? null,
      executionAllowed: candidate.executionAllowed ?? null,
      executionBlockReasons: candidate.executionBlockReasons || [],
      signalReason: candidate.signalReason || stateLabels[candidate.state] || candidate.state,
    };
  }
  if (candidate.state === "BUY_READY") {
    return {
      signalQualified: true,
      executionAllowed: true,
      executionBlockReasons: [],
      signalReason: "后端候选状态为视频买点成立",
    };
  }
  if (candidate.state === "IN_TOUCH_ZONE_OUTSIDE_WINDOW") {
    return {
      signalQualified: true,
      executionAllowed: false,
      executionBlockReasons: ["后端状态显示回踩区成立，但当前不在买入时段"],
      signalReason: "后端候选状态为回踩区等待窗口",
    };
  }
  if (candidate.state === "WAITING_ELIGIBLE_DATE") {
    return {
      signalQualified: false,
      executionAllowed: false,
      executionBlockReasons: ["尚未到达后端给出的最早可买日期"],
      signalReason: "等待下一交易日起跨日观察",
    };
  }
  if (candidate.state === "BELOW_MA5") {
    return {
      signalQualified: false,
      executionAllowed: false,
      executionBlockReasons: ["后端状态显示当前低于回踩区"],
      signalReason: "等待新的后端信号",
    };
  }
  return {
    signalQualified: null,
    executionAllowed: null,
    executionBlockReasons: [],
    signalReason: stateLabels[candidate.state] || candidate.state,
  };
}

export function candidateToStock(candidate: Candidate, group: "观察" | "待买"): Stock {
  const signal = candidateSignal(candidate);
  return {
    code: candidate.code,
    name: candidate.name,
    price: Number(candidate.lastLivePrice || 0),
    pct: 0,
    volume: 0,
    rank: 0,
    ma5: Number(candidate.lastMa5Live || candidate.lastMa5Close || 0),
    deviation5: Number(candidate.lastDeviation || 0),
    signalQualified: signal.signalQualified ?? undefined,
    signalReason: signal.signalReason,
    executionAllowed: signal.executionAllowed ?? undefined,
    executionBlockReasons: signal.executionBlockReasons,
    manualConfirmationRequired: true,
    group,
    stage: candidate.state,
    reason: signal.signalReason,
    reminder: signal.executionBlockReasons.join("；") || "等待人工执行或继续观察",
    lastUpdated: candidate.updatedAt || candidate.touchDetectedAt || "",
    poolBatchId: candidate.sourceBatchId,
    poolRankAtGeneration: 0,
  };
}

export function selectionToStock(item: SelectionItem): Stock {
  return {
    code: item.code,
    name: item.name,
    price: Number(item.closePrice || 0),
    pct: 0,
    volume: Number(item.turnover || 0),
    rank: Number(item.rawRank || 0),
    ma5: Number(item.ma5Close || 0),
    deviation5:
      Number(item.closePrice) > 0 && Number(item.ma5Close) > 0
        ? ((Number(item.closePrice) - Number(item.ma5Close)) / Number(item.ma5Close)) * 100
        : 0,
    signalQualified: item.aboveMa5 && item.marketAllowed,
    signalReason: item.aboveMa5 ? "入选日收盘价站上入选日MA5" : item.exclusionReason || "未转入跨日观察",
    executionAllowed: false,
    executionBlockReasons: item.candidateCreated ? ["入选当天不能买，下一交易日起观察"] : [item.exclusionReason || "未创建候选"],
    manualConfirmationRequired: true,
    group: "初筛",
    stage: item.marketAllowed ? "INITIAL_SCREENED" : "INITIAL_REJECTED",
    reason: item.exclusionReason || (item.aboveMa5 ? "已转入跨日观察" : "未满足入选日MA5条件"),
    reminder: item.candidateCreated ? "已由后端创建跨日候选" : item.exclusionReason || "仅展示正式批次结果",
    lastUpdated: item.dataAsOf || "",
    poolBatchId: item.batchId,
    poolSource: item.source,
    poolRankAtGeneration: item.rawRank,
  };
}

export function mergeWorkbenchPayload(current: WorkbenchPayload, patch: WorkbenchPayload): WorkbenchPayload {
  return {
    ...current,
    ...patch,
    officialSelection: patch.officialSelection ?? current.officialSelection,
    initialPool: patch.initialPool ?? current.initialPool ?? [],
    observationPool: patch.observationPool ?? current.observationPool ?? [],
    buyReadyPool: patch.buyReadyPool ?? current.buyReadyPool ?? [],
    positions: patch.positions ?? current.positions ?? [],
    accountState: patch.accountState ?? current.accountState,
  };
}

export interface DashboardStats {
  officialDate: string;
  initialCount: number;
  observationCount: number;
  buyReadyCount: number;
  positionCount: number;
  nextDaySellCount: number;
  morningExitCount: number;
  deferredCount: number;
  staleQuoteCount: number;
  missingHistoryCount: number;
  todayTradeCount: number;
  unfinishedReviewCount: number;
}

export function dashboardStats(
  official: SelectionBatch | null | undefined,
  initial: SelectionItem[],
  observation: Candidate[],
  buyReady: Candidate[],
  positions: Position[],
  trades: TradeLog[],
  stocks: Stock[],
): DashboardStats {
  const today = todayText();
  return {
    officialDate: official?.selectionDate || "-",
    initialCount: initial.length,
    observationCount: observation.filter(item => item.state !== "BUY_READY").length,
    buyReadyCount: buyReady.length,
    positionCount: positions.length,
    nextDaySellCount: positions.filter(item => item.originalExitState === "NEXT_DAY_OBSERVING").length,
    morningExitCount: positions.filter(item => item.originalExitState === "MORNING_EXIT_DUE").length,
    deferredCount: positions.filter(item => item.originalExitState === "DEFERRED_TO_AFTERNOON" || item.deferExitDecision).length,
    staleQuoteCount: stocks.filter(item => /过期|旧|失败/.test(String(item.historyStatus || item.reminder || ""))).length,
    missingHistoryCount: stocks.filter(item => /缺少|不足|失败/.test(String(item.historyStatus || ""))).length,
    todayTradeCount: trades.filter(item => item.date === today).length,
    unfinishedReviewCount: trades.some(item => item.date === today) ? 1 : 0,
  };
}

export function turnoverChangesEmpty(): TurnoverChanges {
  return { newEntries: [], dropped: [], rankUp: [], rankDown: [] };
}

export function intradayPreviewFromPayload(payload?: WorkbenchPayload | null): IntradayPreview {
  return payload?.intradayPreview || { items: [], changes: turnoverChangesEmpty() };
}

export function activityFromPayload(
  payload: WorkbenchPayload | { message?: string; success?: boolean; source?: string; durationMs?: number },
  title: string,
  kind: ActivityEntry["kind"] = "info",
): ActivityEntry {
  return {
    id: `${Date.now()}_${Math.random().toString(36).slice(2)}`,
    kind: payload.success === false ? "warning" : kind,
    title,
    detail: [payload.message, payload.source ? `来源: ${payload.source}` : "", payload.durationMs ? `耗时: ${payload.durationMs}ms` : ""]
      .filter(Boolean)
      .join(" · "),
    time: new Date().toISOString(),
    source: payload.source,
  };
}

export function activityFromCandidateEvent(event: CandidateEvent): ActivityEntry {
  const eventTime = event.event_time || event.eventTime || new Date().toISOString();
  return {
    id: `${event.id || event.event_type || "candidate"}_${eventTime}`,
    kind: event.event_type === "STATE_CHANGED" ? "refresh" : event.event_type === "BUY_RECORDED" ? "trade" : "info",
    title: event.event_type || "候选事件",
    detail: [event.reason, event.price ? `价 ${price(event.price)}` : "", event.deviation ? `偏离 ${pct(event.deviation)}` : ""]
      .filter(Boolean)
      .join(" · "),
    time: eventTime,
    source: event.source,
  };
}

export function dataAgeLabel(payload?: WorkbenchPayload | null): string {
  if (payload?.dataAgeSeconds === undefined || payload.dataAgeSeconds === null) return "-";
  const seconds = Number(payload.dataAgeSeconds);
  if (!Number.isFinite(seconds)) return "-";
  if (seconds < 60) return `${Math.round(seconds)}秒`;
  return `${Math.round(seconds / 60)}分钟`;
}

export function isQuoteStale(payload?: WorkbenchPayload | null, rules?: RuleConfig | null): boolean {
  if (payload?.isStale) return true;
  const age = Number(payload?.dataAgeSeconds);
  const limit = Number(payload?.quoteFreshnessSeconds || rules?.quoteFreshnessSeconds);
  return Number.isFinite(age) && Number.isFinite(limit) && limit > 0 && age > limit;
}

export function accountFallback(): AccountState {
  return {
    initialCash: 0,
    availableCash: 0,
    holdingValue: 0,
    totalAssets: 0,
    realizedPnL: 0,
    floatingPnL: 0,
    totalPnL: 0,
    totalReturnPct: 0,
  };
}

export function healthStatus(health: HealthPayload | null): string {
  if (!health) return "API未连接";
  return `${health.contract || "unknown"} · ${health.gitCommit || "unknown"}`;
}

export function tradeCsv(trades: TradeLog[]): string {
  const header = ["类型", "日期", "时间", "代码", "名称", "价格", "数量", "金额", "佣金", "印花税", "过户费", "总费用", "原因", "规则结论", "违规标签"];
  const rows = trades.map(trade => [
    trade.type,
    trade.date,
    trade.time,
    trade.code,
    trade.name,
    trade.price,
    trade.quantity,
    trade.amount,
    trade.commission,
    trade.stampDuty,
    trade.transferFee,
    trade.totalFee,
    trade.reason,
    trade.rulesConclusion,
    (trade.violationTags || []).join("|"),
  ]);
  return [header, ...rows]
    .map(row =>
      row
        .map(value => {
          const text = String(value ?? "");
          return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
        })
        .join(","),
    )
    .join("\n");
}

export function downloadText(filename: string, content: string, mime = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function positionStatusLabel(position: Position): string {
  if (position.isTodayBuy) return "今日买入，T+1锁定";
  if (position.originalExitState) return stateLabels[position.originalExitState] || String(position.originalExitState);
  if (position.executionBlocked) return "执行受阻";
  if (position.availableQuantity <= 0 && position.t1LockedQuantity > 0) return "T+1锁定";
  return position.advice || "持仓观察";
}

export function latestRefreshTime(payload?: WorkbenchPayload | null): string {
  return payload?.serverTime ? dateTime(payload.serverTime) : "-";
}
