import type {
  AccountMode,
  CandidateEvent,
  HealthPayload,
  HistoryJob,
  ReportRecord,
  ReviewContext,
  RuleConfig,
  SettingsPayload,
  TodayReview,
  TradeLog,
  WorkbenchPayload,
} from "../types";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function query(params: Record<string, string | number | boolean | undefined | null> = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const out = search.toString();
  return out ? `?${out}` : "";
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers:
      options.body instanceof FormData || options.body instanceof Blob || options.body instanceof ArrayBuffer
        ? options.headers
        : { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text().catch(() => "");
  if (!response.ok) {
    const message =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail?: unknown }).detail || `请求失败 ${response.status}`)
        : `请求失败 ${response.status}`;
    throw new ApiError(message, response.status, body);
  }
  return body as T;
}

export interface TradeInput {
  code: string;
  name: string;
  type: "BUY" | "SELL";
  price: number;
  quantity: number;
  date?: string;
  time?: string;
  reason?: string;
  remark?: string;
  manualConfirmed?: boolean;
  mode?: AccountMode;
  historicalBackfill?: boolean;
}

export interface TradeUpdateInput extends Partial<TradeInput> {
  id?: string;
  rulesConclusion?: TradeLog["rulesConclusion"];
  violationTags?: string[];
  commission?: number;
  stampDuty?: number;
  transferFee?: number;
  totalFee?: number;
  manualFeeOverride?: boolean;
}

export const api = {
  health: () => request<HealthPayload>("/api/health"),
  rules: () => request<{ config: RuleConfig }>("/api/rules"),
  latestSelection: () => request<WorkbenchPayload>("/api/selection/official/latest"),
  candidates: () => request<{ candidates: WorkbenchPayload["observationPool"] }>("/api/candidates"),
  candidateEvents: (candidateId: string) =>
    request<{ events: CandidateEvent[] }>(`/api/candidates/${encodeURIComponent(candidateId)}/events`),
  cancelCandidate: (candidateId: string, reason: string) =>
    request<{ success: boolean }>(`/api/candidates/${encodeURIComponent(candidateId)}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  generateOfficial: (force = false) =>
    request<WorkbenchPayload>("/api/selection/official/generate", {
      method: "POST",
      body: JSON.stringify({ force }),
    }),
  previewSelection: () => request<WorkbenchPayload>("/api/selection/preview"),
  importSelection: (file: File, options: { asOfficial: boolean; fetchHistory: boolean; selectionDate?: string }) => {
    const search = query({
      filename: file.name,
      asOfficial: options.asOfficial,
      fetchHistory: options.fetchHistory,
      selectionDate: options.selectionDate,
    });
    return request<WorkbenchPayload>(`/api/selection/import${search}`, {
      method: "POST",
      headers: { "x-filename": encodeURIComponent(file.name) },
      body: file,
    });
  },
  refreshQuotes: () =>
    request<WorkbenchPayload>("/api/watchlist/refresh-quotes", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  portfolio: (mode?: AccountMode) => request<WorkbenchPayload>(`/api/portfolio${query({ mode })}`),
  trades: (mode?: AccountMode) => request<{ list: TradeLog[] }>(`/api/trades${query({ mode })}`),
  createTrade: (payload: TradeInput) =>
    request<{ success: boolean; trade: TradeLog }>("/api/trades", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateTrade: (tradeId: string, payload: TradeUpdateInput) =>
    request<{ success: boolean; trade: TradeLog }>(`/api/trades/${encodeURIComponent(tradeId)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteTrade: (tradeId: string, mode?: AccountMode) =>
    request<{ success: boolean }>(`/api/trades/${encodeURIComponent(tradeId)}${query({ mode })}`, {
      method: "DELETE",
    }),
  recalculateFees: (mode?: AccountMode) =>
    request<{ success: boolean; updatedCount: number; trades: TradeLog[]; accountState: WorkbenchPayload["accountState"] }>(
      `/api/trades/recalculate-fees${query({ mode })}`,
      { method: "POST", body: JSON.stringify({}) },
    ),
  deferExit: (code: string, payload: { buyDate?: string; reason?: string; mode?: AccountMode }) =>
    request<{ success: boolean; decision: { deferReason: string; decisionTime: string } }>(
      `/api/positions/${encodeURIComponent(code)}/defer-exit`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  settings: () => request<SettingsPayload>("/api/settings"),
  updateSettings: (payload: SettingsPayload) =>
    request<SettingsPayload>("/api/settings", { method: "POST", body: JSON.stringify(payload) }),
  fetchHistory: (code?: string) =>
    request<{ success: boolean; message?: string; fetched?: number; failed?: number; results?: Record<string, unknown> }>(
      "/api/watchlist/fetch-history",
      { method: "POST", body: JSON.stringify(code ? { code } : {}) },
    ),
  startHistoryJob: () =>
    request<HistoryJob>("/api/watchlist/history-jobs", { method: "POST", body: JSON.stringify({}) }),
  historyJob: (jobId: string) => request<HistoryJob>(`/api/watchlist/history-jobs/${encodeURIComponent(jobId)}`),
  reviewToday: (mode?: AccountMode) => request<TodayReview>(`/api/review/today${query({ mode })}`),
  reviewContext: (mode?: AccountMode) => request<ReviewContext>(`/api/reports/context${query({ mode })}`),
  reports: (type: "daily" | "weekly" | "monthly") =>
    request<{ reports: ReportRecord[] }>(`/api/reports/list${query({ type })}`),
  saveReport: (payload: ReportRecord) =>
    request<{ success: boolean; report: ReportRecord; jsonPath: string; mdPath: string }>("/api/reports/save", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
