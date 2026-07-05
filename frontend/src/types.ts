export type AccountMode = "simulation" | "real";

export type CandidateState =
  | "INITIAL_SCREENED"
  | "INITIAL_REJECTED"
  | "WAITING_ELIGIBLE_DATE"
  | "OBSERVING"
  | "IN_TOUCH_ZONE_OUTSIDE_WINDOW"
  | "BUY_READY"
  | "BELOW_MA5"
  | "BOUGHT"
  | "NEXT_DAY_OBSERVING"
  | "MORNING_EXIT_DUE"
  | "DEFERRED_TO_AFTERNOON"
  | "AFTERNOON_EXIT_DUE"
  | "LIMIT_UP_HOLD"
  | "LIMIT_UP_OPENED_EXIT_DUE"
  | "CLOSED"
  | "INVALIDATED"
  | "CANCELLED";

export type MarketPhase =
  | "pre_market"
  | "trading"
  | "lunch_break"
  | "after_close"
  | "weekend"
  | "holiday"
  | "unknown";

export interface HealthPayload {
  status: string;
  version: string;
  contract: string;
  gitCommit: string;
  buildTime: string;
  serverTime: string;
  timezone: string;
}

export interface RuleConfig {
  strategyName: string;
  strategyVersion: string;
  turnoverTopN: number;
  touchTolerancePct: number;
  morningBuyWindow: { start: string; end: string; endExclusive?: boolean };
  afternoonBuyWindow: { start: string; end: string; endExclusive?: boolean };
  quoteFreshnessSeconds: number;
  lotSize: number;
  ruleBoundaries?: Record<string, string>;
}

export interface SelectionBatch {
  batchId: string;
  selectionDate: string;
  generatedAt: string;
  source: string;
  isOfficial: boolean;
  dataAsOf: string;
  rawTopN: number;
}

export interface SelectionItem {
  id: string;
  batchId: string;
  code: string;
  name: string;
  rawRank: number;
  turnover: number;
  closePrice: number | null;
  ma5Close: number | null;
  marketAllowed: boolean;
  exclusionReason: string;
  aboveMa5: boolean;
  candidateCreated: boolean;
  selectionDate?: string;
  source?: string;
  dataAsOf?: string;
}

export interface Candidate {
  id: string;
  code: string;
  name: string;
  sourceBatchId: string;
  selectionDate: string;
  eligibleFrom: string;
  state: CandidateState;
  waitingTradeDays: number;
  lastClose: number | null;
  lastMa5Close: number | null;
  lastLivePrice: number | null;
  lastMa5Live: number | null;
  lastDeviation: number | null;
  touchStartedAt?: string | null;
  touchDetectedAt?: string | null;
  boughtTradeId?: string | null;
  invalidatedReason?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  signalQualified?: boolean | null;
  signalReason?: string;
  executionAllowed?: boolean | null;
  executionBlockReasons?: string[];
  manualConfirmationRequired?: boolean;
  maxBuyableLotQuantity?: number;
}

export interface CandidateEvent {
  id?: string;
  candidate_id?: string;
  event_type?: string;
  eventTime?: string;
  event_time?: string;
  tradeDate?: string;
  trade_date?: string;
  price?: number;
  ma5?: number;
  deviation?: number;
  quoteTime?: string;
  quote_time?: string;
  quoteAgeSeconds?: number;
  quote_age_seconds?: number;
  source?: string;
  reason?: string;
  payload?: Record<string, unknown>;
}

export interface Position {
  code: string;
  name: string;
  quantity: number;
  availableQuantity: number;
  settledQuantity: number;
  todayBuyQuantity: number;
  t1LockedQuantity: number;
  isTodayBuy: boolean;
  isT1Locked: boolean;
  operationDate: string;
  valuationDate: string;
  nextSellableTradeDate: string;
  nextActionTime: string;
  marketPhase: MarketPhase | string;
  canExecuteSellNow: boolean;
  sellBlockedReason: string;
  avgCost: number;
  currentPrice: number;
  marketValue: number;
  floatingPnL: number;
  floatingPnLPct: number;
  ma5: number;
  deviation5: number;
  holdDays: number;
  belowMa5Days: number;
  buyDate: string;
  advice: string;
  riskLevel: "normal" | "warning" | "danger";
  originalExitState?: CandidateState | string;
  originalExitMessage?: string;
  nextOriginalActionTime?: string;
  isLimitUp?: boolean;
  deferExitDecision?: { deferReason: string; decisionTime: string } | null;
  executionBlocked?: boolean;
  executionBlockReason?: string;
  originalRuleViolation?: boolean;
  programCompletionNote?: string;
  tradeLink?: StockTradeLink;
}

export interface TradeRuleSnapshot {
  candidateCycleId?: string;
  selectionBatchId?: string;
  selectionDate?: string;
  eligibleFrom?: string;
  tradeDateTime?: string;
  tradePrice?: number;
  ma5Live?: number;
  deviation?: number;
  buyWindow?: string;
  quoteAgeSeconds?: number;
  signalQualified?: boolean;
  executionAllowed?: boolean;
  executionBlockReasons?: string[];
  manualConfirmationRequired?: boolean;
  marketInfoNote?: string;
  ruleBoundaryNote?: string;
  positionBeforeTrade?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface TradeLog {
  id: string;
  code: string;
  name: string;
  type: "BUY" | "SELL";
  date: string;
  time: string;
  price: number;
  quantity: number;
  amount: number;
  commission: number;
  stampDuty: number;
  transferFee: number;
  totalFee: number;
  reason: string;
  remark: string;
  rulesConclusion: "符合规则" | "违规交易" | "部分不符" | "其他";
  violationTags: string[];
  snapshot: TradeRuleSnapshot | Record<string, unknown>;
}

export interface AccountState {
  initialCash: number;
  availableCash: number;
  holdingValue: number;
  totalAssets: number;
  realizedPnL: number;
  floatingPnL: number;
  holdingPnL?: number;
  totalPnL: number;
  accountPnL?: number;
  totalReturnPct: number;
  todayPnL?: number;
  todayRealizedPnL?: number;
  asOfDate?: string;
  operationDate?: string;
  valuationDate?: string;
  reconciliationMode?: boolean;
}

export interface TurnoverChangeStock {
  code: string;
  name?: string;
  rank?: number;
  oldRank?: number;
  newRank?: number;
  currentRank?: number | null;
  volume?: number;
  price?: number;
  pct?: number;
  marketAllowed?: boolean;
  exclusionReason?: string;
  isPinned?: boolean;
}

export interface TurnoverChanges {
  newEntries: TurnoverChangeStock[];
  dropped: TurnoverChangeStock[];
  rankUp: TurnoverChangeStock[];
  rankDown: TurnoverChangeStock[];
}

export interface IntradayPreview {
  items: TurnoverChangeStock[];
  changes: TurnoverChanges;
}

export interface WorkbenchPayload {
  officialSelection?: SelectionBatch | null;
  initialPool?: SelectionItem[];
  observationPool?: Candidate[];
  buyReadyPool?: Candidate[];
  list?: Stock[];
  positions?: Position[];
  accountState?: AccountState;
  sourceHealth?: unknown;
  durationMs?: number;
  message?: string;
  requestId?: string;
  source?: string;
  isStale?: boolean;
  dataAgeSeconds?: number;
  quoteFreshnessSeconds?: number;
  serverTime?: string;
  success?: boolean;
  inProgress?: boolean;
  intradayPreview?: IntradayPreview;
}

export interface Stock {
  code: string;
  name: string;
  price: number;
  pct: number;
  volume: number;
  rank: number;
  ma5: number;
  ma10?: number;
  ma20?: number;
  deviation5: number;
  signalQualified?: boolean;
  signalReason?: string;
  executionAllowed?: boolean;
  executionBlockReasons?: string[];
  manualConfirmationRequired?: boolean;
  maxBuyableLotQuantity?: number;
  group: "初筛" | "观察" | "待买";
  stage: CandidateState | string;
  reason: string;
  reminder: string;
  lastUpdated: string;
  historyStatus?: string;
  poolBatchId?: string;
  poolSource?: string;
  poolGeneratedAt?: string;
  poolRankAtGeneration?: number;
}

export interface StockTradeLink {
  lastBuy?: Partial<TradeLog> | null;
  lastSell?: Partial<TradeLog> | null;
  todayTrades?: Partial<TradeLog>[];
  hasComplianceIssue?: boolean;
  complianceTags?: string[];
  tradeCount?: number;
}

export interface ReviewContext {
  todayTrades: TradeLog[];
  currentPositions: Position[];
  accountState: AccountState;
  asOfDate: string;
  todayPnL?: number;
  realizedPnL?: number;
  marketSnapshot?: Record<string, unknown>;
  sectors?: Array<Record<string, unknown>>;
  holdingDeviation?: Array<Record<string, unknown>>;
  stockLinks?: Array<Record<string, unknown>>;
  summaryStatistics?: {
    complianceRate?: number;
    buyComplianceRate?: number;
    sellComplianceRate?: number;
  };
}

export interface TodayReview {
  date: string;
  todayTrades: TradeLog[];
  positions: Position[];
  accountState: AccountState;
  audit: Record<string, unknown>;
  stockLinks: Array<Record<string, unknown>>;
}

export interface ReportRecord {
  id: string;
  type: "daily" | "weekly" | "monthly";
  date: string;
  summary?: string;
  tomorrowPlan?: string;
  createdTime?: string;
  [key: string]: unknown;
}

export interface SettingsPayload {
  currentMode?: AccountMode;
  initialCash?: number;
  realInitialCash?: number;
  activeInitialCash?: number;
  quoteSource?: string;
  quote_source?: string;
  historySource?: string;
  autoRefresh?: boolean;
  refreshIntervalSeconds?: number;
  feeProfile?: string;
  commissionRate?: number;
  minCommission?: number;
  stampDutyRate?: number;
  transferFeeRate?: number;
  soundNotification?: boolean;
  desktopNotification?: boolean;
  simulationFees?: FeeConfig;
  realFees?: FeeConfig;
  thsReconciliation?: ReconciliationConfig;
  simulationThsReconciliation?: ReconciliationConfig;
  realThsReconciliation?: ReconciliationConfig;
  [key: string]: unknown;
}

export interface FeeConfig {
  feeProfile?: string;
  commissionRate?: number;
  minCommission?: number;
  stampDutyRate?: number;
  transferFeeRate?: number;
}

export interface ReconciliationConfig {
  enabled?: boolean;
  accountCapital?: number;
  totalAssets?: number;
  availableCash?: number;
  holdingValue?: number;
  holdingPnL?: number;
  todayPnL?: number;
}

export interface KLinePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  amount?: number;
  ma5?: number;
  ma10?: number;
  ma20?: number;
}

export interface HistoryJob {
  success?: boolean;
  inProgress?: boolean;
  jobId?: string;
  status: "running" | "completed" | "failed";
  total: number;
  completed: number;
  fetched: number;
  failed: number;
  skipped: number;
  error?: string;
  results?: Record<string, { success: boolean; status?: string; error?: string }>;
  list?: Stock[];
}

export type ActivityKind = "info" | "success" | "warning" | "danger" | "refresh" | "trade" | "report";

export interface ActivityEntry {
  id: string;
  kind: ActivityKind;
  title: string;
  detail?: string;
  time: string;
  source?: string;
}
