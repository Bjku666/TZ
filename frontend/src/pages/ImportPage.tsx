import { FileSpreadsheet, Upload } from "lucide-react";
import { useState } from "react";
import { todayText } from "../api/adapters";
import { Badge, Button, Card, EmptyState, SectionTitle, StatTile } from "../components/common/Primitives";
import type { WorkbenchPayload } from "../types";

export function ImportPage({
  busy,
  onImport,
}: {
  busy: string | null;
  onImport: (file: File, options: { asOfficial: boolean; fetchHistory: boolean; selectionDate?: string }) => Promise<WorkbenchPayload>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [asOfficial, setAsOfficial] = useState(false);
  const [fetchHistory, setFetchHistory] = useState(false);
  const [selectionDate, setSelectionDate] = useState(todayText());
  const [confirmedClose, setConfirmedClose] = useState(false);
  const [confirmedRank, setConfirmedRank] = useState(false);
  const [result, setResult] = useState<WorkbenchPayload | null>(null);
  const summary = (result as { summary?: Record<string, unknown> } | null)?.summary || {};
  const canSubmit = Boolean(file) && (!asOfficial || (selectionDate && confirmedClose && confirmedRank));

  async function submit() {
    if (!file || !canSubmit) return;
    const payload = await onImport(file, { asOfficial, fetchHistory, selectionDate });
    setResult(payload);
  }

  return (
    <div className="space-y-4">
      <Card>
        <SectionTitle title="数据导入" subtitle="导入不会简单覆盖正式候选；作为正式收盘批次时必须显式确认日期和榜单完整性。" />
        <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1fr]">
          <div className="space-y-3">
            <label className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded border border-dashed border-slate-700 bg-slate-950/60 p-6 text-center hover:border-cyan-700">
              <FileSpreadsheet className="h-8 w-8 text-cyan-300" />
              <span className="mt-2 text-sm font-bold text-slate-200">{file ? file.name : "选择 .xlsx / .xls / .csv 文件"}</span>
              <span className="mt-1 text-xs text-slate-500">{file ? `${(file.size / 1024).toFixed(1)} KB` : "支持同花顺导出表格"}</span>
              <input
                type="file"
                accept=".xlsx,.xls,.csv"
                className="hidden"
                onChange={event => setFile(event.target.files?.[0] || null)}
              />
            </label>
            <label className="flex items-center gap-2 rounded border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
              <input type="checkbox" checked={fetchHistory} onChange={event => setFetchHistory(event.target.checked)} className="h-4 w-4 accent-cyan-500" />
              导入后补充缺失K线
            </label>
          </div>

          <div className="space-y-3">
            <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
              <div className="mb-2 text-xs font-black text-slate-200">导入用途</div>
              <div className="grid grid-cols-2 gap-2">
                <Button onClick={() => setAsOfficial(false)} variant={!asOfficial ? "primary" : "ghost"}>仅作为盘中预览导入</Button>
                <Button onClick={() => setAsOfficial(true)} variant={asOfficial ? "primary" : "ghost"}>作为正式收盘批次导入</Button>
              </div>
            </div>
            {asOfficial && (
              <div className="space-y-2 rounded border border-amber-900/60 bg-amber-950/20 p-3">
                <label className="block">
                  <span className="text-[10px] font-bold text-slate-500">selection_date</span>
                  <input type="date" value={selectionDate} onChange={event => setSelectionDate(event.target.value)} className="mt-1 h-8 w-full rounded border border-slate-800 bg-slate-950 px-2 font-mono text-xs text-slate-200 outline-none focus:border-cyan-600" />
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input type="checkbox" checked={confirmedClose} onChange={event => setConfirmedClose(event.target.checked)} className="h-4 w-4 accent-amber-500" />
                  我确认这是该交易日收盘后完整榜单
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input type="checkbox" checked={confirmedRank} onChange={event => setConfirmedRank(event.target.checked)} className="h-4 w-4 accent-amber-500" />
                  我确认原始前20排名可验证
                </label>
              </div>
            )}
            <Button onClick={submit} disabled={!canSubmit || busy === "import"} variant="primary" className="w-full">
              <Upload className="h-3.5 w-3.5" />
              {busy === "import" ? "导入中" : "开始导入"}
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <SectionTitle title="导入结果" subtitle="识别统计来自后端导入返回；没有字段时不伪造。" />
        {!result ? (
          <EmptyState title="暂无导入结果" />
        ) : (
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <StatTile label="识别行数" value={String(summary.rows ?? summary.totalRows ?? "暂无真实数据")} />
            <StatTile label="代码行数" value={String(summary.codeRows ?? summary.validCodeRows ?? "暂无真实数据")} />
            <StatTile label="符合范围数量" value={String(summary.allowedRows ?? summary.validRows ?? result.initialPool?.length ?? "暂无真实数据")} tone="green" />
            <StatTile label="排除数量" value={String(summary.excludedRows ?? "暂无真实数据")} tone="amber" />
            <StatTile label="数据截止日期" value={String(summary.dataAsOf ?? selectionDate ?? "暂无真实数据")} />
            <StatTile label="补K线进度" value={String((result as { history?: { fetched?: number; failed?: number } }).history ? `成功 ${(result as { history?: { fetched?: number; failed?: number } }).history?.fetched || 0} / 失败 ${(result as { history?: { fetched?: number; failed?: number } }).history?.failed || 0}` : "未启动")} />
          </div>
        )}
        {result?.message && <div className="mt-3 rounded border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-400">{result.message}</div>}
        {summary.exclusionReasons ? (
          <pre className="mt-3 max-h-48 overflow-auto rounded border border-slate-800 bg-slate-950 p-3 text-[11px] text-slate-400">{JSON.stringify(summary.exclusionReasons, null, 2)}</pre>
        ) : (
          <div className="mt-3"><Badge tone="slate">排除原因：暂无真实数据，请等待后端返回</Badge></div>
        )}
      </Card>
    </div>
  );
}
