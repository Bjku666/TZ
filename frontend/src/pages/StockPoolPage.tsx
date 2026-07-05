import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Button, Card, SectionTitle } from "../components/common/Primitives";
import { KLinePanel } from "../components/stock/KLinePanel";
import { StockDetailPanel } from "../components/stock/StockDetailPanel";
import { StockTable, type StockPoolTab } from "../components/stock/StockTable";
import type { Candidate, CandidateEvent, HistoryJob, SelectionItem, TradeLog } from "../types";

const tabs: Array<{ key: StockPoolTab; label: string }> = [
  { key: "initial", label: "今日初筛" },
  { key: "observation", label: "跨日观察" },
  { key: "buy", label: "当前待买" },
];

export function StockPoolPage({
  initial,
  observation,
  buyReady,
  candidateEvents,
  trades,
  historyJob,
  busy,
  onOpenBuy,
  onSelectCandidate,
  onFetchOne,
  onFetchAll,
}: {
  initial: SelectionItem[];
  observation: Candidate[];
  buyReady: Candidate[];
  candidateEvents: Record<string, CandidateEvent[]>;
  trades: TradeLog[];
  historyJob: HistoryJob | null;
  busy: string | null;
  onOpenBuy: (candidate: Candidate) => void;
  onSelectCandidate: (candidateId: string) => void;
  onFetchOne: (code: string) => void;
  onFetchAll: () => void;
}) {
  const [tab, setTab] = useState<StockPoolTab>("initial");
  const [search, setSearch] = useState("");
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(buyReady[0] || observation[0] || null);
  const [selectedInitial, setSelectedInitial] = useState<SelectionItem | null>(initial[0] || null);

  const normalizedSearch = search.trim().toLowerCase();
  const filteredInitial = useMemo(
    () =>
      initial.filter(item => {
        if (!normalizedSearch) return true;
        return item.code.includes(normalizedSearch) || item.name.toLowerCase().includes(normalizedSearch);
      }),
    [initial, normalizedSearch],
  );
  const activeObservation = useMemo(
    () => observation.filter(item => item.state !== "BUY_READY" && item.state !== "CLOSED" && item.state !== "CANCELLED"),
    [observation],
  );
  const filteredObservation = useMemo(
    () =>
      activeObservation.filter(item => {
        if (!normalizedSearch) return true;
        return item.code.includes(normalizedSearch) || item.name.toLowerCase().includes(normalizedSearch);
      }),
    [activeObservation, normalizedSearch],
  );
  const filteredBuy = useMemo(
    () =>
      buyReady.filter(item => {
        if (!normalizedSearch) return true;
        return item.code.includes(normalizedSearch) || item.name.toLowerCase().includes(normalizedSearch);
      }),
    [buyReady, normalizedSearch],
  );

  const displayCandidate = selectedCandidate || filteredBuy[0] || filteredObservation[0] || null;
  const displayInitial = selectedInitial || (displayCandidate ? initial.find(item => item.code === displayCandidate.code) || null : filteredInitial[0] || null);
  const displayCode = displayCandidate?.code || displayInitial?.code || "";
  const displayName = displayCandidate?.name || displayInitial?.name || "";
  const events = displayCandidate ? candidateEvents[displayCandidate.id] || [] : [];

  function selectCandidate(candidate: Candidate) {
    setSelectedCandidate(candidate);
    setSelectedInitial(initial.find(item => item.code === candidate.code) || null);
    onSelectCandidate(candidate.id);
  }

  function selectInitial(item: SelectionItem) {
    setSelectedInitial(item);
    const candidate = [...buyReady, ...observation].find(row => row.code === item.code) || null;
    setSelectedCandidate(candidate);
    if (candidate) onSelectCandidate(candidate.id);
  }

  const tableCandidates = tab === "buy" ? filteredBuy : filteredObservation;

  return (
    <div className="space-y-4">
      <Card>
        <SectionTitle
          title="股票池"
          subtitle="搜索只改变显示，不改变候选状态；所有交易状态来自当前后端。"
          action={
            <div className="relative w-72">
              <Search className="pointer-events-none absolute left-2 top-2.5 h-3.5 w-3.5 text-slate-600" />
              <input
                value={search}
                onChange={event => setSearch(event.target.value)}
                placeholder="搜索代码或名称"
                className="h-8 w-full rounded border border-slate-800 bg-slate-950 pl-8 pr-2 text-xs text-slate-200 outline-none focus:border-cyan-600"
              />
            </div>
          }
        />
        <div className="mt-4 flex flex-wrap gap-2">
          {tabs.map(item => (
            <Button key={item.key} onClick={() => setTab(item.key)} variant={tab === item.key ? "primary" : "ghost"}>
              {item.label}
            </Button>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(22rem,0.8fr)]">
        <Card className="min-w-0">
          <StockTable
            tab={tab}
            initial={filteredInitial}
            candidates={tableCandidates}
            selectedCode={displayCode}
            onSelectInitial={selectInitial}
            onSelectCandidate={selectCandidate}
            onBuy={onOpenBuy}
          />
        </Card>
        <StockDetailPanel candidate={displayCandidate} selection={displayInitial} events={events} />
      </div>

      {displayCode && (
        <KLinePanel
          code={displayCode}
          name={displayName}
          candidate={displayCandidate}
          selection={displayInitial}
          trades={trades}
          historyJob={historyJob}
          busy={busy}
          onFetchOne={onFetchOne}
          onFetchAll={onFetchAll}
        />
      )}
    </div>
  );
}
