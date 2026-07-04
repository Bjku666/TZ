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
  | "CLOSED"
  | "INVALIDATED"
  | "CANCELLED";

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
  closePrice: number;
  ma5Close: number;
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
  lastClose: number;
  lastMa5Close: number;
  lastLivePrice: number;
  lastMa5Live: number;
  lastDeviation: number;
  touchStartedAt?: string;
  touchDetectedAt?: string;
  boughtTradeId?: string;
  invalidatedReason?: string;
  createdAt?: string;
  updatedAt?: string;
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
  signalQualified: boolean;
  signalReason: string;
  executionAllowed: boolean;
  executionBlockReasons: string[];
  manualConfirmationRequired: boolean;
  maxBuyableLotQuantity?: number;
  group: "初筛" | "观察" | "待买";
  stage: CandidateState | string;
  reason: string;
  reminder: string;
  lastUpdated: string;
  poolBatchId?: string;
  poolSource?: string;
  poolGeneratedAt?: string;
  poolRankAtGeneration?: number;
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
  marketPhase: string;
  canExecuteSellNow: boolean;
  sellBlockedReason: string;
  avgCost: number;
  currentPrice: number;
  marketValue: number;
  floatingPnL: number;
  floatingPnLPct: number;
  buyDate: string;
  advice: string;
  riskLevel: "normal" | "warning" | "danger";
  originalExitState?: CandidateState;
  originalExitMessage?: string;
  nextOriginalActionTime?: string;
  isLimitUp?: boolean;
  deferExitDecision?: { deferReason: string; decisionTime: string } | null;
  executionBlocked?: boolean;
  executionBlockReason?: string;
  originalRuleViolation?: boolean;
  programCompletionNote?: string;
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
  snapshot: Record<string, unknown>;
}

export interface AccountState {
  initialCash: number;
  availableCash: number;
  holdingValue: number;
  totalAssets: number;
  realizedPnL: number;
  floatingPnL: number;
  totalPnL: number;
  totalReturnPct: number;
  todayPnL?: number;
  todayRealizedPnL?: number;
  asOfDate?: string;
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
  marketAllowed?: boolean;
  exclusionReason?: string;
}

export interface TurnoverChanges {
  newEntries: TurnoverChangeStock[];
  dropped: TurnoverChangeStock[];
  rankUp: TurnoverChangeStock[];
  rankDown: TurnoverChangeStock[];
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
}

export interface KLinePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  ma5?: number;
  ma10?: number;
  ma20?: number;
  volume?: number;
}
