import { useCallback, useMemo, useState } from "react";
import type { ActivityEntry } from "../types";

const MAX_ENTRIES = 120;

function initialEntries(): ActivityEntry[] {
  return [
    {
      id: "boot",
      kind: "info",
      title: "工作台已启动",
      detail: "等待后端真实数据加载",
      time: new Date().toISOString(),
    },
  ];
}

export function useActivityLog() {
  const [entries, setEntries] = useState<ActivityEntry[]>(initialEntries);

  const add = useCallback((entry: Omit<ActivityEntry, "id" | "time"> & { id?: string; time?: string }) => {
    const next: ActivityEntry = {
      id: entry.id || `${Date.now()}_${Math.random().toString(36).slice(2)}`,
      time: entry.time || new Date().toISOString(),
      kind: entry.kind,
      title: entry.title,
      detail: entry.detail,
      source: entry.source,
    };
    setEntries(current => [next, ...current.filter(item => item.id !== next.id)].slice(0, MAX_ENTRIES));
  }, []);

  const addMany = useCallback((items: ActivityEntry[]) => {
    setEntries(current => {
      const existing = new Set(current.map(item => item.id));
      const fresh = items.filter(item => !existing.has(item.id));
      return [...fresh, ...current].slice(0, MAX_ENTRIES);
    });
  }, []);

  const clear = useCallback(() => setEntries([]), []);

  return useMemo(() => ({ entries, add, addMany, clear }), [add, addMany, clear, entries]);
}
