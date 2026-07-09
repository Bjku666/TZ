import { Clock3, Landmark, Minus, Plus, Save, Settings2, ShieldAlert, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import type { AppSettings, Mode, Notice, Reconciliation, SettingsData, Side, StrategyId, StrategySnapshot, Trade, Workspace } from "./types";
import { apiPath, modeLabel, money, nowTime, request, signedMoney, today, tone } from "./lib";
import { Badge, Empty, Field, Mini, NumberField } from "./ui";

type SettingsTab = "account" | "fee" | "reconciliation" | "market";
type SecurityLookup = { code: string; name: string; found: boolean; source: string };
type Mode3Fields = {
  ma10AtEntry: string;
  distanceToMa10Pct: string;
  priorLimitUp: boolean;
  entryPatternNote: string;
  manualJudgement: string;
  exitReason: string;
  extendedObservation: boolean;
  maxProfitPct: string;
  exitNote: string;
};
const auditOptions = ["符合规则", "部分不符", "违规交易", "无法判断"] as const;
const hourOptions = Array.from({ length: 24 }, (_, index) => index);
const minuteOptions = Array.from({ length: 60 }, (_, index) => index);
const quickTimes = ["09:30", "10:00", "14:50", "14:55", "15:00"];
const mode3EntryChecklist = [
  ["priorVolumeExpansion", "前期存在明显放量上涨"],
  ["bearishCandle", "当前K线为阴线"],
  ["pullbackVolumeShrunk", "当前回调成交量缩小"],
  ["nearMa10", "股价已经接近十日线"],
  ["ma10Uptrend", "十日线保持向上，整体趋势未破坏"],
  ["midTermDistanceOk", "十日线与二十日线、三十日线距离不过大"],
  ["notFirstPullbackBearish", "当前不是第一根回调阴线"],
  ["positionSplit", "已进行分仓，没有集中买入单只股票"],
] as const;
type Mode3EntryCheckKey = typeof mode3EntryChecklist[number][0];
const mode3ExitReasons = [
  ["", "请选择退出原因"],
  ["TARGET_PROFIT", "次日盈利约2%止盈"],
  ["OPEN_BELOW_MA10", "开盘跌破十日线并确认支撑失效"],
  ["INTRADAY_AVERAGE_BROKEN", "冲高后跌破分时均价线"],
  ["MA5_PRESSURE_FAILED", "反弹无法突破五日线"],
  ["MA10_STOP", "跌破十日线止损"],
  ["HARD_STOP", "触及约3%硬止损"],
  ["EXTENDED_SAME_DAY_EXIT", "突破五日线延长后当日尾盘退出"],
  ["OTHER", "其他人工原因"],
] as const;

export function TradeModal({
  mode,
  strategyId,
  workspace: w,
  config,
  onClose,
  onMutate,
}: {
  mode: Mode;
  strategyId: StrategyId;
  workspace: Workspace;
  config: { side: Side; code?: string; editing?: Trade };
  onClose: () => void;
  onMutate: (p: Promise<Workspace>) => void;
}) {
  const edit = config.editing;
  const position = w.positions.find((item) => item.code === config.code || item.code === edit?.code);
  const initialFees = edit || { commission: 0, stampDuty: 0, transferFee: 0 };
  const [form, setForm] = useState({
    code: edit?.code || config.code || "",
    name: edit?.name || position?.name || "",
    type: edit?.type || config.side,
    date: edit?.date || today(),
    time: edit?.time || nowTime(),
    price: String(edit?.price || position?.currentPrice || ""),
    quantity: String(edit?.quantity || (config.side === "SELL" ? position?.availableQuantity || "" : "")),
    reason: edit?.reason || "",
    remark: edit?.remark || "",
    historicalBackfill: edit?.historicalBackfill || false,
    manualFeeOverride: edit?.manualFeeOverride || false,
    commission: String(initialFees.commission || ""),
    stampDuty: String(initialFees.stampDuty || ""),
    transferFee: String(initialFees.transferFee || ""),
    rulesConclusion: edit?.rulesConclusion || "无法判断",
    violationTags: edit?.violationTags?.join("、") || "",
  });
  const [mode3Entry, setMode3Entry] = useState<Record<Mode3EntryCheckKey, boolean>>(() => initialMode3EntryChecklist(edit?.strategySnapshot));
  const [mode3Fields, setMode3Fields] = useState<Mode3Fields>(() => initialMode3Fields(edit?.strategySnapshot));
  const [nameTouched, setNameTouched] = useState(Boolean(edit?.name));
  const [lookupHint, setLookupHint] = useState("");
  const side = form.type as Side;
  const isMode3 = strategyId === "mode3";
  const activePosition = w.positions.find((item) => item.code === form.code) || position;
  const price = Number(form.price || 0);
  const quantity = Number(form.quantity || 0);
  const amount = price * quantity;
  const settings = w.settings[mode];
  const autoFees = useMemo(() => calculateFeePreview(side, amount, settings), [side, amount, settings]);
  const manualFees = useMemo(() => ({
    commission: Math.max(0, Number(form.commission || 0)),
    stampDuty: Math.max(0, Number(form.stampDuty || 0)),
    transferFee: Math.max(0, Number(form.transferFee || 0)),
    totalFee: Math.max(0, Number(form.commission || 0)) + Math.max(0, Number(form.stampDuty || 0)) + Math.max(0, Number(form.transferFee || 0)),
  }), [form.commission, form.stampDuty, form.transferFee]);
  const fees = form.manualFeeOverride ? manualFees : autoFees;
  const projectedCash = side === "BUY" ? w.account.availableCash - amount - fees.totalFee : w.account.availableCash + amount - fees.totalFee;
  const projectedRealized = side === "SELL" && activePosition ? amount - fees.totalFee - activePosition.avgCost * quantity : 0;
  const quantityWarning = quantity > 0 && quantity % 100 !== 0;
  const overSell = side === "SELL" && activePosition && !form.historicalBackfill && quantity > activePosition.availableQuantity;
  const cashWarning = side === "BUY" && projectedCash < 0;
  const t1Warning = side === "SELL" && activePosition && activePosition.availableQuantity <= 0 && !form.historicalBackfill;

  const findLocalSecurity = (code: string) => {
    const normalized = code.trim();
    return w.positions.find((item) => item.code === normalized) || w.trades.find((trade) => trade.code === normalized);
  };
  const set = (key: keyof typeof form, value: string | boolean) => setForm((current) => ({ ...current, [key]: value }));
  const setMode3Check = (key: Mode3EntryCheckKey, value: boolean) => setMode3Entry((current) => ({ ...current, [key]: value }));
  const setMode3Field = (key: keyof typeof mode3Fields, value: string | boolean) => setMode3Fields((current) => ({ ...current, [key]: value }));
  const setManualFeeOverride = (checked: boolean) => {
    setForm((current) => ({
      ...current,
      manualFeeOverride: checked,
      commission: checked && !current.commission ? autoFees.commission.toFixed(2) : current.commission,
      stampDuty: checked && !current.stampDuty ? autoFees.stampDuty.toFixed(2) : current.stampDuty,
      transferFee: checked && !current.transferFee ? autoFees.transferFee.toFixed(2) : current.transferFee,
    }));
  };
  const setHistoricalBackfill = (checked: boolean) => {
    setForm((current) => ({
      ...current,
      historicalBackfill: checked,
      rulesConclusion: checked ? current.rulesConclusion || "无法判断" : current.rulesConclusion,
      violationTags: checked && !current.violationTags && current.rulesConclusion !== "符合规则" ? "历史补录" : current.violationTags,
    }));
  };
  const handleCodeChange = (value: string) => {
    const code = value.trim();
    const local = findLocalSecurity(code);
    setLookupHint(local?.name ? `已从${"availableQuantity" in local ? "当前持仓" : "历史交易"}带入名称` : "");
    setForm((current) => ({
      ...current,
      code: value,
      name: !nameTouched && local?.name ? local.name : current.name,
    }));
  };
  const handleNameChange = (value: string) => {
    setNameTouched(true);
    set("name", value);
  };
  const setSide = (next: Side) => {
    const nextPosition = next === "SELL" ? activePosition || w.positions[0] : undefined;
    setForm((current) => ({
      ...current,
      type: next,
      code: nextPosition?.code || current.code,
      name: nextPosition?.name || current.name,
      price: nextPosition ? String(nextPosition.currentPrice || current.price) : current.price,
      quantity: next === "SELL" && nextPosition ? String(nextPosition.availableQuantity || "") : current.quantity,
    }));
    if (nextPosition?.name) {
      setNameTouched(false);
      setLookupHint("已从当前持仓带入名称");
    }
  };
  const selectPosition = (code: string) => {
    const next = w.positions.find((item) => item.code === code);
    setForm((current) => ({
      ...current,
      code,
      name: next?.name || current.name,
      price: next ? String(next.currentPrice) : current.price,
      quantity: side === "SELL" && next ? String(next.availableQuantity || "") : current.quantity,
    }));
    if (next?.name) {
      setNameTouched(false);
      setLookupHint("已从当前持仓带入名称");
    }
  };
  useEffect(() => {
    const code = form.code.trim();
    if (nameTouched || code.length < 6 || findLocalSecurity(code)?.name) return;
    let cancelled = false;
    setLookupHint("正在查找股票名称...");
    const timer = window.setTimeout(() => {
      void request<SecurityLookup>(apiPath(mode, `/securities/${encodeURIComponent(code)}`, strategyId))
        .then((result) => {
          if (cancelled || form.code.trim() !== code) return;
          if (result.found && result.name) {
            setForm((current) => current.code.trim() === code && !nameTouched ? { ...current, name: result.name } : current);
            setLookupHint(`已从${result.source}带入名称`);
          } else {
            setLookupHint("未找到名称，可手动填写");
          }
        })
        .catch(() => !cancelled && setLookupHint("名称查找失败，可手动填写"));
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [form.code, mode, strategyId, nameTouched]);
  const save = () => {
    const payload = {
      ...edit,
      code: form.code.trim(),
      name: form.name.trim(),
      type: side,
      date: form.date,
      time: normalizeTime(form.time),
      price,
      quantity,
      amount,
      reason: form.reason,
      remark: form.remark,
      historicalBackfill: form.historicalBackfill,
      manualFeeOverride: form.manualFeeOverride,
      commission: fees.commission,
      stampDuty: fees.stampDuty,
      transferFee: fees.transferFee,
      totalFee: fees.totalFee,
      rulesConclusion: form.historicalBackfill ? form.rulesConclusion : undefined,
      violationTags: form.historicalBackfill ? form.violationTags : [],
      strategySnapshot: isMode3 ? buildMode3Snapshot(side, mode3Entry, mode3Fields) : edit?.strategySnapshot || {},
      accountMode: mode,
      strategyId,
    };
    onMutate(request(apiPath(mode, edit ? `/trades/${edit.id}` : "/trades", strategyId), { method: edit ? "PUT" : "POST", body: JSON.stringify(payload) }));
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-4 backdrop-blur-[3px]" onMouseDown={onClose}>
      <section className={`max-h-[94vh] w-full ${isMode3 ? "max-w-[672px]" : "max-w-[512px]"} overflow-hidden rounded-xl border border-[#25324a] bg-[#121722] shadow-2xl`} onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-[#25324a] bg-[#0f1d3a] px-6 py-4">
          <div className="flex items-center gap-3">
            <Landmark size={18} className="mode-accent" />
            <div>
              <h2 className="text-[16px] font-black leading-5 text-white">{side === "BUY" ? "买入操作登记" : "卖出平仓登记"}</h2>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-[#8a94a3]">TZ WORKSPACE: {modeLabel(mode)} / {w.strategy.name}</p>
            </div>
          </div>
          <button className="icon-btn border-0 bg-transparent" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="max-h-[calc(94vh-132px)] overflow-y-auto px-6 py-6">
          <div className="grid rounded-lg border border-[#25324a] bg-[#111821] p-1 sm:grid-cols-2">
            <button onClick={() => setSide("BUY")} className={`side-toggle ${side === "BUY" ? "side-toggle-buy-active" : ""}`}>
              <Plus size={14} />
              买入低吸 (BUY)
            </button>
            <button onClick={() => setSide("SELL")} className={`side-toggle ${side === "SELL" ? "side-toggle-sell-active" : ""}`}>
              <Minus size={14} />
              卖出离场 (SELL)
            </button>
          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <Field label="股票代码">
              {side === "SELL" && w.positions.length ? (
                <select className="input" value={form.code} onChange={(event) => selectPosition(event.target.value)}>
                  <option value="">选择可卖持仓</option>
                  {w.positions.map((item) => (
                    <option key={item.code} value={item.code}>{item.name} ({item.code}) - 可卖 {item.availableQuantity} 股</option>
                  ))}
                </select>
              ) : (
                <input className="input font-mono" placeholder="e.g. 002594" value={form.code} onChange={(event) => handleCodeChange(event.target.value)} />
              )}
            </Field>
            <Field label="股票名称">
              <input className="input" placeholder="输入代码后自动带入，可手动改" value={form.name} onChange={(event) => handleNameChange(event.target.value)} />
              {lookupHint && <div className="mt-1 text-[10px] leading-4 text-[#77808f]">{lookupHint}</div>}
            </Field>
            <Field label="成交日期">
              <input type="date" className="input font-mono" value={form.date} onChange={(event) => set("date", event.target.value)} />
            </Field>
            <Field label="成交时间">
              <TimeWheelPicker value={form.time} onChange={(value) => set("time", value)} />
            </Field>
            <Field label="成交价格 (元)">
              <input
                type="text"
                inputMode="decimal"
                className="input font-mono"
                placeholder="直接输入成交价"
                value={form.price}
                onFocus={(event) => event.currentTarget.select()}
                onChange={(event) => set("price", normalizePriceInput(event.target.value))}
              />
            </Field>
            <Field label={`${side === "BUY" ? "买入" : "卖出"}数量 (股)`}>
              <input type="number" step="100" className="input font-mono" placeholder={side === "BUY" ? "100 股整数倍" : `最大可卖：${activePosition?.availableQuantity ?? 0}`} value={form.quantity} onChange={(event) => set("quantity", event.target.value)} />
            </Field>
          </div>

          <div className="mt-4">
            <Field label={side === "BUY" ? "买入动机与回踩依据" : "卖出动机与纪律描述"}>
              <textarea
                className="input min-h-[58px] resize-none"
                value={form.reason}
                onChange={(event) => set("reason", event.target.value)}
                placeholder={side === "BUY" ? "描述当前交易模式的入场依据" : "描述当前交易模式的离场依据"}
              />
            </Field>
          </div>

          {isMode3 && side === "BUY" && (
            <div className="mt-4 rounded-lg border border-[#25324a] bg-[#111821] p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="text-[12px] font-black text-white">模式三入场检查表</div>
                <Badge tone="indigo">plannedExitRule: NEXT_TRADING_DAY</Badge>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {mode3EntryChecklist.map(([key, label]) => (
                  <label key={key} className="flex gap-2 rounded-md border border-[#27313b] bg-[#0f151f] p-2 text-[11px] leading-5 text-[#cfd6df]">
                    <input type="checkbox" checked={mode3Entry[key]} onChange={(event) => setMode3Check(key, event.target.checked)} />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <Field label="买入时十日线价格">
                  <input className="input font-mono" inputMode="decimal" value={mode3Fields.ma10AtEntry} onChange={(event) => setMode3Field("ma10AtEntry", normalizePriceInput(event.target.value))} />
                </Field>
                <Field label="买入价距离十日线百分比">
                  <input className="input font-mono" inputMode="decimal" placeholder="例如 1.2" value={mode3Fields.distanceToMa10Pct} onChange={(event) => setMode3Field("distanceToMa10Pct", normalizeSignedDecimalInput(event.target.value))} />
                </Field>
              </div>
              <label className="mt-3 flex gap-2 rounded-md border border-[#27313b] bg-[#0f151f] p-2 text-[11px] leading-5 text-[#9aa3af]">
                <input type="checkbox" checked={mode3Fields.priorLimitUp} onChange={(event) => setMode3Field("priorLimitUp", event.target.checked)} />
                <span>前期出现涨停，仅作为优先条件记录，不作为必买条件</span>
              </label>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <Field label="买入图形说明">
                  <textarea className="input min-h-[58px] resize-none" value={mode3Fields.entryPatternNote} onChange={(event) => setMode3Field("entryPatternNote", event.target.value)} />
                </Field>
                <Field label="其他人工判断">
                  <textarea className="input min-h-[58px] resize-none" value={mode3Fields.manualJudgement} onChange={(event) => setMode3Field("manualJudgement", event.target.value)} />
                </Field>
              </div>
            </div>
          )}

          {isMode3 && side === "SELL" && (
            <div className="mt-4 rounded-lg border border-[#25324a] bg-[#111821] p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="text-[12px] font-black text-white">模式三退出记录</div>
                <Badge tone={mode3Fields.extendedObservation ? "amber" : "slate"}>{mode3Fields.extendedObservation ? "已登记延长观察" : "未延长"}</Badge>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="退出原因">
                  <select className="input" value={mode3Fields.exitReason} onChange={(event) => setMode3Field("exitReason", event.target.value)}>
                    {mode3ExitReasons.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </Field>
                <Field label="盘中最高盈利百分比">
                  <input className="input font-mono" inputMode="decimal" placeholder="例如 2.3" value={mode3Fields.maxProfitPct} onChange={(event) => setMode3Field("maxProfitPct", normalizeSignedDecimalInput(event.target.value))} />
                </Field>
              </div>
              <label className="mt-3 flex gap-2 rounded-md border border-[#27313b] bg-[#0f151f] p-2 text-[11px] leading-5 text-[#9aa3af]">
                <input type="checkbox" checked={mode3Fields.extendedObservation} onChange={(event) => setMode3Field("extendedObservation", event.target.checked)} />
                <span>10:00 前突破五日线，登记延长观察至当日尾盘</span>
              </label>
              <div className="mt-3">
                <Field label="退出备注">
                  <textarea className="input min-h-[58px] resize-none" value={mode3Fields.exitNote} onChange={(event) => setMode3Field("exitNote", event.target.value)} />
                </Field>
              </div>
            </div>
          )}

          <label className="mt-5 flex gap-3 rounded-lg border border-[#25324a] bg-[#111821] p-3 text-[11px] leading-5 text-[#9aa3af]">
            <input type="checkbox" className="mt-1" checked={form.historicalBackfill} onChange={(event) => setHistoricalBackfill(event.target.checked)} />
            <span>
              <b className="block text-white">设置为历史补录/追溯数据交易</b>
              选中后，买入跳过可用现金限制，卖出豁免 T+1 校验，并可手工指定审计评级。
            </span>
          </label>

          {form.historicalBackfill && (
            <div className="mt-3 grid gap-4 rounded-lg border border-[#25324a] bg-[#111821] p-4 sm:grid-cols-2">
              <Field label="历史补录审计评级">
                <select className="input" value={form.rulesConclusion} onChange={(event) => set("rulesConclusion", event.target.value)}>
                  {auditOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                </select>
              </Field>
              <Field label="偏差标签">
                <input className="input" placeholder="例如：历史补录、追高、非计划交易" value={form.violationTags} onChange={(event) => set("violationTags", event.target.value)} />
              </Field>
            </div>
          )}

          <label className="mt-3 flex gap-3 rounded-lg border border-[#25324a] bg-[#111821] p-3 text-[11px] leading-5 text-[#9aa3af]">
            <input type="checkbox" className="mt-1" checked={form.manualFeeOverride} onChange={(event) => setManualFeeOverride(event.target.checked)} />
            <span>
              <b className="block text-white">使用券商实际费用</b>
              勾选后按下方佣金、印花税、过户费入账；手续费重算不会覆盖这笔交易。
            </span>
          </label>

          {form.manualFeeOverride && (
            <div className="mt-3 grid gap-4 rounded-lg border border-[#25324a] bg-[#111821] p-4 sm:grid-cols-3">
              <Field label="佣金">
                <input type="number" min="0" step="0.01" className="input font-mono" value={form.commission} onChange={(event) => set("commission", event.target.value)} />
              </Field>
              <Field label="印花税">
                <input type="number" min="0" step="0.01" className="input font-mono" value={form.stampDuty} onChange={(event) => set("stampDuty", event.target.value)} />
              </Field>
              <Field label="过户费">
                <input type="number" min="0" step="0.01" className="input font-mono" value={form.transferFee} onChange={(event) => set("transferFee", event.target.value)} />
              </Field>
            </div>
          )}

          {(side === "SELL" || amount > 0) && (
            <div className="mt-5 rounded-lg border border-[#25324a] bg-[#111821] p-4 text-[12px]">
              <PreviewRow label="成交总额:" value={`¥ ${money(amount)}`} />
              <PreviewRow label={form.manualFeeOverride ? "券商实际综合税费:" : "自动估算综合税费:"} value={`¥ ${money(fees.totalFee)}`} />
              <PreviewRow label={side === "BUY" ? "交易后预计可用:" : "交易后预计到账可用:"} value={`¥ ${money(projectedCash)}`} cls={projectedCash >= 0 ? "text-emerald-300" : "text-rose-300"} />
              {side === "SELL" && <PreviewRow label="预计实现盈亏:" value={signedMoney(projectedRealized)} cls={tone(projectedRealized)} />}

              <div className="mt-4 space-y-2">
                {quantityWarning && <Warning text="成交数量不是 100 股整数倍，会被纳入纪律审计提醒。" />}
                {cashWarning && <Warning text="买入后现金为负，后端会标记资金不足。" />}
                {overSell && <Warning text="卖出数量超过当前可卖数量，非历史补录无法提交。" />}
                {t1Warning && <Warning text="触发 T+1 交易锁机制：该股票今日可卖数量为 0，需要设置历史补录或等待可卖后登记。" />}
              </div>
            </div>
          )}

          {mode === "real" && (
            <div className="mt-4 rounded-lg border border-orange-900 bg-orange-950/30 p-3 text-xs leading-5 text-orange-300">
              <ShieldAlert size={15} className="mr-2 inline" />
              当前正在记录实盘交易，请确认成交信息来自同花顺或券商真实成交回报。
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-[#25324a] bg-[#101620] px-6 py-4">
          <button className="btn" onClick={onClose}>取消</button>
          <button
            className={`${side === "BUY" ? "btn-buy" : "btn-sell"} min-w-28`}
            disabled={!form.code || !form.name || price <= 0 || quantity <= 0 || Boolean(overSell || t1Warning)}
            onClick={save}
          >
            {edit ? "保存修改" : "登记入账"}
          </button>
        </div>
      </section>
    </div>
  );
}

export function SettingsDrawer({
  mode,
  strategyId,
  settings,
  onClose,
  onMutate,
}: {
  mode: Mode;
  strategyId: StrategyId;
  settings: AppSettings;
  onClose: () => void;
  onMutate: (p: Promise<Workspace>) => void;
}) {
  const [tab, setTab] = useState<SettingsTab>("account");
  const [local, setLocal] = useState<AppSettings>(() => structuredClone(settings));
  const rec = local.reconciliation[mode];
  const market = local.market || {};
  const patchAccount = (target: Mode, patch: Partial<SettingsData>) => setLocal((current) => ({ ...current, [target]: { ...current[target], ...patch } }));
  const patchRec = (patch: Partial<Reconciliation>) =>
    setLocal((current) => ({ ...current, reconciliation: { ...current.reconciliation, [mode]: { ...current.reconciliation[mode], ...patch } } }));
  const patchMarket = (patch: Record<string, unknown>) => setLocal((current) => ({ ...current, market: { ...current.market, ...patch } }));
  const saveSettings = () => {
    onMutate(request(apiPath(mode, "/settings", strategyId), { method: "PUT", body: JSON.stringify(local) }));
    onClose();
  };
  const saveAndRecalculateFees = () => {
    const task = request<Workspace>(apiPath(mode, "/settings", strategyId), { method: "PUT", body: JSON.stringify(local) })
      .then(() => request<Workspace>(apiPath(mode, "/trades/recalculate-fees", strategyId), { method: "POST", body: "{}" }));
    onMutate(task);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-[3px]" onMouseDown={onClose}>
      <aside className="ml-auto flex h-full w-full max-w-[654px] flex-col border-l border-[#25324a] bg-[#121722] shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-[#25324a] bg-[#151b2b] px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-indigo-600/30 text-indigo-300">
              <Settings2 size={19} />
            </div>
            <div>
              <h2 className="text-lg font-black text-white">策略与账户设置中心</h2>
              <p className="mt-1 text-xs text-[#8a94a3]">设置模拟与实盘的本金、手续费及行情参数</p>
            </div>
          </div>
          <button className="icon-btn border-0 bg-transparent" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="flex border-b border-[#25324a] bg-[#121722] px-4">
          {[
            ["account", "账户管理"],
            ["fee", "费用配置"],
            ["reconciliation", "同花顺对账"],
            ["market", "行情源配置"],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key as SettingsTab)}
              className={`border-b-2 px-4 py-4 text-[13px] font-black ${
                tab === key ? "border-indigo-500 text-indigo-300" : "border-transparent text-[#8a94a3] hover:text-white"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          {tab === "account" && (
            <div className="space-y-6">
              <h3 className="text-[15px] font-black text-[#cfd6df]">初始本金与描述</h3>
              <AccountPanel target="simulation" title="模拟训练账户" code="ACCOUNT_SIMULATION" account={local.simulation} onPatch={(patch) => patchAccount("simulation", patch)} />
              <AccountPanel target="real" title="实盘记录账户" code="ACCOUNT_REAL" account={local.real} onPatch={(patch) => patchAccount("real", patch)} />
            </div>
          )}

          {tab === "fee" && (
            <div className="space-y-5">
              <PanelHeader title="模拟与实盘手续费配置" subtitle="两套费率各自保存；交易保存和手续费重算只会读取当前账本对应费率。" />
              <FeePanel target="simulation" title="模拟训练手续费" code="FEE_SIMULATION" account={local.simulation} onPatch={(patch) => patchAccount("simulation", patch)} />
              <FeePanel target="real" title="实盘记录手续费" code="FEE_REAL" account={local.real} onPatch={(patch) => patchAccount("real", patch)} />
              <div className="rounded-lg border border-[#25324a] bg-[#111821] p-4">
                <div className="text-[12px] leading-5 text-[#9aa3af]">
                  修改费率后，已登记的历史交易不会自动变化；需要重算手续费才会刷新资产、费用和盈亏。
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button className="btn-primary" onClick={saveSettings}>
                    <Save size={15} />
                    仅保存费率
                  </button>
                  <button className="btn" onClick={saveAndRecalculateFees}>
                    保存并重算当前账本手续费
                  </button>
                </div>
              </div>
            </div>
          )}

          {tab === "reconciliation" && (
            <div className="space-y-5">
              <PanelHeader title="同花顺期末数手工对账" subtitle="仅用于对照展示，不读取券商、不覆盖流水。" />
              <label className="flex gap-2 rounded-lg border border-[#25324a] bg-[#111821] p-3 text-xs text-[#9aa3af]">
                <input type="checkbox" checked={rec.enabled} onChange={(event) => patchRec({ enabled: event.target.checked, updatedAt: new Date().toISOString() })} />
                启用对账数字
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <NumberField label="券商总资产" value={rec.totalAssets} onChange={(value) => patchRec({ totalAssets: value })} />
                <NumberField label="可用现金" value={rec.availableCash} onChange={(value) => patchRec({ availableCash: value })} />
                <NumberField label="持仓市值" value={rec.holdingValue} onChange={(value) => patchRec({ holdingValue: value })} />
                <NumberField label="持仓盈亏" value={rec.holdingPnL} onChange={(value) => patchRec({ holdingPnL: value })} />
                <NumberField label="今日盈亏" value={rec.todayPnL} onChange={(value) => patchRec({ todayPnL: value })} />
                <Field label="备注">
                  <input className="input" value={rec.remark} onChange={(event) => patchRec({ remark: event.target.value })} />
                </Field>
              </div>
            </div>
          )}

          {tab === "market" && (
            <div className="space-y-5">
              <PanelHeader title="行情源配置" subtitle="默认离线使用最近成交价；启用实时行情后用于持仓监控、浮动盈亏和股票名称补全。" />
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex gap-2 rounded-lg border border-[#25324a] bg-[#111821] p-3 text-xs text-[#9aa3af]">
                  <input type="checkbox" checked={Boolean(market.enableRealtime)} onChange={(event) => patchMarket({ enableRealtime: event.target.checked })} />
                  启用实时行情
                </label>
                <label className="flex gap-2 rounded-lg border border-[#25324a] bg-[#111821] p-3 text-xs text-[#9aa3af]">
                  <input type="checkbox" checked={Boolean(market.autoRefresh)} onChange={(event) => patchMarket({ autoRefresh: event.target.checked })} />
                  自动刷新工作区
                </label>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="行情源">
                  <select className="input" value={String(market.provider || "sina")} onChange={(event) => patchMarket({ provider: event.target.value })}>
                    <option value="sina">Sina 实时行情</option>
                    <option value="manual">手工行情快照</option>
                  </select>
                </Field>
                <Field label="行情来源说明">
                  <input className="input" value={String(market.source || "")} onChange={(event) => patchMarket({ source: event.target.value })} />
                </Field>
                <NumberField label="自动刷新间隔 (秒)" value={Number(market.refreshInterval || 60)} onChange={(value) => patchMarket({ refreshInterval: value })} />
                <NumberField label="请求超时 (秒)" value={Number(market.timeoutSeconds || 3)} onChange={(value) => patchMarket({ timeoutSeconds: value })} />
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <Mini label="基础买入约束" value="价格有效、资金充足，数量应为 100 股整数倍" />
                <Mini label="基础卖出约束" value="T+1 可卖数量内登记，策略节点由当前交易模式决定" />
                <Mini label="当前行情口径" value={market.enableRealtime ? `${market.provider || "sina"} · ${market.autoRefresh ? "自动刷新" : "手动刷新"}` : "离线：最近成交价"} />
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-[#25324a] bg-[#101620] px-6 py-4">
          <button className="btn" onClick={onClose}>取消</button>
          <button className="btn-primary" onClick={saveSettings}>
            <Save size={15} />
            保存修改
          </button>
        </div>
      </aside>
    </div>
  );
}

export function Notices({ mode, strategyId, items, onClose, onReload }: { mode: Mode; strategyId: StrategyId; items: Notice[]; onClose: () => void; onReload: () => void }) {
  const act = async (url: string, init: RequestInit) => {
    await request(url, init);
    onReload();
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-[2px]" onMouseDown={onClose}>
      <aside className="ml-auto h-full w-full max-w-lg overflow-y-auto border-l border-[#25324a] bg-[#121722] p-5" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-black text-white">通知中心</h2>
            <p className="mt-1 text-xs text-[#8a94a3]">{modeLabel(mode)}账户通知</p>
          </div>
          <button className="icon-btn" onClick={onClose}><X size={17} /></button>
        </div>
        <div className="mt-4 flex gap-2">
          <button className="btn" onClick={() => void act(apiPath(mode, "/notifications/read-all", strategyId), { method: "POST", body: "{}" })}>全部已读</button>
          <button className="btn" onClick={() => void act(apiPath(mode, "/notifications", strategyId), { method: "DELETE" })}>清空</button>
        </div>
        <div className="mt-4 space-y-2">
          {!items.length ? (
            <Empty text="暂无通知。" />
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                onClick={() => !item.read && void act(apiPath(mode, `/notifications/${item.id}/read`, strategyId), { method: "PUT", body: "{}" })}
                className={`w-full rounded-lg border p-3 text-left ${item.read ? "border-[#25324a] opacity-60" : "border-cyan-900 bg-cyan-950/20"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <b className="text-sm text-white">{item.title}</b>
                  <Badge tone={item.read ? "slate" : "cyan"}>{item.type}</Badge>
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-400">{item.message}</p>
                <div className="mt-2 font-mono text-[10px] text-[#77808f]">{item.timestamp}</div>
              </button>
            ))
          )}
        </div>
      </aside>
    </div>
  );
}

function AccountPanel({ target, title, code, account, onPatch }: { target: Mode; title: string; code: string; account: SettingsData; onPatch: (patch: Partial<SettingsData>) => void }) {
  const isReal = target === "real";
  return (
    <section className={`rounded-lg border p-4 ${isReal ? "border-rose-900/70 bg-rose-950/10" : "border-blue-800/70 bg-blue-950/10"}`}>
      <div className="mb-4 flex items-center justify-between border-b border-[#25324a] pb-3">
        <div className={`font-black ${isReal ? "text-rose-300" : "text-blue-300"}`}>● {title}</div>
        <div className="font-mono text-[10px] tracking-widest text-[#77808f]">{code}</div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <NumberField label={`${isReal ? "实盘" : "训练"}初始本金 (元)`} value={account.initialCash} onChange={(value) => onPatch({ initialCash: value })} />
        <Field label="默认交易备注">
          <input className="input" value={account.defaultRemark} onChange={(event) => onPatch({ defaultRemark: event.target.value })} />
        </Field>
      </div>
      <Field label={`${isReal ? "实盘" : "训练"}账户用途说明`}>
        <textarea className="input mt-3 min-h-[58px] resize-none" value={account.accountDesc} onChange={(event) => onPatch({ accountDesc: event.target.value })} />
      </Field>
    </section>
  );
}

function FeePanel({ target, title, code, account, onPatch }: { target: Mode; title: string; code: string; account: SettingsData; onPatch: (patch: Partial<SettingsData>) => void }) {
  const isReal = target === "real";
  return (
    <section className={`rounded-lg border p-4 ${isReal ? "border-rose-900/70 bg-rose-950/10" : "border-blue-800/70 bg-blue-950/10"}`}>
      <div className="mb-4 flex items-center justify-between border-b border-[#25324a] pb-3">
        <div className={`font-black ${isReal ? "text-rose-300" : "text-blue-300"}`}>● {title}</div>
        <div className="font-mono text-[10px] tracking-widest text-[#77808f]">{code}</div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <RateField label="佣金费率" value={account.commissionRate} onChange={(value) => onPatch({ commissionRate: value })} />
        <NumberField label="最低佣金" value={account.minCommission} onChange={(value) => onPatch({ minCommission: value })} />
        <RateField label="卖出印花税率" value={account.stampDutyRate} onChange={(value) => onPatch({ stampDutyRate: value })} />
        <RateField label="过户费率" value={account.transferFeeRate} onChange={(value) => onPatch({ transferFeeRate: value })} />
      </div>
      <label className="mt-4 flex gap-2 rounded-lg border border-[#25324a] bg-[#111821] p-3 text-xs text-[#9aa3af]">
        <input type="checkbox" checked={account.enableMinCommission} onChange={(event) => onPatch({ enableMinCommission: event.target.checked })} />
        启用最低佣金
      </label>
    </section>
  );
}

function RateField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  const [text, setText] = useState(() => formatRateInput(value));
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!editing) setText(formatRateInput(value));
  }, [editing, value]);

  const update = (raw: string) => {
    const next = normalizeRateInput(raw);
    setText(next);
    const parsed = Number(next);
    if (next && next !== "." && Number.isFinite(parsed) && parsed >= 0) {
      onChange(parsed);
    }
  };

  const commit = () => {
    setEditing(false);
    const parsed = Number(text);
    const safeValue = Number.isFinite(parsed) && parsed >= 0 ? parsed : value;
    onChange(safeValue);
    setText(formatRateInput(safeValue));
  };

  return (
    <Field label={label}>
      <input
        type="text"
        inputMode="decimal"
        className="input font-mono"
        placeholder="例如 0.00030986"
        value={text}
        onFocus={() => setEditing(true)}
        onBlur={commit}
        onChange={(event) => update(event.target.value)}
      />
      <div className="mt-1 text-[10px] leading-4 text-[#77808f]">
        {rateHint(Number(text || value))}
      </div>
    </Field>
  );
}

function PanelHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h3 className="text-[15px] font-black text-white">{title}</h3>
      <p className="mt-1 text-xs leading-5 text-[#8a94a3]">{subtitle}</p>
    </div>
  );
}

function PreviewRow({ label, value, cls = "text-white" }: { label: string; value: string; cls?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-[#25324a] py-2 last:border-b-0">
      <span className="text-[#8a94a3]">{label}</span>
      <span className={`font-mono font-black ${cls}`}>{value}</span>
    </div>
  );
}

function Warning({ text }: { text: string }) {
  return <div className="rounded-lg border border-amber-700/70 bg-amber-950/25 p-3 text-[11px] leading-5 text-amber-200">{text}</div>;
}

function TimeWheelPicker({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const hourRef = useRef<HTMLDivElement | null>(null);
  const minuteRef = useRef<HTMLDivElement | null>(null);
  const { hour, minute } = parseTime(value);
  const display = formatTime(hour, minute);

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", closeOutside);
    return () => document.removeEventListener("mousedown", closeOutside);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    window.requestAnimationFrame(() => {
      hourRef.current?.querySelector(`[data-value="${hour}"]`)?.scrollIntoView({ block: "center" });
      minuteRef.current?.querySelector(`[data-value="${minute}"]`)?.scrollIntoView({ block: "center" });
    });
  }, [hour, minute, open]);

  const chooseTime = (nextValue: string) => {
    onChange(nextValue);
    setOpen(false);
  };
  const setPart = (nextHour: number, nextMinute: number) => chooseTime(formatTime(nextHour, nextMinute));

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        className="input flex h-[42px] items-center justify-between gap-2 px-3 text-left font-mono"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{display}</span>
        <Clock3 size={15} className="shrink-0 text-[#7f8a99]" />
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+0.45rem)] z-[70] rounded-lg border border-[#303a49] bg-[#0f151f] p-3 shadow-2xl">
          <div className="grid grid-cols-[1fr_auto_1fr] gap-2">
            <TimeWheelColumn label="时" value={hour} options={hourOptions} containerRef={hourRef} onSelect={(next) => setPart(next, minute)} />
            <div className="pt-[48px] font-mono text-lg font-black text-[#77808f]">:</div>
            <TimeWheelColumn label="分" value={minute} options={minuteOptions} containerRef={minuteRef} onSelect={(next) => setPart(hour, next)} />
          </div>

          <div className="mt-3 grid grid-cols-5 gap-1.5">
            <button type="button" className="time-chip" onClick={() => chooseTime(nowTime())}>现在</button>
            {quickTimes.map((time) => (
              <button key={time} type="button" className="time-chip" onClick={() => chooseTime(time)}>
                {time}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TimeWheelColumn({
  label,
  value,
  options,
  containerRef,
  onSelect,
}: {
  label: string;
  value: number;
  options: number[];
  containerRef: RefObject<HTMLDivElement | null>;
  onSelect: (value: number) => void;
}) {
  return (
    <div className="min-w-0">
      <div className="mb-2 text-center text-[10px] font-black text-[#77808f]">{label}</div>
      <div ref={containerRef} className="time-wheel max-h-[150px] overflow-y-auto rounded-md border border-[#25324a] bg-[#0c1118] p-1">
        {options.map((option) => {
          const active = option === value;
          return (
            <button
              key={option}
              type="button"
              data-value={option}
              className={`time-wheel-item h-8 w-full rounded-[5px] font-mono text-xs font-black transition ${
                active ? "bg-[var(--tz-accent-soft)] text-[var(--tz-accent-text)] shadow-[inset_0_0_0_1px_var(--tz-accent-border)]" : "text-[#8a94a3] hover:bg-[#151d2a] hover:text-white"
              }`}
              onClick={() => onSelect(option)}
            >
              {padTime(option)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function snapshotObject(value: unknown): StrategySnapshot {
  return value && typeof value === "object" ? value as StrategySnapshot : {};
}

function initialMode3EntryChecklist(snapshot?: StrategySnapshot): Record<Mode3EntryCheckKey, boolean> {
  const entry = snapshotObject(snapshot?.entryChecklist);
  return Object.fromEntries(mode3EntryChecklist.map(([key]) => [key, Boolean(entry[key])])) as Record<Mode3EntryCheckKey, boolean>;
}

function initialMode3Fields(snapshot?: StrategySnapshot): Mode3Fields {
  const item = snapshotObject(snapshot);
  return {
    ma10AtEntry: stringValue(item.ma10AtEntry),
    distanceToMa10Pct: stringValue(item.distanceToMa10Pct),
    priorLimitUp: Boolean(item.priorLimitUp),
    entryPatternNote: stringValue(item.entryPatternNote),
    manualJudgement: stringValue(item.manualJudgement),
    exitReason: stringValue(item.exitReason),
    extendedObservation: Boolean(item.extendedObservation),
    maxProfitPct: stringValue(item.maxProfitPct),
    exitNote: stringValue(item.exitNote),
  };
}

function buildMode3Snapshot(side: Side, entry: Record<Mode3EntryCheckKey, boolean>, fields: Mode3Fields): StrategySnapshot {
  if (side === "BUY") {
    return {
      entryChecklist: entry,
      ma10AtEntry: numberOrEmpty(fields.ma10AtEntry),
      distanceToMa10Pct: numberOrEmpty(fields.distanceToMa10Pct),
      priorLimitUp: fields.priorLimitUp,
      plannedExitRule: "NEXT_TRADING_DAY",
      entryPatternNote: fields.entryPatternNote.trim(),
      manualJudgement: fields.manualJudgement.trim(),
    };
  }
  return {
    exitReason: fields.exitReason,
    extendedObservation: fields.extendedObservation,
    maxProfitPct: numberOrEmpty(fields.maxProfitPct),
    exitNote: fields.exitNote.trim(),
  };
}

function stringValue(value: unknown) {
  return value === undefined || value === null ? "" : String(value);
}

function numberOrEmpty(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : "";
}

function parseTime(value: string) {
  const [rawHour, rawMinute] = String(value || "").split(":");
  return {
    hour: clampTimePart(Number.parseInt(rawHour, 10), 23),
    minute: clampTimePart(Number.parseInt(rawMinute, 10), 59),
  };
}

function normalizeTime(value: string) {
  const { hour, minute } = parseTime(value);
  return formatTime(hour, minute);
}

function normalizePriceInput(value: string) {
  const normalized = value
    .replace(/[０-９]/g, (char) => String.fromCharCode(char.charCodeAt(0) - 0xfee0))
    .replace(/[，,。．]/g, ".")
    .replace(/[^\d.]/g, "");
  if (!normalized) return "";
  const [whole, ...decimalParts] = normalized.split(".");
  const decimal = decimalParts.join("").slice(0, 3);
  return decimalParts.length ? `${whole || "0"}.${decimal}` : whole;
}

function normalizeSignedDecimalInput(value: string) {
  const normalized = value
    .replace(/[０-９]/g, (char) => String.fromCharCode(char.charCodeAt(0) - 0xfee0))
    .replace(/[，,。．]/g, ".")
    .replace(/[^\d.-]/g, "");
  if (!normalized) return "";
  const sign = normalized.startsWith("-") ? "-" : "";
  const unsigned = normalized.replace(/-/g, "");
  const [whole, ...decimalParts] = unsigned.split(".");
  const decimal = decimalParts.join("").slice(0, 3);
  return decimalParts.length ? `${sign}${whole || "0"}.${decimal}` : `${sign}${whole}`;
}

function normalizeRateInput(value: string) {
  const normalized = value
    .replace(/[０-９]/g, (char) => String.fromCharCode(char.charCodeAt(0) - 0xfee0))
    .replace(/[，,。．]/g, ".")
    .replace(/[^\d.]/g, "");
  if (!normalized) return "";
  const [whole, ...decimalParts] = normalized.split(".");
  const decimal = decimalParts.join("").slice(0, 10);
  return decimalParts.length ? `${whole || "0"}.${decimal}` : whole;
}

function formatRateInput(value: number) {
  if (!Number.isFinite(value)) return "0";
  return Number(value).toFixed(10).replace(/0+$/, "").replace(/\.$/, "");
}

function rateHint(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "费率为 0";
  return `约万分之 ${(value * 10000).toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}`;
}

function formatTime(hour: number, minute: number) {
  return `${padTime(clampTimePart(hour, 23))}:${padTime(clampTimePart(minute, 59))}`;
}

function padTime(value: number) {
  return String(value).padStart(2, "0");
}

function clampTimePart(value: number, max: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.min(max, Math.max(0, value));
}

function calculateFeePreview(side: Side, amount: number, settings: SettingsData) {
  const commissionRaw = amount * Number(settings.commissionRate || 0);
  const commission = settings.enableMinCommission && amount > 0 ? Math.max(commissionRaw, Number(settings.minCommission || 0)) : commissionRaw;
  const stampDuty = side === "SELL" ? amount * Number(settings.stampDutyRate || 0) : 0;
  const transferFee = amount * Number(settings.transferFeeRate || 0);
  return {
    commission,
    stampDuty,
    transferFee,
    totalFee: commission + stampDuty + transferFee,
  };
}
