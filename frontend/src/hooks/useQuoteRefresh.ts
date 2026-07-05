import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { autoRefreshSeconds, detectMarketPhase } from "../api/adapters";
import type { MarketPhase, WorkbenchPayload } from "../types";

interface UseQuoteRefreshOptions {
  enabled: boolean;
  refresh: () => Promise<WorkbenchPayload | undefined>;
  onPaused?: (reason: string) => void;
}

export function useQuoteRefresh({ enabled, refresh, onPaused }: UseQuoteRefreshOptions) {
  const [phase, setPhase] = useState<MarketPhase>(detectMarketPhase());
  const [visible, setVisible] = useState(() => document.visibilityState === "visible");
  const [countdown, setCountdown] = useState<number | null>(null);
  const [lastAutoRefreshAt, setLastAutoRefreshAt] = useState<string>("");
  const [running, setRunning] = useState(false);
  const inFlight = useRef(false);
  const nextAt = useRef<number | null>(null);

  const intervalSeconds = useMemo(() => autoRefreshSeconds(phase), [phase]);
  const active = enabled && visible && intervalSeconds !== null;

  const runRefresh = useCallback(
    async (source: "manual" | "auto" = "manual") => {
      if (inFlight.current) return;
      inFlight.current = true;
      setRunning(true);
      try {
        await refresh();
        if (source === "auto") setLastAutoRefreshAt(new Date().toISOString());
      } finally {
        inFlight.current = false;
        setRunning(false);
        if (intervalSeconds) {
          nextAt.current = Date.now() + intervalSeconds * 1000;
          setCountdown(intervalSeconds);
        }
      }
    },
    [intervalSeconds, refresh],
  );

  useEffect(() => {
    const onVisibility = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setPhase(detectMarketPhase()), 30000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!enabled) {
      setCountdown(null);
      nextAt.current = null;
      return;
    }
    if (!visible) {
      setCountdown(null);
      nextAt.current = null;
      onPaused?.("页面隐藏，自动刷新暂停");
      return;
    }
    if (!intervalSeconds) {
      setCountdown(null);
      nextAt.current = null;
      onPaused?.("当前非连续交易刷新时段，自动实时刷新暂停");
      return;
    }
    nextAt.current = Date.now() + intervalSeconds * 1000;
    setCountdown(intervalSeconds);
  }, [enabled, intervalSeconds, onPaused, visible]);

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => {
      if (!nextAt.current) return;
      const seconds = Math.max(0, Math.ceil((nextAt.current - Date.now()) / 1000));
      setCountdown(seconds);
      if (seconds <= 0) {
        runRefresh("auto").catch(() => undefined);
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [active, runRefresh]);

  return {
    phase,
    visible,
    intervalSeconds,
    countdown,
    active,
    running,
    lastAutoRefreshAt,
    manualRefresh: () => runRefresh("manual"),
  };
}
