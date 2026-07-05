import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { AppShell } from "./layout/AppShell";
import type { PageKey } from "./layout/Sidebar";
import { DashboardPage } from "./pages/DashboardPage";
import { StockPoolPage } from "./pages/StockPoolPage";
import { IntradayPage } from "./pages/IntradayPage";
import { PositionsPage } from "./pages/PositionsPage";
import { TradesPage } from "./pages/TradesPage";
import { AssetsPage } from "./pages/AssetsPage";
import { ReviewPage } from "./pages/ReviewPage";
import { ImportPage } from "./pages/ImportPage";
import { SettingsPage } from "./pages/SettingsPage";
import { BuyTradeModal } from "./components/trade/BuyTradeModal";
import { SellTradeModal } from "./components/trade/SellTradeModal";
import { EditTradeModal } from "./components/trade/EditTradeModal";
import { useActivityLog } from "./hooks/useActivityLog";
import { useQuoteRefresh } from "./hooks/useQuoteRefresh";
import { useWorkbench } from "./hooks/useWorkbench";
import type { AccountMode, Candidate, Position, TradeLog } from "./types";

const pageKeys: PageKey[] = ["dashboard", "stockPool", "intraday", "positions", "trades", "assets", "review", "import", "settings"];

function pageFromHash(): PageKey {
  const key = window.location.hash.replace(/^#\/?/, "") as PageKey;
  return pageKeys.includes(key) ? key : "dashboard";
}

export default function App() {
  const [page, setPage] = useState<PageKey>(() => pageFromHash());
  const [buyTarget, setBuyTarget] = useState<Candidate | null>(null);
  const [sellTarget, setSellTarget] = useState<Position | null>(null);
  const [editTarget, setEditTarget] = useState<TradeLog | null>(null);
  const activityLog = useActivityLog();
  const workbench = useWorkbench({
    addActivity: activityLog.add,
    addActivities: activityLog.addMany,
  });
  const onPaused = useCallback(
    (reason: string) => {
      activityLog.add({ kind: "info", title: "自动刷新暂停", detail: reason });
    },
    [activityLog.add],
  );
  const quoteRefresh = useQuoteRefresh({
    enabled: Boolean(workbench.settings.autoRefresh ?? true),
    refresh: workbench.refreshQuotes,
    onPaused,
  });
  const handlePageChange = useCallback((nextPage: PageKey) => {
    setPage(nextPage);
    window.history.replaceState(null, "", `#/${nextPage}`);
  }, []);
  const handleModeChange = useCallback(
    (nextMode: AccountMode) => {
      void workbench.switchMode(nextMode);
    },
    [workbench],
  );

  useEffect(() => {
    const onHashChange = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const renderPage = () => {
    if (workbench.loading) {
      return (
        <div className="flex min-h-[28rem] items-center justify-center rounded border border-slate-800 bg-slate-950/60">
          <div className="text-center">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-cyan-300" />
            <div className="mt-3 text-sm font-bold text-slate-300">正在加载后端真实数据</div>
          </div>
        </div>
      );
    }

    if (workbench.error) {
      return (
        <div className="rounded border border-rose-900 bg-rose-950/25 p-4 text-sm text-rose-200">
          <AlertCircle className="mr-2 inline h-4 w-4" />
          {workbench.error}
        </div>
      );
    }

    switch (page) {
      case "dashboard":
        return (
          <DashboardPage
            official={workbench.officialSelection}
            initial={workbench.initialPool}
            observation={workbench.observationPool}
            buyReady={workbench.buyReadyPool}
            positions={workbench.positions}
            trades={workbench.trades}
            stocks={workbench.stocks}
            account={workbench.account}
            phase={quoteRefresh.phase}
            busy={workbench.busy}
            onGenerate={() => void workbench.generateOfficial()}
            onRefresh={() => void quoteRefresh.manualRefresh()}
            onBackfill={() => void workbench.startHistoryBackfill()}
            onNavigate={handlePageChange}
          />
        );
      case "stockPool":
        return (
          <StockPoolPage
            initial={workbench.initialPool}
            observation={workbench.observationPool}
            buyReady={workbench.buyReadyPool}
            candidateEvents={workbench.candidateEvents}
            trades={workbench.trades}
            historyJob={workbench.historyJob}
            busy={workbench.busy}
            onOpenBuy={setBuyTarget}
            onSelectCandidate={workbench.setSelectedCandidateId}
            onFetchOne={code => void workbench.fetchSingleHistory(code)}
            onFetchAll={() => void workbench.startHistoryBackfill()}
          />
        );
      case "intraday":
        return (
          <IntradayPage
            payload={workbench.workbench}
            settings={workbench.settings}
            phase={quoteRefresh.phase}
            autoRefreshActive={quoteRefresh.active}
            countdown={quoteRefresh.countdown}
            intervalSeconds={quoteRefresh.intervalSeconds}
            running={quoteRefresh.running}
            busy={workbench.busy}
            preview={workbench.preview}
            onRefresh={() => void quoteRefresh.manualRefresh()}
            onPreview={() => void workbench.loadPreview()}
          />
        );
      case "positions":
        return (
          <PositionsPage
            positions={workbench.positions}
            onSell={setSellTarget}
            onDefer={position => void workbench.deferExit(position, "用户选择延迟至14:30后处理")}
          />
        );
      case "trades":
        return <TradesPage trades={workbench.trades} onEdit={setEditTarget} onDelete={workbench.deleteTrade} />;
      case "assets":
        return <AssetsPage account={workbench.account} mode={workbench.mode} />;
      case "review":
        return (
          <ReviewPage
            initial={workbench.initialPool}
            observation={workbench.observationPool}
            buyReady={workbench.buyReadyPool}
            trades={workbench.trades}
            positions={workbench.positions}
            account={workbench.account}
            reviewContext={workbench.reviewContext}
            reports={workbench.reports}
            busy={workbench.busy}
            onSave={async payload => {
              await workbench.saveReport(payload);
            }}
          />
        );
      case "import":
        return <ImportPage busy={workbench.busy} onImport={workbench.importSelection} />;
      case "settings":
        return (
          <SettingsPage
            settings={workbench.settings}
            rules={workbench.rules}
            busy={workbench.busy}
            mode={workbench.mode}
            onSave={workbench.saveSettings}
            onRecalculateFees={workbench.recalculateFees}
          />
        );
      default:
        return null;
    }
  };

  return (
    <>
      <AppShell
        page={page}
        onPageChange={handlePageChange}
        health={workbench.health}
        mode={workbench.mode}
        onModeChange={handleModeChange}
        modeSwitching={workbench.busy === "mode"}
        phase={quoteRefresh.phase}
        rules={workbench.rules}
        settings={workbench.settings}
        account={workbench.account}
        payload={workbench.workbench}
        countdown={quoteRefresh.countdown}
        autoRefreshActive={quoteRefresh.active}
        refreshing={quoteRefresh.running || workbench.busy === "refresh"}
        onRefresh={() => void quoteRefresh.manualRefresh()}
        activities={activityLog.entries}
        onClearActivities={activityLog.clear}
      >
        {renderPage()}
      </AppShell>

      {buyTarget && (
        <BuyTradeModal
          candidate={buyTarget}
          account={workbench.account}
          rules={workbench.rules}
          settings={workbench.settings}
          onClose={() => setBuyTarget(null)}
          onSubmit={async payload => {
            await workbench.createTrade(payload);
          }}
        />
      )}

      {sellTarget && (
        <SellTradeModal
          position={sellTarget}
          settings={workbench.settings}
          onClose={() => setSellTarget(null)}
          onSubmit={async payload => {
            await workbench.createTrade(payload);
          }}
          onDefer={async reason => {
            await workbench.deferExit(sellTarget, reason);
          }}
        />
      )}

      {editTarget && (
        <EditTradeModal
          trade={editTarget}
          settings={workbench.settings}
          onClose={() => setEditTarget(null)}
          onSubmit={async (tradeId, payload) => {
            await workbench.updateTrade(tradeId, payload);
          }}
        />
      )}
    </>
  );
}
