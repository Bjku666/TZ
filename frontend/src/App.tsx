import { Children, cloneElement, isValidElement, useState, useEffect, useRef } from "react";
import type { Key, ReactNode } from "react";
import { 
  Activity, 
  Briefcase, 
  TrendingUp, 
  History, 
  FileText, 
  Settings, 
  RefreshCw, 
  Download, 
  Plus, 
  Trash2, 
  Search, 
  Eye, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Calendar, 
  Info, 
  BookOpen, 
  FileSpreadsheet, 
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Coins,
  Edit,
  Clock3
} from "lucide-react";
import KLineChart from "./components/KLineChart";
import { Stock, TradeLog, StockGroup, StockViewGroup, StockStage, Position, AccountState, ReviewReport, TurnoverChanges, TurnoverChangeStock, ReviewScreenedStock, SelfDiagnosisItem, TradingRulesConfig } from "./types";

const QUOTE_AUTO_REFRESH_SECONDS = 30;
const TURNOVER_AUTO_SCAN_SECONDS = 180;
const REVIEW_SCREEN_LIMIT = 50;
const DEFAULT_TRADING_RULES: TradingRulesConfig = {
  lotSize: 100,
  simulationCapital: 10000,
  realCapital: 5000,
  turnoverTopN: 30,
  bigCandleLookbackDays: 20,
  bigCandleThresholdPct: 5,
  buyZone: {
    minDeviationPct: 0,
    maxDeviationPct: 2.5
  },
  observeZone: {
    maxDeviationPct: 5
  },
  highZone: {
    maxDeviationPct: 7
  },
  singleTradeRisk: {
    maxPct: 0.02,
    steadyPct: 0.01
  },
  ma5Risk: {
    effectiveBreakPct: 0,
    stopPriceBufferPct: 0.01
  },
  takeProfit: {
    watchDeviationPct: 5,
    priorityDeviationPct: 7
  },
  buyWindows: [
    { start: "09:35", end: "10:00" },
    { start: "14:30", end: "14:55" }
  ],
  riskCheckTime: "14:50"
};
const CARD_TEXT_ENDING_PERIOD = /([。．]|(?<!\.)\.)([”’"'）)\]】》]*)\s*$/u;
type AccountMode = "simulation" | "real";
type QuoteRefreshTrigger = "manual" | "auto";
type TurnoverScanTrigger = "manual" | "auto";
type FeeProfile = "ths_simulation" | "real_a_share";
type FeeSettings = {
  feeProfile: FeeProfile;
  commissionRate: number;
  minCommission: number;
  stampDutyRate: number;
  transferFeeRate: number;
};

const ZERO_FEE_SETTINGS = {
  commissionRate: 0,
  minCommission: 0,
  stampDutyRate: 0,
  transferFeeRate: 0
};

const DEFAULT_FEE_SETTINGS: FeeSettings = {
  feeProfile: "ths_simulation",
  ...ZERO_FEE_SETTINGS
};

type ActivityLogEntry = {
  time: string;
  icon: string;
  text: string;
  rowClass: string;
  iconClass: string;
  textClass: string;
};

const ACTIVITY_SYMBOLS = [
  "⚡",
  "🚨",
  "⏳",
  "✅",
  "❌",
  "⚠️",
  "💡",
  "🔎",
  "➕",
  "🔄",
  "💸",
  "🗑️",
  "✍️",
  "📝",
  "⚙️",
  "📂",
  "📈",
  "📋",
  "✓"
];

function formatActivityLogEntry(log: string): ActivityLogEntry {
  const [, parsedTime, parsedText] = log.match(/^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$/) || [];
  const time = parsedTime || "--:--:--";
  let text = (parsedText || log).trim();
  let icon = "•";

  const symbol = ACTIVITY_SYMBOLS.find(item => text.startsWith(item));
  if (symbol) {
    icon = symbol === "⏳" ? "🚨" : symbol;
    text = text.slice(symbol.length).trim();
  } else if (/自动刷新|行情刷新|买点区间/.test(text)) {
    icon = "⚡";
  }

  const isRefreshHighlight = icon === "⚡" || /自动刷新|行情刷新完成|重新评估买点区间/.test(text);
  const isFetching = icon === "🚨" || /正在|启动|开始|拉取|扫描/.test(text);

  if (isRefreshHighlight) {
    return {
      time,
      icon: "⚡",
      text,
      rowClass: "border-rose-500/10",
      iconClass: "text-amber-300",
      textClass: "text-rose-400 font-black"
    };
  }

  if (icon === "❌") {
    return {
      time,
      icon,
      text,
      rowClass: "border-rose-500/10",
      iconClass: "text-rose-400",
      textClass: "text-rose-300 font-bold"
    };
  }

  if (icon === "⚠️") {
    return {
      time,
      icon,
      text,
      rowClass: "border-amber-500/10",
      iconClass: "text-amber-300",
      textClass: "text-amber-200 font-bold"
    };
  }

  if (icon === "✅" || icon === "✓") {
    return {
      time,
      icon,
      text,
      rowClass: "border-emerald-500/10",
      iconClass: "text-emerald-300",
      textClass: "text-emerald-200 font-bold"
    };
  }

  if (icon === "💡" || icon === "🔎" || icon === "📈" || icon === "📋") {
    return {
      time,
      icon,
      text,
      rowClass: "border-cyan-500/10",
      iconClass: "text-cyan-300",
      textClass: "text-sky-200 font-semibold"
    };
  }

  return {
    time,
    icon,
    text,
    rowClass: isFetching ? "border-slate-800/80" : "border-slate-800/60",
    iconClass: isFetching ? "text-rose-400" : "text-slate-500",
    textClass: "text-slate-400 font-semibold"
  };
}

function trimCardSentencePeriod(text: string): string {
  return text
    .split("\n")
    .map(line => line.replace(CARD_TEXT_ENDING_PERIOD, "$2"))
    .join("\n");
}

function stripCardTextPeriods(node: ReactNode): ReactNode {
  return Children.map(node, child => {
    if (typeof child === "string") return trimCardSentencePeriod(child);
    if (isValidElement<{ children?: ReactNode }>(child) && child.props.children !== undefined) {
      return cloneElement(child, { children: stripCardTextPeriods(child.props.children) });
    }
    return child;
  });
}

function CardText({
  as = "p",
  className,
  children
}: {
  as?: "p" | "span" | "div";
  className?: string;
  children: ReactNode;
  key?: Key;
}) {
  const Component = as;
  return <Component className={className}>{stripCardTextPeriods(children)}</Component>;
}

function modeFromApi(value: unknown): AccountMode {
  return value === "real" ? "real" : "simulation";
}

function numberSetting(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function feeProfileFromApi(value: unknown): FeeProfile {
  return value === "real_a_share" ? "real_a_share" : "ths_simulation";
}

function feeSettingsFromApi(settings: any): FeeSettings {
  const feeProfile = feeProfileFromApi(settings?.feeProfile);
  return {
    feeProfile,
    commissionRate: numberSetting(settings?.commissionRate, DEFAULT_FEE_SETTINGS.commissionRate),
    minCommission: numberSetting(settings?.minCommission, DEFAULT_FEE_SETTINGS.minCommission),
    stampDutyRate: numberSetting(settings?.stampDutyRate, DEFAULT_FEE_SETTINGS.stampDutyRate),
    transferFeeRate: numberSetting(settings?.transferFeeRate, DEFAULT_FEE_SETTINGS.transferFeeRate)
  };
}

function isZeroFeeSettings(settings: FeeSettings): boolean {
  return (
    settings.commissionRate === 0 &&
    settings.minCommission === 0 &&
    settings.stampDutyRate === 0 &&
    settings.transferFeeRate === 0
  );
}

function feeProfileForValues(settings: FeeSettings): FeeProfile {
  return isZeroFeeSettings(settings) ? "ths_simulation" : "real_a_share";
}

function feeSettingsWithValue(settings: FeeSettings, key: keyof Omit<FeeSettings, "feeProfile">, value: number): FeeSettings {
  const next = { ...settings, [key]: value };
  return { ...next, feeProfile: feeProfileForValues(next) };
}

function feeSettingsLabel(settings: FeeSettings, mode: AccountMode): string {
  if (isZeroFeeSettings(settings)) return "同花顺模拟口径（全部费用为0）";
  return mode === "real" ? "实盘/A股费用口径（按当前配置计算）" : "模拟训练费率（按当前配置计算）";
}

function percentFeeLabel(value: number): string {
  const safeValue = Number.isFinite(value) ? value : 0;
  if (safeValue === 0) return "0%";
  return `${(safeValue * 100).toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}%`;
}

function rulesFromApi(config: Partial<TradingRulesConfig> | undefined): TradingRulesConfig {
  const incoming = config || {};
  return {
    ...DEFAULT_TRADING_RULES,
    ...incoming,
    buyZone: { ...DEFAULT_TRADING_RULES.buyZone, ...(incoming.buyZone || {}) },
    observeZone: { ...DEFAULT_TRADING_RULES.observeZone, ...(incoming.observeZone || {}) },
    highZone: { ...DEFAULT_TRADING_RULES.highZone, ...(incoming.highZone || {}) },
    singleTradeRisk: { ...DEFAULT_TRADING_RULES.singleTradeRisk, ...(incoming.singleTradeRisk || {}) },
    ma5Risk: { ...DEFAULT_TRADING_RULES.ma5Risk, ...(incoming.ma5Risk || {}) },
    takeProfit: { ...DEFAULT_TRADING_RULES.takeProfit, ...(incoming.takeProfit || {}) },
    buyWindows: incoming.buyWindows?.length ? incoming.buyWindows : DEFAULT_TRADING_RULES.buyWindows
  };
}

function localDateString(date = new Date()): string {
  const localTime = date.getTime() - date.getTimezoneOffset() * 60_000;
  return new Date(localTime).toISOString().slice(0, 10);
}

function formatDateTimeLabel(value?: string | null): string {
  if (!value) return "-";
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? new Date(parsed).toLocaleString() : value;
}

function formatMoneyShort(value?: number | null): string {
  const safeValue = Number(value);
  if (!Number.isFinite(safeValue) || safeValue <= 0) return "-";
  if (safeValue >= 100000000) return `${(safeValue / 100000000).toFixed(1)}亿`;
  return `${(safeValue / 10000).toFixed(0)}万`;
}

function isMainBoard(code: string): boolean {
  if (!code) return false;
  if (code === "000725") return false;
  if (code.startsWith("600") || code.startsWith("601") || code.startsWith("603") || code.startsWith("605")) {
    return true;
  }
  if (code.startsWith("000") || code.startsWith("001") || code.startsWith("002")) {
    return true;
  }
  return false;
}

function tradeAmount(trade: TradeLog): number {
  return Number.isFinite(trade.amount) && trade.amount > 0 ? trade.amount : trade.price * trade.quantity;
}

function tradeSettlementAmount(trade: TradeLog): number {
  const amount = tradeAmount(trade);
  const totalFee = Number(trade.totalFee) || 0;
  return trade.type === "BUY" ? amount + totalFee : amount - totalFee;
}

type PositionSellPlan = {
  tone: "danger" | "warning" | "normal" | "neutral";
  triggerKey: "missing-ma5" | "t1-lock" | "clear" | "ma5-risk" | "take-profit" | "next-day" | "hold";
  priority: number;
  statusLabel: string;
  title: string;
  primaryAction: string;
  nextMorningRule: string;
  takeProfitRule: string;
  ma5RiskRule: string;
  sizingRule: string;
  sellReason: string;
  buttonLabel: string;
  cardClass: string;
  dotClass: string;
  badgeClass: string;
};

function formatPrice(value?: number | null): string {
  const safeValue = Number(value);
  return Number.isFinite(safeValue) && safeValue > 0 ? `¥${safeValue.toFixed(2)}` : "-";
}

function signedPercent(value: number): string {
  const safeValue = Number.isFinite(value) ? value : 0;
  return `${safeValue >= 0 ? "+" : ""}${safeValue.toFixed(2)}%`;
}

function formatPercent(value?: number | null, withSign = false): string {
  const safeValue = Number(value);
  if (!Number.isFinite(safeValue)) return "-";
  return `${withSign && safeValue >= 0 ? "+" : ""}${safeValue.toFixed(2)}%`;
}

function signedCurrency(value: number, suffix = ""): string {
  const safeValue = Number.isFinite(value) ? value : 0;
  return `${safeValue >= 0 ? "+" : ""}${safeValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${suffix}`;
}

function holdingTimeLabel(position: Position): string {
  if (position.holdDays <= 0) return "今日建仓";
  return `持有 ${position.holdDays} 天`;
}

function percentDistance(currentPrice: number, linePrice: number): number | null {
  if (!Number.isFinite(currentPrice) || !Number.isFinite(linePrice) || linePrice <= 0) return null;
  return ((currentPrice - linePrice) / linePrice) * 100;
}

function minutesFromClock(value: string): number | null {
  const [hour, minute] = value.split(":").map(Number);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return null;
  return hour * 60 + minute;
}

function isAllowedBuyWindow(value: Date, rules: TradingRulesConfig = DEFAULT_TRADING_RULES): boolean {
  const day = value.getDay();
  if (day < 1 || day > 5) return false;
  const minutes = value.getHours() * 60 + value.getMinutes();
  return rules.buyWindows.some(window => {
    const start = minutesFromClock(window.start);
    const end = minutesFromClock(window.end);
    return start !== null && end !== null && minutes >= start && minutes <= end;
  });
}

function estimateBuyRiskAmount(
  price: number,
  quantity: number,
  ma5: number,
  estimatedSellFee = 0,
  rules: TradingRulesConfig = DEFAULT_TRADING_RULES
): {
  stopPrice: number;
  riskAmount: number;
  riskPct: number;
} {
  const safePrice = Number(price);
  const safeQuantity = Number(quantity);
  const safeMa5 = Number(ma5);
  if (!Number.isFinite(safePrice) || !Number.isFinite(safeQuantity) || !Number.isFinite(safeMa5) || safeMa5 <= 0 || safeQuantity <= 0) {
    return { stopPrice: 0, riskAmount: 0, riskPct: 0 };
  }
  const stopPrice = safeMa5 * (1 - rules.ma5Risk.stopPriceBufferPct);
  const riskAmount = Math.max(0, safePrice - stopPrice) * safeQuantity + Math.max(0, estimatedSellFee);
  return {
    stopPrice,
    riskAmount,
    riskPct: 0
  };
}

function lineDistanceLabel(currentPrice: number, linePrice: number, mode: "target" | "floor"): string {
  const distance = percentDistance(currentPrice, linePrice);
  if (distance === null) return "缺少价格";
  if (mode === "target") {
    return distance >= 0 ? `已越过 ${Math.abs(distance).toFixed(2)}%` : `距触发 ${Math.abs(distance).toFixed(2)}%`;
  }
  return distance >= 0 ? `安全垫 ${distance.toFixed(2)}%` : `已跌破 ${Math.abs(distance).toFixed(2)}%`;
}

function buildPositionSellPlan(position: Position, rules: TradingRulesConfig = DEFAULT_TRADING_RULES): PositionSellPlan {
  const deviation = Number.isFinite(position.deviation5) ? position.deviation5 : 0;
  const hasMa5 = Number.isFinite(position.ma5) && position.ma5 > 0;
  const belowMa5 = hasMa5 && deviation < 0;
  const takeProfitWatch = hasMa5 && deviation >= rules.takeProfit.watchDeviationPct;
  const farFromMa5 = hasMa5 && deviation > rules.takeProfit.priorityDeviationPct;
  const belowDays = Math.max(0, Math.floor(Number(position.belowMa5Days) || 0));
  const availableQuantity = Math.max(0, Math.floor(Number(position.availableQuantity) || 0));
  const t1Locked = availableQuantity <= 0;
  const actionableQuantity = t1Locked ? position.quantity : availableQuantity;
  const smallPosition = actionableQuantity < 200;
  const sizingRule = smallPosition
    ? t1Locked
      ? "今日仓暂无可卖数量，不能执行卖出，只能记录风险并规划明日动作。"
      : "100股或小仓位不能卖半手：要么继续持有，要么一次卖完。"
    : "200股以上才考虑卖一半，剩余仓位继续用5日线管理。";
  const holdText = holdingTimeLabel(position);
  const nextMorningRule = t1Locked
    ? "今日建仓受T+1限制，盘中跌破只能记录风险；明日10:00前核对强弱，不强再按可卖数量处理。"
    : position.holdDays <= 1
      ? "次日10:00前核对强度：高开低走、冲高回落、弱于板块、没有继续上攻、跌破MA5，都按“不强”处理，冲高卖出或退出。"
    : `${holdText}，首个隔日强弱窗口已过；后续仍看是否弱于板块、冲高回落或跌破MA5。`;
  const takeProfitRule = !hasMa5
    ? "缺少MA5，先补齐K线后再判断是否远离5日线。"
    : t1Locked && farFromMa5
        ? `当前偏离MA5 ${signedPercent(deviation)}，但今日仓T+1不可卖；先写好明日止盈计划。`
    : farFromMa5
      ? `当前偏离MA5 ${signedPercent(deviation)}，已进入远离5日线止盈层。${sizingRule}`
      : takeProfitWatch
        ? `当前偏离MA5 ${signedPercent(deviation)}，进入5%-7%止盈观察层，不新增仓。`
      : `当前偏离MA5 ${signedPercent(deviation)}，尚未明显远离5日线；不因普通上涨随意卖飞。`;
  const ma5RiskRule = !hasMa5
    ? "缺少MA5，暂不能执行5日线风控判断。"
    : t1Locked && (belowMa5 || belowDays >= 3)
      ? "当前跌破MA5，但今日建仓没有可卖数量；先记录风险，明日开盘后按强弱和可卖数量优先处理。"
    : t1Locked
      ? "今日建仓暂无可卖数量，14:50只复核MA5位置并记录，不触发卖出动作。"
    : belowDays >= 3
      ? `已跌破MA5 ${belowDays} 天且未站回，触发清仓层。`
      : belowMa5
        ? `当前跌破MA5，14:50仍在5日线下方就考虑减仓或卖出；若连续3天站不回，清仓。`
        : "当前仍在MA5上方，14:50例行复查；跌破后连续3天站不回才清仓。";

  if (!hasMa5) {
    return {
      tone: "neutral",
      triggerKey: "missing-ma5",
      priority: 4,
      statusLabel: "等待MA5",
      title: "先补齐均线，再判断卖点",
      primaryAction: "当前缺少MA5，先补K线或刷新行情，暂不把风险判断拍死。",
      nextMorningRule,
      takeProfitRule,
      ma5RiskRule,
      sizingRule,
      sellReason: "缺少MA5数据，手动卖出并补充决策依据",
      buttonLabel: "记录卖出",
      cardClass: "bg-slate-900/60 border-slate-800 text-slate-200",
      dotClass: "bg-slate-500",
      badgeClass: "bg-slate-950/50 text-slate-300 border border-slate-700"
    };
  }

  if (t1Locked) {
    return {
      tone: belowMa5 ? "warning" : "neutral",
      triggerKey: "t1-lock",
      priority: belowMa5 ? 2 : 4,
      statusLabel: "T+1锁仓",
      title: belowMa5 ? "今日建仓跌破MA5，先记录风险" : "今日建仓，T+1不可卖",
      primaryAction: belowMa5
        ? "这只票今天没有可卖数量，不能提示14:50卖出；收盘前只确认是否继续跌破，明日10:00前优先处理。"
        : "今日仓按T+1锁定，今天不生成卖出动作；明日再按强弱、远离MA5和跌破MA5三层规则执行。",
      nextMorningRule,
      takeProfitRule,
      ma5RiskRule,
      sizingRule,
      sellReason: "今日建仓T+1不可卖，仅记录风险观察",
      buttonLabel: "T+1锁仓",
      cardClass: belowMa5 ? "bg-slate-900/70 border-amber-900/70 text-slate-200" : "bg-slate-900/60 border-slate-800 text-slate-200",
      dotClass: belowMa5 ? "bg-amber-500" : "bg-slate-500",
      badgeClass: belowMa5 ? "bg-amber-950 text-amber-300 border border-amber-700/60" : "bg-slate-950/50 text-slate-300 border border-slate-700"
    };
  }

  if (belowDays >= 3) {
    return {
      tone: "danger",
      triggerKey: "clear",
      priority: 0,
      statusLabel: "清仓点",
      title: "连续3天站不回MA5，按纪律清仓",
      primaryAction: `已跌破MA5 ${belowDays} 天。这里不再找理由，优先执行清仓纪律。`,
      nextMorningRule,
      takeProfitRule,
      ma5RiskRule,
      sizingRule,
      sellReason: "连续3天未站回MA5，按纪律清仓",
      buttonLabel: "记录清仓",
      cardClass: "bg-slate-900/70 border-rose-900/70 text-slate-200",
      dotClass: "bg-rose-500",
      badgeClass: "bg-rose-950 text-rose-300 border border-rose-700/60"
    };
  }

  if (belowMa5) {
    return {
      tone: "danger",
      triggerKey: "ma5-risk",
      priority: 1,
      statusLabel: "风控点",
      title: "跌破MA5，等14:50做去留",
      primaryAction: smallPosition
        ? "100股持仓：14:50仍跌破MA5，按全卖或继续持有二选一，不做半手幻想。"
        : "200股以上：14:50仍跌破MA5，考虑减仓或卖出，先把风险压下来。",
      nextMorningRule,
      takeProfitRule,
      ma5RiskRule,
      sizingRule,
      sellReason: "14:50仍跌破5日线（MA5），执行减仓或卖出风控纪律",
      buttonLabel: smallPosition ? "记录全卖" : "记录卖出",
      cardClass: "bg-slate-900/70 border-rose-900/70 text-slate-200",
      dotClass: "bg-rose-500",
      badgeClass: "bg-rose-950 text-rose-300 border border-rose-700/60"
    };
  }

  if (farFromMa5) {
    return {
      tone: "warning",
      triggerKey: "take-profit",
      priority: 2,
      statusLabel: "止盈点",
      title: "远离MA5，进入止盈观察",
      primaryAction: smallPosition
        ? "股价明显远离5日线；100股持仓只做“持有或全卖”的选择。"
        : "股价明显远离5日线；200股以上可按原规则先卖一半锁定利润。",
      nextMorningRule,
      takeProfitRule,
      ma5RiskRule,
      sizingRule,
      sellReason: smallPosition ? "远离5日线止盈，小仓位按全卖或持有二选一" : "远离5日线止盈，200股以上考虑卖出一半",
      buttonLabel: "记录止盈",
      cardClass: "bg-slate-900/70 border-amber-900/70 text-slate-200",
      dotClass: "bg-amber-500",
      badgeClass: "bg-amber-950 text-amber-300 border border-amber-700/60"
    };
  }

  if (takeProfitWatch) {
    return {
      tone: "warning",
      triggerKey: "take-profit",
      priority: 3,
      statusLabel: "止盈观察",
      title: "偏离MA5 5%-7%，进入止盈观察",
      primaryAction: "趋势还没坏，但已经明显偏离5日线；不新增仓，观察是否冲高回落或继续远离。",
      nextMorningRule,
      takeProfitRule,
      ma5RiskRule,
      sizingRule,
      sellReason: "偏离5日线5%-7%，进入止盈观察后主动减仓或止盈",
      buttonLabel: "记录止盈",
      cardClass: "bg-slate-900/70 border-amber-900/70 text-slate-200",
      dotClass: "bg-amber-500",
      badgeClass: "bg-amber-950 text-amber-300 border border-amber-700/60"
    };
  }

  if (position.holdDays <= 1) {
    return {
      tone: "warning",
      triggerKey: "next-day",
      priority: 4,
      statusLabel: "次日观察",
      title: "隔日短线，10点前看强不强",
      primaryAction: "新仓或隔日仓的核心是强度。10点前不继续上攻，就冲高卖出或退出。",
      nextMorningRule,
      takeProfitRule,
      ma5RiskRule,
      sizingRule,
      sellReason: "次日10点前不强，冲高卖出或退出",
      buttonLabel: "记录卖出",
      cardClass: "bg-slate-900/70 border-cyan-900/60 text-slate-200",
      dotClass: "bg-cyan-400",
      badgeClass: "bg-cyan-950 text-cyan-300 border border-cyan-700/60"
    };
  }

  return {
    tone: "normal",
    triggerKey: "hold",
    priority: 5,
    statusLabel: "持有观察",
    title: "未远离、未跌破，继续按MA5管理",
    primaryAction: "当前位置没有触发卖点。继续盯强弱、板块跟随和14:50的MA5位置。",
    nextMorningRule,
    takeProfitRule,
    ma5RiskRule,
    sizingRule,
    sellReason: "按持仓卖点规则主动卖出",
    buttonLabel: "记录卖出",
    cardClass: "bg-slate-900/60 border-slate-800 text-slate-200",
    dotClass: "bg-emerald-500",
    badgeClass: "bg-emerald-950 text-emerald-300 border border-emerald-700/60"
  };
}

function sortedPositionsByExitPriority(positions: Position[], rules: TradingRulesConfig = DEFAULT_TRADING_RULES): Position[] {
  return [...positions].sort((a, b) => {
    const planA = buildPositionSellPlan(a, rules);
    const planB = buildPositionSellPlan(b, rules);
    if (planA.priority !== planB.priority) return planA.priority - planB.priority;

    const belowDaysDiff = (Number(b.belowMa5Days) || 0) - (Number(a.belowMa5Days) || 0);
    if (belowDaysDiff !== 0) return belowDaysDiff;

    const deviationA = Number.isFinite(a.deviation5) ? a.deviation5 : 0;
    const deviationB = Number.isFinite(b.deviation5) ? b.deviation5 : 0;
    if (planA.triggerKey === "ma5-risk") return deviationA - deviationB;
    if (planA.triggerKey === "take-profit") return deviationB - deviationA;

    const holdDaysDiff = (Number(b.holdDays) || 0) - (Number(a.holdDays) || 0);
    if (holdDaysDiff !== 0) return holdDaysDiff;

    return a.code.localeCompare(b.code);
  });
}

export default function App() {
  // 核心应用状态
  const [activeTab, setActiveTab] = useState<"dashboard" | "watchlist" | "intraday" | "trades" | "review" | "settings">("dashboard");
  const [accountState, setAccountState] = useState<AccountState>({
    initialCash: 10000,
    availableCash: 10000,
    holdingValue: 0,
    totalAssets: 10000,
    realizedPnL: 0,
    floatingPnL: 0,
    totalPnL: 0,
    totalReturnPct: 0,
    todayPnL: 0,
    todayRealizedPnL: 0,
    asOfDate: localDateString()
  });
  const [positions, setPositions] = useState<Position[]>([]);
  const [watchlist, setWatchlist] = useState<Stock[]>([]);
  const [turnoverChanges, setTurnoverChanges] = useState<TurnoverChanges | null>(null);
  const [trades, setTrades] = useState<TradeLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLog, setActionLog] = useState<string[]>([]);
  const [currentMode, setCurrentMode] = useState<AccountMode>("simulation");

  // 筛选与交互状态
  const [watchlistGroup, setWatchlistGroup] = useState<StockViewGroup>("初筛");
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // 交易确认模态框状态
  const [showTradeModal, setShowTradeModal] = useState(false);
  const [tradeTarget, setTradeTarget] = useState<Stock | null>(null);
  const [tradeType, setTradeType] = useState<"BUY" | "SELL">("BUY");
  const [tradePrice, setTradePrice] = useState(0);
  const [tradeQuantity, setTradeQuantity] = useState(100);
  const [tradeReason, setTradeReason] = useState("");
  const [tradeRemark, setTradeRemark] = useState("");

  // 复盘报告相关状态
  const [reviewType, setReviewType] = useState<"daily" | "weekly" | "monthly">("daily");
  const [reportsList, setReportsList] = useState<ReviewReport[]>([]);
  const [auditStats, setAuditStats] = useState<any>(null);
  const [reportSummary, setReportSummary] = useState("");
  const [reportPlan, setReportPlan] = useState("");
  const [reportDate, setReportDate] = useState(localDateString());

  // 标准化多维度复盘工作台状态
  const [shTrend, setShTrend] = useState("向上");
  const [shVolume, setShVolume] = useState("放量");
  const [shFlow, setShFlow] = useState("净流入");
  const [szTrend, setSzTrend] = useState("向上");
  const [szVolume, setSzVolume] = useState("放量");
  const [szFlow, setSzFlow] = useState("净流入");
  const [cyTrend, setCyTrend] = useState("向上");
  const [cyVolume, setCyVolume] = useState("放量");
  const [cyFlow, setCyFlow] = useState("净流入");
  const [systemicRisk, setSystemicRisk] = useState(false);
  const [marketConclusion, setMarketConclusion] = useState("");

  const [reviewedEtfCount, setReviewedEtfCount] = useState(50);
  const [hotSectors, setHotSectors] = useState("");
  const [etfFlowNotes, setEtfFlowNotes] = useState("");

  const [top200Reviewed, setTop200Reviewed] = useState(false);
  const [volRatioReviewed, setVolRatioReviewed] = useState(false);
  const [limitUpReviewed, setLimitUpReviewed] = useState(false);
  const [step1Screened, setStep1Screened] = useState<ReviewScreenedStock[]>([]);
  const [step2Screened, setStep2Screened] = useState<ReviewScreenedStock[]>([]);
  const [step3Screened, setStep3Screened] = useState<ReviewScreenedStock[]>([]);
  const [isScreening, setIsScreening] = useState(false);
  const [diagnosedHoldings, setDiagnosedHoldings] = useState<SelfDiagnosisItem[]>([]);

  const [sellCompliant, setSellCompliant] = useState("符合模式");
  const [profitExperience, setProfitExperience] = useState("");
  const [lossAnalysis, setLossAnalysis] = useState("");

  // 交易费用配置 state
  const [feeSettings, setFeeSettings] = useState<FeeSettings>(DEFAULT_FEE_SETTINGS);
  const [tradingRules, setTradingRules] = useState<TradingRulesConfig>(DEFAULT_TRADING_RULES);

  // 5个复盘视图状态与聚合数据 state
  const [activeReviewSubTab, setActiveReviewSubTab] = useState<"today" | "market" | "sector" | "stock" | "action">("today");
  const [reportContext, setReportContext] = useState<any>(null);

  // 编辑单笔交易记录状态
  const [editingTrade, setEditingTrade] = useState<TradeLog | null>(null);
  const [editPrice, setEditPrice] = useState(0);
  const [editQuantity, setEditQuantity] = useState(100);
  const [editDate, setEditDate] = useState("");
  const [editTime, setEditTime] = useState("");
  const [editReason, setEditReason] = useState("");
  const [editRemark, setEditRemark] = useState("");
  const [editCommission, setEditCommission] = useState(0);
  const [editStampDuty, setEditStampDuty] = useState(0);
  const [editTransferFee, setEditTransferFee] = useState(0);
  const [editRulesConclusion, setEditRulesConclusion] = useState("");
  const [editViolationTags, setEditViolationTags] = useState<string[]>([]);

  // 同花顺表格导入状态
  const [showImportPanel, setShowImportPanel] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [autoFetchHistoryAfterImport, setAutoFetchHistoryAfterImport] = useState(true);

  // 实时系统时钟
  const [currentTime, setCurrentTime] = useState(new Date());
  const [quoteRefreshing, setQuoteRefreshing] = useState(false);
  const [autoQuoteRefreshEnabled, setAutoQuoteRefreshEnabled] = useState(false);
  const [quoteRefreshCountdown, setQuoteRefreshCountdown] = useState(QUOTE_AUTO_REFRESH_SECONDS);
  const [lastQuoteRefreshAt, setLastQuoteRefreshAt] = useState<Date | null>(null);
  const [turnoverScanning, setTurnoverScanning] = useState(false);
  const [autoTurnoverScanEnabled, setAutoTurnoverScanEnabled] = useState(false);
  const [turnoverScanCountdown, setTurnoverScanCountdown] = useState(TURNOVER_AUTO_SCAN_SECONDS);
  const [lastTurnoverScanAt, setLastTurnoverScanAt] = useState<Date | null>(null);
  const quoteRefreshInFlightRef = useRef(false);
  const turnoverScanInFlightRef = useRef(false);
  const lastQuoteRefreshAtMsRef = useRef(Date.now());
  const lastTurnoverScanAtMsRef = useRef(Date.now());
  const refreshQuotesRef = useRef<(trigger?: QuoteRefreshTrigger) => Promise<void>>(async () => {});
  const scanTurnoverChangesRef = useRef<(trigger?: TurnoverScanTrigger) => Promise<void>>(async () => {});

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const stockHash = (code: string) => code.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);

  const confidenceStars = (confidence: number) => {
    if (confidence >= 92) return "★★★★★";
    if (confidence >= 84) return "★★★★";
    if (confidence >= 70) return "★★★";
    return "★★";
  };

  const enrichScreenedStock = (stock: Stock, step: "step1" | "step2" | "step3", index: number): ReviewScreenedStock => {
    let confidence = Math.max(58, 88 - Math.min(index, 30));
    let reason = "高成交活跃票，流动性足够，适合纳入拉网复盘观察。";
    let limitHeight = "";
    const volRatioSource = "未接入真实量比，不作为交易依据";
    const conceptSource = "未接入真实题材，需要手动核查";

    if (step === "step1") {
      if (stock.canBuy) {
        confidence = 95;
        reason = `成交额排名靠前，且回踩接近5日线纪律买点，偏离度 ${stock.deviation5}%。`;
      } else if (stock.bigCandlePct >= 5 && stock.deviation5 >= 0) {
        confidence = 86;
        reason = `具备近期大阳启动痕迹，当前偏离5日线 ${stock.deviation5}%，等待回踩确认。`;
      } else if (stock.volume >= 1500000000) {
        confidence = 82;
        reason = `单日成交额 ${(stock.volume / 100000000).toFixed(1)} 亿，属于前排高容量资金池。`;
      }
    }

    if (step === "step2") {
      confidence = Math.min(90, Math.round(72 + Math.min(Math.abs(stock.pct), 8) * 2));
      reason = `未接入真实量比；当前仅按成交额 ${(stock.volume / 100000000).toFixed(1)} 亿和涨跌幅复查放量异动线索。`;
      if (stock.pct > 2 && stock.canBuy) {
        reason = "放量突破后仍贴近纪律买点，多头承接和回踩位置都需要重点核查。";
      } else if (stock.pct < 0 && stock.deviation5 >= 0 && stock.deviation5 <= 3) {
        reason = `放量后回踩未破5日线，偏离度 ${stock.deviation5}%，重点检查是否洗盘承接。`;
      }
    }

    if (step === "step3") {
      const hash = stockHash(stock.code);
      const isLimitUp = stock.pct >= 9.5;
      const isLimitDown = stock.pct <= -9.5;
      limitHeight = isLimitUp ? (hash % 2 === 0 ? "首板强势" : "连板高度") : isLimitDown ? "跌停风险" : "强趋势票";
      confidence = isLimitUp ? 94 : isLimitDown ? 30 : Math.min(90, 75 + Math.max(stock.pct, 0));
      if (isLimitUp) {
        reason = "涨停或接近涨停，需手动核查真实题材、封板质量和次日溢价风险。";
      } else if (isLimitDown) {
        reason = "跌停或接近跌停，情绪退潮明显，只做风险记录，不做抄底幻想。";
      } else {
        reason = `强趋势涨幅 ${stock.pct.toFixed(2)}%，需手动核查真实题材后再判断是否具备回踩二波条件。`;
      }
    }

    return {
      code: stock.code,
      name: stock.name,
      price: stock.price,
      pct: stock.pct,
      volume: stock.volume,
      rank: stock.rank,
      volRatioSource,
      confidence,
      stars: confidenceStars(confidence),
      reason,
      stage: stock.stage,
      group: stock.group,
      deviation5: stock.deviation5,
      conceptSource,
      limitHeight
    };
  };

  const fillScreenList = (primary: Stock[], fallback: Stock[]) => {
    const seen = new Set(primary.map(stock => stock.code));
    const targetSize = Math.min(REVIEW_SCREEN_LIMIT, Math.max(20, primary.length), fallback.length);
    const filled = [...primary];
    for (const stock of fallback) {
      if (filled.length >= targetSize) break;
      if (!seen.has(stock.code)) {
        filled.push(stock);
        seen.add(stock.code);
      }
    }
    return filled.slice(0, REVIEW_SCREEN_LIMIT);
  };

  const performAutoScreening = (list: Stock[]) => {
    if (!list.length) {
      setStep1Screened([]);
      setStep2Screened([]);
      setStep3Screened([]);
      return { step1Count: 0, step2Count: 0, step3Count: 0 };
    }

    const byVolume = [...list].sort((a, b) => b.volume - a.volume);
    const step1Source = byVolume.slice(0, Math.min(REVIEW_SCREEN_LIMIT, byVolume.length));

    const step2Primary = [...list]
      .filter(stock => stock.volume >= 1000000000 && stock.volume <= 2000000000)
      .sort((a, b) => {
        const bScore = stockHash(b.code) % 18 + Math.abs(b.pct);
        const aScore = stockHash(a.code) % 18 + Math.abs(a.pct);
        return bScore - aScore;
      });
    const step2Source = fillScreenList(step2Primary, byVolume);

    const step3Primary = [...list]
      .filter(stock => stock.pct >= 3 || stock.pct <= -3 || stock.stage === "强势确认" || stock.stage === "待买观察")
      .sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct));
    const step3Source = fillScreenList(step3Primary, byVolume);

    const nextStep1 = step1Source.map((stock, index) => enrichScreenedStock(stock, "step1", index));
    const nextStep2 = step2Source.map((stock, index) => enrichScreenedStock(stock, "step2", index));
    const nextStep3 = step3Source.map((stock, index) => enrichScreenedStock(stock, "step3", index));
    setStep1Screened(nextStep1);
    setStep2Screened(nextStep2);
    setStep3Screened(nextStep3);
    return { step1Count: nextStep1.length, step2Count: nextStep2.length, step3Count: nextStep3.length };
  };

  useEffect(() => {
    performAutoScreening(watchlist);
  }, [watchlist]);

  const diagnosisTypeLabel = (item: SelfDiagnosisItem) => {
    if (item.type === "holding") return "当前持仓";
    if (item.type === "todayBuy") return "今日买入";
    if (item.type === "todaySell") return "今日卖出";
    if (item.sourceTitle) return item.sourceTitle;
    return "手动加入";
  };

  const addToSelfDiagnosis = (stock: ReviewScreenedStock, sourceStep: "step1" | "step2" | "step3", sourceTitle: string) => {
    setDiagnosedHoldings(prev => {
      const defaultNotes = stock.reason ? `[${sourceTitle}] ${stock.reason}` : "";
      const existing = prev.find(item => item.code === stock.code);
      if (existing) {
        return prev.map(item => item.code === stock.code ? {
          ...item,
          sourceStep,
          sourceTitle,
          notes: item.notes || defaultNotes
        } : item);
      }
      return [
        ...prev,
        {
          code: stock.code,
          name: stock.name,
          type: "manual",
          sourceStep,
          sourceTitle,
          judgment: "客观观察评估：手动加入自我诊断，等待纪律确认",
          actionPlan: "只按MA5生命线与既定计划执行，不盘中临时起意",
          notes: defaultNotes
        }
      ];
    });
    logAction(`➕ 已加入自我诊断：${stock.name} (${stock.code})`);
  };

  const handleManualScreening = () => {
    setIsScreening(true);
    logAction("⏳ 正在复查当前成交额前30初筛池...");
    window.setTimeout(() => {
      const result = performAutoScreening(watchlist);
      setTop200Reviewed(true);
      setVolRatioReviewed(true);
      setLimitUpReviewed(true);
      setIsScreening(false);
      logAction(`✅ 当前初筛池三步复查完成：步骤1 ${result.step1Count} 只，步骤2 ${result.step2Count} 只，步骤3 ${result.step3Count} 只。`);
    }, 300);
  };

  // 步骤4默认只来自当前持仓与今日交易；步骤1-3股票必须手动加入。
  useEffect(() => {
    const linkedItems: SelfDiagnosisItem[] = Array.isArray(reportContext?.stockLinks)
      ? reportContext.stockLinks
        .filter((link: any) => link.position || (link.todayTrades || []).some((trade: any) => trade.date === reportDate))
        .map((link: any) => {
          const todayRows = (link.todayTrades || []).filter((trade: any) => trade.date === reportDate);
          const firstTrade = todayRows[0];
          const type = link.position ? "holding" : firstTrade?.type === "SELL" ? "todaySell" : "todayBuy";
          const tags = Array.isArray(link.complianceTags) ? link.complianceTags : [];
          return {
            code: link.code,
            name: link.name,
            type,
            judgment: link.reviewFocus || (link.position ? "第三方客观评估：按当前持仓卖点计划复盘" : "今日交易记录：复查是否符合交易纪律"),
            actionPlan: link.actionPlan || link.position?.advice || "只按交易计划执行，避免盘中临时起意",
            notes: [
              tags.length ? `合规标签：${tags.join("、")}` : "",
              link.lastBuy ? `最近买入：${link.lastBuy.date || ""} ${link.lastBuy.price || ""}` : "",
              link.lastSell ? `最近卖出：${link.lastSell.date || ""} ${link.lastSell.price || ""}` : ""
            ].filter(Boolean).join("；"),
            complianceTags: tags,
            linkedTradeIds: todayRows.map((trade: any) => trade.id).filter(Boolean)
          };
        })
      : [];

    const positionCodes = new Set(positions.map(pos => pos.code));
    const holdingItems: SelfDiagnosisItem[] = positions.map(pos => ({
      code: pos.code,
      name: pos.name,
      type: "holding",
      judgment: pos.tradeLink?.hasComplianceIssue ? "持仓关联交易存在违规标签，优先复盘买卖依据" : "第三方客观评估：买点完好，纪律持有",
      actionPlan: pos.advice || "5日线之上安全运行，暂无变动",
      notes: pos.tradeLink?.complianceTags?.length ? `合规标签：${pos.tradeLink.complianceTags.join("、")}` : "",
      complianceTags: pos.tradeLink?.complianceTags || []
    }));

    const tradeItems: SelfDiagnosisItem[] = Array.from(
      trades
        .filter(trade => trade.date === reportDate && !positionCodes.has(trade.code))
        .reduce((items, trade) => {
          const existing = items.get(trade.code);
          const type = trade.type === "BUY" ? "todayBuy" : "todaySell";
          items.set(trade.code, {
            code: trade.code,
            name: trade.name,
            type: existing?.type === "todayBuy" ? "todayBuy" : type,
            judgment: trade.type === "BUY"
              ? "今日买入记录：复查是否符合强势回踩纪律买点"
              : "今日卖出记录：复查卖出是否执行破位/止盈纪律",
            actionPlan: trade.type === "BUY" ? "明日严格按MA5生命线管理，不符合不加仓" : "复查卖出后不反手追涨",
            notes: trade.reason || trade.remark || ""
          });
          return items;
        }, new Map<string, SelfDiagnosisItem>())
        .values()
    );

    const baseItems = linkedItems.length ? linkedItems : [...holdingItems, ...tradeItems];
    const baseCodes = new Set(baseItems.map(item => item.code));

    setDiagnosedHoldings(prev => {
      const baseWithEdits = baseItems.map(item => {
        const existing = prev.find(prevItem => prevItem.code === item.code);
        return existing ? {
          ...existing,
          ...item,
          judgment: existing.judgment,
          actionPlan: existing.actionPlan,
          notes: existing.notes || item.notes
        } : item;
      });
      const manualItems = prev.filter(item => item.type === "manual" && !baseCodes.has(item.code));
      return [...baseWithEdits, ...manualItems];
    });
  }, [positions, trades, reportDate, reportContext]);

  const applyRuntimeSettings = (settings: any) => {
    setCurrentMode(modeFromApi(settings?.currentMode));
    setFeeSettings(feeSettingsFromApi(settings));
  };

  const loadRulesConfig = async () => {
    try {
      const res = await fetch("/api/rules/config");
      if (res.ok) {
        const data = await res.json();
        setTradingRules(rulesFromApi(data.config));
      }
    } catch (err) {
      console.error("加载规则配置失败:", err);
    }
  };

  // 加载初始设置
  const loadSettings = async () => {
    try {
      const res = await fetch("/api/settings");
      if (res.ok) {
        const settings = await res.json();
        applyRuntimeSettings(settings);
      }
    } catch (err) {
      console.error("加载设置失败:", err);
    }
  };

  useEffect(() => {
    loadSettings();
    loadRulesConfig();
  }, []);

  // 切换运行模式
  const handleToggleMode = async (mode: AccountMode) => {
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ currentMode: mode })
      });
      if (res.ok) {
        const settings = await res.json();
        applyRuntimeSettings(settings);
        logAction(`🔄 运行模式已切换至: ${mode === "simulation" ? "模拟训练" : "实盘记录"}`);
      }
    } catch (err) {
      logAction("❌ 切换运行模式失败");
    }
  };

  // 加载系统所有数据
  const loadAllData = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      // 1. 获取持仓与资产
      const resPortfolio = await fetch(`/api/portfolio?mode=${currentMode}`);
      if (resPortfolio.ok) {
        const data = await resPortfolio.json();
        setAccountState(data.accountState);
        setPositions(data.positions);
      }
      
      // 2. 获取自选池
      const resWatchlist = await fetch("/api/watchlist");
      if (resWatchlist.ok) {
        const data = await resWatchlist.json();
        setWatchlist(data.list);
        // 如果没有选中的股票，默认选当前视图的第一只
        if (data.list.length > 0 && !selectedStock) {
          const firstVisible = firstStockForGroup(data.list, watchlistGroup);
          if (firstVisible) setSelectedStock(firstVisible);
        }
      }

      // 3. 获取交易历史
      const resTrades = await fetch(`/api/trades?mode=${currentMode}`);
      if (resTrades.ok) {
        const data = await resTrades.json();
        setTrades(data.list);
      }

      // 4. 获取复盘审计
      const resAudit = await fetch(`/api/reports/audit?mode=${currentMode}`);
      if (resAudit.ok) {
        const data = await resAudit.json();
        setAuditStats(data);
      }

      // 5. 获取复盘报告列表
      const resReports = await fetch(`/api/reports/list?type=${reviewType}`);
      if (resReports.ok) {
        const data = await resReports.json();
        setReportsList(data.reports);
      }

      // 6. 获取复盘报告聚合数据上下文
      const contextParams = new URLSearchParams({ mode: currentMode, asOfDate: reportDate });
      const resContext = await fetch(`/api/reports/context?${contextParams.toString()}`);
      if (resContext.ok) {
        const data = await resContext.json();
        setReportContext(data);
      }

    } catch (err) {
      console.error("加载数据错误:", err);
      logAction("❌ 数据加载发生异常，请检查后台连接");
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, [watchlistGroup, reviewType, currentMode, activeTab, reportDate]);

  const logAction = (msg: string) => {
    const timestamp = new Date().toTimeString().split(" ")[0];
    setActionLog(prev => [`[${timestamp}] ${msg}`, ...prev.slice(0, 49)]);
  };

  // 重建股票池
  const handleGenerateStockPool = async () => {
    setLoading(true);
    logAction("⏳ 正在拉取主板成交额排行并执行纪律筛选...");
    try {
      const res = await fetch("/api/watchlist/generate", { method: "POST" });
      const data = await res.json().catch(() => null);
      if (!res.ok || data?.success === false) {
        if (Array.isArray(data?.list)) setWatchlist(data.list);
        throw new Error(data?.message || "自动股票池生成失败");
      }
      setWatchlist(data.list || []);
      setTurnoverChanges(null);
      logAction(`✅ ${data.message || `已生成并锁定今日初筛池 ${(data.list || []).length} 只`}`);
      setActiveTab("watchlist");
      setWatchlistGroup("初筛");
      if ((data.list || []).length > 0) {
        setSelectedStock(data.list[0]);
      }
      logAction("💡 提示: 初筛股票可能缺少K线计算指标，可点击「补充所有K线」进行指标加载");
    } catch (err) {
      const errorMessage = err instanceof Error && err.message ? err.message : "自动股票池生成失败，请稍后重试";
      logAction(`❌ ${errorMessage}`);
    } finally {
      setLoading(false);
      loadAllData(true);
    }
  };

  const handleRebuildStockPool = () => {
    if (
      watchlist.length > 0 &&
      !window.confirm("重建今日初筛池会覆盖当前股票池名单，旧池会按后端规则备份。确认继续吗？")
    ) {
      return;
    }
    void handleGenerateStockPool();
  };

  // 刷新当前池行情：只更新价格、成交额、均线偏离和分组，不改变股票池名单。
  const handleRefreshQuotes = async (trigger: QuoteRefreshTrigger = "manual") => {
    const isManualRefresh = trigger === "manual";
    if (quoteRefreshInFlightRef.current) {
      if (isManualRefresh) {
        logAction("⏳ 行情刷新正在进行中，请稍等片刻。");
      }
      return;
    }

    quoteRefreshInFlightRef.current = true;
    setQuoteRefreshing(true);
    if (isManualRefresh) setLoading(true);
    logAction(isManualRefresh ? "⏳ 立刻刷新当前池行情启动..." : "⏳ 30秒自动刷新当前池行情启动...");
    try {
      const res = await fetch("/api/watchlist/refresh-quotes", { method: "POST" });
      const data = await res.json().catch(() => null);
      if (!res.ok || data?.success === false) {
        if (Array.isArray(data?.list)) setWatchlist(data.list);
        throw new Error(data?.message || "行情刷新失败，保留本地缓存");
      }

      setWatchlist(data?.list || []);
      const refreshMessage = data?.message ? `（${data.message}）` : "";
      logAction(
        isManualRefresh
          ? `⚡ 当前池行情刷新完成，已重新评估买点区间。${refreshMessage}`
          : `⚡ 30秒自动刷新当前池行情完成，已重新评估买点区间。${refreshMessage}`
      );
    } catch (err) {
      const errorMessage = err instanceof Error && err.message ? err.message : "行情刷新失败，保留本地缓存";
      logAction(isManualRefresh ? `❌ ${errorMessage}` : `❌ 自动刷新失败：${errorMessage}`);
    } finally {
      const finishedAt = new Date();
      lastQuoteRefreshAtMsRef.current = finishedAt.getTime();
      setLastQuoteRefreshAt(finishedAt);
      setQuoteRefreshCountdown(QUOTE_AUTO_REFRESH_SECONDS);
      await loadAllData(true);
      quoteRefreshInFlightRef.current = false;
      setQuoteRefreshing(false);
      if (isManualRefresh) setLoading(false);
    }
  };

  // 扫描实时成交额前30变化，但不替换今日锁定池。
  const handleScanTurnoverChanges = async (trigger: TurnoverScanTrigger = "manual") => {
    const isManualScan = trigger === "manual";
    if (turnoverScanInFlightRef.current) {
      if (isManualScan) {
        logAction("⏳ 前30异动扫描正在进行中，请稍等片刻。");
      }
      return;
    }

    turnoverScanInFlightRef.current = true;
    setTurnoverScanning(true);
    if (isManualScan) setLoading(true);
    logAction(isManualScan ? "⏳ 正在手动扫描前30异动，当前初筛池不会被替换..." : "⏳ 3分钟自动扫描前30异动，当前初筛池不会被替换...");
    try {
      const res = await fetch("/api/watchlist/scan-turnover-changes", { method: "POST" });
      const data = await res.json().catch(() => null);
      if (res.status === 404) {
        throw new Error("当前后端未加载异动扫描接口，请重新运行「启动强势回踩系统.command」重启后端。");
      }
      if (!res.ok || data?.success === false) {
        throw new Error(data?.message || "扫描前30异动失败");
      }
      setTurnoverChanges(data.changes || null);
      if (Array.isArray(data.list)) setWatchlist(data.list);
      logAction(`🔎 ${data.message || "扫描完成，当前初筛池未被替换。"}`);
    } catch (err) {
      const errorMessage = err instanceof Error && err.message ? err.message : "扫描前30异动失败";
      logAction(`❌ ${errorMessage}`);
    } finally {
      const finishedAt = new Date();
      lastTurnoverScanAtMsRef.current = finishedAt.getTime();
      setLastTurnoverScanAt(finishedAt);
      setTurnoverScanCountdown(TURNOVER_AUTO_SCAN_SECONDS);
      await loadAllData(true);
      turnoverScanInFlightRef.current = false;
      setTurnoverScanning(false);
      if (isManualScan) setLoading(false);
    }
  };

  const handleIgnoreTurnoverStock = (stock: TurnoverChangeStock) => {
    setTurnoverChanges(prev => prev ? {
      ...prev,
      newEntries: prev.newEntries.filter(item => item.code !== stock.code)
    } : prev);
    logAction(`已忽略新进前30提醒：${stock.name || stock.code}`);
  };

  const handleIncludeTurnoverStock = async (stock: TurnoverChangeStock) => {
    setLoading(true);
    logAction(`⏳ 正在手动纳入今日初筛池: ${stock.name || stock.code}`);
    try {
      const res = await fetch("/api/watchlist/include-turnover-stock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(stock)
      });
      const data = await res.json().catch(() => null);
      if (res.status === 404) {
        throw new Error("当前后端未加载手动纳入接口，请重新运行「启动强势回踩系统.command」重启后端。");
      }
      if (!res.ok || data?.success === false) {
        throw new Error(data?.detail || data?.message || "手动纳入失败");
      }
      setWatchlist(data.list || []);
      setTurnoverChanges(prev => prev ? {
        ...prev,
        newEntries: prev.newEntries.filter(item => item.code !== stock.code)
      } : prev);
      logAction(`✅ ${data.message || "已手动纳入今日初筛池"}`);
    } catch (err) {
      const errorMessage = err instanceof Error && err.message ? err.message : "手动纳入失败";
      logAction(`❌ ${errorMessage}`);
    } finally {
      setLoading(false);
      await loadAllData(true);
    }
  };

  useEffect(() => {
    refreshQuotesRef.current = handleRefreshQuotes;
  });

  useEffect(() => {
    scanTurnoverChangesRef.current = handleScanTurnoverChanges;
  });

  useEffect(() => {
    if (!autoQuoteRefreshEnabled) {
      setQuoteRefreshCountdown(QUOTE_AUTO_REFRESH_SECONDS);
      lastQuoteRefreshAtMsRef.current = Date.now();
      return;
    }

    lastQuoteRefreshAtMsRef.current = Date.now();
    setQuoteRefreshCountdown(QUOTE_AUTO_REFRESH_SECONDS);

    const timer = window.setInterval(() => {
      const elapsedSeconds = Math.floor((Date.now() - lastQuoteRefreshAtMsRef.current) / 1000);
      const secondsLeft = Math.max(QUOTE_AUTO_REFRESH_SECONDS - elapsedSeconds, 0);
      setQuoteRefreshCountdown(secondsLeft);

      if (secondsLeft <= 0 && !quoteRefreshInFlightRef.current) {
        void refreshQuotesRef.current("auto");
      }
    }, 1000);

    return () => window.clearInterval(timer);
  }, [autoQuoteRefreshEnabled]);

  useEffect(() => {
    if (!autoTurnoverScanEnabled) {
      setTurnoverScanCountdown(TURNOVER_AUTO_SCAN_SECONDS);
      lastTurnoverScanAtMsRef.current = Date.now();
      return;
    }

    lastTurnoverScanAtMsRef.current = Date.now();
    setTurnoverScanCountdown(TURNOVER_AUTO_SCAN_SECONDS);

    const timer = window.setInterval(() => {
      const elapsedSeconds = Math.floor((Date.now() - lastTurnoverScanAtMsRef.current) / 1000);
      const secondsLeft = Math.max(TURNOVER_AUTO_SCAN_SECONDS - elapsedSeconds, 0);
      setTurnoverScanCountdown(secondsLeft);

      if (secondsLeft <= 0 && !turnoverScanInFlightRef.current) {
        void scanTurnoverChangesRef.current("auto");
      }
    }, 1000);

    return () => window.clearInterval(timer);
  }, [autoTurnoverScanEnabled]);

  // 补充K线历史
  const handleFetchHistory = async (code?: string, fetchAll = false) => {
    setLoading(true);
    logAction(fetchAll ? "⏳ 正在抓取自选池全量历史K线以补齐MA均线指标..." : `⏳ 正在抓取股票 ${code} 的历史K线...`);
    try {
      const res = await fetch("/api/watchlist/fetch-history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, fetchAll })
      });
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data.list);
        if (fetchAll) {
          const failedItems = Object.entries(data.results || {})
            .filter(([, item]) => !(item as { success?: boolean }).success)
            .slice(0, 5)
            .map(([itemCode, item]) => `${itemCode} ${(item as { status?: string }).status || ""}`.trim());
          if (data.failed > 0) {
            logAction(`⚠️ K线补充完成：成功 ${data.fetched || 0} 只，跳过 ${data.skipped || 0} 只，失败 ${data.failed || 0} 只。${failedItems.length ? `失败示例：${failedItems.join("、")}` : ""}`);
          } else {
            logAction(`✅ K线补充完成：新增/更新 ${data.fetched || 0} 只，跳过已有缓存 ${data.skipped || 0} 只。`);
          }
        } else if (data.success === false) {
          const itemResult = data.results?.[code || ""];
          logAction(`❌ 股票 ${code} K线补齐失败：${itemResult?.error || itemResult?.status || "行情源未返回有效历史K线"}`);
        } else {
          logAction(`✅ 股票 ${code} K线补齐完毕，5日均线指标已更新。`);
        }
      } else {
        throw new Error();
      }
    } catch (err) {
      logAction("❌ 历史K线拉取失败，请检查互联网连接");
    } finally {
      setLoading(false);
      loadAllData(true);
    }
  };

  // 记录股票备注
  const handleSaveRemark = async (code: string, remark: string) => {
    try {
      const res = await fetch("/api/watchlist/update-stock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, remark })
      });
      if (res.ok) {
        logAction(`已保存股票 ${code} 的备注`);
        loadAllData(true);
      }
    } catch (err) {
      logAction("❌ 保存备注失败");
    }
  };

  // 打开买入交易模态框
  const openBuyModal = (stock: Stock) => {
    setTradeTarget(stock);
    setTradeType("BUY");
    setTradePrice(stock.price || 10.0);
    setTradeQuantity(100);
    setTradeReason(stockBelongsToGroup(stock, "待买") ? "盘中手动确认：接近5日线并等待回踩不破" : "");
    setTradeRemark("");
    setShowTradeModal(true);
  };

  // 打开卖出交易模态框
  const openSellModal = (pos: Position) => {
    const availableQuantity = Math.max(0, Math.floor(Number(pos.availableQuantity) || 0));
    if (availableQuantity <= 0) {
      logAction(`${pos.name} 今日无可卖数量，T+1锁仓；已阻止卖出记录入口`);
      return;
    }
    const matched = watchlist.find(s => s.code === pos.code);
    const sellPlan = buildPositionSellPlan(pos, tradingRules);
    setTradeTarget(matched || {
      code: pos.code,
      name: pos.name,
      price: pos.currentPrice,
      pct: 0, volume: 0, rank: 99,
      poolBatchId: "", poolSource: "持仓", poolGeneratedAt: "",
      poolRankAtGeneration: 99, isPoolLocked: true, isPinned: true,
      ma5: pos.ma5, ma10: 0, ma20: 0,
      deviation5: pos.deviation5, bigCandlePct: 10, ma5Upward: true, canBuy: false,
      group: "观察", stage: "继续观察", riskLevel: "normal", reason: "", reminder: "",
      historyStatus: "已有缓存", lastUpdated: "", remark: ""
    });
    setTradeType("SELL");
    setTradePrice(pos.currentPrice || pos.avgCost);
    setTradeQuantity(availableQuantity);
    setTradeReason(sellPlan.sellReason);
    setTradeRemark("");
    setShowTradeModal(true);
  };

  // 提交交易记录
  const handleExecuteTrade = async () => {
    if (!tradeTarget) return;
    try {
      const res = await fetch("/api/trades/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: tradeTarget.code,
          name: tradeTarget.name,
          type: tradeType,
          price: Number(tradePrice),
          quantity: Number(tradeQuantity),
          reason: tradeReason,
          remark: tradeRemark,
          mode: currentMode,
          systemicRisk,
          marketRisk: tradeTarget.marketTradeAllowed === false || tradeTarget.marketRisk === true
        })
      });

      if (res.ok) {
        const data = await res.json();
        logAction(`💸 [${currentMode === "real" ? "实盘" : "模拟"}] 交易已存档！${tradeType === "BUY" ? "买入" : "卖出"} ${tradeTarget.name} ${tradeQuantity} 股，审计结论: [${data.trade.rulesConclusion}]`);
        setShowTradeModal(false);
        loadAllData();
      } else {
        const errData = await res.json();
        alert(errData.error || "交易存档失败，请重试");
      }
    } catch (err) {
      logAction("❌ 交易归档通信失败");
    }
  };

  // 删除交易记录
  const handleDeleteTrade = async (id: string) => {
    if (!confirm("确定要删除这笔交易记录吗？持仓与资金将自动回滚重新推导。")) return;
    try {
      const res = await fetch("/api/trades/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, mode: currentMode })
      });
      if (res.ok) {
        logAction(`🗑️ 交易流水 ${id} 已撤销，持仓重新推算中。`);
        loadAllData();
      }
    } catch (err) {
      logAction("❌ 撤销交易失败");
    }
  };

  // 打开编辑交易流水模态框
  const openEditTradeModal = (trade: TradeLog) => {
    setEditingTrade(trade);
    setEditPrice(trade.price);
    setEditQuantity(trade.quantity);
    setEditDate(trade.date);
    setEditTime(trade.time);
    setEditReason(trade.reason);
    setEditRemark(trade.remark || "");
    const fees = calculateFeeBreakdown(trade.type, trade.price, trade.quantity);
    setEditCommission(fees.comm);
    setEditStampDuty(fees.stamp);
    setEditTransferFee(fees.trans);
    setEditRulesConclusion(trade.rulesConclusion);
    setEditViolationTags(trade.violationTags || []);
  };

  // 提交修改交易流水
  const handleUpdateTrade = async () => {
    if (!editingTrade) return;
    try {
      const res = await fetch("/api/trades/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: editingTrade.id,
          mode: currentMode,
          price: Number(editPrice),
          quantity: Number(editQuantity),
          date: editDate,
          time: editTime,
          reason: editReason,
          remark: editRemark,
          rulesConclusion: editRulesConclusion,
          violationTags: editViolationTags
        })
      });

      if (res.ok) {
        logAction(`✍️ 交易流水 ${editingTrade.id} 编辑成功，账单已重新计算并实时同步费用！`);
        setEditingTrade(null);
        loadAllData();
      } else {
        alert("编辑保存失败，请检查输入");
      }
    } catch (err) {
      logAction("❌ 编辑保存通信失败");
    }
  };

  // 保存复盘日报/周报/月报
  const handleSaveReport = async () => {
    if (!reportSummary) {
      alert("请输入复盘心得总结！");
      return;
    }

    // 按复盘参考日期生成完整快照，不只取当前自然日。
    const reportTrades = trades.filter(t => t.date === reportDate);
    const todayRealizedPnL = Number(
      reportContext?.asOfDate === reportDate
        ? reportContext?.realizedPnL
        : accountState.asOfDate === reportDate
          ? accountState.todayRealizedPnL
          : 0
    ) || 0;
    const buyCount = reportTrades.filter(t => t.type === "BUY").length;
    const sellCount = reportTrades.filter(t => t.type === "SELL").length;
    const reportBuys = reportTrades.filter(t => t.type === "BUY");
    const reportSells = reportTrades.filter(t => t.type === "SELL");
    const compliantCount = reportTrades.filter(t => t.rulesConclusion === "符合规则").length;
    const compliantBuyCount = reportBuys.filter(t => t.rulesConclusion === "符合规则").length;
    const compliantSellCount = reportSells.filter(t => t.rulesConclusion === "符合规则").length;
    const complianceRate = reportTrades.length > 0 ? Number(((compliantCount / reportTrades.length) * 100).toFixed(2)) : 100;
    const buyComplianceRate = reportBuys.length > 0 ? Number(((compliantBuyCount / reportBuys.length) * 100).toFixed(2)) : 100;
    const sellComplianceRate = reportSells.length > 0 ? Number(((compliantSellCount / reportSells.length) * 100).toFixed(2)) : 100;
    const portfolioRisk = positions.filter(p => p.riskLevel === "danger").length > 0 ? "高风险 (部分持仓已破5日线)" : "正常 (持仓均在5日线上方)";
    const autoTomorrowPlan = positions.length === 0
      ? "无持仓；若无0%~2.5%待买且市场/板块不强，明日保持空仓。"
      : positions.map(pos => `${pos.name} ${pos.code}: ${buildPositionSellPlan(pos, tradingRules).primaryAction}`).join("\n");
    const stockScreening = {
      step1: {
        title: "当前成交额前30初筛池复查",
        reviewed: top200Reviewed,
        stocks: step1Screened
      },
      step2: {
        title: "量比前50且成交额10-20亿",
        reviewed: volRatioReviewed,
        stocks: step2Screened
      },
      step3: {
        title: "涨跌停板与情绪高度核查",
        reviewed: limitUpReviewed,
        stocks: step3Screened
      }
    };

    const newReport: ReviewReport = {
      id: `R_${reviewType}_${reportDate}`,
      type: reviewType,
      date: reportDate,
      accountSnapshot: accountState,
      todayTrades: reportTrades,
      currentPositions: positions,
      stockLinks: reportContext?.stockLinks || [],
      linkedStockReviews: reportContext?.stockLinks || [],
      summaryStats: {
        buyCount,
        sellCount,
        ruleComplianceRate: complianceRate,
        buyComplianceRate,
        sellComplianceRate,
        tradeComplianceRate: complianceRate,
        realizedPnL: Number(todayRealizedPnL.toFixed(2)),
        portfolioRisk
      },
      buyCount,
      sellCount,
      ruleComplianceRate: complianceRate,
      violations: reportTrades.filter(t => t.rulesConclusion === "违规交易").flatMap(t => t.violationTags),
      realizedPnL: Number(todayRealizedPnL.toFixed(2)),
      portfolioRisk,
      summary: reportSummary,
      tomorrowPlan: reportPlan || autoTomorrowPlan,
      createdTime: new Date().toLocaleString(),
      marketAnalysis: {
        shTrend,
        shVolume,
        shFlow,
        szTrend,
        szVolume,
        szFlow,
        cyTrend,
        cyVolume,
        cyFlow,
        systemicRisk,
        marketConclusion
      },
      sectorAnalysis: {
        reviewedEtfCount,
        hotSectors,
        etfFlowNotes
      },
      stockAnalysis: {
        top200Reviewed,
        volRatioReviewed,
        limitUpReviewed,
        step1Screened,
        step2Screened,
        step3Screened,
        selfDiagnostics: diagnosedHoldings,
        diagnosedHoldings
      },
      stockScreening,
      selfDiagnosis: {
        items: diagnosedHoldings
      },
      actionAudit: {
        sellCompliant,
        profitExperience,
        lossAnalysis
      },
      reflection: {
        summary: reportSummary,
        tomorrowPlan: reportPlan || autoTomorrowPlan
      }
    };

    try {
      const res = await fetch("/api/reports/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newReport)
      });
      if (res.ok) {
        logAction(`📝 [${reviewType === "daily" ? "日报" : reviewType === "weekly" ? "周报" : "月报"}] 归档成功！日期: ${reportDate}`);
        setReportSummary("");
        setReportPlan("");
        loadAllData();
      }
    } catch (err) {
      logAction("❌ 报告归档失败");
    }
  };

  // 手动修改初始资金
  const handleResetCash = async () => {
    const cashStr = prompt(`请输入您想设定的${currentMode === "real" ? "实盘" : "模拟"}账户初始总现金 (元):`, String(accountState.initialCash));
    if (!cashStr) return;
    const cashNum = Number(cashStr);
    if (isNaN(cashNum) || cashNum <= 0) {
      alert("请输入有效的正数");
      return;
    }
    try {
      const res = await fetch("/api/account/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initialCash: cashNum })
      });
      if (res.ok) {
        const data = await res.json().catch(() => null);
        if (data?.settings) applyRuntimeSettings(data.settings);
        logAction(`⚙️ 初始账户本金设定为: ${cashNum.toLocaleString()} 元，持仓重新审计中。`);
        loadAllData();
      }
    } catch (err) {
      logAction("❌ 设定初始资金失败");
    }
  };

  const handleRecalculateFees = async (silent = false) => {
    try {
      const params = new URLSearchParams({ mode: currentMode });
      const res = await fetch(`/api/trades/recalculate-fees?${params.toString()}`, {
        method: "POST"
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "历史交易费用重算失败");
      }
      const data = await res.json();
      if (Array.isArray(data.trades)) setTrades(data.trades);
      if (data.accountState) setAccountState(data.accountState);
      if (!silent) {
        logAction(`⚙️ 已按当前${currentMode === "real" ? "实盘" : "模拟"}费用口径重算 ${data.updatedCount ?? 0} 笔历史交易。`);
      }
      await loadAllData(true);
      return true;
    } catch (err) {
      logAction("❌ 历史交易费用重算失败");
      alert(err instanceof Error ? err.message : "历史交易费用重算失败");
      return false;
    }
  };

  // 保存系统交易费用费率配置
  const handleSaveFees = async (newFees: typeof feeSettings) => {
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...newFees,
          feeProfile: feeProfileForValues(newFees),
          currentMode
        })
      });
      if (res.ok) {
        const settings = await res.json();
        applyRuntimeSettings(settings);
        logAction(`⚙️ ${currentMode === "real" ? "实盘" : "模拟"}交易费用已更新为：${feeSettingsLabel(feeSettingsFromApi(settings), currentMode)}。`);
        if (window.confirm("费用配置已保存。是否立即按当前费用配置重算当前账户全部历史交易费用？")) {
          await handleRecalculateFees(true);
          logAction(`⚙️ 已按当前费用配置重算${currentMode === "real" ? "实盘" : "模拟"}历史交易。`);
        } else {
          loadAllData(true);
        }
      } else {
        alert("费用配置保存失败");
      }
    } catch (err) {
      logAction("❌ 保存费率配置通信失败");
    }
  };

  // 处理同花顺导出表格导入。导入会覆盖当前股票池，以最新表格为准。
  const handleImportFile = async () => {
    if (!importFile) {
      alert("请先选择同花顺导出的表格文件");
      return;
    }
    if (
      watchlist.length > 0 &&
      !window.confirm("上传同花顺初筛池会以文件内容覆盖当前股票池名单，确认继续吗？")
    ) {
      return;
    }
    try {
      setLoading(true);
      logAction(`⏳ 正在导入同花顺表格并覆盖当前股票池: ${importFile.name}`);
      const params = new URLSearchParams({
        filename: importFile.name,
        fetchHistory: String(autoFetchHistoryAfterImport)
      });
      const res = await fetch(`/api/watchlist/import-file?${params.toString()}`, {
        method: "POST",
        headers: {
          "Content-Type": importFile.type || "application/octet-stream",
          "X-Filename": encodeURIComponent(importFile.name)
        },
        body: importFile
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "导入失败");
      }
      const data = await res.json();
      setWatchlist(data.list || []);
      setTurnoverChanges(null);
      logAction(`📂 ${data.message || "同花顺表格导入完成"}；原始代码 ${data.summary?.codeRows ?? "-"} 行，主板有效 ${data.summary?.mainBoardRows ?? "-"} 行。`);
      if (data.history) {
        logAction(`📈 自动补K线完成：成功 ${data.history.fetched || 0} 只，失败 ${data.history.failed || 0} 只。`);
      } else {
        logAction("💡 已用同花顺代码覆盖股票池，可点击「补充所有K线」补齐历史数据。");
      }
      setShowImportPanel(false);
      setImportFile(null);
      setWatchlistGroup("初筛");
      loadAllData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "同花顺表格导入失败");
    } finally {
      setLoading(false);
    }
  };

  const calculateFeeBreakdown = (side: "BUY" | "SELL", price: number, quantity: number) => {
    const amt = price * quantity;
    const baseCommission = Number((amt * feeSettings.commissionRate).toFixed(2));
    const comm = amt > 0 ? Math.max(feeSettings.minCommission, baseCommission) : 0;
    const trans = Number((amt * feeSettings.transferFeeRate).toFixed(2));
    const stamp = side === "SELL" ? Number((amt * feeSettings.stampDutyRate).toFixed(2)) : 0;
    const total = Number((comm + trans + stamp).toFixed(2));
    const settle = side === "BUY" ? amt + total : amt - total;
    return { comm, trans, stamp, total, settle };
  };

  // 计算交易各种费用 (用于买卖确认框实时计算)
  const calculateEstimateFees = () => calculateFeeBreakdown(tradeType, tradePrice, tradeQuantity);

  const est = calculateEstimateFees();
  const estimatedSellFees = calculateFeeBreakdown("SELL", tradePrice, tradeQuantity);
  const buyRiskEstimate = estimateBuyRiskAmount(tradePrice, tradeQuantity, tradeTarget?.ma5 || 0, estimatedSellFees.total, tradingRules);
  const buyRiskAmount = buyRiskEstimate.riskAmount;
  const maxAllowedRiskAmount = accountState.initialCash * tradingRules.singleTradeRisk.maxPct;
  const buyRiskPct = accountState.initialCash > 0 ? (buyRiskAmount / accountState.initialCash) * 100 : 0;
  const activeTradePosition = tradeTarget ? positions.find(pos => pos.code === tradeTarget.code) : null;
  const activeAvailableQuantity = activeTradePosition ? Math.max(0, Math.floor(Number(activeTradePosition.availableQuantity) || 0)) : 0;
  const currentInBuyWindow = isAllowedBuyWindow(currentTime, tradingRules);
  const activeMarketRisk = systemicRisk || tradeTarget?.marketTradeAllowed === false || tradeTarget?.marketRisk === true;
  const tradeDeviationAtPrice = tradeTarget?.ma5 ? ((tradePrice - tradeTarget.ma5) / tradeTarget.ma5) * 100 : Number.NaN;
  const buyFormHasHardRisk = tradeType === "BUY" && (
    !tradeTarget?.canBuy ||
    !currentInBuyWindow ||
    activeMarketRisk ||
    tradeQuantity < tradingRules.lotSize ||
    accountState.availableCash < tradePrice * tradingRules.lotSize ||
    tradeDeviationAtPrice < tradingRules.buyZone.minDeviationPct ||
    tradeDeviationAtPrice > tradingRules.buyZone.maxDeviationPct ||
    buyRiskAmount <= 0 ||
    buyRiskAmount > maxAllowedRiskAmount
  );

  // 判断 A股交易时间段 (9:30-11:30, 13:00-15:00)
  const isAStockTradingTime = () => {
    const h = currentTime.getHours();
    const m = currentTime.getMinutes();
    const tot = h * 60 + m;
    const isWd = currentTime.getDay() >= 1 && currentTime.getDay() <= 5;
    const morning = tot >= 9 * 60 + 30 && tot <= 11 * 60 + 30;
    const afternoon = tot >= 13 * 60 && tot <= 15 * 60;
    return isWd && (morning || afternoon);
  };

  // 股市状态与交易纪律联动说明
  const getMarketLinkedInstructions = () => {
    const h = currentTime.getHours();
    const m = currentTime.getMinutes();
    const tot = h * 60 + m;
    const isWd = currentTime.getDay() >= 1 && currentTime.getDay() <= 5;
    
    if (!isWd) {
      return {
        phase: "A股已收盘 (周末/休市期)",
        bg: "bg-slate-900/60 border-slate-800 text-slate-300",
        action: "收盘写快照与周复盘",
        color: "text-slate-400",
        guidelines: [
          "💡 自我审计：进入「交易记录审计」和「复盘笔记归档」，总结本周的所有交易操作是否严格执行买入偏离度（0%~2.5%）和卖出（跌破MA5）纪律。",
          "💡 模拟训练备战：切换到「模拟训练」模式，点击「清空交易流水」并重新设定模拟本金进行超短线操盘练习，巩固对回踩均线低吸的认知。"
        ]
      };
    }
    
    if (tot < 9 * 60 + 30) {
      return {
        phase: "A股开盘前 (盘前备战 08:30 - 09:30)",
        bg: "bg-blue-950/30 border-blue-900/60 text-blue-200",
        action: "盘前重计算",
        color: "text-blue-400",
        guidelines: [
          "🎯 构建初筛池：点击「重建今日初筛池」拉取主板成交额最强的前30标的（系统已智能排除ST、创业板、科创板、北交及笨重股）。",
          "🎯 均线指标补齐：在「股票池」界面，点击「补充所有K线」加载历史均线指标。评估哪些强势股有回踩均线潜能，加入 [观察] 分组。",
          "⚠️ 戒骄戒躁：开盘前严禁凭临时直觉/意念追涨下单挂单！必须静待盘中严格的回踩买点出现。"
        ]
      };
    } else if (tot >= 9 * 60 + 30 && tot < 9 * 60 + 35) {
      return {
        phase: "A股开盘过渡期 (09:30 - 09:35)",
        bg: "bg-amber-950/40 border-amber-900/60 text-amber-200",
        action: "开盘静默观察",
        color: "text-amber-400",
        guidelines: [
          "⚠️ 严防乱买冲动：开盘前5分钟（09:30 - 09:35）盘面变化极度剧烈，高开低走与诱多频繁，不建议在此期间做任何买入操作！",
          "⚡ 监控持仓次日强度：如果今天有可卖持仓，需观察高开或低开状态。如果10点前股价无力上攻或冲高回落，考虑做好冲高离场准备。"
        ]
      };
    } else if (tot >= 9 * 60 + 35 && tot <= 10 * 60) {
      return {
        phase: "早盘低吸黄金窗口 (09:35 - 10:00)",
        bg: "bg-emerald-950/30 border-emerald-900/60 text-emerald-200",
        action: "均线低吸介入",
        color: "text-emerald-400",
        guidelines: [
          "✅ 符合铁律买入期：此时间段主力拉升或踩支撑意图已初步明晰。立即核对「继续观察」和「待买」列表！",
          "📈 黄金偏离率买入：若看好个股出现回踩5日线，偏离度在 0% ~ 2.5% 且未有效跌破MA5，符合低吸纪律，可轻仓/按批次记录买入。"
        ]
      };
    } else if (tot > 10 * 60 && tot < 13 * 60) {
      return {
        phase: "盘中静默观察期 (10:00 - 13:00)",
        bg: "bg-slate-950/40 border-slate-800 text-slate-300",
        action: "坚决克制不买",
        color: "text-slate-400",
        guidelines: [
          "❌ 严禁盘中追涨：10:00 到 11:30（以及午休）是主力拉高出货或无量诱多的震荡多发期，此时段追大阳线极易吃套！",
          "⚠️ 纪律约束：只看盘、不交易，不根据短时间内的秒级拉升草率挂单。等待下午尾盘定乾坤的机会。"
        ]
      };
    } else if (tot >= 13 * 60 && tot < 14 * 60 + 30) {
      return {
        phase: "午盘观察静默期 (13:00 - 14:30)",
        bg: "bg-slate-950/40 border-slate-800 text-slate-300",
        action: "耐心看盘不买",
        color: "text-slate-400",
        guidelines: [
          "❌ 严禁午后追涨：午后开盘往往成交量低迷，个股波动缺乏持续性。此时买入，次日极易陷入被动。",
          "🔍 备战尾盘：密切锁定加入自选的「继续观察」个股。看是否有标的在 14:30 后稳步回落至 5 日线附近、而不形成破位。"
        ]
      };
    } else if (tot >= 14 * 60 + 30 && tot < 14 * 60 + 50) {
      return {
        phase: "尾盘低吸确认窗口 (14:30 - 14:50)",
        bg: "bg-emerald-950/30 border-emerald-900/60 text-emerald-200",
        action: "尾盘支撑低吸",
        color: "text-emerald-400",
        guidelines: [
          "✅ 尾盘安全买入期：由于收盘临近，5日线支撑是否有效已得到基本确认，是判定大阳股回踩低吸最为安全的防诱多买点时点！",
          "📈 支撑校验：若股价平稳落在5日线附近，偏离度在 0% ~ 2.5% 且5日线未跌破，可分批补录建仓，锁定低吸机会。"
        ]
      };
    } else if (tot >= 14 * 60 + 50 && tot <= 14 * 60 + 55) {
      return {
        phase: "尾盘持仓风控执行时段 (14:50 - 14:55)",
        bg: "bg-rose-950/30 border-rose-900/70 text-rose-100",
        action: "持仓逐只对账",
        color: "text-rose-400",
        guidelines: [
          "14:50 持仓对账：按下方每只持仓的卖点卡执行，优先处理清仓点和风控点。",
          "跌破 MA5：若当前价仍在5日线下方，100股按全卖或继续持有二选一，200股以上先考虑减仓；连续3天站不回则清仓。"
        ]
      };
    } else if (tot > 14 * 60 + 55 && tot < 15 * 60) {
      return {
        phase: "尾盘锁定静默期 (14:55 - 15:00)",
        bg: "bg-amber-950/40 border-amber-900/60 text-amber-200",
        action: "锁定交易静默",
        color: "text-amber-400",
        guidelines: [
          "⚠️ 严禁最后几分钟胡乱下单：14:57 以后进入集合竞价锁死。拒绝任何赌博性质的草率决定！",
          "📝 盘后对账备战：收拾心情，准备迎接收盘后的账目盈亏核算与复盘总结。"
        ]
      };
    } else {
      return {
        phase: "A股已收盘",
        bg: "bg-slate-900 border-slate-800 text-slate-300",
        action: "收盘复盘总结",
        color: "text-slate-400",
        guidelines: [
          "📝 流水补录对账：仔细核对今日的所有交易记录是否完备。系统已根据昨日K线与偏离度对您今日的所有买卖自动完成合规审计。",
          "📝 复盘日记归档：进入「复盘笔记归档」工作台，书写今日心得并生成复盘日报，客观审视今日是否存在违规交易。"
        ]
      };
    }
  };

  // 今日复盘相关计算
  const reviewAsOfDate = String(reportContext?.asOfDate || reportDate || accountState.asOfDate || localDateString());
  const todayTrades = trades.filter(t => t.date === reviewAsOfDate);
  const todayRealizedPnL = Number(
    reportContext?.realizedPnL ??
    (accountState.asOfDate === reviewAsOfDate ? accountState.todayRealizedPnL : 0) ??
    0
  );
  const reviewBuyCount = todayTrades.filter(t => t.type === "BUY").length;
  const reviewCompliantCount = todayTrades.filter(t => t.rulesConclusion === "符合规则").length;
  const complianceRate = todayTrades.length > 0 ? Number(((reviewCompliantCount / todayTrades.length) * 100).toFixed(2)) : 100;

  const hasStrongStartSignal = (stock: Stock) => stock.bigCandlePct >= 5;
  const hasValidMa5 = (stock: Stock) => stock.ma5 > 0;
  const observationStages: StockStage[] = ["强势确认", "继续观察", "偏高不追", "远离不追", "待买观察"];
  const observationStageForStock = (stock: Stock): StockStage | null => {
    if (hasStrongStartSignal(stock) && hasValidMa5(stock) && stock.deviation5 >= 0) {
      if (stock.deviation5 <= tradingRules.buyZone.maxDeviationPct) return "待买观察";
      if (stock.deviation5 <= tradingRules.observeZone.maxDeviationPct) return "继续观察";
      if (stock.deviation5 <= tradingRules.highZone.maxDeviationPct) return "偏高不追";
      return "远离不追";
    }
    return observationStages.includes(stock.stage) ? stock.stage : null;
  };
  const isObservationStock = (stock: Stock) => observationStageForStock(stock) !== null;

  const stockBelongsToGroup = (stock: Stock, group: StockViewGroup) => {
    if (group === "初筛") return true;
    if (group === "持仓") {
      return positions.some(pos => pos.code === stock.code);
    }
    if (group === "待买") {
      return Boolean(stock.canBuy);
    }
    if (group === "观察") return isObservationStock(stock);
    return false;
  };

  const stocksForGroup = (list: Stock[], group: StockViewGroup) => (
    list.filter(stock => stockBelongsToGroup(stock, group))
  );
  const sortedPositions = sortedPositionsByExitPriority(positions, tradingRules);
  const marketInstructions = getMarketLinkedInstructions();
  const marketIsTrading = isAStockTradingTime();
  const currentTimeLabel = currentTime.toLocaleTimeString("zh-CN", { hour12: false });
  const isPortfolioRiskWindow = marketInstructions.phase.includes("尾盘持仓风控");
  const urgentPositionCount = sortedPositions.filter(position => buildPositionSellPlan(position, tradingRules).priority <= 1).length;

  const firstStockForGroup = (list: Stock[], group: StockViewGroup) => (
    stocksForGroup(list, group)[0] || list[0]
  );

  const buyReadyStocks = stocksForGroup(watchlist, "待买");
  const buyReadyPreviewStocks = buyReadyStocks.slice(0, 4);
  const buyReadyMoreCount = Math.max(0, buyReadyStocks.length - buyReadyPreviewStocks.length);
  const todayTotalPnLForAccount = accountState.todayPnL ?? 0;

  // 股票搜索过滤。初筛是成交额前30基础池；观察/待买是从基础池派生出的规则视图。
  const filteredWatchlist = watchlist.filter(s => {
    if (!stockBelongsToGroup(s, watchlistGroup)) return false;
    if (searchQuery) {
      return s.code.includes(searchQuery) || s.name.includes(searchQuery);
    }
    return true;
  });
  const poolMeta = watchlist.find(s => s.poolBatchId || s.poolGeneratedAt || s.poolSource);
  const initialPoolCount = stocksForGroup(watchlist, "初筛").length;
  const observationCount = stocksForGroup(watchlist, "观察").length;
  const pendingBuyCount = buyReadyStocks.length;
  const poolGeneratedDate = poolMeta?.poolGeneratedAt && Number.isFinite(Date.parse(poolMeta.poolGeneratedAt))
    ? localDateString(new Date(poolMeta.poolGeneratedAt))
    : "";
  const hasTodayPool = initialPoolCount > 0 && poolGeneratedDate === localDateString();
  const latestWatchlistUpdatedAt = watchlist.reduce((latest, stock) => {
    const parsed = Date.parse(stock.lastUpdated || "");
    return Number.isFinite(parsed) ? Math.max(latest, parsed) : latest;
  }, 0);
  const latestWatchlistUpdateLabel = latestWatchlistUpdatedAt > 0
    ? new Date(latestWatchlistUpdatedAt).toLocaleTimeString()
    : "未同步";
  const poolGeneratedLabel = poolMeta?.poolGeneratedAt
    ? formatDateTimeLabel(poolMeta.poolGeneratedAt)
    : (poolMeta?.poolBatchId || "-");
  const missingKLineCount = watchlist.filter(stock => stock.historyStatus !== "已有缓存").length;
  const latestQuoteLabel = lastQuoteRefreshAt ? lastQuoteRefreshAt.toLocaleTimeString() : latestWatchlistUpdateLabel;
  const changeTotal = turnoverChanges
    ? turnoverChanges.newEntries.length + turnoverChanges.dropped.length + turnoverChanges.rankUp.length + turnoverChanges.rankDown.length
    : 0;
  const turnoverRankLabel = (item: TurnoverChangeStock) => {
    const oldRank = item.oldRank ?? item.currentRank;
    const newRank = item.newRank ?? item.rank;
    if (oldRank && newRank && oldRank !== newRank) return `${oldRank}->${newRank}`;
    return `#${newRank || oldRank || "-"}`;
  };

  const reviewSteps = [
    { key: "today", label: "今日复盘", title: "流水审计", index: "01" },
    { key: "market", label: "大盘多空", title: "系统环境", index: "02" },
    { key: "sector", label: "板块回踩", title: "题材资金", index: "03" },
    { key: "stock", label: "持仓偏差", title: "个股诊断", index: "04" },
    { key: "action", label: "纠错自省", title: "总日报", index: "05" },
  ] as const;
  const activeReviewIndex = Math.max(0, reviewSteps.findIndex(step => step.key === activeReviewSubTab));

  const renderReviewStepper = () => (
    <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-lg space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-cyan-400" />
          <span className="text-xs font-black text-slate-200 tracking-wider">盘后步进式闭环复盘系统</span>
        </div>
        <span className="text-[10px] font-mono font-bold bg-slate-950 text-slate-400 px-2.5 py-1 rounded border border-slate-800 w-fit">
          复盘进度 {activeReviewIndex + 1} / {reviewSteps.length}
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {reviewSteps.map((step, idx) => {
          const isActive = activeReviewSubTab === step.key;
          const isComplete = idx < activeReviewIndex;
          return (
            <button
              key={step.key}
              onClick={() => setActiveReviewSubTab(step.key)}
              className={`p-3 rounded-lg border text-left transition ${
                isActive
                  ? "bg-cyan-950/25 border-cyan-500/70 shadow-md shadow-cyan-950/20"
                  : isComplete
                    ? "bg-slate-950/70 border-emerald-900/40 hover:border-slate-700"
                    : "bg-slate-950/30 border-slate-800/60 hover:border-slate-700"
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className={`h-6 w-6 rounded-full flex items-center justify-center font-mono text-[10px] font-black shrink-0 ${
                  isActive
                    ? "bg-cyan-400 text-slate-950"
                    : isComplete
                      ? "bg-emerald-950 text-emerald-300 border border-emerald-700/50"
                      : "bg-slate-900 text-slate-500 border border-slate-800"
                }`}>
                  {isComplete ? "✓" : step.index}
                </span>
                <div className="min-w-0">
                  <span className={`text-[11px] font-black block truncate ${isActive ? "text-cyan-300" : "text-slate-300"}`}>
                    {step.label}
                  </span>
                  <span className="text-[9px] text-slate-500 block truncate">{step.title}</span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );

  const renderReviewNavFooter = (
    previous: typeof reviewSteps[number]["key"] | null,
    next: typeof reviewSteps[number]["key"] | null,
    nextLabel?: string
  ) => (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-4 border-t border-slate-900">
      {previous ? (
        <button
          onClick={() => setActiveReviewSubTab(previous)}
          className="flex items-center justify-center gap-1.5 px-4 py-2 bg-slate-900 hover:bg-slate-850 text-slate-400 hover:text-slate-200 border border-slate-800 rounded-lg text-xs font-bold transition"
        >
          <ChevronLeft className="h-4 w-4" />
          <span>返回上一步：{reviewSteps.find(step => step.key === previous)?.label}</span>
        </button>
      ) : <span />}
      {next && (
        <button
          onClick={() => setActiveReviewSubTab(next)}
          className="flex items-center justify-center gap-2 px-5 py-2.5 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white font-extrabold text-xs rounded-lg shadow-md transition"
        >
          <span>{nextLabel || `进入下一步：${reviewSteps.find(step => step.key === next)?.label}`}</span>
          <ChevronRight className="h-4 w-4" />
        </button>
      )}
    </div>
  );

  const syncReportDraftFromReview = () => {
    const reportTrades = trades.filter(t => t.date === reportDate);
    const buyCount = reportTrades.filter(t => t.type === "BUY").length;
    const sellCount = reportTrades.filter(t => t.type === "SELL").length;
    const compliantCount = reportTrades.filter(t => t.type === "BUY" && t.rulesConclusion === "符合规则").length;
    const draftComplianceRate = buyCount > 0 ? Number(((compliantCount / buyCount) * 100).toFixed(2)) : 100;
    const draftPnl = Number(
      reportContext?.asOfDate === reportDate
        ? reportContext?.realizedPnL
        : accountState.asOfDate === reportDate
          ? accountState.todayRealizedPnL
          : 0
    ) || 0;

    let text = `【${reportDate} 闭环复盘日报】\n\n`;
    text += `一、流水与合规审计\n`;
    text += `- 买入 ${buyCount} 次，卖出 ${sellCount} 次。\n`;
    text += `- 规则符合率：${draftComplianceRate}%\n`;
    text += `- 已实现盈亏：${draftPnl >= 0 ? "+" : ""}${draftPnl.toFixed(2)} 元\n\n`;
    text += `二、大盘与板块\n`;
    text += `- 上证：${shTrend} / ${shVolume} / ${shFlow}\n`;
    text += `- 深成：${szTrend} / ${szVolume} / ${szFlow}\n`;
    text += `- 创业板：${cyTrend} / ${cyVolume} / ${cyFlow}\n`;
    text += `- 系统性风险：${systemicRisk ? "是" : "否"}\n`;
    text += `- 市场结论：${marketConclusion || "未填写"}\n`;
    text += `- 热点板块：${hotSectors || "未填写"}\n\n`;
    text += `三、全市场扫描\n`;
    text += `- 步骤1 当前前30初筛池复查：${top200Reviewed ? "已复查" : "未确认"}，保存 ${step1Screened.length} 只。\n`;
    text += `- 步骤2 放量异动线索：${volRatioReviewed ? "已复查" : "未确认"}，保存 ${step2Screened.length} 只。\n`;
    text += `- 步骤3 情绪高度：${limitUpReviewed ? "已复查" : "未确认"}，保存 ${step3Screened.length} 只。\n\n`;
    text += `四、自我诊断\n`;
    if (diagnosedHoldings.length === 0) {
      text += `- 暂无自我诊断记录。\n`;
    } else {
      diagnosedHoldings.forEach(item => {
        text += `- 【${diagnosisTypeLabel(item)}】${item.name}(${item.code})：${item.judgment}；${item.actionPlan || "无指令"}\n`;
      });
    }
    text += `\n五、纠错自省\n- `;

    let plan = `【${reportDate} 明日执行计划】\n`;
    const planItems = diagnosedHoldings.filter(item => item.actionPlan);
    if (planItems.length === 0) {
      plan += `- 没有纪律触发点时空仓等待，只做计划内强势回踩。\n`;
    } else {
      planItems.forEach(item => {
        plan += `- ${item.name}(${item.code})：${item.actionPlan}\n`;
      });
    }

    setReportSummary(text);
    setReportPlan(plan);
    logAction("📋 已同步前四步数据到纠错自省草稿");
  };

  const renderTurnoverList = (
    title: string,
    items: TurnoverChangeStock[],
    tone: "cyan" | "amber" | "emerald" | "rose"
  ) => {
    const toneClass = {
      cyan: "border-cyan-500/25 text-cyan-300",
      amber: "border-amber-500/25 text-amber-300",
      emerald: "border-emerald-500/25 text-emerald-300",
      rose: "border-rose-500/25 text-rose-300"
    }[tone];
    return (
      <div className={`border ${toneClass} bg-slate-950/40 rounded-lg p-2 min-h-[82px]`}>
        <div className="text-[10px] font-bold mb-1.5 flex items-center justify-between">
          <span>{title}</span>
          <span className="font-mono">{items.length}</span>
        </div>
        {items.length === 0 ? (
          <div className="text-[10px] text-slate-600">暂无</div>
        ) : (
          <div className="space-y-1.5">
            {items.slice(0, 5).map(item => (
              <div key={`${title}-${item.code}`} className="flex items-center justify-between gap-2 text-[10px] text-slate-400">
                <span className="min-w-0 truncate">
                  <span className="text-slate-300">{item.name || item.code}</span>
                  <span className="font-mono text-slate-500 ml-1">{item.code}</span>
                </span>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="font-mono text-slate-300 whitespace-nowrap">{turnoverRankLabel(item)}</span>
                  {title === "新进" && (
                    <>
                      <button
                        onClick={() => void handleIncludeTurnoverStock(item)}
                        className="px-2 py-0.5 bg-cyan-600 hover:bg-cyan-500 text-white border border-cyan-400/30 rounded font-semibold transition"
                      >
                        纳入
                      </button>
                      <button
                        onClick={() => handleIgnoreTurnoverStock(item)}
                        className="px-2 py-0.5 bg-slate-900 hover:bg-slate-800 text-slate-400 border border-slate-700 rounded transition"
                      >
                        忽略
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
            {items.length > 5 && <div className="text-[10px] text-slate-600">+{items.length - 5} 只</div>}
          </div>
        )}
      </div>
    );
  };

  const renderTurnoverPreviewRows = (items: TurnoverChangeStock[], kind: "new" | "dropped") => {
    if (items.length === 0) {
      return (
        <div className="rounded border border-dashed border-slate-800 bg-slate-950/30 px-3 py-2 text-[10px] text-slate-600">
          {kind === "new" ? "暂无新进前30提醒" : "暂无跌出前30提醒"}
        </div>
      );
    }

    return (
      <div className="space-y-1.5">
        {items.slice(0, 3).map(item => (
          <div key={`${kind}-${item.code}`} className="flex items-center justify-between gap-2 rounded border border-slate-800 bg-slate-950/45 px-2.5 py-2">
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-200">
                <span className="truncate">{item.name || item.code}</span>
                <span className="font-mono text-[10px] text-slate-500">{item.code}</span>
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-[10px] text-slate-500">
                <span className="font-mono">{turnoverRankLabel(item)}</span>
                <span>{formatMoneyShort(item.volume)}</span>
              </div>
            </div>
            {kind === "new" ? (
              <div className="flex shrink-0 items-center gap-1.5">
                <button
                  onClick={() => void handleIncludeTurnoverStock(item)}
                  className="inline-flex items-center gap-1 rounded bg-cyan-600 px-2.5 py-1 text-[10px] font-bold text-white hover:bg-cyan-500 transition"
                >
                  <Plus className="h-3 w-3" />
                  <span>纳入</span>
                </button>
                <button
                  onClick={() => handleIgnoreTurnoverStock(item)}
                  className="inline-flex items-center gap-1 rounded border border-slate-700 bg-slate-900 px-2 py-1 text-[10px] font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
                >
                  <XCircle className="h-3 w-3" />
                  <span>忽略</span>
                </button>
              </div>
            ) : (
              <span className="shrink-0 rounded border border-amber-500/20 bg-amber-950/20 px-2 py-1 text-[10px] font-semibold text-amber-300">
                只提醒
              </span>
            )}
          </div>
        ))}
        {items.length > 3 && (
          <div className="text-[10px] text-slate-600">另有 {items.length - 3} 只，可在下方完整明细处理</div>
        )}
      </div>
    );
  };

  const renderBuyReadyCard = (stock: Stock, dense = false) => (
    <div
      key={stock.code}
      className={`group rounded-lg border border-cyan-500/25 bg-slate-950/70 transition hover:border-cyan-400/60 hover:bg-cyan-950/10 ${
        dense ? "p-3" : "p-4"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="truncate text-sm font-black text-slate-100">{stock.name}</span>
            <span className="font-mono text-[11px] font-semibold text-slate-400">{stock.code}</span>
            <span className="rounded bg-cyan-950/70 px-1.5 py-0.5 text-[10px] font-black text-cyan-300">
              #{stock.poolRankAtGeneration || stock.rank || "-"}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-[11px]">
            <span className="text-slate-300">现价 <b className="text-sm text-slate-100">{formatPrice(stock.price)}</b></span>
            <span className="text-cyan-300">MA5 <b className="text-sm">{formatPrice(stock.ma5)}</b></span>
            <span className="rounded border border-cyan-500/30 bg-cyan-950/30 px-2 py-0.5 font-black text-cyan-200">
              偏离 {formatPercent(stock.deviation5)}
            </span>
            <span className={stock.pct >= 0 ? "font-bold text-rose-400" : "font-bold text-emerald-400"}>
              {formatPercent(stock.pct, true)}
            </span>
          </div>
        </div>
        <button
          onClick={() => openBuyModal(stock)}
          disabled={!stock.canBuy || !currentInBuyWindow || systemicRisk || stock.marketTradeAllowed === false || stock.marketRisk === true}
          className="shrink-0 rounded bg-rose-600 px-3 py-1.5 text-xs font-black text-white shadow-sm transition hover:bg-rose-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
        >
          盘中确认
        </button>
      </div>
      <CardText className="mt-2 line-clamp-1 text-[11px] font-semibold text-slate-300">
        {stock.reason || stock.reminder || "MA5偏离率0%~2.5%，等待盘中确认"}
      </CardText>
    </div>
  );

  const renderBuyReadyPreview = () => (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 shadow-sm">
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-cyan-400" />
          <h3 className="text-sm font-black text-slate-100">待买观察简表</h3>
          <span className="rounded bg-cyan-950 px-2 py-0.5 text-xs font-black text-cyan-300">{buyReadyStocks.length} 只</span>
        </div>
        <button
          type="button"
          onClick={handleQuickBuyEntry}
          className="inline-flex items-center justify-center gap-1.5 rounded border border-cyan-600/40 bg-cyan-950/40 px-3 py-1.5 text-xs font-bold text-cyan-200 transition hover:bg-cyan-900/50"
        >
          <Eye className="h-3.5 w-3.5" />
          <span>查看待买</span>
        </button>
      </div>
      {buyReadyStocks.length === 0 ? (
        <CardText as="div" className="rounded-lg border border-dashed border-slate-800 bg-slate-950/50 p-4 text-center text-xs font-semibold text-slate-500">
          暂无待买观察。刷新行情后，这里只显示进入 MA5 0%~2.5% 低吸区且通过资金/风险约束的股票
        </CardText>
      ) : (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {buyReadyPreviewStocks.map(stock => renderBuyReadyCard(stock, true))}
          {buyReadyMoreCount > 0 && (
            <button
              type="button"
              onClick={handleQuickBuyEntry}
              className="rounded-lg border border-dashed border-cyan-700/40 bg-cyan-950/10 p-3 text-left text-xs font-bold text-cyan-300 transition hover:bg-cyan-950/25"
            >
              还有 {buyReadyMoreCount} 只待买观察，点击进入完整列表
            </button>
          )}
        </div>
      )}
    </div>
  );

  const renderPositionDashboardCard = (position: Position, index: number) => {
    const plan = buildPositionSellPlan(position, tradingRules);
    const hasMa5 = Number.isFinite(position.ma5) && position.ma5 > 0;
    const canSellToday = Math.max(0, Math.floor(Number(position.availableQuantity) || 0)) > 0;
    const pnlClass = position.floatingPnL >= 0 ? "text-rose-400" : "text-emerald-400";
    const cardToneClass = plan.tone === "danger"
      ? "border-rose-900/50 border-l-rose-500/80 bg-slate-900/70"
      : plan.tone === "warning"
        ? "border-amber-900/50 border-l-amber-500/80 bg-slate-900/70"
        : plan.tone === "neutral"
          ? "border-slate-800 border-l-slate-600 bg-slate-900/65"
          : "border-emerald-900/40 border-l-emerald-500/70 bg-slate-900/65";
    const actionClass = plan.tone === "danger"
      ? "border-slate-800/70 border-l-rose-500/80 bg-slate-950/25"
      : plan.tone === "warning"
        ? "border-slate-800/70 border-l-amber-500/80 bg-slate-950/25"
        : "border-slate-800/70 border-l-emerald-500/70 bg-slate-950/20";
    const compactStats = [
      {
        label: "现价",
        value: formatPrice(position.currentPrice),
        valueClass: "text-slate-100"
      },
      {
        label: "MA5 / 偏离",
        value: hasMa5 ? `${formatPrice(position.ma5)} / ${formatPercent(position.deviation5)}` : "待补K线",
        valueClass: position.deviation5 < 0 ? "text-emerald-400" : "text-cyan-300"
      },
      {
        label: "浮盈亏",
        value: `${signedCurrency(position.floatingPnL)} (${formatPercent(position.floatingPnLPct, true)})`,
        valueClass: pnlClass
      },
      {
        label: "可卖 / 跌破",
        value: `${position.availableQuantity}股 / ${Math.max(0, Math.floor(Number(position.belowMa5Days) || 0))}天`,
        valueClass: "text-slate-100"
      }
    ];

    return (
      <div key={position.code} className={`rounded-lg border border-l-2 p-2.5 sm:p-3 ${cardToneClass}`}>
        <div className="grid grid-cols-1 gap-2 xl:grid-cols-[250px_minmax(360px,460px)_minmax(380px,1fr)] xl:items-center xl:gap-3">
          <div className="flex min-w-0 items-center gap-3 xl:border-r xl:border-slate-800/50 xl:pr-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-slate-700 bg-slate-950/60 text-[10px] font-black text-slate-300">
              {index + 1}
            </span>
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${plan.dotClass}`}></span>
            <div className="min-w-0">
              <div className="truncate text-sm font-black text-slate-100">{position.name}</div>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[11px] font-semibold text-slate-400">
                <span>{position.code}</span>
                <span>{holdingTimeLabel(position)}</span>
              </div>
            </div>
          </div>

          <div className="grid min-w-0 grid-cols-2 gap-1.5">
            {compactStats.map(stat => (
              <div key={stat.label} className="flex min-h-[52px] min-w-0 flex-col justify-center rounded border border-slate-800/55 bg-slate-950/25 px-2.5 py-1.5">
                <span className="block text-[10px] font-bold text-slate-500">{stat.label}</span>
                <span className={`mt-0.5 break-words font-mono text-[12px] font-black leading-tight ${stat.valueClass}`}>
                  {stat.value}
                </span>
              </div>
            ))}
          </div>

          <div className={`rounded border border-l-2 px-3 py-2 xl:ml-10 ${actionClass}`}>
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <span className={`rounded px-2 py-0.5 text-[10px] font-black ${plan.badgeClass}`}>{plan.statusLabel}</span>
              <button
                onClick={() => openSellModal(position)}
                disabled={!canSellToday}
                className={`shrink-0 rounded px-2.5 py-1 text-[11px] font-black text-white transition ${
                  canSellToday ? "bg-emerald-600 hover:bg-emerald-500" : "bg-slate-800 text-slate-500 cursor-not-allowed"
                }`}
              >
                {plan.buttonLabel}
              </button>
            </div>
            <div className="text-sm font-black leading-tight text-slate-50">{plan.title}</div>
            <CardText className="mt-1 line-clamp-2 text-[11px] font-semibold leading-snug text-slate-300">{plan.primaryAction}</CardText>
          </div>
        </div>
      </div>
    );
  };

  const renderScreenedStockRows = (
    stocks: ReviewScreenedStock[],
    sourceStep: "step1" | "step2" | "step3",
    sourceTitle: string
  ) => {
    if (isScreening) {
      return (
        <div className="py-8 text-center space-y-2">
          <div className="animate-spin rounded-full h-4 w-4 border-2 border-cyan-500 border-t-transparent mx-auto"></div>
          <CardText className="text-[10px] text-slate-500">正在刷新扫描结果...</CardText>
        </div>
      );
    }

    if (stocks.length === 0) {
      return (
        <CardText as="div" className="p-5 text-center text-slate-600 text-[10px] italic bg-slate-950/70 border border-slate-850 rounded">
          暂无扫描结果，请先刷新当前池或重新运行三步扫描。
        </CardText>
      );
    }

    return (
      <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
        {stocks.map(stock => {
          const alreadyAdded = diagnosedHoldings.some(item => item.code === stock.code);
          return (
            <div key={`${sourceStep}-${stock.code}`} className="bg-slate-900/80 p-2.5 rounded border border-slate-850 hover:border-cyan-900/40 transition space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[11px] font-bold text-slate-200 font-mono truncate">{stock.name}</span>
                    <span className="text-[9px] text-slate-500 font-mono">{stock.code}</span>
                    {stock.rank !== undefined && (
                      <span className="text-[9px] text-slate-500 font-mono">#{stock.rank}</span>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[9px] text-slate-500">
                    <span>成交 {(stock.volume / 100000000).toFixed(1)}亿</span>
                    {stock.volRatioSource && <span>{stock.volRatioSource}</span>}
                    {stock.conceptSource && <span>{stock.conceptSource}</span>}
                    {stock.limitHeight && <span className="text-amber-400">{stock.limitHeight}</span>}
                  </div>
                </div>
                <span className={`text-[10px] font-mono font-bold shrink-0 ${stock.pct >= 0 ? "text-red-400" : "text-emerald-400"}`}>
                  {stock.pct >= 0 ? `+${stock.pct.toFixed(2)}%` : `${stock.pct.toFixed(2)}%`}
                </span>
              </div>

              <div className="flex items-center justify-between gap-2 border-t border-slate-950 pt-1.5">
                <span className="text-[9px] text-cyan-400 font-extrabold">
                  {stock.stars} {stock.confidence ?? "-"}% 信心
                </span>
                <button
                  type="button"
                  onClick={() => addToSelfDiagnosis(stock, sourceStep, sourceTitle)}
                  className={`px-2 py-1 rounded text-[9px] font-bold border transition flex items-center gap-1 ${
                    alreadyAdded
                      ? "bg-slate-950 text-slate-500 border-slate-800"
                      : "bg-cyan-950/50 hover:bg-cyan-900/60 text-cyan-300 border-cyan-700/40"
                  }`}
                >
                  <Plus className="h-3 w-3" />
                  <span>{alreadyAdded ? "已在诊断" : "加入自我诊断"}</span>
                </button>
              </div>
              {stock.reason && <CardText className="text-[9px] text-slate-400 leading-normal">{stock.reason}</CardText>}
            </div>
          );
        })}
      </div>
    );
  };

  const renderScreenStepCard = (
    stepNo: string,
    title: string,
    description: string,
    reviewed: boolean,
    onReviewedChange: (value: boolean) => void,
    stocks: ReviewScreenedStock[],
    sourceStep: "step1" | "step2" | "step3"
  ) => (
    <div className={`p-4 rounded-lg border transition flex flex-col justify-between ${reviewed ? "bg-cyan-950/15 border-cyan-800/40" : "bg-slate-950 border-slate-850"}`}>
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <span className="text-[10px] bg-slate-900 text-slate-400 px-2 py-0.5 rounded font-bold font-mono">步骤 {stepNo}</span>
          <input
            type="checkbox"
            checked={reviewed}
            onChange={(e) => onReviewedChange(e.target.checked)}
            className="rounded text-cyan-600 focus:ring-0 focus:ring-offset-0 bg-slate-900 border-slate-800 cursor-pointer"
          />
        </div>
        <div>
          <h4 className="text-xs font-black text-slate-200 mt-1">{title}</h4>
          <CardText className="text-[11px] text-slate-400 mt-1 leading-relaxed">{description}</CardText>
        </div>
        <div className="border-t border-slate-900 pt-3 space-y-2.5">
          <div className="flex items-center justify-between gap-2">
            <label className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block">扫描结果</label>
            <span className="text-[9px] text-slate-500 font-mono">{stocks.length} 只</span>
          </div>
          {renderScreenedStockRows(stocks, sourceStep, title)}
        </div>
      </div>
      <div className="mt-4 pt-2 border-t border-slate-900/60 flex items-center justify-between">
        <span className="text-[10px] text-cyan-400 block font-bold">{reviewed ? "✓ 已确认复查" : "⏳ 待确认"}</span>
      </div>
    </div>
  );

  const renderPositionSellCard = (position: Position, index: number) => {
    const plan = buildPositionSellPlan(position, tradingRules);
    const priceClass = position.floatingPnL >= 0 ? "text-rose-400" : "text-emerald-400";
    const hasMa5 = Number.isFinite(position.ma5) && position.ma5 > 0;
    const canSellToday = Math.max(0, Math.floor(Number(position.availableQuantity) || 0)) > 0;
    const tradeLink = position.tradeLink;
    const maxLossAmount = Number(position.maxLossAmount) > 0 ? Number(position.maxLossAmount) : accountState.initialCash * tradingRules.singleTradeRisk.maxPct;
    const currentLossAmount = Number(position.currentLossAmount) || Math.max(0, (position.avgCost - position.currentPrice) * position.quantity);
    const maxLossLine = position.quantity > 0 ? position.avgCost - (maxLossAmount / position.quantity) : 0;
    const takeProfitWatchLine = hasMa5 ? position.ma5 * (1 + tradingRules.takeProfit.watchDeviationPct / 100) : 0;
    const takeProfitPriorityLine = hasMa5 ? position.ma5 * (1 + tradingRules.takeProfit.priorityDeviationPct / 100) : 0;
    const ma5DistanceText = hasMa5 ? lineDistanceLabel(position.currentPrice, position.ma5, "floor") : "等待MA5";
    const sellLineRows = [
      {
        label: "止盈观察线",
        formula: "MA5 +5%",
        value: takeProfitWatchLine,
        text: hasMa5 ? lineDistanceLabel(position.currentPrice, takeProfitWatchLine, "target") : "等待MA5",
        active: plan.triggerKey === "take-profit",
        activeClass: "border-amber-800/60 border-l-amber-400/80 bg-slate-950/30",
        labelClass: "text-amber-300"
      },
      {
        label: "优先止盈线",
        formula: "MA5 +7%",
        value: takeProfitPriorityLine,
        text: hasMa5 ? lineDistanceLabel(position.currentPrice, takeProfitPriorityLine, "target") : "等待MA5",
        active: plan.triggerKey === "take-profit" && position.deviation5 > tradingRules.takeProfit.priorityDeviationPct,
        activeClass: "border-amber-800/60 border-l-amber-400/80 bg-slate-950/30",
        labelClass: "text-amber-300"
      },
      {
        label: "5日线风控线",
        formula: "MA5",
        value: hasMa5 ? position.ma5 : 0,
        text: ma5DistanceText,
        active: plan.triggerKey === "ma5-risk" || plan.triggerKey === "clear",
        activeClass: "border-rose-800/60 border-l-rose-400/80 bg-slate-950/30",
        labelClass: "text-rose-300"
      },
      {
        label: "单笔亏损线",
        formula: "本金 -2%",
        value: maxLossLine,
        text: maxLossLine > 0 ? `当前浮亏 ${currentLossAmount.toFixed(2)} / ${maxLossAmount.toFixed(2)} 元` : "等待成本",
        active: maxLossAmount > 0 && currentLossAmount >= maxLossAmount,
        activeClass: "border-red-800/60 border-l-red-400/80 bg-slate-950/30",
        labelClass: "text-red-300"
      }
    ];
    const sellLayers = [
      {
        key: "next-day",
        label: "1. 次日强弱",
        title: "10点前不强就走",
        text: plan.nextMorningRule,
        active: plan.triggerKey === "next-day",
        className: "border-cyan-800/55 border-l-cyan-400/80 bg-slate-950/30 text-cyan-200"
      },
      {
        key: "take-profit",
        label: "2. 止盈",
        title: "远离5日线锁利润",
        text: plan.takeProfitRule,
        active: plan.triggerKey === "take-profit",
        className: "border-amber-800/55 border-l-amber-400/80 bg-slate-950/30 text-amber-200"
      },
      {
        key: "risk",
        label: "3. 止损",
        title: "跌破5日线控风险",
        text: plan.ma5RiskRule,
        active: plan.triggerKey === "ma5-risk" || plan.triggerKey === "clear",
        className: "border-rose-800/55 border-l-rose-400/80 bg-slate-950/30 text-rose-200"
      }
    ];
    const decisionClass = plan.tone === "danger"
      ? "border-rose-800/65 border-l-rose-500/90 bg-slate-950/30"
      : plan.tone === "warning"
        ? "border-amber-800/65 border-l-amber-500/90 bg-slate-950/30"
        : plan.tone === "neutral"
          ? "border-slate-800/75 border-l-slate-600 bg-slate-950/25"
          : "border-emerald-800/55 border-l-emerald-500/75 bg-slate-950/25";
    const coreStats = [
      {
        label: "实时现价",
        value: formatPrice(position.currentPrice),
        valueClass: "text-slate-100"
      },
      {
        label: "持仓均价",
        value: formatPrice(position.avgCost),
        valueClass: "text-slate-100"
      },
      {
        label: "MA5 / 偏离",
        value: hasMa5 ? `${formatPrice(position.ma5)} / ${signedPercent(position.deviation5)}` : "待补K线",
        valueClass: position.deviation5 < 0 ? "text-emerald-400" : "text-rose-400"
      },
      {
        label: "浮动盈亏",
        value: `${signedCurrency(position.floatingPnL)} (${signedPercent(position.floatingPnLPct)})`,
        valueClass: priceClass
      },
      {
        label: "持仓数量",
        value: `${position.quantity} 股`,
        valueClass: "text-slate-100"
      },
      {
        label: "可卖数量",
        value: `${position.availableQuantity} 股`,
        valueClass: canSellToday ? "text-cyan-300" : "text-slate-500"
      }
    ];

    return (
      <div key={position.code} className={`rounded-lg border p-3 ${plan.cardClass}`}>
        <div className="mb-3 flex flex-col gap-2 border-b border-slate-800/50 pb-2.5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-slate-700 bg-slate-950/60 text-[10px] font-black text-slate-300">
              {index + 1}
            </span>
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${plan.dotClass}`}></span>
            <div className="min-w-0">
              <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
                <span className="truncate text-sm font-black text-slate-100">{position.name}</span>
                <span className="font-mono text-xs font-bold text-slate-400">{position.code}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 font-mono text-[10px] text-slate-400">
                <span>{position.buyDate || "买入日期待补"}</span>
                <span>{holdingTimeLabel(position)}</span>
                <span>可卖 {position.availableQuantity} 股</span>
              </div>
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
            <span className="text-[10px] font-mono text-slate-500">按卖点优先级排序</span>
            <span className={`rounded px-2.5 py-1 text-[10px] font-extrabold tracking-widest ${plan.badgeClass}`}>
              {plan.statusLabel}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
          <div className={`rounded-lg border border-l-2 p-3 ${decisionClass}`}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
              <div className="min-w-0">
                <div className="mb-1.5 flex flex-wrap items-center gap-2">
                  <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">自动卖点判定</span>
                  <span className="font-mono text-[10px] font-semibold text-slate-500">
                    跌破MA5 {Math.max(0, Math.floor(Number(position.belowMa5Days) || 0))} 天
                  </span>
                </div>
                <span className={`rounded px-2.5 py-1 text-[10px] font-black ${plan.badgeClass}`}>{plan.statusLabel}</span>
                <h4 className="mt-2 text-lg font-black leading-tight text-slate-50">{plan.title}</h4>
                <CardText className="mt-1.5 text-xs font-semibold leading-snug text-slate-200">
                  {plan.primaryAction}
                </CardText>
                <CardText as="span" className="mt-2 block text-[10px] font-semibold leading-snug text-slate-500">
                  {position.advice || plan.sizingRule}
                </CardText>
              </div>
              <button
                onClick={() => openSellModal(position)}
                disabled={!canSellToday}
                className={`min-h-[34px] shrink-0 rounded px-4 py-2 text-xs font-black text-white shadow transition lg:min-w-[96px] ${
                  canSellToday ? "bg-emerald-600 hover:bg-emerald-500" : "bg-slate-800 text-slate-500 cursor-not-allowed"
                }`}
              >
                {plan.buttonLabel}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-1.5">
            {coreStats.map(stat => (
              <div key={stat.label} className="flex min-h-[58px] min-w-0 flex-col justify-center rounded border border-slate-800/50 bg-slate-950/25 px-2.5 py-1.5">
                <span className="text-[10px] font-bold text-slate-500">{stat.label}</span>
                <span className={`mt-0.5 break-words font-mono text-[12px] font-black leading-tight ${stat.valueClass}`}>
                  {stat.value}
                </span>
              </div>
            ))}
          </div>
        </div>

        {tradeLink && (
          <div className="mt-2 rounded border border-slate-800/50 bg-slate-950/20 p-2.5">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">交易联动</span>
                <span className={`w-fit rounded px-2 py-0.5 text-[10px] font-bold ${
                  tradeLink.hasComplianceIssue ? "bg-amber-950 text-amber-300" : "bg-emerald-950 text-emerald-300"
                }`}>
                  {tradeLink.hasComplianceIssue ? "有审计标签" : "流水合规"}
                </span>
              </div>
              <div className="grid grid-cols-1 gap-2 text-[10px] text-slate-400 md:grid-cols-3 lg:min-w-[640px]">
                <CardText as="span">最近买入：{tradeLink.lastBuy ? `${tradeLink.lastBuy.date || ""} ${formatPrice(Number(tradeLink.lastBuy.price) || 0)}` : "无"}</CardText>
                <CardText as="span">最近卖出：{tradeLink.lastSell ? `${tradeLink.lastSell.date || ""} ${formatPrice(Number(tradeLink.lastSell.price) || 0)}` : "无"}</CardText>
                <CardText as="span">今日流水：{tradeLink.todayTrades?.length || 0} 笔</CardText>
              </div>
            </div>
            {Boolean(tradeLink.complianceTags?.length) && (
              <div className="mt-2 flex flex-wrap gap-1">
                {tradeLink.complianceTags?.map(tag => (
                  <span key={tag} className="rounded bg-rose-950/40 px-1.5 py-0.5 text-[9px] text-rose-300">
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="mt-3 space-y-2">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">止盈 / 止损线</span>
            <span className="font-mono text-[10px] text-slate-500">
              当前价 {formatPrice(position.currentPrice)} · 单笔亏损上限 {maxLossAmount.toFixed(2)} 元
            </span>
          </div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
            {sellLineRows.map(line => (
              <div
                key={line.label}
                className={`min-h-[66px] rounded border p-2.5 ${line.active ? `${line.activeClass} border-l-2` : "border-slate-800/50 bg-slate-950/25"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-[11px] font-bold ${line.labelClass}`}>{line.label}</span>
                  <span className="font-mono text-[10px] text-slate-500">{line.formula}</span>
                </div>
                <div className="mt-1 flex items-end justify-between gap-2">
                  <span className="font-mono text-sm font-black text-slate-100">{formatPrice(line.value)}</span>
                  <span className="text-right font-mono text-[10px] text-slate-400">{line.text}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-2 text-[11px] leading-snug lg:grid-cols-3">
          {sellLayers.map(layer => (
            <div
              key={layer.key}
              className={`rounded border border-l-2 p-2.5 ${layer.active ? layer.className : "border-slate-800/40 border-l-slate-800 bg-slate-950/20 text-slate-400"}`}
            >
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="font-bold">{layer.label}</span>
                {layer.active && <span className="text-[9px] font-black uppercase tracking-wider">当前触发</span>}
              </div>
              <span className="mb-1 block font-bold text-slate-200">{layer.title}</span>
              <CardText as="span" className={layer.active ? "text-slate-200" : "text-slate-400"}>{layer.text}</CardText>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const handleQuickBuyEntry = () => {
    setActiveTab("watchlist");
    setWatchlistGroup("待买");
    const firstBuyReady = stocksForGroup(watchlist, "待买")[0];
    if (firstBuyReady) setSelectedStock(firstBuyReady);
    logAction("💡 已切到待买列表；请选中股票，并在右侧详情卡进行盘中手动确认");
  };

  const handleQuickSellEntry = () => {
    setActiveTab("intraday");
    logAction("💡 已切到盘中持仓监控；请在持仓卡片中点击「记录卖出」归档");
  };

  return (
    <div className="h-screen overflow-hidden bg-slate-950 text-slate-200 flex flex-col font-sans selection:bg-blue-500/20 selection:text-blue-200">
      
      {/* 顶部系统状态 Bar */}
      <header className="shrink-0 bg-slate-900 border-b border-slate-800 py-3 px-4 grid grid-cols-1 lg:grid-cols-[minmax(260px,1fr)_auto_minmax(140px,1fr)] items-center sticky top-0 z-40 shadow-sm text-white gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] border border-white/10 bg-gradient-to-br from-orange-500 via-red-500 to-rose-600 shadow-lg shadow-red-950/35">
            <TrendingUp className="h-[22px] w-[22px] text-white" strokeWidth={3} />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-[16px] font-black leading-tight tracking-normal text-white">强势回踩短线交易纪律系统</h1>
            <div className="mt-1 flex min-w-0 items-center gap-1.5">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-orange-400 shadow-[0_0_0_3px_rgba(251,146,60,0.14)]"></span>
              <CardText className="truncate text-[10px] font-semibold leading-none text-slate-400">主板前排股票 5日线低吸回踩纪律工作台</CardText>
            </div>
          </div>
        </div>

        {/* 同花顺风格账户资产栏 */}
        <div className="justify-self-center flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-xs font-mono py-1.5 px-4 bg-slate-950/70 border border-slate-800 rounded-lg">
          <div className="flex items-center space-x-1.5 border-r border-slate-800 pr-4 last:border-0">
            <span className="text-slate-400 text-[12px]">{currentMode === "real" ? "实盘总资产:" : "模拟总资产:"}</span>
            <span className="font-bold text-slate-100 text-[14px]">{accountState.totalAssets.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          </div>
          <div className="flex items-center space-x-1.5 border-r border-slate-800 pr-4 last:border-0">
            <span className="text-slate-400 text-[12px]">总市值:</span>
            <span className="font-bold text-amber-500 text-[14px]">{accountState.holdingValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          </div>
          <div className="flex items-center space-x-1.5 border-r border-slate-800 pr-4 last:border-0">
            <span className="text-slate-400 text-[12px]">可用资金:</span>
            <span className="font-bold text-slate-100 text-[14px]">{accountState.availableCash.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          </div>
          <div className="flex items-center space-x-1.5 border-r border-slate-800 pr-4 last:border-0">
            <span className="text-slate-400 text-[12px]">总盈亏:</span>
            <span className={`font-bold text-[14px] ${accountState.totalPnL >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
              {signedCurrency(accountState.totalPnL)}
            </span>
          </div>
          <div className="flex items-center space-x-1.5 border-r border-slate-800 pr-4 last:border-0">
            <span className="text-slate-400 text-[12px]" title={accountState.asOfDate ? `结算日 ${accountState.asOfDate}` : undefined}>当日盈亏:</span>
            <span className={`font-bold text-[14px] ${todayTotalPnLForAccount >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
              {signedCurrency(todayTotalPnLForAccount)}
            </span>
          </div>
          <div className="flex items-center space-x-1.5 last:border-0">
            <span className="text-slate-400 text-[12px]">总收益率:</span>
            <span className={`font-bold text-[14px] ${accountState.totalPnL >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
              {accountState.totalPnL >= 0 ? "+" : ""}{accountState.totalReturnPct.toFixed(2)}%
            </span>
          </div>
        </div>

        {/* A股开盘时间时钟 */}
        <div className="justify-self-end flex flex-col items-end gap-1.5 font-mono">
          <div className="flex items-center gap-1.5 rounded-[16px] border border-slate-700/80 bg-slate-950/80 px-2.5 py-1.5 shadow-inner shadow-black/30">
            <Clock3 className="h-3.5 w-3.5 shrink-0 text-amber-400" strokeWidth={2.25} />
            <span className="tabular-nums text-[16px] font-black leading-none tracking-normal text-slate-100">
              {currentTimeLabel}
            </span>
          </div>
          <div className={`flex items-center gap-1 pr-1 text-[12px] font-bold ${marketIsTrading ? "text-rose-400" : "text-slate-500"}`}>
            <span className={`h-2 w-2 rounded-full ${marketIsTrading ? "bg-rose-500 animate-pulse" : "bg-slate-600"}`}></span>
            <span>{marketIsTrading ? "A股交易时间中" : "A股已休市"}</span>
          </div>
        </div>
      </header>

      {/* 核心工作区分割 */}
      <div className="flex-1 min-h-0 flex flex-col md:flex-row overflow-hidden">
        
        {/* 左侧菜单导航 */}
        <nav className="w-full md:w-72 min-h-0 bg-slate-900 border-b md:border-b-0 md:border-r border-slate-800 p-3 flex flex-row md:flex-col justify-around md:justify-start space-y-0 md:space-y-1.5 shrink-0 overflow-x-auto md:overflow-x-hidden md:overflow-y-hidden">
          <div className="flex items-center space-x-1 bg-slate-950 p-1 rounded-lg border border-slate-800 shrink-0 md:mb-2 md:w-full">
            <button
              onClick={() => handleToggleMode("simulation")}
              className={`flex-1 px-3 py-1.5 rounded text-xs font-semibold transition-all ${
                currentMode === "simulation"
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              模拟训练
            </button>
            <button
              onClick={() => handleToggleMode("real")}
              className={`flex-1 px-3 py-1.5 rounded text-xs font-semibold transition-all ${
                currentMode === "real"
                  ? "bg-rose-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              实盘记录
            </button>
          </div>
          <div className="hidden md:block px-3 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">纪律罗盘</div>
          
          <button
            onClick={() => setActiveTab("dashboard")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "dashboard" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <Activity className="h-4 w-4" />
            <span>今日看板</span>
          </button>

          <button
            onClick={() => setActiveTab("watchlist")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "watchlist" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <Briefcase className="h-4 w-4" />
            <span>股票池 & 分组</span>
          </button>

          <button
            onClick={() => setActiveTab("intraday")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "intraday" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <TrendingUp className="h-4 w-4" />
            <span>盘中低吸监控</span>
          </button>

                    <button
            onClick={() => setActiveTab("trades")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "trades" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <History className="h-4 w-4" />
            <span>交易记录审计</span>
          </button>

          <button
            onClick={() => setActiveTab("review")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "review" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <FileText className="h-4 w-4" />
            <span>复盘笔记归档</span>
          </button>

          <button
            onClick={() => setActiveTab("settings")}
            className={`flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition ${activeTab === "settings" ? "bg-blue-600 text-white shadow" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}
          >
            <Settings className="h-4 w-4" />
            <span>交易系统配置</span>
          </button>

          {/* 实时运行操作日志 */}
          <div className="hidden md:flex flex-col flex-1 min-h-0 mt-6 overflow-hidden">
            <div className="flex min-h-0 flex-1 flex-col rounded-lg border border-slate-800/55 bg-slate-950/20 px-3 py-3">
              <div className="flex items-center justify-between gap-2.5 border-b border-slate-800/55 pb-2.5">
                <span className="text-[12px] font-black tracking-wide text-slate-300">事件流日志</span>
                <button
                  type="button"
                  onClick={() => setActionLog([])}
                  className="rounded px-1 py-0.5 text-[10px] font-semibold text-slate-500 transition hover:text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                >
                  重置
                </button>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto pr-1 font-mono">
                {actionLog.length === 0 ? (
                  <div className="flex h-full items-center justify-center text-[10px] italic text-slate-600">暂无系统事件</div>
                ) : (
                  actionLog.map((log, i) => {
                    const entry = formatActivityLogEntry(log);
                    return (
                      <div
                        key={`${log}-${i}`}
                        className={`grid grid-cols-[4.25rem_1rem_minmax(0,1fr)] gap-x-1.5 border-b py-2.5 text-[10px] leading-relaxed last:border-0 ${entry.rowClass}`}
                      >
                        <span className="pt-0.5 text-[10px] font-semibold tracking-wide text-slate-500">
                          {entry.time}
                        </span>
                        <span className={`pt-0.5 text-[11px] leading-none ${entry.iconClass}`} aria-hidden="true">
                          {entry.icon}
                        </span>
                        <span className={`min-w-0 whitespace-normal break-words text-[10px] leading-[1.5] ${entry.textClass}`}>
                          {entry.text}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </nav>

        {/* 右侧主视口 */}
        <main className="flex-1 min-h-0 min-w-0 bg-slate-950 p-4 md:p-6 overflow-y-auto overscroll-contain">
          {loading && (
            <div className="fixed top-12 right-6 bg-blue-600 border border-blue-500 text-white text-[10px] font-mono py-1 px-3.5 rounded shadow-lg flex items-center space-x-2 animate-bounce z-50">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-white animate-ping"></span>
              <span>同步中...</span>
            </div>
          )}

          {/* TAB 1: 今日看板 */}
          {activeTab === "dashboard" && (
            <div className="space-y-6">
              
              {/* 热力引导语 */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4 items-center">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="h-4 w-4 text-amber-400 fill-amber-400" />
                    <h3 className="text-sm font-semibold text-slate-200">欢迎使用强势回踩短线交易纪律系统</h3>
                  </div>
                  <CardText className="text-xs text-slate-400">本系统围绕<b>沪深主板前排股5日均线（0%~2.5%）回踩低吸</b>交易纪律，约束盘前选股，强化交易存证，阻断乱买冲动。</CardText>
                </div>
                <div className="w-full lg:w-[420px] rounded-lg border border-slate-800 bg-slate-950/45 px-3 py-3">
                  <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-cyan-300">
                        <Briefcase className="h-3.5 w-3.5 shrink-0" />
                        <span>盘前第一步</span>
                      </div>
                      <CardText className="text-[11px] text-slate-400 leading-normal">
                        {hasTodayPool
                          ? `今日初筛池 ${initialPoolCount} 只，${poolMeta?.isPoolLocked ? "已锁池" : "未锁池"}`
                          : initialPoolCount > 0
                            ? "当前池不是今日批次，开盘前先重建今日名单"
                            : "先拉取主板成交额前30，锁定今日基础名单"}
                      </CardText>
                    </div>
                    {hasTodayPool ? (
                      <button
                        type="button"
                        onClick={() => {
                          setActiveTab("watchlist");
                          setWatchlistGroup("初筛");
                        }}
                        className="shrink-0 px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded text-xs font-semibold shadow-sm flex items-center justify-center gap-1.5 transition"
                      >
                        <Briefcase className="h-3.5 w-3.5" />
                        <span>查看股票池</span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={handleRebuildStockPool}
                        disabled={loading}
                        className="shrink-0 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded text-xs font-semibold shadow-sm flex items-center justify-center gap-1.5 transition"
                      >
                        <Briefcase className="h-3.5 w-3.5" />
                        <span>{loading ? "构建中..." : "构建今日初筛池"}</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* 🚦 股市状态联动交易纪律指南 */}
              {(() => {
                const instr = marketInstructions;
                return (
                  <div className={`border p-4 rounded-xl shadow-sm ${instr.bg} space-y-3`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="flex h-2.5 w-2.5 relative">
                          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
                        </span>
                        <h4 className="text-xs font-bold uppercase tracking-wider">
                          {instr.phase}
                        </h4>
                      </div>
                      <span className="text-[10px] bg-slate-950/10 px-2.5 py-0.5 rounded-full font-bold">
                        {instr.action}
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      <h5 className="text-xs font-bold">全局时间提醒</h5>
                      <div className="text-xs space-y-1 pl-1 leading-relaxed">
                        {instr.guidelines.map((g, idx) => (
                          <CardText key={idx} className="font-medium">{g}</CardText>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* 大统计面板 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
                  <span className="text-xs text-slate-300 font-black uppercase block tracking-wider">主板初筛</span>
                  <div className="flex items-baseline space-x-2 mt-1">
                    <span className="text-3xl font-black text-slate-100">{initialPoolCount}</span>
                    <span className="text-xs text-slate-300 font-bold">基础候选</span>
                  </div>
                  <CardText className="text-[11px] text-slate-400 mt-2 font-semibold">成交额前30，已排除ST/创业/科创/北交等</CardText>
                </div>
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm">
                  <span className="text-xs text-slate-300 font-black uppercase block tracking-wider">观察</span>
                  <div className="flex items-baseline space-x-2 mt-1">
                    <span className="text-3xl font-black text-slate-100">{observationCount}</span>
                    <span className="text-xs text-slate-300 font-bold">等待回踩</span>
                  </div>
                  <CardText className="text-[11px] text-slate-400 mt-2 font-semibold">含待买观察、继续观察、偏高不追、远离不追</CardText>
                </div>
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm border-l-cyan-500 border-l-4">
                  <span className="text-xs text-cyan-300 font-black uppercase block tracking-wider">待买观察</span>
                  <div className="flex items-baseline space-x-2 mt-1">
                    <span className="text-3xl font-black text-cyan-300">{pendingBuyCount}</span>
                    <span className="text-xs text-cyan-300 font-bold">重点盯</span>
                  </div>
                  <CardText className="text-[11px] text-slate-300 mt-2 font-semibold">大阳启动后回踩MA5 0%~2.5%，未跌破且通过资金/风险约束</CardText>
                </div>
              </div>

              {renderBuyReadyPreview()}

              {/* 持仓卖点与交易铁律操作指南卡 */}
              <div className="space-y-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center space-x-2">
                    <ShieldAlert className="h-4 w-4 text-cyan-400" />
                    <h3 className="text-sm font-black text-slate-100">
                      当前持仓精简监控
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={handleQuickSellEntry}
                    className="inline-flex w-fit items-center gap-1.5 rounded border border-emerald-700/50 bg-emerald-950/30 px-3 py-1.5 text-xs font-bold text-emerald-300 transition hover:bg-emerald-900/40"
                  >
                    <Briefcase className="h-3.5 w-3.5" />
                    <span>查看完整持仓卡</span>
                  </button>
                </div>

                {positions.length === 0 ? (
                  <CardText as="div" className="bg-slate-900/40 border border-slate-800 rounded-lg p-4 text-center text-xs font-semibold text-slate-500">
                    当前账户暂无持仓。买入流水录入后，这里会按次日强度、远离MA5止盈、跌破MA5风控三层规则生成卖点计划。
                  </CardText>
                ) : (
                  <div className="grid grid-cols-1 gap-3">
                    {sortedPositions.map((p, idx) => renderPositionDashboardCard(p, idx))}
                  </div>
                )}
              </div>

              {isPortfolioRiskWindow && positions.length > 0 && (
                <div className="border p-4 rounded-xl shadow-sm bg-rose-950/40 border-rose-900 text-rose-100 animate-pulse space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div className="flex items-center space-x-2">
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75 animate-ping"></span>
                        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-rose-500"></span>
                      </span>
                      <h4 className="text-xs font-black uppercase tracking-wider">尾盘持仓风险卡</h4>
                    </div>
                    <span className="w-fit rounded bg-rose-950 border border-rose-700/60 px-2.5 py-0.5 text-[10px] font-black text-rose-200">
                      清仓/风控 {urgentPositionCount} 只
                    </span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px] leading-relaxed">
                    <CardText as="div" className="rounded border border-rose-800/50 bg-slate-950/30 p-2.5 text-rose-100">
                      先处理上方持仓卡里标记为“清仓点”和“风控点”的股票。
                    </CardText>
                    <CardText as="div" className="rounded border border-rose-800/50 bg-slate-950/30 p-2.5 text-rose-100">
                      14:50 仍跌破 MA5：100股按全卖或继续持有二选一，200股以上优先减仓。
                    </CardText>
                    <CardText as="div" className="rounded border border-rose-800/50 bg-slate-950/30 p-2.5 text-rose-100">
                      连续3天站不回 MA5 的票，不再延迟判断，按纪律清仓。
                    </CardText>
                  </div>
                </div>
              )}

              {/* ACTIVE PLAYBOOK | 强势回踩交易铁律控制台 */}
              <div className="space-y-4">
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
                  <div className="border-b border-slate-800 pb-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div className="space-y-1">
                      <span className="text-[10px] text-cyan-400 font-extrabold uppercase tracking-widest block">ACTIVE PLAYBOOK</span>
                      <h3 className="text-sm font-black text-slate-100 flex items-center space-x-2">
                        <span>主板成交额前排强势股的 5 日线回踩低吸模式</span>
                      </h3>
                    </div>
                    <CardText className="text-[11px] text-slate-400 font-medium">只在强势确认后等待 MA5 附近回踩；进入待买也必须经过资金、时间和风控校验。</CardText>
                  </div>

                  {/* 6格铁律矩阵 */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {/* 1. 股票范围 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <Briefcase className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">股票范围</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">沪深主板 A 股</h4>
                        <CardText className="text-[11px] text-slate-400 leading-normal">
                          代码以 600/601/603/605/000/001/002 开头。<b>排除 ST、创业板、科创板、北交所及京东方A等笨重股</b>，坚决只做主板前排最强流动性大阳股！
                        </CardText>
                      </div>
                    </div>

                    {/* 2. 强势确认 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <TrendingUp className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">强势确认</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">近 10-20 日有 ≥5% 阳线</h4>
                        <CardText className="text-[11px] text-slate-400 leading-normal">
                          近 20 个交易日内必须出现过单日涨幅大于或等于 <b>5%</b>、且收盘高于开盘的阳线，证明已有强势启动信号。
                        </CardText>
                      </div>
                    </div>

                    {/* 3. 买点区间 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <CheckCircle2 className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">买点区间</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">距 MA5 0% ~ 2.5% 黄金低吸区</h4>
                        <CardText className="text-[11px] text-slate-400 leading-normal">
                          股价调整回踩至 <b>0%~2.5%</b> 为待买观察；<b>2.5%~5%</b> 继续观察；<b>5%~7%</b> 偏高不追；<b>&gt;7%</b> 远离不追；<b>&lt;0%</b> 跌破MA5，不进入待买。
                        </CardText>
                      </div>
                    </div>

                    {/* 4. 买入时间 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <Calendar className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">买入时间</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">9:35-10:00 / 14:30-14:55</h4>
                        <CardText className="text-[11px] text-slate-400 leading-normal">
                          早盘 9:35 确认高位承接且不破 MA5 收回；尾盘 14:30-14:55 确认支撑彻底稳固。<b>严禁 9:30 抢开盘、午盘中段或临期最后几分钟无计划追高。</b>
                        </CardText>
                      </div>
                    </div>

                    {/* 5. 资金约束 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <Coins className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">资金约束</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">可用资金: ¥{accountState.availableCash.toLocaleString(undefined, { minimumFractionDigits: 2 })}</h4>
                        <CardText className="text-[11px] text-slate-400 leading-normal">
                          单只标的最少买 1 手（100股）。现金不足 1 手时坚决克制手痒不买，任何时候<b>绝不私用未授权高杠杆</b>，记录交易时严格检验账面现金。
                        </CardText>
                      </div>
                    </div>

                    {/* 6. 卖出纪律 */}
                    <div className="bg-slate-950 border border-slate-800/60 rounded-lg p-3.5 space-y-2">
                      <div className="flex items-center space-x-2 text-cyan-400">
                        <AlertCircle className="h-4 w-4 shrink-0" />
                        <span className="text-xs font-bold uppercase tracking-wider">卖出纪律</span>
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-xs font-extrabold text-slate-200">5 日线管理仓位 + 本金2%硬风控</h4>
                        <CardText className="text-[11px] text-slate-400 leading-normal">
                          次日 10:00 前不强就走（无溢价冲高无力）；偏离 MA5 5%~7% 进入止盈观察，&gt;7% 优先止盈；14:50 跌破看减仓/直接清仓；3日不收回强制淘汰。单笔亏损触及本金2%时进入硬风控。
                        </CardText>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 纪律流水快捷补录控制台 */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row items-center justify-between gap-4 shadow-md">
                  <div className="space-y-1">
                    <h4 className="text-xs font-bold uppercase text-slate-200 tracking-wider flex items-center space-x-1.5">
                      <Plus className="h-3.5 w-3.5 text-cyan-400" />
                      <span>短线实盘交易补录控制台</span>
                    </h4>
                    <CardText className="text-[10px] text-slate-400 leading-normal">在实盘/模拟盘中成交后，请在此记入，系统自动同步审计，并在「交易记录审计」生成违规证据归档。</CardText>
                  </div>
                  <div className="flex items-center space-x-3 w-full md:w-auto shrink-0">
                    <button
                      onClick={handleQuickBuyEntry}
                      className="flex-1 md:flex-initial px-5 py-2.5 bg-rose-950/50 hover:bg-rose-900/50 border border-rose-900/60 rounded-lg font-black text-xs text-rose-200 transition duration-150 active:scale-95 cursor-pointer inline-flex items-center justify-center gap-1.5"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      <span>记录实盘买入</span>
                    </button>
                    <button
                      onClick={handleQuickSellEntry}
                      className="flex-1 md:flex-initial px-5 py-2.5 bg-emerald-950/50 hover:bg-emerald-900/50 border border-emerald-900/60 rounded-lg font-black text-xs text-emerald-200 transition duration-150 active:scale-95 cursor-pointer inline-flex items-center justify-center gap-1.5"
                    >
                      <Briefcase className="h-3.5 w-3.5" />
                      <span>记录实盘卖出</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: 股票池与分组表格 */}
          {activeTab === "watchlist" && (
            <div className="space-y-4">
              
              {/* 今日锁池与行情同步中心 */}
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-sm space-y-3">
                <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-3 border-b border-slate-800 pb-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <ShieldAlert className="h-4 w-4 text-cyan-400" />
                      <h3 className="text-sm font-black text-slate-100">今日锁池与行情同步</h3>
                      <span className={`rounded px-2 py-0.5 text-xs font-black ${poolMeta?.isPoolLocked ? "bg-cyan-950 text-cyan-300" : "bg-slate-800 text-slate-300"}`}>
                        {poolMeta?.isPoolLocked ? "已锁池" : "未锁池"}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] font-semibold text-slate-400">
                      <span>批次 <b className="font-mono text-slate-200">{poolGeneratedLabel}</b></span>
                      <span>池内 <b className="font-mono text-slate-200">{initialPoolCount}</b></span>
                      <span>观察/待买 <b className="font-mono text-cyan-300">{observationCount}/{pendingBuyCount}</b></span>
                      <span>K线缺口 <b className={missingKLineCount > 0 ? "font-mono text-amber-300" : "font-mono text-emerald-300"}>{missingKLineCount}</b></span>
                      <span>行情 <b className="font-mono text-slate-200">{latestQuoteLabel}</b></span>
                    </div>
                  </div>

                  <div className="relative w-full xl:w-80">
                    <Search className="h-3.5 w-3.5 text-slate-500 absolute left-3 top-2.5" />
                    <input
                      type="text"
                      placeholder="输入代码或名称搜索..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-8 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded text-xs focus:outline-none focus:border-cyan-500 font-mono text-slate-200"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 2xl:grid-cols-[1fr_1.35fr] gap-3 items-stretch">
                  <div className="rounded-lg border border-cyan-800/40 bg-cyan-950/10 p-3">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-sm font-black text-cyan-200">
                          <RefreshCw className={`h-4 w-4 ${quoteRefreshing ? "animate-spin" : ""}`} />
                          <span>安全刷新行情</span>
                          <span className="rounded bg-cyan-950 px-2 py-0.5 text-xs font-black text-cyan-300">
                            {autoQuoteRefreshEnabled ? (quoteRefreshing ? "刷新中" : `${quoteRefreshCountdown}s`) : "手动"}
                          </span>
                        </div>
                        <CardText className="mt-1 text-[11px] font-semibold text-slate-300">
                          更新现价、成交额、MA5偏离并重算分组；名单不变
                        </CardText>
                      </div>
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto] lg:w-[520px]">
                      <button
                        type="button"
                        role="switch"
                        aria-checked={autoQuoteRefreshEnabled}
                        onClick={() => setAutoQuoteRefreshEnabled(prev => !prev)}
                        className={`px-3.5 py-1.5 rounded border text-xs font-semibold flex items-center justify-between gap-3 transition ${
                          autoQuoteRefreshEnabled
                            ? "bg-cyan-600/20 border-cyan-500/40 text-cyan-200"
                            : "bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        <span>自动刷新当前池行情 30秒</span>
                        <span className={`h-4 w-7 rounded-full p-0.5 transition ${autoQuoteRefreshEnabled ? "bg-cyan-500" : "bg-slate-700"}`}>
                          <span className={`block h-3 w-3 rounded-full bg-white transition ${autoQuoteRefreshEnabled ? "translate-x-3" : "translate-x-0"}`}></span>
                        </span>
                      </button>
                      <button
                        onClick={() => void handleRefreshQuotes("manual")}
                        disabled={quoteRefreshing}
                        className="px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded text-xs font-black shadow-sm flex items-center justify-center gap-1.5 transition"
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${quoteRefreshing ? "animate-spin" : ""}`} />
                        <span>{quoteRefreshing ? "刷新中..." : "立刻刷新"}</span>
                      </button>
                    </div>
                    </div>
                  </div>

                  <div className="rounded-lg border border-amber-800/40 bg-amber-950/10 p-3">
                    <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2 text-sm font-black text-amber-200">
                          <AlertCircle className="h-4 w-4" />
                          <span>前30异动提醒</span>
                          <span className="rounded bg-amber-950 px-2 py-0.5 text-xs font-black text-amber-300">
                            {autoTurnoverScanEnabled ? (turnoverScanning ? "扫描中" : `${turnoverScanCountdown}s`) : "手动"}
                          </span>
                        </div>
                        <CardText className="mt-1 text-[11px] font-semibold text-slate-300">
                          只提醒新进/跌出，不自动替换锁池
                        </CardText>
                      </div>
                      <div className="grid grid-cols-4 gap-2 text-xs font-mono xl:w-[360px]">
                        <div className="rounded border border-cyan-500/20 bg-cyan-950/10 px-2 py-1.5 text-slate-300">新进 <span className="font-black text-cyan-300">{turnoverChanges?.newEntries.length || 0}</span></div>
                        <div className="rounded border border-amber-500/20 bg-amber-950/10 px-2 py-1.5 text-slate-300">跌出 <span className="font-black text-amber-300">{turnoverChanges?.dropped.length || 0}</span></div>
                        <div className="rounded border border-emerald-500/20 bg-emerald-950/10 px-2 py-1.5 text-slate-300">上升 <span className="font-black text-emerald-300">{turnoverChanges?.rankUp.length || 0}</span></div>
                        <div className="rounded border border-rose-500/20 bg-rose-950/10 px-2 py-1.5 text-slate-300">下降 <span className="font-black text-rose-300">{turnoverChanges?.rankDown.length || 0}</span></div>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
                      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                        <div className="space-y-1.5">
                          <div className="text-[11px] font-black text-cyan-300">新进前30</div>
                          {turnoverChanges ? renderTurnoverPreviewRows(turnoverChanges.newEntries, "new") : (
                            <div className="rounded border border-dashed border-slate-800 bg-slate-950/30 px-3 py-2 text-[11px] font-semibold text-slate-500">
                              等待扫描
                            </div>
                          )}
                        </div>
                        <div className="space-y-1.5">
                          <div className="text-[11px] font-black text-amber-300">跌出前30</div>
                          {turnoverChanges ? renderTurnoverPreviewRows(turnoverChanges.dropped, "dropped") : (
                            <div className="rounded border border-dashed border-slate-800 bg-slate-950/30 px-3 py-2 text-[11px] font-semibold text-slate-500">
                              等待扫描
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto] lg:w-[500px] xl:grid-cols-1 xl:w-[210px]">
                        <button
                          type="button"
                          role="switch"
                          aria-checked={autoTurnoverScanEnabled}
                          onClick={() => setAutoTurnoverScanEnabled(prev => !prev)}
                          className={`px-3.5 py-1.5 rounded border text-xs font-semibold flex items-center justify-between gap-3 transition ${
                            autoTurnoverScanEnabled
                              ? "bg-amber-600/20 border-amber-500/40 text-amber-200"
                              : "bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200"
                          }`}
                        >
                          <span>自动扫描 3分钟</span>
                          <span className={`h-4 w-7 rounded-full p-0.5 transition ${autoTurnoverScanEnabled ? "bg-amber-500" : "bg-slate-700"}`}>
                            <span className={`block h-3 w-3 rounded-full bg-white transition ${autoTurnoverScanEnabled ? "translate-x-3" : "translate-x-0"}`}></span>
                          </span>
                        </button>
                        <button
                          onClick={() => void handleScanTurnoverChanges("manual")}
                          disabled={turnoverScanning}
                          className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded text-xs font-black shadow-sm flex items-center justify-center gap-1.5 transition"
                        >
                          <AlertCircle className="h-3.5 w-3.5" />
                          <span>{turnoverScanning ? "扫描中..." : "手动扫描"}</span>
                        </button>
                        <span className="text-[10px] font-mono text-slate-500">上次 {lastTurnoverScanAt ? lastTurnoverScanAt.toLocaleTimeString() : "未触发"}</span>
                      </div>
                    </div>
                  </div>

                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-950/30 px-3 py-3 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="flex items-center gap-2 text-sm font-black text-slate-200">
                      <Activity className="h-4 w-4 text-slate-400" />
                      <span>数据修复</span>
                    </div>
                    <span className="text-[11px] font-semibold text-slate-400">补K线只补指标；重建/上传会覆盖名单</span>
                  </div>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <button
                      onClick={handleRebuildStockPool}
                      className="px-3.5 py-1.5 bg-rose-950/60 hover:bg-rose-900/60 text-rose-200 border border-rose-700/50 rounded text-xs font-black shadow-sm transition"
                    >
                      重建今日初筛池
                    </button>
                    <button
                      onClick={() => handleFetchHistory(undefined, true)}
                      className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 rounded text-xs font-black shadow-sm transition"
                    >
                      补充所有K线
                    </button>
                    <button
                      onClick={() => setShowImportPanel(!showImportPanel)}
                      className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 rounded text-xs font-black shadow-sm flex items-center justify-center gap-1.5 transition"
                    >
                      <FileSpreadsheet className="h-3.5 w-3.5" />
                      <span>上传同花顺初筛池</span>
                    </button>
                  </div>
                </div>

                {turnoverChanges && (
                  <div className="border-t border-slate-800 pt-3">
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <span className="text-sm font-black text-slate-200">成交额前30变动提醒</span>
                      <span className="text-xs text-slate-400 font-mono">{changeTotal} 条</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2">
                      {renderTurnoverList("新进", turnoverChanges.newEntries, "cyan")}
                      {renderTurnoverList("跌出", turnoverChanges.dropped, "amber")}
                      {renderTurnoverList("上升", turnoverChanges.rankUp, "emerald")}
                      {renderTurnoverList("下降", turnoverChanges.rankDown, "rose")}
                    </div>
                  </div>
                )}
              </div>

              {/* 同花顺表格导入区域 */}
              {showImportPanel && (
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                    <span className="text-xs font-bold text-slate-300">同花顺表格导入当前初筛池</span>
                    <button onClick={() => setShowImportPanel(false)} className="text-slate-500 hover:text-slate-300 text-xs">取消</button>
                  </div>
                  <CardText className="text-[10px] text-slate-500">
                    支持 .xlsx / .xls / .csv。系统会以表格中的股票代码为准，清洗成沪深主板前30只并覆盖当前股票池；旧股票池会先自动备份。
                  </CardText>
                  <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-center">
                    <input
                      type="file"
                      accept=".xlsx,.xls,.csv"
                      onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 file:mr-3 file:rounded file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-slate-300 hover:file:bg-slate-700"
                    />
                    <label className="flex items-center gap-2 text-[11px] text-slate-400">
                      <input
                        type="checkbox"
                        checked={autoFetchHistoryAfterImport}
                        onChange={(e) => setAutoFetchHistoryAfterImport(e.target.checked)}
                        className="h-3.5 w-3.5 accent-cyan-500"
                      />
                      导入后自动补K线
                    </label>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[10px] text-slate-500">
                      {importFile ? `已选择: ${importFile.name}` : "尚未选择文件"}
                    </span>
                    <button
                      onClick={handleImportFile}
                      disabled={!importFile || loading}
                      className="px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded text-xs font-semibold"
                    >
                      覆盖导入
                    </button>
                  </div>
                </div>
              )}

              {/* 分组 TAB 与表格视口 */}
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
                
                {/* 列表区域 */}
                <div className="xl:col-span-2 space-y-3">
                  
                  {/* 分组 Tab 切换器 */}
                  <div className="flex bg-slate-900 border border-slate-800 p-1 rounded-lg">
                    {(["初筛", "观察", "待买"] as StockGroup[]).map(gp => {
                      const count = stocksForGroup(watchlist, gp).length;
                      return (
                        <button
                          key={gp}
                          onClick={() => {
                            setWatchlistGroup(gp);
                            // 默认选择当前派生视图中的第一个
                            const first = firstStockForGroup(watchlist, gp);
                            if (first) setSelectedStock(first);
                          }}
                          className={`flex-1 py-1.5 text-xs font-bold rounded-md transition ${watchlistGroup === gp ? "bg-slate-950 text-cyan-400 shadow-inner" : "text-slate-500 hover:text-slate-300"}`}
                        >
                          {gp} ({count})
                        </button>
                      );
                    })}
                  </div>

                  {/* 表格 */}
                  <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="border-b border-slate-800/80 bg-slate-950/40 text-slate-500 font-mono">
                          <th className="p-3">股票</th>
                          <th className="p-3 text-right">最新现价</th>
                          <th className="p-3 text-right">涨跌幅</th>
                          <th className="p-3 text-right">成交额(万)</th>
                          <th className="p-3 text-right">5日偏离率</th>
                          <th className="p-3 text-right">大阳特征</th>
                          <th className="p-3">流程阶段 / 状态</th>
                          <th className="p-3">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredWatchlist.length === 0 ? (
                          <tr>
                            <td colSpan={8} className="p-8 text-center text-slate-500 italic">
                              当前分组暂无匹配的股票
                            </td>
                          </tr>
                        ) : (
                          filteredWatchlist.map(s => {
                            const isSelected = selectedStock?.code === s.code;
                            const displayStage = watchlistGroup === "待买"
                              ? "待买观察"
                              : watchlistGroup === "观察"
                                ? (observationStageForStock(s) || s.stage)
                                : s.stage;
                            return (
                              <tr
                                key={s.code}
                                onClick={() => setSelectedStock(s)}
                                className={`border-b border-slate-800/40 hover:bg-slate-800/30 cursor-pointer transition ${isSelected ? "bg-slate-800/50" : ""}`}
                              >
                                <td className="p-3 font-mono">
                                  <div className="font-semibold text-slate-200">{s.name}</div>
                                  <div className="text-[10px] text-slate-500">
                                    {s.code}
                                    <span className="ml-1">锁池#{s.poolRankAtGeneration || s.rank || "-"}</span>
                                    {s.isPinned && <span className="ml-1 text-cyan-400">钉住</span>}
                                  </div>
                                </td>
                                <td className="p-3 text-right font-mono font-semibold text-slate-300">
                                  {s.price > 0 ? s.price.toFixed(2) : "未同步"}
                                </td>
                                <td className={`p-3 text-right font-mono font-semibold ${s.pct >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
                                  {s.pct >= 0 ? "+" : ""}{s.pct.toFixed(2)}%
                                </td>
                                <td className="p-3 text-right font-mono text-slate-400">
                                  {s.volume > 0 ? (s.volume / 10000).toLocaleString(undefined, { maximumFractionDigits: 0 }) : "0"}
                                </td>
                                <td className={`p-3 text-right font-mono font-bold ${s.deviation5 < 0 ? "text-emerald-500" : s.deviation5 <= tradingRules.buyZone.maxDeviationPct ? "text-cyan-400 underline decoration-cyan-500" : "text-rose-400"}`}>
                                  {s.deviation5}%
                                </td>
                                <td className="p-3 text-right font-mono text-slate-400">
                                  {s.bigCandlePct > 0 ? `${s.bigCandlePct}%` : "未计算"}
                                </td>
                                <td className="p-3">
                                  <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                                    displayStage === "待买观察" ? "bg-cyan-950 text-cyan-400 border border-cyan-500/20" :
                                    displayStage === "继续观察" ? "bg-amber-950 text-amber-400 border border-amber-500/20" :
                                    displayStage === "偏高不追" ? "bg-orange-950 text-orange-300 border border-orange-500/20" :
                                    displayStage === "远离不追" ? "bg-rose-950 text-rose-400 border border-rose-500/20" :
                                    "bg-slate-800 text-slate-400"
                                  }`}>
                                    {displayStage}
                                  </span>
                                </td>
                                <td className="p-3" onClick={e => e.stopPropagation()}>
                                  <div className="flex space-x-1.5">
                                    {s.historyStatus !== "已有缓存" && (
                                      <button
                                        onClick={() => handleFetchHistory(s.code)}
                                        className="px-1.5 py-0.5 bg-slate-800 hover:bg-slate-700 text-cyan-400 text-[10px] rounded"
                                        title="补充单只历史均线"
                                      >
                                        补K线
                                      </button>
                                    )}
                                    {watchlistGroup === "待买" && (
                                      <button
                                        onClick={() => openBuyModal(s)}
                                        disabled={!s.canBuy || !currentInBuyWindow || systemicRisk || s.marketTradeAllowed === false || s.marketRisk === true}
                                        className="px-2 py-0.5 bg-rose-600 hover:bg-rose-500 disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed text-white font-semibold text-[10px] rounded"
                                      >
                                        盘中确认
                                      </button>
                                    )}
                                    {watchlistGroup === "持仓" && (
                                      <button
                                        onClick={() => {
                                          const pos = positions.find(p => p.code === s.code);
                                          if (pos) openSellModal(pos);
                                        }}
                                        className="px-2 py-0.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-[10px] rounded"
                                      >
                                        确认卖出
                                      </button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* 右侧详情及 K 线分析区域 */}
                <div className="space-y-4">
                  {selectedStock ? (
                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-4 shadow-md">
                      
                      {/* 标题 */}
                      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                        <div>
                          <h3 className="text-sm font-bold text-slate-200">{selectedStock.name}</h3>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {selectedStock.code} | {isMainBoard(selectedStock.code) ? "主板" : "非主板"} | 锁池#{selectedStock.poolRankAtGeneration || selectedStock.rank || "-"}
                            {selectedStock.isPinned ? " | 钉住" : ""}
                          </span>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${selectedStock.ma5Upward ? "bg-rose-950 text-rose-400 border border-rose-500/20" : "bg-slate-950 text-slate-500"}`}>
                          {selectedStock.ma5Upward ? "MA5 向上 ↗" : "MA5参考"}
                        </span>
                      </div>

                      {/* 实盘 K 线渲染 */}
                      <KLineChart code={selectedStock.code} name={selectedStock.name} />

                      {/* 规则诊断分析 */}
                      <div className="bg-slate-950/80 border border-slate-850 p-3 rounded-lg space-y-2">
                        <div className="text-xs font-semibold text-slate-300 flex items-center space-x-1">
                          <Info className="h-3.5 w-3.5 text-cyan-400" />
                          <span>纪律诊断结论：</span>
                        </div>
                        <CardText className="text-xs text-slate-400 font-mono leading-relaxed">{selectedStock.reason || "暂未计算得出诊断。您可以点击「刷新当前池行情」重新诊断。"}</CardText>
                        
                        {selectedStock.reminder && (
                          <div className="border-t border-slate-800/40 pt-1.5 mt-1.5 flex items-start space-x-1.5">
                            <span className="text-[10px] font-bold text-cyan-500 uppercase shrink-0 mt-0.5">指令:</span>
                            <CardText as="span" className="text-xs text-slate-300 font-medium">{selectedStock.reminder}</CardText>
                          </div>
                        )}
                      </div>

                      {/* 快捷自选备注保存区 */}
                      <div className="space-y-2">
                        <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">个股观察备忘录 (手写证据)</label>
                        <textarea
                          placeholder="在此写下您对该股题材、热点或大阴阳线启动的历史细节观察..."
                          value={selectedStock.remark}
                          onChange={(e) => {
                            const newText = e.target.value;
                            setWatchlist(prev => prev.map(s => s.code === selectedStock.code ? { ...s, remark: newText } : s));
                            setSelectedStock(prev => prev ? { ...prev, remark: newText } : null);
                          }}
                          className="w-full h-20 bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 focus:outline-none focus:border-cyan-500 leading-relaxed"
                        />
                        <div className="text-right">
                          <button
                            onClick={() => handleSaveRemark(selectedStock.code, selectedStock.remark)}
                            className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded text-[10px] font-semibold"
                          >
                            保存备忘备注
                          </button>
                        </div>
                      </div>

                      {/* 快速买入面板 */}
                      <div className="flex space-x-2 pt-2">
                        <button
                          onClick={() => openBuyModal(selectedStock)}
                          className="flex-1 py-2 bg-rose-600 hover:bg-rose-500 disabled:opacity-40 text-white rounded text-xs font-bold transition shadow"
                        >
                          记录交易
                        </button>
                        {positions.some(p => p.code === selectedStock.code) && (
                          <button
                            onClick={() => {
                              const pos = positions.find(p => p.code === selectedStock.code);
                              if (pos) openSellModal(pos);
                            }}
                            className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-bold transition shadow"
                          >
                            记录卖出归档
                          </button>
                        )}
                      </div>

                    </div>
                  ) : (
                    <CardText as="div" className="bg-slate-900 border border-slate-800 p-8 rounded-lg text-center text-slate-500 italic">
                      请点击左侧列表中的股票，调阅其高保真日K线及纪律红黄绿灯判定。
                    </CardText>
                  )}
                </div>

              </div>

            </div>
          )}

          {/* TAB 3: 盘中低吸监控 */}
          {activeTab === "intraday" && (
            <div className="space-y-6">
              
              {/* 今日信号播报 */}
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-4 shadow-md">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-800 pb-2">
                  <div className="flex items-center space-x-2">
                    <TrendingUp className="h-4.5 w-4.5 text-cyan-400" />
                    <h3 className="text-sm font-bold text-slate-200">盘中强回踩低吸监控</h3>
                  </div>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <button
                      type="button"
                      role="switch"
                      aria-checked={autoQuoteRefreshEnabled}
                      onClick={() => setAutoQuoteRefreshEnabled(prev => !prev)}
                      className={`px-3 py-1.5 rounded border text-xs font-semibold flex items-center justify-between gap-3 transition ${
                        autoQuoteRefreshEnabled
                          ? "bg-cyan-600/20 border-cyan-500/40 text-cyan-200"
                          : "bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <span>自动刷新当前池行情 30秒</span>
                      <span className={`h-4 w-7 rounded-full p-0.5 transition ${autoQuoteRefreshEnabled ? "bg-cyan-500" : "bg-slate-700"}`}>
                        <span className={`block h-3 w-3 rounded-full bg-white transition ${autoQuoteRefreshEnabled ? "translate-x-3" : "translate-x-0"}`}></span>
                      </span>
                    </button>
                    <button
                      onClick={() => void handleRefreshQuotes("manual")}
                      disabled={quoteRefreshing}
                      className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-cyan-700 disabled:opacity-75 disabled:cursor-not-allowed text-white rounded text-xs font-semibold shadow-md flex items-center justify-center space-x-1.5 transition"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${quoteRefreshing ? "animate-spin" : ""}`} />
                      <span>{quoteRefreshing ? "刷新中..." : "立刻刷新当前池行情"}</span>
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-3 bg-slate-950/60 border border-slate-850 rounded-lg">
                    <span className="text-[10px] text-slate-500 font-bold block">行情最新同步</span>
                    <span className="text-xs font-mono text-slate-300 mt-1 block">
                      {watchlist[0]?.lastUpdated ? new Date(watchlist[0].lastUpdated).toLocaleTimeString() : "未同步"}
                    </span>
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-850 rounded-lg">
                    <span className="text-[10px] text-slate-500 font-bold block">成交额沪深主板前排前30</span>
                    <span className="text-xs font-mono text-slate-300 mt-1 block">已启用主力成交量筛选约束</span>
                  </div>
                  <div className="p-3 bg-slate-950/60 border border-slate-850 rounded-lg">
                    <span className="text-[10px] text-slate-500 font-bold block">自动刷新当前池行情</span>
                    <span className="text-xs text-slate-300 mt-1 block">
                      {autoQuoteRefreshEnabled
                        ? (quoteRefreshing ? "正在刷新行情..." : `${quoteRefreshCountdown}s 后自动刷新`)
                        : "已关闭，手动刷新可用"}
                    </span>
                    <span className="text-[10px] text-slate-500 mt-1 block">
                      上次刷新 {lastQuoteRefreshAt ? lastQuoteRefreshAt.toLocaleTimeString() : latestWatchlistUpdateLabel}
                    </span>
                  </div>
                </div>
              </div>

              {/* 待买观察候选提示 */}
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-4">
                <div className="flex flex-col gap-2 border-b border-slate-800 pb-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center space-x-2">
                    <CheckCircle2 className="h-4 w-4 text-cyan-400" />
                    <h3 className="text-sm font-black text-slate-100">待买观察候选</h3>
                    <span className="rounded bg-cyan-950 px-2 py-0.5 text-xs font-black text-cyan-300">{buyReadyStocks.length} 只</span>
                  </div>
                  <span className="text-[11px] font-semibold text-slate-400">5日线偏离度 0%~2.5%，盘中确认并通过资金/风险约束后才记录买入</span>
                </div>

                <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                  {buyReadyStocks.length === 0 ? (
                    <CardText as="div" className="p-8 text-center text-slate-500 bg-slate-950 rounded-lg border border-slate-800/40 text-xs font-semibold xl:col-span-2">
                      盘中暂无进入待买观察层（大阳启动后回踩MA5，偏离度0%~2.5%、未跌破MA5且通过资金/风险约束）的主板股。请刷新当前池行情或等待回踩。
                    </CardText>
                  ) : (
                    buyReadyStocks.map(s => renderBuyReadyCard(s))
                  )}
                </div>
              </div>

              {/* 持仓实时卖点监控 */}
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg space-y-4">
                <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
                  <Briefcase className="h-4 w-4 text-cyan-400" />
                  <h3 className="text-xs font-bold uppercase text-slate-200 tracking-wider">持仓实时监控 (卖点纪律)</h3>
                </div>

                <div className="space-y-3">
                  {positions.length === 0 ? (
                    <CardText as="div" className="p-8 text-center text-slate-500 italic bg-slate-950 rounded-lg border border-slate-800/40 text-xs">
                      当前暂无持仓。买入流水录入后，这里会同步显示实时价格、MA5偏离、持仓时间和卖点计划。
                    </CardText>
                  ) : (
                    sortedPositions.map((p, idx) => renderPositionSellCard(p, idx))
                  )}
                </div>
              </div>

            </div>
          )}

          {/* TAB 4: 交易流水审计 */}
          {activeTab === "trades" && (
            <div className="space-y-6">
              
              {/* 今日统计 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">总买入次数</span>
                  <span className="text-2xl font-bold font-mono text-rose-500 block mt-1">{trades.filter(t => t.type === "BUY").length} 次</span>
                  <CardText className="text-[10px] text-slate-500 mt-2">包含实盘或模拟买入存底</CardText>
                </div>
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">交易合规率</span>
                  <span className={`text-2xl font-bold font-mono block mt-1 ${auditStats ? (auditStats.complianceRate >= 80 ? "text-rose-500" : "text-amber-500") : "text-slate-400"}`}>
                    {auditStats ? `${auditStats.complianceRate}%` : "未完成"}
                  </span>
                  <CardText className="text-[10px] text-slate-500 mt-2">买入和卖出规则不含违规标签的比例</CardText>
                </div>
                <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                  <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">累计已平仓盈亏</span>
                  <span className={`text-2xl font-bold font-mono block mt-1 ${accountState.realizedPnL >= 0 ? "text-rose-500" : "text-emerald-500"}`}>
                    {signedCurrency(accountState.realizedPnL, " 元")}
                  </span>
                  <CardText className="text-[10px] text-slate-500 mt-2">只统计已卖出落袋部分，不含当前持仓浮盈亏</CardText>
                </div>
              </div>

              {/* 交易审计详细列表 */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <div className="flex items-center space-x-2">
                    <History className="h-4 w-4 text-cyan-400" />
                    <h3 className="text-xs font-bold uppercase text-slate-200 tracking-wider">交易流水账单（交易买卖驱动资产）</h3>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">交易保存前自动触发 watchlist 状态备份</span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 bg-slate-950/40 text-slate-500 font-mono">
                        <th className="p-3">时间</th>
                        <th className="p-3">股票</th>
                        <th className="p-3">方向</th>
                        <th className="p-3 text-right">价格</th>
                        <th className="p-3 text-right">数量</th>
                        <th className="p-3 text-right">成交额</th>
                        <th className="p-3 text-right">佣金</th>
                        <th className="p-3 text-right">印花税</th>
                        <th className="p-3 text-right">过户费</th>
                        <th className="p-3 text-right">总费用</th>
                        <th className="p-3 text-right">结算额</th>
                        <th className="p-3">纪律合规审计</th>
                        <th className="p-3">买入依据 / 计划备注</th>
                        <th className="p-3">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.length === 0 ? (
                        <tr>
                          <td colSpan={14} className="p-8 text-center text-slate-500 italic">
                            <CardText as="span">暂无任何买卖存档记录。可在分组表格点击「买入」进行录入。</CardText>
                          </td>
                        </tr>
                      ) : (
                        [...trades].reverse().map(t => (
                          <tr key={t.id} className="border-b border-slate-800/40 hover:bg-slate-800/10">
                            <td className="p-3 font-mono text-slate-400">
                              <div>{t.date}</div>
                              <div className="text-[10px] text-slate-500">{t.time}</div>
                            </td>
                            <td className="p-3 font-mono font-bold text-slate-200">
                              <div>{t.name}</div>
                              <div className="text-[10px] text-slate-500">{t.code}</div>
                            </td>
                            <td className="p-3">
                              <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${t.type === "BUY" ? "bg-rose-950 text-rose-400" : "bg-emerald-950 text-emerald-400"}`}>
                                {t.type === "BUY" ? "买入" : "卖出"}
                              </span>
                            </td>
                            <td className="p-3 text-right font-mono font-semibold text-slate-300">{t.price.toFixed(2)}</td>
                            <td className="p-3 text-right font-mono text-slate-400">{t.quantity}</td>
                            <td className="p-3 text-right font-mono text-slate-400">{tradeAmount(t).toFixed(2)}</td>
                            <td className="p-3 text-right font-mono text-slate-500">{t.commission.toFixed(2)}</td>
                            <td className="p-3 text-right font-mono text-slate-500">{t.stampDuty.toFixed(2)}</td>
                            <td className="p-3 text-right font-mono text-slate-500">{t.transferFee.toFixed(2)}</td>
                            <td className="p-3 text-right font-mono text-slate-500">
                              {t.totalFee.toFixed(2)}
                            </td>
                            <td className={`p-3 text-right font-mono font-bold ${t.type === "BUY" ? "text-rose-400" : "text-emerald-400"}`}>
                              {tradeSettlementAmount(t).toFixed(2)}
                            </td>
                            <td className="p-3">
                              <div className="space-y-1">
                                <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                  t.rulesConclusion === "符合规则" ? "bg-rose-950 text-rose-400" : "bg-amber-950 text-amber-400"
                                }`}>
                                  {t.rulesConclusion}
                                </span>
                                {t.violationTags && t.violationTags.length > 0 && (
                                  <div className="flex flex-wrap gap-1">
                                    {t.violationTags.map(tag => (
                                      <span key={tag} className="text-[9px] bg-rose-950/40 text-rose-300 px-1 rounded">
                                        {tag}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </td>
                            <td className="p-3 text-slate-400 max-w-xs break-words">
                              <CardText className="font-semibold text-slate-300">{t.reason}</CardText>
                              {t.remark && <CardText className="text-[10px] text-slate-500 mt-1 italic">备注: {t.remark}</CardText>}
                            </td>
                            <td className="p-3">
                              <div className="flex items-center space-x-1.5">
                                <button
                                  onClick={() => openEditTradeModal(t)}
                                  className="p-1 text-slate-500 hover:text-cyan-400 hover:bg-cyan-950/20 rounded transition"
                                  title="编辑并重新计算费用"
                                >
                                  <Edit className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  onClick={() => handleDeleteTrade(t.id)}
                                  className="p-1 text-slate-500 hover:text-rose-400 hover:bg-rose-955/20 rounded transition"
                                  title="撤销这笔交易"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

            </div>
          )}

          {/* TAB 5: 复盘报告与笔记 */}
          {activeTab === "review" && (
            <div className="space-y-6">
              
              {/* 五大维度闭环复盘导航 */}
              {renderReviewStepper()}

              {/* 子视图 1: 今日复盘 */}
              {activeReviewSubTab === "today" && (
                <div className="space-y-6 animate-fade-in">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                      <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">今日买卖次数</span>
                      <span className="text-xl font-bold font-mono text-slate-200 block mt-1">
                        {(todayTrades?.filter((t: any) => t.type === "BUY").length || 0)} 买 / {(todayTrades?.filter((t: any) => t.type === "SELL").length || 0)} 卖
                      </span>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                      <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">今日合规纪律率</span>
                      <span className={`text-xl font-bold font-mono block mt-1 ${
                        complianceRate >= 80 ? "text-rose-500" : "text-amber-500"
                      }`}>
                        {complianceRate}%
                      </span>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                      <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">今日手续费账单</span>
                      <span className="text-xl font-bold font-mono text-cyan-400 block mt-1">
                        {(todayTrades?.reduce((acc: number, t: any) => acc + (t.totalFee || 0), 0) || 0).toFixed(2)} 元
                      </span>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                      <span className="text-[10px] text-slate-500 font-bold uppercase block tracking-wider">今日已平仓盈亏</span>
                      <span className={`text-xl font-bold font-mono block mt-1 ${
                        todayRealizedPnL >= 0 
                          ? "text-rose-400" 
                          : "text-emerald-400"
                      }`}>
                        {signedCurrency(todayRealizedPnL, " 元")}
                      </span>
                      <CardText className="text-[10px] text-slate-500 mt-2">只看今日卖出结算，不含持仓市值变化</CardText>
                    </div>
                  </div>

                  {/* 违规警告横幅 */}
                  {todayTrades?.some((t: any) => t.rulesConclusion === "违规交易") && (
                    <div className="bg-rose-950/20 border border-rose-900/60 p-4 rounded-lg flex items-start space-x-3 text-rose-300">
                      <ShieldAlert className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />
                      <div>
                        <h4 className="text-xs font-bold uppercase tracking-wider text-rose-400">🚨 短线纪律雷达报警：捕获违规硬伤！</h4>
                        <CardText className="text-[11px] mt-1 text-rose-300 leading-relaxed">
                          今日流水中包含违规买入。例如偏离5日线（MA5）过高、或5日均线仍向下时临时起意买入。硬伤交易会极快稀释您的长期复利！请前往「操作复盘与存档」标签写下深刻反省。
                        </CardText>
                      </div>
                    </div>
                  )}

                  {/* 今日流水明细 */}
                  <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
                    <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">今日交易流水审计（数据自动回溯推导持仓）</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead>
                          <tr className="border-b border-slate-800 bg-slate-950/40 text-slate-500 font-mono">
                            <th className="p-3">时间</th>
                            <th className="p-3">股票</th>
                            <th className="p-3">方向</th>
                            <th className="p-3 text-right">价格</th>
                            <th className="p-3 text-right">数量</th>
                            <th className="p-3 text-right">手续费</th>
                            <th className="p-3">审计状态</th>
                            <th className="p-3">反思依据</th>
                          </tr>
                        </thead>
                        <tbody>
                          {!todayTrades || todayTrades.length === 0 ? (
                            <tr>
                              <td colSpan={8} className="p-8 text-center text-slate-500 italic">
                                <CardText as="span">今日无任何买卖操作。短线空仓也是一种极高雅的操作纪律！</CardText>
                              </td>
                            </tr>
                          ) : (
                            todayTrades.map((t: any) => (
                              <tr key={t.id} className="border-b border-slate-800/40 hover:bg-slate-800/10">
                                <td className="p-3 font-mono text-slate-400">{t.time}</td>
                                <td className="p-3 font-mono text-slate-200 font-bold">{t.name} ({t.code})</td>
                                <td className="p-3">
                                  <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                    t.type === "BUY" ? "bg-rose-950 text-rose-400" : "bg-emerald-950 text-emerald-400"
                                  }`}>
                                    {t.type === "BUY" ? "买入" : "卖出"}
                                  </span>
                                </td>
                                <td className="p-3 text-right font-mono font-semibold text-slate-300">{t.price.toFixed(2)}</td>
                                <td className="p-3 text-right font-mono text-slate-400">{t.quantity}</td>
                                <td className="p-3 text-right font-mono text-slate-500">{t.totalFee.toFixed(2)}</td>
                                <td className="p-3">
                                  <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                    t.rulesConclusion === "符合规则" ? "bg-rose-950 text-rose-400" : "bg-amber-950 text-amber-400"
                                  }`}>
                                    {t.rulesConclusion}
                                  </span>
                                </td>
                                <td className="p-3 text-slate-400 max-w-xs truncate" title={t.reason}>
                                  <CardText as="span">{t.reason}</CardText>
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  {renderReviewNavFooter(null, "market", "进入下一步：大盘多空研判")}
                </div>
              )}
                         {/* 子视图 2: 大盘复盘 */}
              {activeReviewSubTab === "market" && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in">
                  
                  {/* Left Column: Interactive evaluation */}
                  <div className="lg:col-span-2 bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg space-y-5">
                    <div className="border-b border-slate-800 pb-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                      <div>
                      <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest">
                        核心指数趋势与资金大普查行动
                      </h3>
                      <CardText className="text-[11px] text-slate-400 mt-1">请核对上证、深证和创业板指数的走势、成交量及资金动向，确立底层交易水位。</CardText>
                      </div>
                      <span className={`text-[10px] font-black px-2.5 py-1 rounded border ${
                        systemicRisk ? "bg-rose-950/50 text-rose-300 border-rose-800" : "bg-cyan-950/40 text-cyan-300 border-cyan-800/50"
                      }`}>
                        {systemicRisk ? "风险收紧" : "常规水位"}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {/* 上证综指 */}
                      <div className="bg-slate-950/70 p-4 rounded-lg border border-slate-800 space-y-3 shadow-inner">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-extrabold text-slate-200">上证指数</span>
                          <span className="text-[10px] font-mono text-slate-500">000001.SH</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div>
                            <span className="text-[10px] text-slate-500">走势趋势:</span>
                            <select value={shTrend} onChange={(e) => setShTrend(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="向上">向上 (多头主导)</option>
                              <option value="震荡">震荡 (均线粘合)</option>
                              <option value="向下">向下 (破位防踩)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">成交量能:</span>
                            <select value={shVolume} onChange={(e) => setShVolume(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="放量">放量 (资金活跃)</option>
                              <option value="缩量">缩量 (追高谨慎)</option>
                              <option value="持平">持平 (存量博弈)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">资金流向:</span>
                            <select value={shFlow} onChange={(e) => setShFlow(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="净流入">资金主力净流入</option>
                              <option value="净流出">资金主力净流出</option>
                            </select>
                          </div>
                        </div>
                      </div>

                      {/* 深证成指 */}
                      <div className="bg-slate-950/70 p-4 rounded-lg border border-slate-800 space-y-3 shadow-inner">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-extrabold text-slate-200">深证成指</span>
                          <span className="text-[10px] font-mono text-slate-500">399001.SZ</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div>
                            <span className="text-[10px] text-slate-500">走势趋势:</span>
                            <select value={szTrend} onChange={(e) => setSzTrend(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="向上">向上 (多头主导)</option>
                              <option value="震荡">震荡 (均线粘合)</option>
                              <option value="向下">向下 (破位防踩)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">成交量能:</span>
                            <select value={szVolume} onChange={(e) => setSzVolume(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="放量">放量 (资金活跃)</option>
                              <option value="缩量">缩量 (追高谨慎)</option>
                              <option value="持平">持平 (存量博弈)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">资金流向:</span>
                            <select value={szFlow} onChange={(e) => setSzFlow(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="净流入">资金主力净流入</option>
                              <option value="净流出">资金主力净流出</option>
                            </select>
                          </div>
                        </div>
                      </div>

                      {/* 创业板指 */}
                      <div className="bg-slate-950/70 p-4 rounded-lg border border-slate-800 space-y-3 shadow-inner">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-extrabold text-slate-200">创业板指</span>
                          <span className="text-[10px] font-mono text-slate-500">399006.SZ</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div>
                            <span className="text-[10px] text-slate-500">走势趋势:</span>
                            <select value={cyTrend} onChange={(e) => setCyTrend(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="向上">向上 (多头主导)</option>
                              <option value="震荡">震荡 (均线粘合)</option>
                              <option value="向下">向下 (破位防踩)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">成交量能:</span>
                            <select value={cyVolume} onChange={(e) => setCyVolume(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="放量">放量 (资金活跃)</option>
                              <option value="缩量">缩量 (追高谨慎)</option>
                              <option value="持平">持平 (存量博弈)</option>
                            </select>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-500">资金流向:</span>
                            <select value={cyFlow} onChange={(e) => setCyFlow(e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-[11px] text-slate-300 mt-0.5 focus:outline-none">
                              <option value="净流入">资金主力净流入</option>
                              <option value="净流出">资金主力净流出</option>
                            </select>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 系统性大盘风险判定 */}
                    <div className="bg-slate-950/70 p-4 rounded-lg border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                      <div className="space-y-1">
                        <span className="text-xs font-extrabold text-slate-200">🚦 判定今日市场是否遇系统性见顶/大阴大跌风险？</span>
                        <CardText className="text-[11px] text-slate-400">大盘出现系统性下踩时，暂停开新仓，持仓优先按MA5与单笔本金2%亏损线处理。</CardText>
                      </div>
                      <div className="flex items-center space-x-3 shrink-0">
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input 
                            type="checkbox" 
                            checked={systemicRisk} 
                            onChange={(e) => {
                              setSystemicRisk(e.target.checked);
                              logAction(e.target.checked ? "⚠️ 警报：手动确认系统性风险，买入审计将禁止开新仓！" : "✓ 提示：解除系统性风险状态，买入窗口恢复按常规规则审计");
                            }}
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-300 after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-rose-600"></div>
                        </label>
                        <span className={`text-xs font-black ${systemicRisk ? "text-rose-500 animate-pulse" : "text-slate-500"}`}>
                          {systemicRisk ? "【已触发】系统性风险状态" : "【正常】无系统性风险"}
                        </span>
                      </div>
                    </div>

                    {/* 联动止损上调报警 */}
                    {systemicRisk && (
                      <div className="bg-rose-950/40 border border-rose-900 p-4 rounded-lg text-rose-200 flex items-start space-x-3 shadow-md">
                        <ShieldAlert className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />
                        <div>
                          <h4 className="text-xs font-black uppercase text-rose-400">🚨 止损风控铁律升级警报</h4>
                          <CardText className="text-[11px] mt-1 text-rose-300 leading-normal">
                            当前已手动确认触发系统性大盘风险！系统会在买入审计中标记并阻止新开仓；已有持仓按 MA5 跌破、连续3天未收回和单笔本金2%亏损线优先处理。
                          </CardText>
                          <CardText className="text-[10px] mt-1 text-slate-400 font-medium">请立即核对持仓，如有股票跌破5日线或当前浮亏触及本金2%，14:50 前优先执行风控。</CardText>
                        </div>
                      </div>
                    )}

                    <div className="bg-slate-950/70 p-4 rounded-lg border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-xs font-extrabold text-slate-200">大盘研判综合结论</span>
                        <span className="text-[10px] text-slate-500">保存日报时同步归档</span>
                      </div>
                      <textarea
                        value={marketConclusion}
                        onChange={(e) => setMarketConclusion(e.target.value)}
                        placeholder="写下今天大盘的综合研判，例如缩量回踩5日线、多头承接、系统性风险低或需降低仓位。"
                        rows={3}
                        className="w-full bg-slate-900 border border-slate-850 rounded p-2 text-xs text-slate-300 focus:outline-none focus:border-cyan-500 leading-relaxed"
                      />
                    </div>
                  </div>

                  {/* Right Column: Static gauge & advise */}
                  <div className="col-span-1 space-y-4">
                    <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl min-h-[220px] flex flex-col items-center justify-center text-center space-y-4 shadow-lg">
                      <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                        多空强度综合指数
                      </span>

                      {/* 圆形仪表盘 */}
                      <div className="relative flex items-center justify-center">
                        <svg className="w-32 h-32 transform -rotate-90">
                          <circle
                            cx="64"
                            cy="64"
                            r="50"
                            className="stroke-slate-850"
                            strokeWidth="8"
                            fill="transparent"
                          />
                          <circle
                            cx="64"
                            cy="64"
                            r="50"
                            className="stroke-cyan-500 transition-all duration-500"
                            strokeWidth="8"
                            fill="transparent"
                            strokeDasharray={314}
                            strokeDashoffset={314 - (314 * (systemicRisk ? 20 : (reportContext?.marketSnapshot?.bullishIndex || 55))) / 100}
                          />
                        </svg>
                        <div className="absolute flex flex-col items-center">
                          <span className="text-3xl font-mono font-black text-cyan-400">
                            {systemicRisk ? 20 : (reportContext?.marketSnapshot?.bullishIndex || 55)}%
                          </span>
                          <span className="text-[9px] text-slate-500">多头仓位上限建议</span>
                        </div>
                      </div>

                      <div className="space-y-1">
                        <span className="text-xs font-bold text-slate-300">多空评级: </span>
                        <span className={`text-xs font-black px-2 py-0.5 rounded ${
                          systemicRisk 
                            ? "bg-rose-950 text-rose-400" 
                            : "bg-amber-950 text-amber-400"
                        }`}>
                          {systemicRisk 
                            ? "大盘高危风控状态 (严格控仓或空仓)" 
                            : "震荡回踩期 (控制底仓低吸)"}
                        </span>
                      </div>
                    </div>

                    <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl space-y-2">
                      <h4 className="text-xs font-extrabold text-slate-300">上证、深证及创业板复盘硬指标</h4>
                      <CardText className="text-[11px] text-slate-400 leading-normal">
                        若遇系统性风险（例如主力资金呈断崖式净流出、多指数破位MA5），系统暂停新开仓，持仓按跌破MA5、连续3天不收回和单笔本金2%亏损线处理，以第三方冷静逻辑阻断扛单行为。
                      </CardText>
                    </div>
                  </div>

                  <div className="lg:col-span-3">
                    {renderReviewNavFooter("today", "sector", "进入下一步：板块回踩扫描")}
                  </div>
                </div>
              )}

              {/* 子视图 3: 板块复盘 */}
              {activeReviewSubTab === "sector" && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in">
                  
                  {/* Left Column: 50 ETF Checker */}
                  <div className="lg:col-span-2 bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-4">
                    <div className="border-b border-slate-800 pb-2 flex items-center justify-between">
                      <div className="space-y-0.5">
                        <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest flex items-center space-x-1.5">
                          <span>🔥 50只行业板块 ETF 趋势及资金多头大复盘</span>
                        </h3>
                        <CardText className="text-[11px] text-slate-400">拉网式大复盘 50 个行业 ETF 的主力资金流向与五日生命线排列，锁定最热强势回踩板块。</CardText>
                      </div>
                      <div className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-center shrink-0">
                        <span className="text-[10px] text-slate-500 block">今日扫过标的</span>
                        <span className="text-xs font-mono font-black text-cyan-400">{reviewedEtfCount} / 50 只</span>
                      </div>
                    </div>

                    {/* ETF 扫描进度及一键拉网按钮 */}
                    <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
                      <div className="space-y-1.5 w-full sm:w-auto">
                        <span className="text-xs font-bold text-slate-200 block">行业 ETF 多空能量网筛选进度</span>
                        <div className="w-full sm:w-64 bg-slate-900 rounded-full h-2.5 border border-slate-800 overflow-hidden">
                          <div 
                            className="bg-cyan-500 h-2.5 rounded-full transition-all duration-300" 
                            style={{ width: `${(reviewedEtfCount / 50) * 100}%` }}
                          ></div>
                        </div>
                      </div>
                      <button 
                        onClick={() => {
                          setReviewedEtfCount(50);
                          logAction("✅ 成功拉网复盘全市场 50 个主流行业 ETF！已记录主力成交及资金承接风口。");
                        }}
                        className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-800/40 rounded text-xs font-bold transition shadow cursor-pointer"
                      >
                        ⚡ 快速一键拉网已复盘 50 个主流 ETF
                      </button>
                    </div>

                    {/* 代表性行业 ETF 观察清单 */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                      {[
                        { code: "512480", name: "半导体 ETF" },
                        { code: "515030", name: "新能源车 ETF" },
                        { code: "512010", name: "医药医疗 ETF" },
                        { code: "512880", name: "大证券 ETF" },
                        { code: "159869", name: "动漫游戏 ETF" },
                        { code: "512660", name: "高端军工 ETF" },
                        { code: "515220", name: "红利煤炭 ETF" },
                        { code: "515060", name: "重整房地产 ETF" },
                      ].map((etf, i) => (
                        <div key={i} className="p-3 bg-slate-950 border border-slate-850 rounded flex items-center justify-between hover:border-slate-700">
                          <div className="space-y-0.5">
                            <span className="text-slate-500 block text-[9px] font-mono">{etf.code}</span>
                            <span className="font-bold text-slate-300">{etf.name}</span>
                          </div>
                          <span className="text-[10px] bg-cyan-950/40 text-cyan-400 border border-cyan-900/40 px-1.5 py-0.5 rounded font-bold">
                            已阅趋势
                          </span>
                        </div>
                      ))}
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-black text-slate-500 uppercase block tracking-wider">
                        概念及板块热度榜参考 (大智慧/同花顺人气榜前排)
                      </label>
                      <input 
                        type="text" 
                        value={hotSectors}
                        onChange={(e) => setHotSectors(e.target.value)}
                        placeholder="例如: 固态电池、AI算力大容量高人气、低空经济、证券红利低估重估支撑"
                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 mt-1 focus:outline-none focus:border-cyan-500"
                      />
                    </div>
                  </div>

                  {/* Right Column: Sector Notes */}
                  <div className="col-span-1 bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-4">
                    <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider border-b border-slate-800 pb-2">
                      行业板块资金规律备忘
                    </h3>
                    <div className="space-y-3">
                      <div>
                        <label className="text-[10px] font-black text-slate-500 block tracking-wider uppercase">主力板块资金流入与承接共振观察</label>
                        <textarea
                          rows={6}
                          value={etfFlowNotes}
                          onChange={(e) => setEtfFlowNotes(e.target.value)}
                          placeholder="例如: 今日半导体及大金融主力资金有深度共振，ETF呈大幅度净流入。科技回踩五日均线形成强力托底，符合强势回踩做多期。"
                          className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 mt-1 focus:outline-none focus:border-cyan-500 leading-relaxed"
                        />
                      </div>
                      <div className="p-3.5 bg-slate-950 border border-slate-850 rounded text-[11px] text-slate-400 space-y-1.5">
                        <span className="font-bold text-slate-300 block">💡 行业 ETF 交易指引:</span>
                        <CardText as="span">做超短线必须做到「板块护航，个股突围」。只要大板块趋势向上且没有见顶断崖，旗下强势股的回踩五日线行为便是安全的黄金买入段。</CardText>
                      </div>
                    </div>
                  </div>

                  <div className="lg:col-span-3">
                    {renderReviewNavFooter("market", "stock", "进入下一步：个股诊断")}
                  </div>
                </div>
              )}

              {/* 子视图 4: 个股复盘 */}
              {activeReviewSubTab === "stock" && (
                <div className="space-y-6 animate-fade-in">
                  
                  {/* Step 1 to 3: Global Stock Screen Wizards */}
                  <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-5">
                    <div className="border-b border-slate-800 pb-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                      <div>
                        <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest">
                          当前初筛池三步复查
                        </h3>
                        <CardText className="text-[11px] text-slate-400 mt-1">步骤1-3保留完整扫描结果，只有点击“加入自我诊断”的股票才会进入步骤4。</CardText>
                      </div>
                      <button
                        type="button"
                        onClick={handleManualScreening}
                        disabled={isScreening}
                        className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-bold text-[11px] rounded shadow transition flex items-center justify-center gap-1.5 shrink-0"
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${isScreening ? "animate-spin" : ""}`} />
                        <span>{isScreening ? "正在复查..." : "重新复查初筛池"}</span>
                      </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {renderScreenStepCard(
                        "1",
                        "当前成交额前30初筛池复查",
                        "按当前锁定的主板成交额前30基础池复查，完整结果会落盘到 JSON，日报正文只摘要前10只。",
                        top200Reviewed,
                        setTop200Reviewed,
                        step1Screened,
                        "step1"
                      )}
                      {renderScreenStepCard(
                        "2",
                        "放量异动线索复查",
                        "当前未接入真实量比，仅按成交额与涨跌幅保存复查线索；真实量比需手动核查后再作为交易依据。",
                        volRatioReviewed,
                        setVolRatioReviewed,
                        step2Screened,
                        "step2"
                      )}
                      {renderScreenStepCard(
                        "3",
                        "涨跌停 / 连板 / 情绪高度扫描",
                        "核查涨停、跌停、连板与强趋势票，记录情绪高度和风险方向。",
                        limitUpReviewed,
                        setLimitUpReviewed,
                        step3Screened,
                        "step3"
                      )}
                    </div>
                  </div>

                  {/* Step 4: Self diagnostics */}
                  <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-4">
                    <div className="border-b border-slate-800 pb-2 flex flex-col md:flex-row md:items-center justify-between gap-2">
                      <div className="space-y-0.5">
                        <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest flex items-center space-x-1.5">
                          <span>步骤 4：我的自我诊断记录</span>
                        </h3>
                        <CardText className="text-[11px] text-slate-400">这里只记录我真正需要复盘的持仓、今日交易票和手动加入的重点观察票，不自动塞入所有系统扫描结果。</CardText>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono">
                        共有 {diagnosedHoldings.length} 条自我诊断记录
                      </span>
                    </div>

                    {diagnosedHoldings.length === 0 ? (
                      <CardText as="div" className="p-8 text-center text-slate-500 italic bg-slate-950 rounded border border-slate-850 text-xs">
                        暂无自我诊断对象。当前持仓、今日交易会自动进入；步骤1-3中的股票需要手动点击“加入自我诊断”。
                      </CardText>
                    ) : (
                      <div className="space-y-4">
                        {diagnosedHoldings.map((diag, idx) => (
                          <div key={diag.code} className="bg-slate-950 p-4 rounded-lg border border-slate-850 space-y-3">
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-900 pb-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-xs font-mono font-black text-slate-200">{diag.name} ({diag.code})</span>
                                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                                  diag.type === "holding" ? "bg-amber-950/60 text-amber-400 border-amber-900/40" :
                                  diag.type === "todayBuy" ? "bg-rose-950/60 text-rose-300 border-rose-900/40" :
                                  diag.type === "todaySell" ? "bg-emerald-950/60 text-emerald-300 border-emerald-900/40" :
                                  "bg-cyan-950/60 text-cyan-300 border-cyan-900/40"
                                }`}>
                                  {diagnosisTypeLabel(diag)}
                                </span>
                              </div>
                              {diag.type === "manual" && (
                                <button
                                  type="button"
                                  onClick={() => setDiagnosedHoldings(prev => prev.filter(item => item.code !== diag.code))}
                                  className="text-[10px] text-slate-500 hover:text-rose-300 transition"
                                >
                                  移除
                                </button>
                              )}
                            </div>
                            
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div>
                                <label className="text-[9px] text-slate-500 uppercase block tracking-wider mb-1">客观判断</label>
                                <select 
                                  value={diag.judgment} 
                                  onChange={(e) => {
                                    const updated = [...diagnosedHoldings];
                                    updated[idx].judgment = e.target.value;
                                    setDiagnosedHoldings(updated);
                                  }}
                                  className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-xs text-slate-300 focus:outline-none"
                                >
                                  <option value="第三方客观评估：买点完好，无理由坚定持有">买点成立，生命线支撑有力，持有</option>
                                  <option value="第三方客观评估：破位跌破5日线，必须割肉清仓">已经破位MA5，必须清仓割肉</option>
                                  <option value="第三方客观评估：未有跌破但三天未冲高，应微亏调仓">连续3日未收回，符合时间淘汰机制，退出</option>
                                  <option value="第三方客观评估：距均线乖离过大，看分批止盈锁定盈利">乖离过大远离MA5，分批止盈锁定浮盈</option>
                                </select>
                              </div>

                              <div>
                                <label className="text-[9px] text-slate-500 uppercase block tracking-wider mb-1">明日执行指令</label>
                                <input 
                                  type="text"
                                  value={diag.actionPlan}
                                  onChange={(e) => {
                                    const updated = [...diagnosedHoldings];
                                    updated[idx].actionPlan = e.target.value;
                                    setDiagnosedHoldings(updated);
                                  }}
                                  placeholder="例如: 9:35破5日线无承接必须退出，不抱幻想"
                                  className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-2 text-xs text-slate-300 focus:outline-none"
                                />
                              </div>
                            </div>

                            <div>
                              <label className="text-[9px] text-slate-500 uppercase block tracking-wider mb-1">手写诊断</label>
                              <textarea
                                value={diag.notes || ""}
                                onChange={(e) => {
                                  const updated = [...diagnosedHoldings];
                                  updated[idx].notes = e.target.value;
                                  setDiagnosedHoldings(updated);
                                }}
                                rows={2}
                                placeholder="写下该股的回踩、承接、卖出纪律或情绪偏差。"
                                className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-xs text-slate-300 focus:outline-none leading-relaxed"
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  {renderReviewNavFooter("sector", "action", "进入最后一步：纠错自省归档")}
                </div>
              )}

              {/* 子视图 5: 纠错自省归档 */}
              {activeReviewSubTab === "action" && (
                <div className="space-y-6 animate-fade-in">
                  <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_0.85fr] gap-6 items-start">
                    <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg space-y-5">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-800 pb-3">
                        <div className="flex items-center gap-2">
                          <BookOpen className="h-4 w-4 text-cyan-400" />
                          <div>
                            <h3 className="text-xs font-black uppercase text-slate-200 tracking-wider">步骤 5：纠错自省归档</h3>
                            <CardText className="text-[11px] text-slate-500 mt-0.5">最后只写反思与明日计划，前四步会作为完整快照一起保存。</CardText>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={syncReportDraftFromReview}
                          className="px-3 py-2 bg-cyan-950/60 hover:bg-cyan-900/70 text-cyan-300 border border-cyan-800/60 rounded-lg text-[11px] font-black transition flex items-center justify-center gap-1.5"
                        >
                          <Sparkles className="h-3.5 w-3.5" />
                          <span>一键同步前四步</span>
                        </button>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">复盘时间维度</label>
                          <div className="flex bg-slate-950 p-1 rounded border border-slate-800 mt-1">
                            {(["daily", "weekly", "monthly"] as const).map(t => (
                              <button
                                key={t}
                                onClick={() => setReviewType(t)}
                                className={`flex-1 py-1.5 text-[10px] font-bold rounded transition ${reviewType === t ? "bg-slate-800 text-cyan-400" : "text-slate-500 hover:text-slate-300"}`}
                              >
                                {t === "daily" ? "日报" : t === "weekly" ? "周报" : "月报"}
                              </button>
                            ))}
                          </div>
                        </div>

                        <div>
                          <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">复盘参考日期</label>
                          <input
                            type="date"
                            value={reportDate}
                            onChange={(e) => setReportDate(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs font-mono text-slate-300 mt-1 focus:outline-none focus:border-cyan-500"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div>
                          <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">卖出纪律</label>
                          <select
                            value={sellCompliant}
                            onChange={(e) => setSellCompliant(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 mt-1 focus:outline-none focus:border-cyan-500"
                          >
                            <option value="符合模式">符合模式</option>
                            <option value="执行偏慢">执行偏慢</option>
                            <option value="存在幻想扛单">存在幻想扛单</option>
                            <option value="止盈过早">止盈过早</option>
                          </select>
                        </div>
                        <div className="md:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div>
                            <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">盈利经验</label>
                            <input
                              value={profitExperience}
                              onChange={(e) => setProfitExperience(e.target.value)}
                              placeholder="赚钱来自哪条纪律？"
                              className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 mt-1 focus:outline-none focus:border-cyan-500"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">亏损分析</label>
                            <input
                              value={lossAnalysis}
                              onChange={(e) => setLossAnalysis(e.target.value)}
                              placeholder="亏损来自哪条偏差？"
                              className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 mt-1 focus:outline-none focus:border-cyan-500"
                            />
                          </div>
                        </div>
                      </div>

                      <div>
                        <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">纠错自省日报</label>
                        <textarea
                          rows={10}
                          value={reportSummary}
                          onChange={(e) => setReportSummary(e.target.value)}
                          placeholder="写今天最重要的偏差：有没有临时起意、追涨、扛单、止盈犹豫、违反MA5纪律。"
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-300 mt-1 focus:outline-none focus:border-cyan-500 leading-relaxed"
                        />
                      </div>

                      <div>
                        <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">明日计划</label>
                        <textarea
                          rows={5}
                          value={reportPlan}
                          onChange={(e) => setReportPlan(e.target.value)}
                          placeholder="写明日只允许观察的对象、买入等待位置、持仓破位后的清仓计划。"
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-300 mt-1 focus:outline-none focus:border-cyan-500 leading-relaxed"
                        />
                      </div>

                      <button
                        onClick={handleSaveReport}
                        className="w-full py-3 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white font-black text-xs rounded-lg transition shadow-md"
                      >
                        保存并合成今日总日报
                      </button>
                    </div>

                    <div className="space-y-4">
                      <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg space-y-4">
                        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                          <div className="flex items-center gap-2">
                            <Sparkles className="h-4 w-4 text-cyan-400" />
                            <h3 className="text-xs font-black uppercase text-slate-200 tracking-wider">归档快照</h3>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">{reportDate}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3">
                            <span className="text-[9px] text-slate-500 block">交易流水</span>
                            <span className="text-sm font-black text-slate-200 font-mono">{trades.filter(t => t.date === reportDate).length} 条</span>
                          </div>
                          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3">
                            <span className="text-[9px] text-slate-500 block">自我诊断</span>
                            <span className="text-sm font-black text-cyan-300 font-mono">{diagnosedHoldings.length} 条</span>
                          </div>
                          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3">
                            <span className="text-[9px] text-slate-500 block">扫描结果</span>
                            <span className="text-sm font-black text-slate-200 font-mono">{step1Screened.length + step2Screened.length + step3Screened.length} 只</span>
                          </div>
                          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3">
                            <span className="text-[9px] text-slate-500 block">当前持仓</span>
                            <span className="text-sm font-black text-slate-200 font-mono">{positions.length} 只</span>
                          </div>
                        </div>
                        <CardText as="div" className="bg-cyan-950/10 border border-cyan-900/30 rounded-lg p-3 text-[11px] text-slate-400 leading-relaxed">
                          JSON 会保存完整数组；Markdown 只摘要扫描前10只，便于阅读。
                        </CardText>
                      </div>

                      <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg space-y-4">
                        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                          <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4 text-cyan-400" />
                            <h3 className="text-xs font-black uppercase text-slate-200 tracking-wider">
                              历史{reviewType === "daily" ? "日" : reviewType === "weekly" ? "周" : "月"}报
                            </h3>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">{reportsList.length} 篇</span>
                        </div>

                        <div className="space-y-3 max-h-[360px] overflow-y-auto pr-1">
                          {reportsList.length === 0 ? (
                            <CardText as="div" className="p-8 text-center text-slate-500 italic bg-slate-950 rounded-lg border border-slate-800/40 text-xs">
                              暂无任何历史复盘记录。
                            </CardText>
                          ) : (
                            reportsList.map(rep => (
                              <div key={rep.id} className="bg-slate-950 border border-slate-800/60 p-3 rounded-lg space-y-2">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <span className="text-xs font-bold font-mono text-cyan-400 flex items-center gap-1.5">
                                    <Calendar className="h-3.5 w-3.5" />
                                    <span>{rep.date}</span>
                                  </span>
                                  <span className={`text-[10px] font-bold font-mono ${rep.realizedPnL >= 0 ? "text-rose-400" : "text-emerald-400"}`}>
                                    {rep.realizedPnL >= 0 ? "+" : ""}{rep.realizedPnL.toLocaleString()}
                                  </span>
                                </div>
                                <div className="grid grid-cols-3 gap-2 text-center">
                                  <div className="bg-slate-900/60 rounded border border-slate-800 p-2">
                                    <span className="text-[9px] text-slate-500 block">买/卖</span>
                                    <span className="text-[11px] font-bold text-slate-300">{rep.buyCount}/{rep.sellCount}</span>
                                  </div>
                                  <div className="bg-slate-900/60 rounded border border-slate-800 p-2">
                                    <span className="text-[9px] text-slate-500 block">合规</span>
                                    <span className="text-[11px] font-bold text-cyan-300">{rep.ruleComplianceRate}%</span>
                                  </div>
                                  <div className="bg-slate-900/60 rounded border border-slate-800 p-2">
                                    <span className="text-[9px] text-slate-500 block">风险</span>
                                    <span className="text-[11px] font-bold text-slate-300">{(rep.portfolioRisk || "").split(" ")[0] || "-"}</span>
                                  </div>
                                </div>
                                <CardText className="text-[11px] text-slate-400 leading-relaxed max-h-16 overflow-hidden whitespace-pre-wrap">{rep.summary}</CardText>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {renderReviewNavFooter("stock", null)}
                </div>
              )}

            </div>
          )}

          {/* TAB 6: 账户系统设置 */}
          {activeTab === "settings" && (
            <div className="max-w-2xl mx-auto space-y-6">
              
              <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-4">
                <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
                  <Coins className="h-4 w-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-slate-200">
                    {currentMode === "real" ? "实盘交易费用口径配置" : "模拟交易费用口径配置"}
                  </h3>
                </div>

                <div className="p-3 bg-slate-950 border border-slate-800 rounded text-xs text-slate-300 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <span className="font-bold">{feeSettingsLabel(feeSettings, currentMode)}</span>
                  <span className="font-mono text-slate-500">
                    佣金 {percentFeeLabel(feeSettings.commissionRate)} / 最低 {feeSettings.minCommission.toFixed(2)} / 印花税 {percentFeeLabel(feeSettings.stampDutyRate)} / 过户费 {percentFeeLabel(feeSettings.transferFeeRate)}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-1">券商佣金比例 (双向收取)</label>
                    <input
                      type="number"
                      step="0.0001"
                      value={feeSettings.commissionRate}
                      onChange={(e) => setFeeSettings(p => feeSettingsWithValue(p, "commissionRate", Number(e.target.value)))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs font-mono text-slate-300 disabled:text-slate-600 disabled:cursor-not-allowed focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-[10px] text-slate-500 block mt-1">例如: 0.0003 代表万分之三</span>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-1">单笔佣金最低起征点 (元)</label>
                    <input
                      type="number"
                      step="1"
                      value={feeSettings.minCommission}
                      onChange={(e) => setFeeSettings(p => feeSettingsWithValue(p, "minCommission", Number(e.target.value)))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs font-mono text-slate-300 disabled:text-slate-600 disabled:cursor-not-allowed focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-[10px] text-slate-500 block mt-1">不足此金额按此值收取 (标准 A股 为 5.0)</span>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-1">印花税比例 (仅在卖出收取)</label>
                    <input
                      type="number"
                      step="0.0001"
                      value={feeSettings.stampDutyRate}
                      onChange={(e) => setFeeSettings(p => feeSettingsWithValue(p, "stampDutyRate", Number(e.target.value)))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs font-mono text-slate-300 disabled:text-slate-600 disabled:cursor-not-allowed focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-[10px] text-slate-500 block mt-1">例如: 0.0005 代表千分之零点五</span>
                  </div>

                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-1">过户费比例 (双向收取)</label>
                    <input
                      type="number"
                      step="0.00001"
                      value={feeSettings.transferFeeRate}
                      onChange={(e) => setFeeSettings(p => feeSettingsWithValue(p, "transferFeeRate", Number(e.target.value)))}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs font-mono text-slate-300 disabled:text-slate-600 disabled:cursor-not-allowed focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-[10px] text-slate-500 block mt-1">例如: 0.00001 代表十万分之一</span>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-end gap-2 pt-2 border-t border-slate-800/60">
                  <button
                    onClick={() => handleRecalculateFees(false)}
                    className="inline-flex items-center justify-center gap-1.5 px-4 py-2 bg-slate-950 hover:bg-slate-900 border border-slate-700 text-slate-300 rounded text-xs font-semibold transition"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    <span>按当前配置重算历史交易费用</span>
                  </button>
                  <button
                    onClick={() => handleSaveFees(feeSettings)}
                    className="px-4 py-2 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white rounded text-xs font-semibold shadow transition"
                  >
                    保存当前模式费用口径
                  </button>
                </div>
              </div>

              <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-4">
                <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
                  <Settings className="h-4 w-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-slate-200">
                    {currentMode === "real" ? "实盘交易账户设置" : "模拟交易账户设置"}
                  </h3>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="text-xs font-bold text-slate-300 block mb-1">
                      {currentMode === "real" ? "调整实盘初始总本金 (元)" : "调整模拟初始总本金 (元)"}
                    </label>
                    <CardText className="text-[10px] text-slate-500 mb-2">
                      {currentMode === "real" 
                        ? "更改后，系统的实盘可用现金与实盘已实现盈亏将根据您的实盘交易历史重新计算。" 
                        : "更改后，系统的模拟可用现金与模拟已实现盈亏将根据您的模拟交易历史重新计算。"}
                    </CardText>
                    <div className="flex space-x-2">
                      <input
                        type="number"
                        value={accountState.initialCash}
                        readOnly
                        className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs font-mono text-slate-400 focus:outline-none"
                      />
                      <button
                        onClick={handleResetCash}
                        className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold"
                      >
                        手动修改
                      </button>
                    </div>
                  </div>

                  <div className="border-t border-slate-800 pt-4">
                    <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">文件与数据同步校验</h4>
                    <div className="bg-slate-950 p-4 rounded border border-slate-850 font-mono text-xs space-y-2 text-slate-400">
                      <div><span className="text-slate-500">Watchlist文件：</span>data/watchlist.csv</div>
                      <div><span className="text-slate-500">交易流水文件：</span>data/trades/trade_log.csv</div>
                      <div><span className="text-slate-500">历史均线缓存：</span>data/history/*.csv (个股历史K线)</div>
                      <div><span className="text-slate-500">报告归档位置：</span>data/reports/*</div>
                      <div><span className="text-slate-500">自动备份地址：</span>data/backups/ (写入前自动触发)</div>
                    </div>
                  </div>

                  <div className="border-t border-slate-800 pt-4 flex space-x-3">
                    <button
                      onClick={() => {
                        if (confirm("是否清空所有自选股票并重置股票池？")) {
                          fetch("/api/watchlist/generate", { method: "POST" })
                            .then(() => {
                              logAction("⚙️ 系统数据初始化完成！");
                              loadAllData();
                            });
                        }
                      }}
                      className="px-3.5 py-2 bg-slate-800 hover:bg-rose-950/40 text-slate-400 hover:text-rose-300 border border-slate-700 hover:border-rose-900 rounded text-xs font-semibold transition"
                    >
                      恢复股票自选池
                    </button>
                    <button
                      onClick={() => {
                        if (confirm("这会清空你所有的交易流水，确认彻底重置资产和账户流水吗？")) {
                          fetch("/api/trades/delete", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ id: "ALL", mode: currentMode })
                          }).finally(() => {
                            logAction("⚙️ 账户数据已重置。");
                            loadAllData();
                          });
                        }
                      }}
                      className="px-3.5 py-2 bg-slate-800 hover:bg-rose-950/40 text-slate-400 hover:text-rose-300 border border-slate-700 hover:border-rose-900 rounded text-xs font-semibold transition"
                    >
                      清空交易流水
                    </button>
                  </div>

                </div>
              </div>

            </div>
          )}

        </main>
      </div>

      {/* 交易确认及纪律合规模态框 (Modal) */}
      {showTradeModal && tradeTarget && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-lg w-full p-6 space-y-4 shadow-2xl overflow-y-auto max-h-[90vh]">
            
            {/* 头 */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-200">
                录入{tradeType === "BUY" ? "买入" : "卖出"}交易记录 ({tradeTarget.name})
              </h3>
              <button
                onClick={() => setShowTradeModal(false)}
                className="text-slate-500 hover:text-slate-300"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            {/* 极简实时纪律审计指示灯 */}
            {tradeType === "BUY" && (
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-850 space-y-2">
                <span className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">实时纪律雷达监控</span>
                
                {/* 板块/大阳线/MA5 诊断 */}
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${isMainBoard(tradeTarget.code) ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                    <span className="text-slate-400">沪深主板: {isMainBoard(tradeTarget.code) ? "满足" : "不符"}</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${tradeTarget.bigCandlePct >= 5.0 ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                    <span className="text-slate-400">20日大阳: {tradeTarget.bigCandlePct >= 5.0 ? "有" : "无"}</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${tradeTarget.ma5Upward ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                    <span className="text-slate-400">MA5向上: {tradeTarget.ma5Upward ? "满足" : "不符"}</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${tradeDeviationAtPrice >= tradingRules.buyZone.minDeviationPct && tradeDeviationAtPrice <= tradingRules.buyZone.maxDeviationPct ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                    <span className="text-slate-400">{tradingRules.buyZone.minDeviationPct}%~{tradingRules.buyZone.maxDeviationPct}%偏离: {tradeDeviationAtPrice >= tradingRules.buyZone.minDeviationPct && tradeDeviationAtPrice <= tradingRules.buyZone.maxDeviationPct ? "满足" : "不符"}</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${currentInBuyWindow ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                    <span className="text-slate-400">买入窗口: {currentInBuyWindow ? "允许" : "不在窗口"}</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${accountState.availableCash >= tradePrice * tradingRules.lotSize ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                    <span className="text-slate-400">资金一手: {accountState.availableCash >= tradePrice * tradingRules.lotSize ? "满足" : "不足"}</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${buyRiskAmount > 0 && buyRiskAmount <= maxAllowedRiskAmount ? "bg-rose-500" : "bg-emerald-500"}`}></span>
                    <span className="text-slate-400">单笔风险: {buyRiskAmount.toFixed(2)} / {maxAllowedRiskAmount.toFixed(2)}</span>
                  </div>
                </div>

                {/* 违规警告 */}
                {buyFormHasHardRisk && (
                  <CardText className="text-[10px] text-amber-500 italic leading-normal border-t border-slate-900 pt-1.5">
                    警告：当前录入数据存在买入纪律风险（买入窗口、资金一手、0%~2.5%偏离、系统性风险或单笔2%本金风险未通过）。继续录入将产生审计标签。
                  </CardText>
                )}
              </div>
            )}

            {/* 交易录入表单 */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易方向</label>
                <div className="flex bg-slate-950 p-1 rounded border border-slate-800 mt-1">
                  <button
                    onClick={() => setTradeType("BUY")}
                    className={`flex-1 py-1 text-xs font-bold rounded transition ${tradeType === "BUY" ? "bg-rose-950 text-rose-400" : "text-slate-500"}`}
                  >
                    买入 (BUY)
                  </button>
                  <button
                    onClick={() => setTradeType("SELL")}
                    className={`flex-1 py-1 text-xs font-bold rounded transition ${tradeType === "SELL" ? "bg-emerald-950 text-emerald-400" : "text-slate-500"}`}
                  >
                    卖出 (SELL)
                  </button>
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易价格 (元)</label>
                <input
                  type="number"
                  step="0.01"
                  value={tradePrice}
                  onChange={(e) => setTradePrice(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs font-mono text-slate-200 mt-1 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易数量 (股)</label>
                <input
                  type="number"
                  step="100"
                  max={tradeType === "SELL" && activeAvailableQuantity > 0 ? activeAvailableQuantity : undefined}
                  value={tradeQuantity}
                  onChange={(e) => {
                    const nextQuantity = Number(e.target.value);
                    setTradeQuantity(
                      tradeType === "SELL" && activeAvailableQuantity > 0
                        ? Math.min(nextQuantity, activeAvailableQuantity)
                        : nextQuantity
                    );
                  }}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs font-mono text-slate-200 mt-1 focus:outline-none focus:border-cyan-500"
                />
                {tradeType === "SELL" && activeTradePosition && (
                  <CardText className="text-[10px] text-slate-500 mt-1">
                    当前持有 {activeTradePosition.quantity} 股，可卖 {activeAvailableQuantity} 股
                  </CardText>
                )}
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">一手价格合计</label>
                <div className="p-2 bg-slate-950 rounded border border-slate-800 mt-1 text-xs font-mono font-bold text-slate-300">
                  {(tradePrice * tradeQuantity).toLocaleString(undefined, { minimumFractionDigits: 2 })} 元
                </div>
              </div>
            </div>

            {/* 预计税费卡片 */}
            <div className="bg-slate-950 p-3 rounded border border-slate-850 text-[10px] font-mono text-slate-500 space-y-1">
              <div className="flex justify-between text-slate-400 font-bold">
                <span>费用口径:</span>
                <span>{feeSettingsLabel(feeSettings, currentMode)}</span>
              </div>
              <div className="flex justify-between">
                <span>印花税 ({percentFeeLabel(feeSettings.stampDutyRate)}, 仅卖出):</span>
                <span>{est.stamp.toFixed(2)} 元</span>
              </div>
              <div className="flex justify-between">
                <span>券商佣金 ({percentFeeLabel(feeSettings.commissionRate)}, 最低{feeSettings.minCommission.toFixed(2)}元):</span>
                <span>{est.comm.toFixed(2)} 元</span>
              </div>
              <div className="flex justify-between">
                <span>过户费 ({percentFeeLabel(feeSettings.transferFeeRate)}):</span>
                <span>{est.trans.toFixed(2)} 元</span>
              </div>
              <div className="flex justify-between border-t border-slate-900 pt-1 text-slate-400 font-bold">
                <span>预计净结算金额 ({tradeType === "BUY" ? "实际付出" : "实际到账"}):</span>
                <span className={tradeType === "BUY" ? "text-rose-400" : "text-emerald-400"}>
                  {est.settle.toLocaleString(undefined, { minimumFractionDigits: 2 })} 元
                </span>
              </div>
              {tradeType === "BUY" && (
                <div className="flex justify-between border-t border-slate-900 pt-1 text-slate-400 font-bold">
                  <span>预估止损亏损 / 本金2%上限:</span>
                  <span className={buyRiskAmount <= maxAllowedRiskAmount && buyRiskAmount > 0 ? "text-cyan-300" : "text-amber-300"}>
                    {buyRiskAmount.toFixed(2)} / {maxAllowedRiskAmount.toFixed(2)} 元 ({buyRiskPct.toFixed(2)}%)
                  </span>
                </div>
              )}
            </div>

            {/* 强制反思书写 */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">
                操盘原因与决策证据 (纪律约束：拒绝临时意念下单)
              </label>
              <textarea
                rows={2}
                value={tradeReason}
                onChange={(e) => setTradeReason(e.target.value)}
                placeholder="为什么买/卖它？5日线偏离度是多少？是否符合大阳拉升？如果是违规买入，请写下原因反思..."
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 focus:outline-none focus:border-cyan-500 leading-normal"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">流水备注 (备用)</label>
              <input
                type="text"
                value={tradeRemark}
                onChange={(e) => setTradeRemark(e.target.value)}
                placeholder="实盘/模拟 归档单号等备注"
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* 执行 */}
            <button
              onClick={handleExecuteTrade}
              disabled={buyFormHasHardRisk}
              className="w-full py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed text-white font-bold text-xs rounded transition shadow"
            >
              {buyFormHasHardRisk ? "买入硬约束未通过" : "确认并录入交易账簿"}
            </button>

          </div>
        </div>
      )}

      {/* 编辑交易记录模态框 */}
      {editingTrade && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-lg w-full p-6 space-y-4 shadow-2xl overflow-y-auto max-h-[90vh]">
            
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-200">
                编辑交易流水记录 (ID: {editingTrade.id.substring(0, 8)}...)
              </h3>
              <button
                onClick={() => setEditingTrade(null)}
                className="text-slate-500 hover:text-slate-300"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">代码/名称</label>
                <div className="p-2 bg-slate-950 rounded border border-slate-850 mt-1 text-xs text-slate-400 font-mono font-bold">
                  {editingTrade.code} - {editingTrade.name} ({editingTrade.type === "BUY" ? "买入" : "卖出"})
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易时间</label>
                <div className="flex space-x-1.5 mt-1">
                  <input
                    type="date"
                    value={editDate}
                    onChange={(e) => setEditDate(e.target.value)}
                    className="flex-1 bg-slate-950 border border-slate-850 rounded p-1.5 text-xs font-mono text-slate-200 focus:outline-none"
                  />
                  <input
                    type="text"
                    value={editTime}
                    onChange={(e) => setEditTime(e.target.value)}
                    placeholder="14:30:00"
                    className="w-24 bg-slate-950 border border-slate-850 rounded p-1.5 text-xs font-mono text-slate-200 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易价格 (元)</label>
                <input
                  type="number"
                  step="0.01"
                  value={editPrice}
                  onChange={(e) => {
                    const price = Number(e.target.value);
                    setEditPrice(price);
                    const fees = calculateFeeBreakdown(editingTrade?.type || "BUY", price, editQuantity);
                    setEditCommission(fees.comm);
                    setEditTransferFee(fees.trans);
                    setEditStampDuty(fees.stamp);
                  }}
                  className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs font-mono text-slate-200 mt-1 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase block tracking-wider">交易数量 (股)</label>
                <input
                  type="number"
                  step="100"
                  value={editQuantity}
                  onChange={(e) => {
                    const qty = Number(e.target.value);
                    setEditQuantity(qty);
                    const fees = calculateFeeBreakdown(editingTrade?.type || "BUY", editPrice, qty);
                    setEditCommission(fees.comm);
                    setEditTransferFee(fees.trans);
                    setEditStampDuty(fees.stamp);
                  }}
                  className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs font-mono text-slate-200 mt-1 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            {/* 编辑税费细分费用 */}
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-850 space-y-3">
              <span className="text-[10px] font-bold text-slate-400 uppercase block tracking-wider">
                手续费细目预览 (保存时后端按当前费用口径重新计算)
              </span>
              
              <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                <div>
                  <label className="text-[9px] text-slate-500 block">券商佣金 (元)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editCommission}
                    disabled
                    onChange={(e) => setEditCommission(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-[11px] text-slate-500 mt-1 disabled:cursor-not-allowed focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-[9px] text-slate-500 block">印花税 (元)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editStampDuty}
                    disabled
                    onChange={(e) => setEditStampDuty(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-[11px] text-slate-500 mt-1 disabled:cursor-not-allowed focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-[9px] text-slate-500 block">过户费 (元)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editTransferFee}
                    disabled
                    onChange={(e) => setEditTransferFee(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-[11px] text-slate-500 mt-1 disabled:cursor-not-allowed focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-between border-t border-slate-900 pt-2 text-[11px] font-mono font-bold text-slate-300">
                <span>总交易费用预览:</span>
                <span className="text-cyan-400 font-mono">
                  {(Number(editCommission) + Number(editStampDuty) + Number(editTransferFee)).toFixed(2)} 元
                </span>
              </div>
            </div>

            {/* 编辑审计属性与违规标签 */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold text-slate-500 block tracking-wider mb-1">纪律审计结论</label>
                <select
                  value={editRulesConclusion}
                  onChange={(e) => setEditRulesConclusion(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="符合规则">符合规则 (合规交易)</option>
                  <option value="违规交易">违规交易 (违纪操作)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-500 block tracking-wider mb-1">违纪标签 (逗号分隔)</label>
                <input
                  type="text"
                  value={editViolationTags.join(", ")}
                  onChange={(e) => setEditViolationTags(e.target.value.split(",").map(x => x.trim()).filter(Boolean))}
                  placeholder="无违纪 (或写未向上买入,偏离度过高等)"
                  className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            {/* 反思原因 */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 block tracking-wider">交易因由决策反思 (纠错重点)</label>
              <textarea
                rows={2}
                value={editReason}
                onChange={(e) => setEditReason(e.target.value)}
                className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs text-slate-300 focus:outline-none focus:border-cyan-500 leading-normal"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 block tracking-wider">流水备注</label>
              <input
                type="text"
                value={editRemark}
                onChange={(e) => setEditRemark(e.target.value)}
                className="w-full bg-slate-950 border border-slate-850 rounded p-2 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <button
              onClick={handleUpdateTrade}
              className="w-full py-2 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white font-bold text-xs rounded transition shadow"
            >
              保存修改并实时重算持仓账目
            </button>

          </div>
        </div>
      )}

    </div>
  );
}
