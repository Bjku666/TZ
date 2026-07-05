import { useMemo, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { candidateToStock, compactMoney, pct, price } from "../../api/adapters";
import { Badge, Button, Field } from "../common/Primitives";
import type { AccountState, Candidate, RuleConfig, SettingsPayload } from "../../types";
import type { TradeInput } from "../../api/client";

function localDate() {
  return new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function localTime() {
  return new Date().toTimeString().slice(0, 8);
}

function estimateFees(type: "BUY" | "SELL", priceValue: number, quantity: number, settings: SettingsPayload) {
  const amount = Math.max(0, priceValue * quantity);
  const commissionRate = Number(settings.commissionRate ?? 0.00031);
  const minCommission = Number(settings.minCommission ?? 0);
  const stampRate = Number(settings.stampDutyRate ?? 0.0005);
  const transferRate = Number(settings.transferFeeRate ?? 0.00001);
  const commission = amount > 0 ? Math.max(amount * commissionRate, minCommission) : 0;
  const stampDuty = type === "SELL" ? amount * stampRate : 0;
  const transferFee = amount * transferRate;
  return { amount, commission, stampDuty, transferFee, totalFee: commission + stampDuty + transferFee };
}

export function BuyTradeModal({
  candidate,
  account,
  rules,
  settings,
  onClose,
  onSubmit,
}: {
  candidate: Candidate;
  account: AccountState;
  rules: RuleConfig | null;
  settings: SettingsPayload;
  onClose: () => void;
  onSubmit: (payload: TradeInput) => Promise<void>;
}) {
  const stock = candidateToStock(candidate, "待买");
  const [priceValue, setPriceValue] = useState(Number(candidate.lastLivePrice || 0));
  const [quantity, setQuantity] = useState(Number(rules?.lotSize || 100));
  const [date, setDate] = useState(localDate());
  const [time, setTime] = useState(localTime());
  const [reason, setReason] = useState("视频原版MA5回踩人工确认买入");
  const [remark, setRemark] = useState("");
  const [manualConfirmed, setManualConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const lotSize = Number(rules?.lotSize || 100);
  const fees = useMemo(() => estimateFees("BUY", priceValue, quantity, settings), [priceValue, quantity, settings]);
  const quantityWarning = quantity > 0 && quantity % lotSize !== 0;
  const oneLotAmount = priceValue * lotSize;
  const canSubmit = priceValue > 0 && quantity > 0 && manualConfirmed;

  async function submit() {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      await onSubmit({
        code: candidate.code,
        name: candidate.name,
        type: "BUY",
        price: priceValue,
        quantity,
        date,
        time,
        reason,
        remark,
        manualConfirmed,
      });
      onClose();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <div className="max-h-[92vh] w-full max-w-3xl overflow-auto rounded border border-slate-800 bg-slate-900 p-5 shadow-2xl">
        <div className="mb-4 flex items-start justify-between gap-4 border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-sm font-black text-slate-100">买入交易记录</h3>
            <p className="mt-1 text-xs text-slate-500">
              {candidate.name} <span className="font-mono">{candidate.code}</span>
            </p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200">
            <XCircle className="h-5 w-5" />
          </button>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-3">
            <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="候选状态" value={stock.stage} />
                <Field label="当前价格" value={price(candidate.lastLivePrice)} mono />
                <Field label="MA5 live" value={price(candidate.lastMa5Live)} mono tone="cyan" />
                <Field label="偏离率" value={pct(candidate.lastDeviation)} mono />
                <Field label="入选日期" value={candidate.selectionDate} mono />
                <Field label="原始批次" value={candidate.sourceBatchId || "-"} mono />
              </div>
            </div>
            <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
              <div className="mb-2 text-[11px] font-black text-slate-400">信号与执行</div>
              <div className="grid grid-cols-2 gap-2">
                <Badge tone={stock.signalQualified ? "green" : "red"}>
                  {stock.signalQualified ? <CheckCircle2 className="mr-1 h-3 w-3" /> : <XCircle className="mr-1 h-3 w-3" />}
                  signalQualified
                </Badge>
                <Badge tone={stock.executionAllowed ? "green" : "red"}>executionAllowed</Badge>
              </div>
              <div className="mt-2 text-[11px] leading-5 text-slate-500">{stock.executionBlockReasons?.join("；") || stock.signalReason}</div>
            </div>
            <div className="grid grid-cols-2 gap-3 rounded border border-slate-800 bg-slate-950/60 p-3">
              <Field label="可用现金" value={compactMoney(account.availableCash)} mono tone="green" />
              <Field label="一手金额" value={compactMoney(oneLotAmount)} mono />
              <Field label="预计费用" value={compactMoney(fees.totalFee)} mono tone="amber" />
              <Field label="预计占用" value={compactMoney(fees.amount + fees.totalFee)} mono />
            </div>
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Input label="买入价格" type="number" step="0.01" value={priceValue} onChange={value => setPriceValue(Number(value))} />
              <Input label="买入数量" type="number" step={lotSize} value={quantity} onChange={value => setQuantity(Number(value))} />
              <Input label="买入日期" type="date" value={date} onChange={setDate} />
              <Input label="买入时间" value={time} onChange={setTime} />
            </div>
            {quantityWarning && <div className="rounded border border-amber-900 bg-amber-950/30 p-2 text-xs font-bold text-amber-300">数量不是{lotSize}股整数倍，保存时仍由后端最终校验。</div>}
            <label className="block">
              <span className="text-[10px] font-bold text-slate-500">买入原因</span>
              <textarea value={reason} onChange={event => setReason(event.target.value)} rows={3} className="mt-1 w-full rounded border border-slate-800 bg-slate-950 p-2 text-xs text-slate-200 outline-none focus:border-cyan-600" />
            </label>
            <Input label="备注" value={remark} onChange={setRemark} />
            <label className="flex items-center gap-2 rounded border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
              <input type="checkbox" checked={manualConfirmed} onChange={event => setManualConfirmed(event.target.checked)} className="h-4 w-4 accent-cyan-500" />
              我已人工核对后端候选状态、买入窗口、价格、数量和资金占用
            </label>
            <div className="flex justify-end gap-2 border-t border-slate-800 pt-3">
              <Button onClick={onClose} variant="ghost">取消</Button>
              <Button onClick={submit} disabled={!canSubmit || submitting} variant="primary">
                {submitting ? "保存中" : "确认并保存买入"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Input({
  label,
  value,
  onChange,
  type = "text",
  step,
}: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  type?: string;
  step?: string | number;
}) {
  return (
    <label className="block">
      <span className="text-[10px] font-bold text-slate-500">{label}</span>
      <input
        type={type}
        step={step}
        value={value}
        onChange={event => onChange(event.target.value)}
        className="mt-1 h-9 w-full rounded border border-slate-800 bg-slate-950 px-2 font-mono text-xs text-slate-200 outline-none focus:border-cyan-600"
      />
    </label>
  );
}
