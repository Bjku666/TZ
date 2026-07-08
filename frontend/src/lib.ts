import type { Mode } from "./types";

export const today = () => new Date().toISOString().slice(0, 10);
export const nowTime = () => new Date().toTimeString().slice(0, 5);
export const money = (value: number) => Number(value || 0).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const tone = (value: number) => value >= 0 ? "text-rose-400" : "text-emerald-400";

export async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { ...init, headers: { "Content-Type": "application/json", ...(init.headers || {}) } });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail || `请求失败 ${response.status}`);
  return body as T;
}
export const apiPath = (mode: Mode, suffix: string) => `/api/accounts/${mode}${suffix}`;
