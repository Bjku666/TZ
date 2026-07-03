/**
 * 强势回踩短线交易纪律系统 - 共享数据结构
 */

export type StockGroup = "初筛" | "观察" | "待买";
export type StockViewGroup = StockGroup | "持仓";

export type StockStage = 
  | "初筛通过" 
  | "强势确认"
  | "继续观察"
  | "偏高不追"
  | "远离不追"
  | "待买观察" 
  | "跌破MA5"
  | "未达规则"
  | "风险排除"
  | "淘汰";

export type RiskLevel = "normal" | "warning" | "danger";

export type HistoryStatus = "已有缓存" | "缺少历史K线" | "自动获取失败" | "数据不足" | "缓存过旧";

export interface Stock {
  code: string;
  name: string;
  price: number;
  pct: number;
  volume: number; // 成交额 (元)
  rank: number;   // 成交额排名
  poolBatchId: string;
  poolSource: string;
  poolGeneratedAt: string;
  poolRankAtGeneration: number;
  isPoolLocked: boolean;
  isPinned: boolean;
  ma5: number;
  ma10: number;
  ma20: number;
  deviation5: number;   // 5日线偏离率 (%)
  bigCandlePct: number; // 最近20日内最大阳线涨幅 (%)
  ma5Upward: boolean;   // 5日线是否向上，仅作参考
  canBuy: boolean;      // 是否满足待买观察条件 (MA5偏离率0%-2.5%、资金与风险约束通过)
  marketTradeAllowed?: boolean;
  marketRisk?: boolean;
  marketRiskReasons?: string[];
  sectorName?: string;
  sectorWeak?: boolean;
  lotCost?: number;
  stopPrice?: number;
  riskAmount?: number;
  maxRiskAmount?: number;
  riskPct?: number;
  group: StockGroup;
  stage: StockStage;
  riskLevel: RiskLevel;
  reason: string;       // 阶段判定原因
  reminder: string;     // 操作提醒
  historyStatus: HistoryStatus;
  lastUpdated: string;
  remark: string;       // 备注
}

export interface TurnoverChangeStock {
  code: string;
  name: string;
  rank: number;
  volume: number;
  price?: number;
  pct?: number;
  oldRank?: number;
  newRank?: number;
  currentRank?: number | null;
  isPinned?: boolean;
}

export interface TurnoverChanges {
  newEntries: TurnoverChangeStock[];
  dropped: TurnoverChangeStock[];
  rankUp: TurnoverChangeStock[];
  rankDown: TurnoverChangeStock[];
}

export interface Position {
  code: string;
  name: string;
  quantity: number;
  availableQuantity: number; // 可卖数量 (支持T+1等规则)
  avgCost: number;           // 平均成本 (元)
  currentPrice: number;      // 现价
  marketValue: number;       // 市值
  floatingPnL: number;       // 浮动盈亏
  floatingPnLPct: number;    // 浮动盈亏比例 (%)
  currentLossAmount?: number; // 当前浮亏金额，仅亏损时为正
  maxLossAmount?: number;     // 单笔最大允许亏损金额
  lossRiskPct?: number;       // 当前亏损占本金比例
  ma5: number;
  deviation5: number;        // 5日线偏离度
  holdDays: number;          // 持股天数
  belowMa5Days: number;      // 连续跌破5日线天数
  buyDate: string;           // 买入日期
  advice: string;            // 建议
  riskLevel: RiskLevel;      // 风险级别
  tradeLink?: StockTradeLink;
}

export interface TradeRuleSnapshot {
  group: StockGroup;
  stage: StockStage;
  ma5: number;
  deviation5: number;
  bigCandlePct: number;
  ma5Upward: boolean;
  cashSufficient: boolean;
  inTradingTime: boolean;
  inBuyWindow?: boolean;
  marketRisk?: boolean;
  marketRiskSource?: string;
  marketRiskReasons?: string[];
  marketSnapshot?: Record<string, unknown>;
  sectorSnapshot?: Record<string, unknown>;
  stopPrice?: number;
  riskAmount?: number;
  maxRiskAmount?: number;
  riskPct?: number;
  riskLimitPct?: number;
  buyWindow?: string;
  positionBeforeTrade?: Partial<Position>;
}

export interface TradeLog {
  id: string;
  code: string;
  name: string;
  type: "BUY" | "SELL";
  date: string; // YYYY-MM-DD
  time: string; // HH:MM:SS
  price: number;
  quantity: number;
  amount: number;      // 交易金额 = 价格 * 数量
  commission: number;  // 佣金
  stampDuty: number;   // 印花税
  transferFee: number; // 过户费
  totalFee: number;    // 总手续费
  reason: string;      // 买入/卖出原因
  remark: string;      // 备注
  snapshot: TradeRuleSnapshot;
  rulesConclusion: "符合规则" | "违规交易" | "部分不符" | "其他";
  violationTags: string[]; // e.g. ["非主板", "非成交额前30", "无大阳线", "MA5向下", "跌破MA5买入"]
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
}

export type SelfDiagnosisType = "holding" | "todayBuy" | "todaySell" | "manual";

export interface SelfDiagnosisItem {
  code: string;
  name: string;
  judgment: string;
  actionPlan: string;
  notes?: string;
  type?: SelfDiagnosisType | string;
  sourceStep?: "step1" | "step2" | "step3";
  sourceTitle?: string;
  complianceTags?: string[];
  linkedTradeIds?: string[];
}

export interface StockTradeLink {
  code: string;
  name: string;
  position?: Position | null;
  todayTrades?: TradeLog[];
  allTrades?: TradeLog[];
  lastBuy?: Partial<TradeLog> | null;
  lastSell?: Partial<TradeLog> | null;
  hasComplianceIssue?: boolean;
  complianceTags?: string[];
  tradeCount?: number;
  reviewFocus?: string;
  actionPlan?: string;
}

export interface ReviewScreenedStock {
  code: string;
  name: string;
  price: number;
  pct: number;
  volume: number;
  rank?: number;
  volRatio?: number;
  volRatioSource?: string;
  confidence?: number;
  stars?: string;
  reason?: string;
  stage?: StockStage;
  group?: StockGroup;
  deviation5?: number;
  concept?: string;
  conceptSource?: string;
  limitHeight?: string;
}

export interface ReviewReport {
  id: string;
  type: "daily" | "weekly" | "monthly";
  date: string; // YYYY-MM-DD or date range
  buyCount: number;
  sellCount: number;
  ruleComplianceRate: number; // 规则符合率 (%)
  violations: string[];       // 违规记录
  realizedPnL: number;
  portfolioRisk: string;
  summary: string;            // 心得总结
  tomorrowPlan: string;       // 明日计划/下周计划
  createdTime: string;
  accountSnapshot?: AccountState;
  todayTrades?: TradeLog[];
  currentPositions?: Position[];
  stockLinks?: StockTradeLink[];
  linkedStockReviews?: StockTradeLink[];
  summaryStats?: {
    buyCount: number;
    sellCount: number;
    ruleComplianceRate: number;
    buyComplianceRate?: number;
    sellComplianceRate?: number;
    tradeComplianceRate?: number;
    realizedPnL: number;
    portfolioRisk: string;
  };
  
  // Standardized multi-dimensional review fields
  marketAnalysis?: {
    shTrend: string;
    shVolume: string;
    shFlow: string;
    szTrend: string;
    szVolume: string;
    szFlow: string;
    cyTrend: string;
    cyVolume: string;
    cyFlow: string;
    systemicRisk: boolean;
    marketConclusion?: string;
  };
  sectorAnalysis?: {
    reviewedEtfCount: number;
    hotSectors: string;
    etfFlowNotes: string;
  };
  stockAnalysis?: {
    top200Reviewed: boolean;
    volRatioReviewed: boolean;
    limitUpReviewed: boolean;
    step1Screened?: ReviewScreenedStock[];
    step2Screened?: ReviewScreenedStock[];
    step3Screened?: ReviewScreenedStock[];
    selfDiagnostics?: SelfDiagnosisItem[];
    diagnosedHoldings: SelfDiagnosisItem[];
  };
  stockScreening?: {
    step1: { title: string; reviewed: boolean; stocks: ReviewScreenedStock[] };
    step2: { title: string; reviewed: boolean; stocks: ReviewScreenedStock[] };
    step3: { title: string; reviewed: boolean; stocks: ReviewScreenedStock[] };
  };
  selfDiagnosis?: {
    items: SelfDiagnosisItem[];
  };
  actionAudit?: {
    sellCompliant: string;
    profitExperience: string;
    lossAnalysis: string;
  };
  reflection?: {
    summary: string;
    tomorrowPlan: string;
  };
}

export interface KLinePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number; // 成交量
  amount: number; // 成交额
  ma5?: number;
  ma10?: number;
  ma20?: number;
}
