import type { ReactNode } from "react";
import { Sidebar, type PageKey } from "./Sidebar";
import { TopStatusBar } from "./TopStatusBar";
import type { AccountMode, AccountState, ActivityEntry, HealthPayload, MarketPhase, RuleConfig, SettingsPayload, WorkbenchPayload } from "../types";

export function AppShell({
  page,
  onPageChange,
  children,
  health,
  mode,
  onModeChange,
  modeSwitching,
  phase,
  rules,
  settings,
  account,
  payload,
  countdown,
  autoRefreshActive,
  refreshing,
  onRefresh,
  activities,
  onClearActivities,
}: {
  page: PageKey;
  onPageChange: (page: PageKey) => void;
  children: ReactNode;
  health: HealthPayload | null;
  mode: AccountMode;
  onModeChange: (mode: AccountMode) => void;
  modeSwitching: boolean;
  phase: MarketPhase;
  rules: RuleConfig | null;
  settings: SettingsPayload;
  account: AccountState;
  payload: WorkbenchPayload;
  countdown: number | null;
  autoRefreshActive: boolean;
  refreshing: boolean;
  onRefresh: () => void;
  activities: ActivityEntry[];
  onClearActivities: () => void;
}) {
  return (
    <div className="flex h-full min-h-0 bg-slate-950 text-slate-200">
      <Sidebar
        active={page}
        onChange={onPageChange}
        mode={mode}
        onModeChange={onModeChange}
        modeSwitching={modeSwitching}
        activities={activities}
        onClearActivities={onClearActivities}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopStatusBar
          health={health}
          mode={mode}
          phase={phase}
          rules={rules}
          settings={settings}
          account={account}
          payload={payload}
          countdown={countdown}
          autoRefreshActive={autoRefreshActive}
          refreshing={refreshing}
          onRefresh={onRefresh}
        />
        <main className="min-h-0 flex-1 overflow-auto bg-[#111111]">
          <div className="mx-auto min-h-full max-w-[1180px] p-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
