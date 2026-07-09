import { useEffect, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { Mode, Page, Side, StrategyId, Trade, Workspace } from "./types";
import { apiPath, defaultStrategies, normalizeStrategyId, request } from "./lib";
import { Header, Loading, MobileNav, Sidebar } from "./ui";
import { Today } from "./Today";
import { Positions } from "./Positions";
import { Trades } from "./Trades";
import { Reviews } from "./Reviews";
import { Notices, SettingsDrawer, TradeModal } from "./Overlays";

export default function App() {
  const [mode, setMode] = useState<Mode>(() => (localStorage.getItem("tz-mode") as Mode) || "simulation");
  const [strategyId, setStrategyId] = useState<StrategyId>(() => normalizeStrategyId(localStorage.getItem("tz-strategy")));
  const [page, setPage] = useState<Page>("today");
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [noticesOpen, setNoticesOpen] = useState(false);
  const [tradeModal, setTradeModal] = useState<{ open: boolean; side: Side; code?: string; editing?: Trade }>({ open: false, side: "BUY" });
  const abortRef = useRef<AbortController | null>(null);

  const load = async (target: Mode = mode, refresh = false, targetStrategy: StrategyId = strategyId) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true); setError(""); setWorkspace(null);
    try {
      const data = await request<Workspace>(apiPath(target, refresh ? "/refresh" : "/workspace", targetStrategy), refresh ? { method: "POST", body: "{}", signal: controller.signal } : { signal: controller.signal });
      if (!controller.signal.aborted) setWorkspace(data);
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  };
  useEffect(() => {
    localStorage.setItem("tz-mode", mode);
    localStorage.setItem("tz-strategy", strategyId);
    void load(mode, false, strategyId);
    return () => abortRef.current?.abort();
  }, [mode, strategyId]);
  useEffect(() => {
    const market = workspace?.settings.market;
    if (!market?.enableRealtime || !market.autoRefresh) return;
    const intervalSeconds = Math.max(15, Number(market.refreshInterval || 60));
    const timer = window.setInterval(() => void load(mode, true, strategyId), intervalSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [workspace?.settings.market, mode, strategyId]);

  const mutate = async (promise: Promise<Workspace>) => {
    setLoading(true);
    try { setWorkspace(await promise); setError(""); }
    catch (err) { const message = err instanceof Error ? err.message : "操作失败"; setError(message); window.alert(message); }
    finally { setLoading(false); }
  };
  const switchMode = (next: Mode) => { if (next !== mode) { setPage("today"); setTradeModal({ open: false, side: "BUY" }); setMode(next); } };
  const switchStrategy = (next: StrategyId) => { if (next !== strategyId) { setPage("today"); setTradeModal({ open: false, side: "BUY" }); setStrategyId(next); } };
  const unread = workspace?.notifications.filter((item) => !item.read).length || 0;
  const strategies = workspace?.strategies?.length ? workspace.strategies : defaultStrategies;
  const strategy = workspace?.strategy || strategies.find((item) => item.id === strategyId) || defaultStrategies[0];

  return (
    <div className={`flex h-screen overflow-hidden bg-[#070b0b] text-slate-200 ${mode === "real" ? "tz-mode-real" : "tz-mode-simulation"}`}>
      <Sidebar mode={mode} strategyId={strategyId} strategies={strategies} page={page} quoteUpdatedAt={workspace?.quoteUpdatedAt} onMode={switchMode} onStrategy={switchStrategy} onPage={setPage} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          page={page}
          mode={mode}
          strategyId={strategyId}
          strategy={strategy}
          strategies={strategies}
          phase={workspace?.marketPhase || "连接中"}
          quoteUpdatedAt={workspace?.quoteUpdatedAt}
          unread={unread}
          loading={loading}
          onMode={switchMode}
          onStrategy={switchStrategy}
          onRefresh={() => void load(mode, true, strategyId)}
          onSettings={() => setSettingsOpen(true)}
          onNotices={() => setNoticesOpen(true)}
        />
        <main className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
          {error && <div className="mb-4 flex items-center justify-between rounded-xl border border-rose-900 bg-rose-950/40 p-3 text-sm text-rose-300"><span className="flex items-center gap-2"><AlertTriangle size={16} />{error}</span><button onClick={() => void load(mode, false, strategyId)} className="btn">重试</button></div>}
          {!workspace ? <Loading /> : page === "today" ? (
            <Today
              workspace={workspace}
              onTrade={(side, code) => setTradeModal({ open: true, side, code })}
              onSettings={() => setSettingsOpen(true)}
              onReviews={() => setPage("reviews")}
              onPositions={() => setPage("positions")}
            />
          ) : page === "positions" ? <Positions workspace={workspace} onTrade={(side, code) => setTradeModal({ open: true, side, code })} onMutate={mutate} /> : page === "trades" ? <Trades workspace={workspace} onTrade={(side) => setTradeModal({ open: true, side })} onEdit={(editing) => setTradeModal({ open: true, side: editing.type, code: editing.code, editing })} onMutate={mutate} /> : <Reviews workspace={workspace} onMutate={mutate} />}
        </main>
        <MobileNav page={page} onPage={setPage} />
      </div>
      {tradeModal.open && workspace && <TradeModal mode={mode} strategyId={strategyId} workspace={workspace} config={tradeModal} onClose={() => setTradeModal({ open: false, side: "BUY" })} onMutate={mutate} />}
      {settingsOpen && workspace && <SettingsDrawer mode={mode} strategyId={strategyId} settings={workspace.settings} onClose={() => setSettingsOpen(false)} onMutate={mutate} />}
      {noticesOpen && workspace && <Notices mode={mode} strategyId={strategyId} items={workspace.notifications} onClose={() => setNoticesOpen(false)} onReload={() => void load(mode, false, strategyId)} />}
    </div>
  );
}
