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
  canBuy: boolean;      // 是否满足待买观察条件 (MA5偏离率0%-2%且未放量跌破MA5)
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
  ma5: number;
  deviation5: number;        // 5日线偏离度
  holdDays: number;          // 持股天数
  belowMa5Days: number;      // 连续跌破5日线天数
  buyDate: string;           // 买入日期
  advice: string;            // 建议
  riskLevel: RiskLevel;      // 风险级别
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
    diagnosedHoldings: Array<{ code: string; name: string; judgment: string; actionPlan: string }>;
  };
  actionAudit?: {
    sellCompliant: string;
    profitExperience: string;
    lossAnalysis: string;
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
