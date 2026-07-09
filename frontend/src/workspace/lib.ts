import type { Mode, StrategyId, StrategyMode } from "./types";

export const defaultStrategies: StrategyMode[] = [
  {
    id: "ma5_pullback",
    name: "五日线回踩",
    description: "当前系统原有交易纪律模式",
    ruleStatus: "已启用",
    buyRuleSummary: "100 股整数倍、可用资金充足，并限制在 09:30-10:00 或 14:30-15:00 买入窗口。",
    positionRuleSummary: "T+1 锁定后进入次日观察，10:00 处理；可明确延迟至 14:30 尾盘。",
    reviewFocus: "计划依据、执行偏差、结果情绪、下一交易日硬规则。",
  },
  {
    id: "mode2",
    name: "模式2",
    description: "规则名称与交易纪律待配置",
    ruleStatus: "待配置",
    buyRuleSummary: "暂只执行基础账户约束：价格有效、100 股整数倍、可用资金充足。",
    positionRuleSummary: "持仓监控策略待配置，系统先提示人工复核。",
    reviewFocus: "复盘模板先沿用通用四段式，后续可替换为模式2专用字段。",
    placeholder: true,
  },
  {
    id: "mode3",
    name: "十日线缩量回踩隔日反弹",
    description: "前期明显放量、上升趋势中缩量阴线回踩十日线，尾盘分仓买入，次日早盘利用反弹退出。",
    ruleStatus: "已启用",
    buyRuleSummary: "只在 14:50-15:00 尾盘登记买入；必须确认缩量阴线、回踩十日线、趋势未破坏、非第一根回调阴线并完成分仓。",
    positionRuleSummary: "今日买入 T+1 锁定；次日 09:25 起检查，09:45-10:00 为主要退出窗口，10:00 后需卖出或登记突破五日线延长至尾盘。",
    reviewFocus: "放量与缩量条件、14:50 后执行、分仓确认、次日退出率、10:00 前处理和超期持仓。",
    placeholder: false,
  },
];

export const normalizeStrategyId = (value: string | null | undefined): StrategyId =>
  defaultStrategies.some((item) => item.id === value) ? value as StrategyId : "ma5_pullback";

export const today = () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};
export const nowTime = () => new Date().toTimeString().slice(0, 5);
export const money = (value: number) => Number(value || 0).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const signedMoney = (value: number) => `${value >= 0 ? "+" : "-"}¥${money(Math.abs(value || 0))}`;
export const pct = (value: number) => `${value >= 0 ? "+" : ""}${Number(value || 0).toFixed(2)}%`;
export const tone = (value: number) => value >= 0 ? "text-rose-400" : "text-emerald-400";
export const bgTone = (value: number) => value >= 0 ? "bg-rose-500" : "bg-emerald-500";
export const modeLabel = (mode: Mode) => mode === "real" ? "实盘记录" : "模拟训练";
export const strategyLabel = (strategyId: StrategyId, strategies: StrategyMode[] = defaultStrategies) => strategies.find((item) => item.id === strategyId)?.name || strategyId;
export const reviewTypeLabel = (type: "daily" | "weekly" | "monthly") => type === "daily" ? "日复盘" : type === "weekly" ? "周复盘" : "月复盘";

export async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { ...init, headers: { "Content-Type": "application/json", ...(init.headers || {}) } });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail || `请求失败 ${response.status}`);
  return body as T;
}
export const apiPath = (mode: Mode, suffix: string, strategyId?: StrategyId) => {
  const path = `/api/accounts/${mode}${suffix}`;
  if (!strategyId) return path;
  const glue = path.includes("?") ? "&" : "?";
  return `${path}${glue}strategy=${encodeURIComponent(strategyId)}`;
};
