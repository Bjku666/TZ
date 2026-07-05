import { Download, Edit, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { compactMoney, dateTime, downloadText, money, tradeCsv } from "../api/adapters";
import { Badge, Button, Card, EmptyState, SectionTitle } from "../components/common/Primitives";
import type { TradeLog } from "../types";

export function TradesPage({
  trades,
  onEdit,
  onDelete,
}: {
  trades: TradeLog[];
  onEdit: (trade: TradeLog) => void;
  onDelete: (tradeId: string) => Promise<void>;
}) {
  const [date, setDate] = useState("");
  const [search, setSearch] = useState("");
  const [type, setType] = useState<"ALL" | "BUY" | "SELL">("ALL");
  const [compliance, setCompliance] = useState("ALL");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<TradeLog | null>(null);
  const [deleting, setDeleting] = useState(false);

  const filtered = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return trades.filter(trade => {
      if (date && trade.date !== date) return false;
      if (type !== "ALL" && trade.type !== type) return false;
      if (compliance !== "ALL" && trade.rulesConclusion !== compliance) return false;
      if (keyword && !trade.code.includes(keyword) && !trade.name.toLowerCase().includes(keyword)) return false;
      return true;
    });
  }, [compliance, date, search, trades, type]);

  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await onDelete(pendingDelete.id);
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <SectionTitle
          title="交易记录"
          subtitle="交易编辑、删除和费用重算均由后端服务处理。"
          action={
            <Button onClick={() => downloadText(`trades_${Date.now()}.csv`, tradeCsv(filtered), "text/csv;charset=utf-8")} variant="ghost">
              <Download className="h-3.5 w-3.5" />
              导出CSV
            </Button>
          }
        />
        <div className="mt-4 grid gap-3 md:grid-cols-5">
          <input type="date" value={date} onChange={event => setDate(event.target.value)} className="h-8 rounded border border-slate-800 bg-slate-950 px-2 font-mono text-xs text-slate-200 outline-none focus:border-cyan-600" />
          <div className="relative">
            <Search className="pointer-events-none absolute left-2 top-2.5 h-3.5 w-3.5 text-slate-600" />
            <input value={search} onChange={event => setSearch(event.target.value)} placeholder="股票搜索" className="h-8 w-full rounded border border-slate-800 bg-slate-950 pl-8 pr-2 text-xs text-slate-200 outline-none focus:border-cyan-600" />
          </div>
          <select value={type} onChange={event => setType(event.target.value as "ALL" | "BUY" | "SELL")} className="h-8 rounded border border-slate-800 bg-slate-950 px-2 text-xs text-slate-200 outline-none focus:border-cyan-600">
            <option value="ALL">全部类型</option>
            <option value="BUY">买入</option>
            <option value="SELL">卖出</option>
          </select>
          <select value={compliance} onChange={event => setCompliance(event.target.value)} className="h-8 rounded border border-slate-800 bg-slate-950 px-2 text-xs text-slate-200 outline-none focus:border-cyan-600">
            <option value="ALL">全部合规状态</option>
            <option value="符合规则">符合规则</option>
            <option value="部分不符">部分不符</option>
            <option value="违规交易">违规交易</option>
            <option value="其他">其他</option>
          </select>
          <Button onClick={() => { setDate(""); setSearch(""); setType("ALL"); setCompliance("ALL"); }} variant="muted">清空筛选</Button>
        </div>
      </Card>

      <Card className="p-0">
        {filtered.length === 0 ? (
          <div className="p-4">
            <EmptyState title="暂无交易流水" detail="买入或卖出弹窗保存后会显示在这里。" />
          </div>
        ) : (
          <div className="overflow-auto">
            <table className="min-w-[1280px] w-full text-left text-xs">
              <thead className="sticky top-0 z-10 bg-slate-950 text-[11px] text-slate-500">
                <tr>
                  {["类型", "日期", "时间", "股票", "价格", "数量", "金额", "佣金", "印花税", "过户费", "总费用", "原因", "规则结论", "违规标签", "操作"].map(head => (
                    <th key={head} className="whitespace-nowrap px-3 py-2 font-black">{head}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map(trade => (
                  <>
                    <tr key={trade.id} className="border-t border-slate-800/70 bg-slate-950/30 hover:bg-slate-900/60">
                      <td className="px-3 py-2"><Badge tone={trade.type === "BUY" ? "red" : "green"}>{trade.type === "BUY" ? "买入" : "卖出"}</Badge></td>
                      <td className="px-3 py-2 font-mono">{trade.date}</td>
                      <td className="px-3 py-2 font-mono">{trade.time}</td>
                      <td className="px-3 py-2 font-bold text-slate-100">{trade.name}<span className="ml-2 font-mono text-slate-500">{trade.code}</span></td>
                      <td className="px-3 py-2 font-mono">{trade.price.toFixed(2)}</td>
                      <td className="px-3 py-2 font-mono">{trade.quantity}</td>
                      <td className="px-3 py-2 font-mono">{compactMoney(trade.amount)}</td>
                      <td className="px-3 py-2 font-mono">{money(trade.commission)}</td>
                      <td className="px-3 py-2 font-mono">{money(trade.stampDuty)}</td>
                      <td className="px-3 py-2 font-mono">{money(trade.transferFee)}</td>
                      <td className="px-3 py-2 font-mono">{money(trade.totalFee)}</td>
                      <td className="max-w-[16rem] truncate px-3 py-2">{trade.reason || "-"}</td>
                      <td className="px-3 py-2"><Badge tone={trade.rulesConclusion === "符合规则" ? "green" : trade.rulesConclusion === "违规交易" ? "red" : "amber"}>{trade.rulesConclusion}</Badge></td>
                      <td className="max-w-[12rem] truncate px-3 py-2">{trade.violationTags?.join("、") || "无"}</td>
                      <td className="px-3 py-2">
                        <div className="flex gap-2">
                          <Button onClick={() => setExpanded(expanded === trade.id ? null : trade.id)} variant="muted">快照</Button>
                          <Button onClick={() => onEdit(trade)} variant="ghost"><Edit className="h-3.5 w-3.5" /></Button>
                          <Button onClick={() => setPendingDelete(trade)} variant="danger"><Trash2 className="h-3.5 w-3.5" /></Button>
                        </div>
                      </td>
                    </tr>
                    {expanded === trade.id && (
                      <tr key={`${trade.id}_snapshot`} className="border-t border-slate-800 bg-slate-950">
                        <td colSpan={15} className="px-3 py-3">
                          <pre className="max-h-72 overflow-auto rounded border border-slate-800 bg-slate-900 p-3 text-[11px] leading-5 text-slate-300">
                            {JSON.stringify(trade.snapshot || {}, null, 2)}
                          </pre>
                          <div className="mt-2 text-[11px] text-slate-500">快照时间：{dateTime(String((trade.snapshot || {}).tradeDateTime || ""))}</div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {pendingDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded border border-slate-800 bg-slate-900 p-5">
            <h3 className="text-sm font-black text-slate-100">删除交易流水</h3>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              将删除 {pendingDelete.name} {pendingDelete.code} {pendingDelete.date} 的 {pendingDelete.type === "BUY" ? "买入" : "卖出"} 记录。保存后后端会重新计算持仓、资产和盈亏。
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button onClick={() => setPendingDelete(null)} variant="ghost">取消</Button>
              <Button onClick={confirmDelete} disabled={deleting} variant="danger">{deleting ? "删除中" : "确认删除"}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
