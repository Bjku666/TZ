import { useMemo, useState } from "react";
import { XCircle } from "lucide-react";
import { compactMoney, positionStatusLabel, price } from "../../api/adapters";
import { Badge, Button, Field } from "../common/Primitives";
import type { Position, SettingsPayload } from "../../types";
import type { TradeInput } from "../../api/client";

function localDate() {
  return new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function localTime() {
  return new Date().toTimeString().slice(0, 8);
}

function estimateFees(priceValue: number, quantity: number, settings: SettingsPayload) {
  const amount = Math.max(0, priceValue * quantity);
  const commissionRate = Number(settings.commissionRate ?? 0.00031);
  const minCommission = Number(settings.minCommission ?? 0);
  const stampRate = Number(settings.stampDutyRate ?? 0.0005);
  const transferRate = Number(settings.transferFeeRate ?? 0.00001);
  const commission = amount > 0 ? Math.max(amount * commissionRate, minCommission) : 0;
  const stampDuty = amount * stampRate;
  const transferFee = amount * transferRate;
  return { amount, commission, stampDuty, transferFee, totalFee: commission + stampDuty + transferFee };
}

export function SellTradeModal({
  position,
  settings,
  onClose,
  onSubmit,
  onDefer,
}: {
  position: Position;
  settings: SettingsPayload;
  onClose: () => void;
  onSubmit: (payload: TradeInput) => Promise<void>;
  onDefer?: (reason: string) => Promise<void>;
}) {
  const [priceValue, setPriceValue] = useState(Number(position.currentPrice || 0));
  const [quantity, setQuantity] = useState(Number(position.availableQuantity || position.quantity || 0));
  const [date, setDate] = useState(localDate());
  const [time, setTime] = useState(localTime());
  const [reason, setReason] = useState(position.originalExitMessage || "视频原版隔日卖出人工记录");
  const [remark, setRemark] = useState("");
  const [defer, setDefer] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const fees = useMemo(() => estimateFees(priceValue, quantity, settings), [priceValue, quantity, settings]);
  const quantityWarning = quantity > position.availableQuantity;
  const canSubmit = priceValue > 0 && quantity > 0 && !quantityWarning;

  async function submit() {
    setSubmitting(true);
    try {
      if (defer && onDefer) {
        await onDefer(reason || "用户选择延迟至14:30后处理");
        onClose();
        return;
      }
      if (!canSubmit) return;
      await onSubmit({
        code: position.code,
        name: position.name,
        type: "SELL",
        price: priceValue,
        quantity,
        date,
        time,
        reason,
        remark,
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
            <h3 className="text-sm font-black text-slate-100">卖出交易记录</h3>
            <p className="mt-1 text-xs text-slate-500">
              {position.name} <span className="font-mono">{position.code}</span>
            </p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200">
            <XCircle className="h-5 w-5" />
          </button>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3 rounded border border-slate-800 bg-slate-950/60 p-3">
              <Field label="持仓数量" value={position.quantity} mono />
              <Field label="可卖数量" value={position.availableQuantity} mono tone={position.availableQuantity > 0 ? "green" : "red"} />
              <Field label="T+1锁定" value={position.t1LockedQuantity} mono tone={position.t1LockedQuantity > 0 ? "amber" : "slate"} />
              <Field label="买入日期" value={position.buyDate || "-"} mono />
              <Field label="隔日卖出状态" value={positionStatusLabel(position)} />
              <Field label="是否涨停" value={position.isLimitUp ? "是" : "否"} tone={position.isLimitUp ? "green" : "slate"} />
              <Field label="当前价" value={price(position.currentPrice)} mono />
              <Field label="下一动作" value={position.nextOriginalActionTime || position.nextActionTime || "-"} mono />
            </div>
            <div className="rounded border border-slate-800 bg-slate-950/60 p-3 text-[11px] leading-5 text-slate-500">
              {position.originalExitMessage || position.advice || "后端暂无卖出提醒。"}
              {position.sellBlockedReason && <div className="mt-2 text-amber-300">{position.sellBlockedReason}</div>}
            </div>
            <div className="grid grid-cols-2 gap-3 rounded border border-slate-800 bg-slate-950/60 p-3">
              <Field label="卖出金额" value={compactMoney(fees.amount)} mono />
              <Field label="费用预估" value={compactMoney(fees.totalFee)} mono tone="amber" />
              <Field label="预计到账" value={compactMoney(fees.amount - fees.totalFee)} mono tone="green" />
              <Field label="执行状态" value={position.canExecuteSellNow ? "允许卖出" : "受阻"} tone={position.canExecuteSellNow ? "green" : "red"} />
            </div>
          </div>

          <div className="space-y-3">
            <label className="flex items-center gap-2 rounded border border-amber-900/60 bg-amber-950/20 p-3 text-xs text-amber-200">
              <input type="checkbox" checked={defer} onChange={event => setDefer(event.target.checked)} className="h-4 w-4 accent-amber-500" />
              选择延迟至14:30后处理
            </label>
            {!defer && (
              <div className="grid grid-cols-2 gap-3">
                <Input label="卖出价格" type="number" step="0.01" value={priceValue} onChange={value => setPriceValue(Number(value))} />
                <Input label="卖出数量" type="number" step={100} value={quantity} onChange={value => setQuantity(Number(value))} />
                <Input label="卖出日期" type="date" value={date} onChange={setDate} />
                <Input label="卖出时间" value={time} onChange={setTime} />
              </div>
            )}
            {quantityWarning && <div className="rounded border border-rose-900 bg-rose-950/30 p-2 text-xs font-bold text-rose-300">卖出数量超过当前可卖数量，后端会拒绝保存。</div>}
            <label className="block">
              <span className="text-[10px] font-bold text-slate-500">{defer ? "延迟原因" : "卖出原因"}</span>
              <textarea value={reason} onChange={event => setReason(event.target.value)} rows={3} className="mt-1 w-full rounded border border-slate-800 bg-slate-950 p-2 text-xs text-slate-200 outline-none focus:border-cyan-600" />
            </label>
            <Input label="备注" value={remark} onChange={setRemark} />
            <div className="flex justify-between gap-2 border-t border-slate-800 pt-3">
              <Badge tone={defer ? "amber" : "cyan"}>{defer ? "写入延迟事件" : "写入交易流水"}</Badge>
              <div className="flex gap-2">
                <Button onClick={onClose} variant="ghost">取消</Button>
                <Button onClick={submit} disabled={(!defer && !canSubmit) || submitting} variant={defer ? "ghost" : "primary"}>
                  {submitting ? "处理中" : defer ? "记录延迟" : "确认并保存卖出"}
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
