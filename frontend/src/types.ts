export type Mode = "simulation" | "real";
export type Page = "today" | "positions" | "trades" | "reviews";
export type Side = "BUY" | "SELL";

export type SettingsData = {
  initialCash: number; accountDesc: string; enableReconciliation: boolean; defaultRemark: string;
  commissionRate: number; minCommission: number; enableMinCommission: boolean; stampDutyRate: number; transferFeeRate: number;
};
export type Reconciliation = { enabled: boolean; totalAssets: number; availableCash: number; holdingValue: number; holdingPnL: number; todayPnL: number; updatedAt: string; remark: string };
export type AppSettings = { simulation: SettingsData; real: SettingsData; reconciliation: Record<Mode, Reconciliation>; market: Record<string, unknown> };
export type Trade = { id: string; accountMode: Mode; code: string; name: string; type: Side; date: string; time: string; price: number; quantity: number; amount: number; commission: number; stampDuty: number; transferFee: number; totalFee: number; reason?: string; remark?: string; rulesConclusion: string; violationTags: string[]; historicalBackfill: boolean; manualFeeOverride: boolean; createdAt?: string; updatedAt?: string };
export type Position = { code: string; name: string; quantity: number; availableQuantity: number; t1LockedQuantity: number; avgCost: number; currentPrice: number; marketValue: number; floatingPnL: number; floatingPnLPct: number; ma5: number; deviation5: number; buyDate: string; holdDays: number; status: string; advice?: string; nextActionTime?: string; canExecuteSellNow: boolean; sellBlockedReason?: string; notes?: string[] };
export type Action = { id: string; code: string; name: string; type: string; priority: "normal" | "warning" | "danger"; title: string; message: string; nextActionTime?: string; position?: Position };
export type Review = { id: string; accountMode: Mode; type: "daily" | "weekly" | "monthly"; date: string; planAndBasis: string; executionAndDeviation: string; resultAndEmotion: string; improvementAndNextPlan: string; saved: boolean; createdAt?: string; updatedAt?: string };
export type Notice = { id: string; timestamp: string; accountMode: Mode; type: string; title: string; message: string; relatedCode?: string; read: boolean };
export type Workspace = {
  mode: Mode;
  account: { initialCash: number; availableCash: number; holdingValue: number; totalAssets: number; realizedPnL: number; floatingPnL: number; totalPnL: number; totalReturnPct: number; todayPnL: number; todayRealizedPnL: number; asOfDate: string; reconciliationMode: boolean };
  positions: Position[]; trades: Trade[]; pendingActions: Action[];
  reviewSummary: { tradeCount: number; completedCycles: number; winRate: number; averageWin: number; averageLoss: number; profitLossRatio: number; totalPnL: number; totalReturnPct: number; maxSingleWin: number; maxSingleLoss: number; totalFees: number; complianceRate: number; violationCount: number };
  reviews: Review[]; notifications: Notice[]; settings: AppSettings; marketPhase: string; quoteUpdatedAt?: string;
};

