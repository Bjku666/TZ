import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { activityFromCandidateEvent, activityFromPayload, accountFallback, mergeWorkbenchPayload, resolveMode } from "../api/adapters";
import { api, type TradeInput, type TradeUpdateInput } from "../api/client";
import type {
  AccountMode,
  AccountState,
  ActivityEntry,
  Candidate,
  CandidateEvent,
  HealthPayload,
  HistoryJob,
  IntradayPreview,
  Position,
  ReportRecord,
  ReviewContext,
  RuleConfig,
  SelectionBatch,
  SelectionItem,
  SettingsPayload,
  Stock,
  TodayReview,
  TradeLog,
  WorkbenchPayload,
} from "../types";

const emptyPreview: IntradayPreview = {
  items: [],
  changes: { newEntries: [], dropped: [], rankUp: [], rankDown: [] },
};

interface UseWorkbenchOptions {
  addActivity?: (entry: Omit<ActivityEntry, "id" | "time"> & { id?: string; time?: string }) => void;
  addActivities?: (entries: ActivityEntry[]) => void;
}

export function useWorkbench(options: UseWorkbenchOptions = {}) {
  const { addActivity, addActivities } = options;
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [rules, setRules] = useState<RuleConfig | null>(null);
  const [settings, setSettings] = useState<SettingsPayload>({});
  const [workbench, setWorkbench] = useState<WorkbenchPayload>({
    initialPool: [],
    observationPool: [],
    buyReadyPool: [],
    positions: [],
    list: [],
  });
  const [trades, setTrades] = useState<TradeLog[]>([]);
  const [reviewContext, setReviewContext] = useState<ReviewContext | null>(null);
  const [todayReview, setTodayReview] = useState<TodayReview | null>(null);
  const [reports, setReports] = useState<Record<"daily" | "weekly" | "monthly", ReportRecord[]>>({
    daily: [],
    weekly: [],
    monthly: [],
  });
  const [candidateEvents, setCandidateEvents] = useState<Record<string, CandidateEvent[]>>({});
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [preview, setPreview] = useState<IntradayPreview>(emptyPreview);
  const [historyJob, setHistoryJob] = useState<HistoryJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestSeq = useRef(0);
  const refreshSeq = useRef(0);

  const mode = useMemo<AccountMode>(() => resolveMode(settings), [settings]);

  const initialPool = workbench.initialPool || [];
  const observationPool = workbench.observationPool || [];
  const buyReadyPool = workbench.buyReadyPool || [];
  const positions = workbench.positions || [];
  const stocks = workbench.list || [];
  const officialSelection = workbench.officialSelection || null;
  const account = workbench.accountState || accountFallback();

  const allCandidates = useMemo(() => {
    const byId = new Map<string, Candidate>();
    [...observationPool, ...buyReadyPool].forEach(item => byId.set(item.id, item));
    return Array.from(byId.values());
  }, [buyReadyPool, observationPool]);

  const selectedCandidate = useMemo(
    () => allCandidates.find(item => item.id === selectedCandidateId) || allCandidates[0] || null,
    [allCandidates, selectedCandidateId],
  );

  const selectedInitial = useMemo<SelectionItem | null>(() => {
    if (!selectedCandidate) return initialPool[0] || null;
    return initialPool.find(item => item.code === selectedCandidate.code) || null;
  }, [initialPool, selectedCandidate]);

  const reloadPortfolioAndTrades = useCallback(
    async (nextMode = mode) => {
      const [portfolioPayload, tradePayload, reviewPayload] = await Promise.all([
        api.portfolio(nextMode),
        api.trades(nextMode),
        api.reviewContext(nextMode).catch(() => null),
      ]);
      setWorkbench(current => mergeWorkbenchPayload(current, portfolioPayload));
      setTrades(tradePayload.list || []);
      if (reviewPayload) setReviewContext(reviewPayload);
    },
    [mode],
  );

  const loadAll = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(null);
    try {
      const [healthPayload, rulesPayload, selectionPayload, settingsPayload] = await Promise.all([
        api.health().catch(() => null),
        api.rules(),
        api.latestSelection(),
        api.settings(),
      ]);
      if (seq !== requestSeq.current) return;
      if (healthPayload) setHealth(healthPayload);
      setRules(rulesPayload.config);
      setSettings(settingsPayload);
      const activeMode = resolveMode(settingsPayload);
      const [portfolioPayload, tradePayload, reviewPayload, todayPayload, dailyReports, weeklyReports, monthlyReports] =
        await Promise.all([
          api.portfolio(activeMode),
          api.trades(activeMode),
          api.reviewContext(activeMode).catch(() => null),
          api.reviewToday(activeMode).catch(() => null),
          api.reports("daily").catch(() => ({ reports: [] })),
          api.reports("weekly").catch(() => ({ reports: [] })),
          api.reports("monthly").catch(() => ({ reports: [] })),
        ]);
      if (seq !== requestSeq.current) return;
      setWorkbench(mergeWorkbenchPayload(selectionPayload, portfolioPayload));
      setTrades(tradePayload.list || []);
      setReviewContext(reviewPayload);
      setTodayReview(todayPayload);
      setReports({
        daily: dailyReports.reports || [],
        weekly: weeklyReports.reports || [],
        monthly: monthlyReports.reports || [],
      });
      addActivity?.({
        kind: "success",
        title: "后端数据已加载",
        detail: `正式批次 ${selectionPayload.officialSelection?.selectionDate || "暂无"} · 交易 ${tradePayload.list?.length || 0} 条`,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "加载失败";
      setError(message);
      addActivity?.({ kind: "danger", title: "加载失败", detail: message });
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [addActivity]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (!selectedCandidate?.id || candidateEvents[selectedCandidate.id]) return;
    api
      .candidateEvents(selectedCandidate.id)
      .then(payload => {
        setCandidateEvents(current => ({ ...current, [selectedCandidate.id]: payload.events || [] }));
        addActivities?.((payload.events || []).map(activityFromCandidateEvent));
      })
      .catch(err => {
        addActivity?.({
          kind: "warning",
          title: "候选事件读取失败",
          detail: err instanceof Error ? err.message : "无法读取候选事件",
        });
      });
  }, [addActivities, addActivity, candidateEvents, selectedCandidate?.id]);

  const refreshQuotes = useCallback(async () => {
    const seq = ++refreshSeq.current;
    setBusy("refresh");
    setError(null);
    try {
      const payload = await api.refreshQuotes();
      if (seq !== refreshSeq.current) return payload;
      setWorkbench(current => mergeWorkbenchPayload(current, payload));
      addActivity?.(activityFromPayload(payload, payload.inProgress ? "行情刷新已复用进行中任务" : "行情刷新完成", "refresh"));
      return payload;
    } catch (err) {
      const message = err instanceof Error ? err.message : "行情刷新失败";
      setError(message);
      addActivity?.({ kind: "danger", title: "行情刷新失败", detail: message });
      throw err;
    } finally {
      if (seq === refreshSeq.current) setBusy(null);
    }
  }, [addActivity]);

  const generateOfficial = useCallback(async () => {
    setBusy("generate");
    try {
      const payload = await api.generateOfficial();
      setWorkbench(current => mergeWorkbenchPayload(current, payload));
      addActivity?.(activityFromPayload(payload, "正式收盘批次生成", payload.success === false ? "warning" : "success"));
      return payload;
    } finally {
      setBusy(null);
    }
  }, [addActivity]);

  const loadPreview = useCallback(async () => {
    setBusy("preview");
    try {
      const payload = await api.previewSelection();
      const nextPreview = payload.intradayPreview || emptyPreview;
      setPreview(nextPreview);
      addActivity?.(activityFromPayload(payload, "盘中前20预览更新", payload.success === false ? "warning" : "refresh"));
      return nextPreview;
    } finally {
      setBusy(null);
    }
  }, [addActivity]);

  const importSelection = useCallback(
    async (file: File, options: { asOfficial: boolean; fetchHistory: boolean; selectionDate?: string }) => {
      setBusy("import");
      try {
        const payload = await api.importSelection(file, options);
        setWorkbench(current => mergeWorkbenchPayload(current, payload));
        addActivity?.(activityFromPayload(payload, options.asOfficial ? "同花顺正式批次导入" : "同花顺盘中预览导入", "success"));
        await reloadPortfolioAndTrades();
        return payload;
      } finally {
        setBusy(null);
      }
    },
    [addActivity, reloadPortfolioAndTrades],
  );

  const startHistoryBackfill = useCallback(async () => {
    setBusy("history");
    try {
      const job = await api.startHistoryJob();
      setHistoryJob(job);
      addActivity?.({
        kind: job.status === "completed" ? "success" : "refresh",
        title: "批量K线补齐任务",
        detail: `总数 ${job.total} · 已跳过 ${job.skipped}`,
      });
      return job;
    } finally {
      setBusy(null);
    }
  }, [addActivity]);

  useEffect(() => {
    if (!historyJob?.jobId || historyJob.status !== "running") return;
    const timer = window.setInterval(() => {
      api
        .historyJob(historyJob.jobId || "")
        .then(job => {
          setHistoryJob(job);
          if (job.status !== "running") {
            addActivity?.({
              kind: job.status === "completed" && job.failed === 0 ? "success" : "warning",
              title: "K线补齐任务结束",
              detail: `成功 ${job.fetched} · 失败 ${job.failed} · 跳过 ${job.skipped}`,
            });
            if (job.list) setWorkbench(current => ({ ...current, list: job.list }));
          }
        })
        .catch(err => {
          addActivity?.({ kind: "warning", title: "K线补齐进度读取失败", detail: err instanceof Error ? err.message : "未知错误" });
        });
    }, 1500);
    return () => window.clearInterval(timer);
  }, [addActivity, historyJob?.jobId, historyJob?.status]);

  const fetchSingleHistory = useCallback(
    async (code: string) => {
      setBusy(`history:${code}`);
      try {
        const payload = await api.fetchHistory(code);
        addActivity?.({
          kind: payload.success ? "success" : "warning",
          title: "单股K线补齐",
          detail: payload.message || `${code} · 成功 ${payload.fetched || 0} · 失败 ${payload.failed || 0}`,
        });
        await loadAll();
        return payload;
      } finally {
        setBusy(null);
      }
    },
    [addActivity, loadAll],
  );

  const createTrade = useCallback(
    async (payload: TradeInput) => {
      setBusy("trade");
      try {
        const result = await api.createTrade({ ...payload, mode });
        addActivity?.({
          kind: "trade",
          title: payload.type === "BUY" ? "买入交易保存" : "卖出交易保存",
          detail: `${payload.name} ${payload.code} · ${payload.quantity}股 · ${payload.price}`,
        });
        await reloadPortfolioAndTrades(mode);
        await loadAll();
        return result.trade;
      } finally {
        setBusy(null);
      }
    },
    [addActivity, loadAll, mode, reloadPortfolioAndTrades],
  );

  const updateTrade = useCallback(
    async (tradeId: string, payload: TradeUpdateInput) => {
      setBusy("trade");
      try {
        const result = await api.updateTrade(tradeId, { ...payload, mode });
        addActivity?.({ kind: "trade", title: "交易流水已编辑", detail: `${result.trade.name} ${result.trade.code}` });
        await reloadPortfolioAndTrades(mode);
        return result.trade;
      } finally {
        setBusy(null);
      }
    },
    [addActivity, mode, reloadPortfolioAndTrades],
  );

  const deleteTrade = useCallback(
    async (tradeId: string) => {
      setBusy("trade");
      try {
        await api.deleteTrade(tradeId, mode);
        addActivity?.({ kind: "warning", title: "交易流水已删除", detail: tradeId });
        await reloadPortfolioAndTrades(mode);
      } finally {
        setBusy(null);
      }
    },
    [addActivity, mode, reloadPortfolioAndTrades],
  );

  const deferExit = useCallback(
    async (position: Position, reason: string) => {
      setBusy(`defer:${position.code}`);
      try {
        const result = await api.deferExit(position.code, { buyDate: position.buyDate, reason, mode });
        addActivity?.({
          kind: "warning",
          title: "延迟至尾盘决策已记录",
          detail: `${position.name} ${position.code} · ${result.decision.deferReason}`,
        });
        await reloadPortfolioAndTrades(mode);
        return result.decision;
      } finally {
        setBusy(null);
      }
    },
    [addActivity, mode, reloadPortfolioAndTrades],
  );

  const recalculateFees = useCallback(
    async (nextMode: AccountMode = mode) => {
      setBusy("fees");
      try {
        const result = await api.recalculateFees(nextMode);
        setTrades(result.trades || []);
        setWorkbench(current => mergeWorkbenchPayload(current, { accountState: result.accountState }));
        await reloadPortfolioAndTrades(nextMode);
        addActivity?.({
          kind: "success",
          title: "历史交易费用已重算",
          detail: `${nextMode === "real" ? "实盘记录" : "模拟训练"} · 更新 ${result.updatedCount ?? 0} 笔`,
        });
        return result;
      } finally {
        setBusy(null);
      }
    },
    [addActivity, mode, reloadPortfolioAndTrades],
  );

  const switchMode = useCallback(
    async (nextMode: AccountMode) => {
      if (nextMode === mode) return settings;
      setBusy("mode");
      try {
        const updated = await api.updateSettings({ ...settings, currentMode: nextMode });
        const activeMode = resolveMode(updated);
        setSettings(updated);
        await reloadPortfolioAndTrades(activeMode);
        const todayPayload = await api.reviewToday(activeMode).catch(() => null);
        if (todayPayload) setTodayReview(todayPayload);
        addActivity?.({
          kind: "success",
          title: "账户模式已切换",
          detail: activeMode === "real" ? "当前使用实盘记录资产与交易流水" : "当前使用模拟训练资产与交易流水",
        });
        return updated;
      } finally {
        setBusy(null);
      }
    },
    [addActivity, mode, reloadPortfolioAndTrades, settings],
  );

  const saveSettings = useCallback(
    async (payload: SettingsPayload) => {
      setBusy("settings");
      try {
        const updated = await api.updateSettings(payload);
        setSettings(updated);
        addActivity?.({ kind: "success", title: "设置已保存", detail: "账户、行情源和费用配置已更新" });
        await reloadPortfolioAndTrades(resolveMode(updated));
        return updated;
      } finally {
        setBusy(null);
      }
    },
    [addActivity, reloadPortfolioAndTrades],
  );

  const saveReport = useCallback(
    async (payload: ReportRecord) => {
      setBusy("report");
      try {
        const result = await api.saveReport(payload);
        const reportType = result.report.type || "daily";
        setReports(current => ({
          ...current,
          [reportType]: [result.report, ...current[reportType].filter(item => item.id !== result.report.id)],
        }));
        addActivity?.({ kind: "report", title: "复盘报告已生成", detail: result.mdPath });
        return result;
      } finally {
        setBusy(null);
      }
    },
    [addActivity],
  );

  const accountState = useMemo<AccountState>(() => account || accountFallback(), [account]);

  return {
    health,
    rules,
    settings,
    mode,
    workbench,
    officialSelection,
    initialPool,
    observationPool,
    buyReadyPool,
    allCandidates,
    selectedCandidate,
    selectedInitial,
    candidateEvents,
    positions,
    trades,
    stocks,
    account: accountState,
    preview,
    reviewContext,
    todayReview,
    reports,
    historyJob,
    loading,
    busy,
    error,
    setSelectedCandidateId,
    loadAll,
    refreshQuotes,
    generateOfficial,
    loadPreview,
    importSelection,
    startHistoryBackfill,
    fetchSingleHistory,
    createTrade,
    updateTrade,
    deleteTrade,
    deferExit,
    recalculateFees,
    switchMode,
    saveSettings,
    saveReport,
  };
}
