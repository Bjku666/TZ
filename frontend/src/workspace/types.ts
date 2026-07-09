export type Mode = "simulation" | "real";
export type StrategyId = "ma5_pullback" | "mode2" | "mode3";
export type Page = "today" | "positions" | "trades" | "reviews";
export type Side = "BUY" | "SELL";
export type StrategySnapshot = Record<string, unknown> & {
  entryChecklist?: Record<string, boolean | undefined>;
  ma10AtEntry?: number | string;
  distanceToMa10Pct?: number | string;
  priorLimitUp?: boolean;
  plannedExitRule?: "NEXT_TRADING_DAY" | string;
  entryPatternNote?: string;
  manualJudgement?: string;
  exitReason?: string;
  extendedObservation?: boolean;
  maxProfitPct?: number | string;
  exitNote?: string;
};
export type StrategyMode = {
  id: StrategyId;
  name: string;
  description: string;
  ruleStatus: string;
  buyRuleSummary: string;
  positionRuleSummary: string;
  reviewFocus: string;
  placeholder?: boolean;
};

export type SettingsData = {
  initialCash: number; accountDesc: string; enableReconciliation: boolean; defaultRemark: string;
  commissionRate: number; minCommission: number; enableMinCommission: boolean; stampDutyRate: number; transferFeeRate: number;
};
export type Reconciliation = { enabled: boolean; totalAssets: number; availableCash: number; holdingValue: number; holdingPnL: number; todayPnL: number; updatedAt: string; remark: string };
export type MarketSettings = {
  source?: string; enableRealtime?: boolean; provider?: string; autoRefresh?: boolean; refreshInterval?: number;
  refreshOutsideTradingHours?: boolean; expiryThreshold?: number; timeoutSeconds?: number; showExceptionAlert?: boolean;
  manualQuotes?: Record<string, { name?: string; price?: number; currentPrice?: number; previousClose?: number; updatedAt?: string }>;
};
export type AppSettings = { simulation: SettingsData; real: SettingsData; reconciliation: Record<Mode, Reconciliation>; market: MarketSettings };
export type Trade = { id: string; accountMode: Mode; strategyId: StrategyId; code: string; name: string; type: Side; date: string; time: string; price: number; quantity: number; amount: number; commission: number; stampDuty: number; transferFee: number; totalFee: number; reason?: string; remark?: string; rulesConclusion: string; violationTags: string[]; strategySnapshot?: StrategySnapshot; historicalBackfill: boolean; manualFeeOverride: boolean; createdAt?: string; updatedAt?: string };
export type Position = { code: string; name: string; strategyId?: StrategyId; quantity: number; availableQuantity: number; t1LockedQuantity: number; avgCost: number; currentPrice: number; marketValue: number; floatingPnL: number; floatingPnLPct: number; ma5?: number | null; deviation5?: number | null; referenceLine?: string; referencePrice?: number | null; distanceToReferencePct?: number | null; targetPrice?: number | null; warningStopPrice?: number | null; hardStopPrice?: number | null; buyDate: string; holdDays: number; status: string; advice?: string; nextActionTime?: string; actionType?: string; actionPriority?: "normal" | "warning" | "danger"; actionTitle?: string; canExecuteSellNow: boolean; sellBlockedReason?: string; isTodayBuy?: boolean; isNextDaySellable?: boolean; extendedObservation?: boolean; deferReason?: string; entryStrategySnapshot?: StrategySnapshot; notes?: string[]; quoteUpdatedAt?: string; quoteSource?: string };
export type Action = { id: string; strategyId?: StrategyId; code: string; name: string; type: string; priority: "normal" | "warning" | "danger"; title: string; message: string; nextActionTime?: string; position?: Position };
export type Review = { id: string; accountMode: Mode; strategyId: StrategyId; type: "daily" | "weekly" | "monthly"; date: string; planAndBasis: string; executionAndDeviation: string; resultAndEmotion: string; improvementAndNextPlan: string; saved: boolean; createdAt?: string; updatedAt?: string };
export type Notice = { id: string; timestamp: string; accountMode: Mode; strategyId?: StrategyId; type: string; title: string; message: string; relatedCode?: string; read: boolean };
export type CapitalPoint = {
  date: string;
  totalAssets: number;
  availableCash: number;
  holdingValue: number;
  realizedPnL: number;
  floatingPnL: number;
  totalPnL: number;
  tradeCount: number;
  buyAmount: number;
  sellAmount: number;
  fees: number;
};
export type CapitalAnalysis = {
  initialCash: number;
  currentCash: number;
  holdingValue: number;
  totalAssets: number;
  cashChange: number;
  assetChange: number;
  assetChangePct: number;
  realizedPnL: number;
  floatingPnL: number;
  totalFees: number;
  netBuyAmount: number;
  capitalDeploymentPct: number;
  cashRatioPct: number;
  positionCount: number;
  daily: CapitalPoint[];
};
export type AccountSummary = { initialCash: number; availableCash: number; holdingValue: number; totalAssets: number; realizedPnL: number; floatingPnL: number; totalPnL: number; totalReturnPct: number; todayPnL: number; todayRealizedPnL: number; asOfDate: string; reconciliationMode: boolean };
export type Workspace = {
  mode: Mode;
  strategyId: StrategyId;
  strategy: StrategyMode;
  strategies: StrategyMode[];
  account: AccountSummary;
  strategyAccount?: AccountSummary;
  accountPositions?: Position[];
  positions: Position[]; trades: Trade[]; pendingActions: Action[];
  reviewSummary: { tradeCount: number; completedCycles: number; winRate: number; averageWin: number; averageLoss: number; profitLossRatio: number; totalPnL: number; totalReturnPct: number; maxSingleWin: number; maxSingleLoss: number; totalFees: number; complianceRate: number; violationCount: number; mode3TradeCount?: number; nextDayExitRate?: number; exitBefore10Rate?: number; targetProfitRate?: number; averageHoldingTradingDays?: number; overduePositionCount?: number };
  capitalAnalysis: CapitalAnalysis;
  strategyCapitalAnalysis?: CapitalAnalysis;
  reviews: Review[]; notifications: Notice[]; settings: AppSettings; marketPhase: string; quoteUpdatedAt?: string;
};
