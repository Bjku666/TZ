import { useMemo, useState } from "react";
import { XCircle } from "lucide-react";
import { compactMoney } from "../../api/adapters";
import { Badge, Button, Field } from "../common/Primitives";
import type { SettingsPayload, TradeLog } from "../../types";
import type { TradeUpdateInput } from "../../api/client";

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

export function EditTradeModal({
  trade,
  settings,
  onClose,
  onSubmit,
}: {
  trade: TradeLog;
  settings: SettingsPayload;
  onClose: () => void;
  onSubmit: (tradeId: string, payload: TradeUpdateInput) => Promise<void>;
}) {
  const [type, setType] = useState<"BUY" | "SELL">(trade.type);
  const [price, setPrice] = useState(Number(trade.price || 0));
  const [quantity, setQuantity] = useState(Number(trade.quantity || 0));
  const [date, setDate] = useState(trade.date);
  const [time, setTime] = useState(trade.time);
  const [reason, setReason] = useState(trade.reason || "");
  const [remark, setRemark] = useState(trade.remark || "");
  const [rulesConclusion, setRulesConclusion] = useState<TradeLog["rulesConclusion"]>(trade.rulesConclusion || "其他");
  const [violationTags, setViolationTags] = useState((trade.violationTags || []).join(", "));
  const [manualFeeOverride, setManualFeeOverride] = useState(false);
  const estimated = useMemo(() => estimateFees(type, price, quantity, settings), [type, price, quantity, settings]);
  const [commission, setCommission] = useState(Number(trade.commission || estimated.commission));
  const [stampDuty, setStampDuty] = useState(Number(trade.stampDuty || estimated.stampDuty));
  const [transferFee, setTransferFee] = useState(Number(trade.transferFee || estimated.transferFee));
  const [submitting, setSubmitting] = useState(false);
  const feeTotal = manualFeeOverride ? commission + stampDuty + transferFee : estimated.totalFee;

  async function submit() {
    setSubmitting(true);
    try {
      await onSubmit(trade.id, {
        type,
        price,
        quantity,
        date,
        time,
        reason,
        remark,
        rulesConclusion,
        violationTags: violationTags
          .split(",")
          .map(item => item.trim())
          .filter(Boolean),
        manualFeeOverride,
        commission,
        stampDuty,
        transferFee,
        totalFee: feeTotal,
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
            <h3 className="text-sm font-black text-slate-100">编辑交易流水</h3>
            <p className="mt-1 text-xs text-slate-500">
              {trade.name} <span className="font-mono">{trade.code}</span> · <span className="font-mono">{trade.id}</span>
            </p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200">
            <XCircle className="h-5 w-5" />
          </button>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3 rounded border border-slate-800 bg-slate-950/60 p-3">
              <Field label="交易金额" value={compactMoney(price * quantity)} mono />
              <Field label="总费用" value={compactMoney(feeTotal)} mono tone="amber" />
              <Field label="原规则结论" value={trade.rulesConclusion} />
              <Field label="原违规标签" value={(trade.violationTags || []).join("、") || "无"} />
            </div>
            <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
              <div className="mb-2 text-[11px] font-black text-slate-400">费用细目</div>
              <label className="mb-3 flex items-center gap-2 text-xs text-slate-300">
                <input type="checkbox" checked={manualFeeOverride} onChange={event => setManualFeeOverride(event.target.checked)} className="h-4 w-4 accent-cyan-500" />
                手工覆盖费用
              </label>
              <div className="grid grid-cols-3 gap-2">
                <Input label="手续费" type="number" step="0.01" value={manualFeeOverride ? commission : estimated.commission.toFixed(2)} disabled={!manualFeeOverride} onChange={value => setCommission(Number(value))} />
                <Input label="印花税" type="number" step="0.01" value={manualFeeOverride ? stampDuty : estimated.stampDuty.toFixed(2)} disabled={!manualFeeOverride} onChange={value => setStampDuty(Number(value))} />
                <Input label="过户费" type="number" step="0.01" value={manualFeeOverride ? transferFee : estimated.transferFee.toFixed(2)} disabled={!manualFeeOverride} onChange={value => setTransferFee(Number(value))} />
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-[10px] font-bold text-slate-500">交易类型</span>
                <select value={type} onChange={event => setType(event.target.value as "BUY" | "SELL")} className="mt-1 h-9 w-full rounded border border-slate-800 bg-slate-950 px-2 text-xs text-slate-200 outline-none focus:border-cyan-600">
                  <option value="BUY">买入</option>
                  <option value="SELL">卖出</option>
                </select>
              </label>
              <Input label="价格" type="number" step="0.01" value={price} onChange={value => setPrice(Number(value))} />
              <Input label="数量" type="number" step={100} value={quantity} onChange={value => setQuantity(Number(value))} />
              <Input label="日期" type="date" value={date} onChange={setDate} />
              <Input label="时间" value={time} onChange={setTime} />
              <label className="block">
                <span className="text-[10px] font-bold text-slate-500">审计结论</span>
                <select value={rulesConclusion} onChange={event => setRulesConclusion(event.target.value as TradeLog["rulesConclusion"])} className="mt-1 h-9 w-full rounded border border-slate-800 bg-slate-950 px-2 text-xs text-slate-200 outline-none focus:border-cyan-600">
                  <option value="符合规则">符合规则</option>
                  <option value="部分不符">部分不符</option>
                  <option value="违规交易">违规交易</option>
                  <option value="其他">其他</option>
                </select>
              </label>
            </div>
            <Input label="违规标签（逗号分隔）" value={violationTags} onChange={setViolationTags} />
            <label className="block">
              <span className="text-[10px] font-bold text-slate-500">原因</span>
              <textarea value={reason} onChange={event => setReason(event.target.value)} rows={3} className="mt-1 w-full rounded border border-slate-800 bg-slate-950 p-2 text-xs text-slate-200 outline-none focus:border-cyan-600" />
            </label>
            <Input label="备注" value={remark} onChange={setRemark} />
            <div className="flex justify-between gap-2 border-t border-slate-800 pt-3">
              <Badge tone="cyan">保存后后端重算持仓、均价、资产与盈亏</Badge>
              <div className="flex gap-2">
                <Button onClick={onClose} variant="ghost">取消</Button>
                <Button onClick={submit} disabled={submitting || price <= 0 || quantity <= 0} variant="primary">
                  {submitting ? "保存中" : "保存修改"}
                </Button>
              </div>
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
  disabled,
}: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  type?: string;
  step?: string | number;
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-[10px] font-bold text-slate-500">{label}</span>
      <input
        type={type}
        step={step}
        value={value}
        disabled={disabled}
        onChange={event => onChange(event.target.value)}
        className="mt-1 h-9 w-full rounded border border-slate-800 bg-slate-950 px-2 font-mono text-xs text-slate-200 outline-none focus:border-cyan-600 disabled:cursor-not-allowed disabled:text-slate-600"
      />
    </label>
  );
}
