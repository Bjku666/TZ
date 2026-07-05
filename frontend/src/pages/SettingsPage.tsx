import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Coins, Database, RefreshCw, Save, Settings as SettingsIcon } from "lucide-react";
import { Badge, Button, Card, SectionTitle, StatTile } from "../components/common/Primitives";
import { ModeSwitch } from "../components/common/ModeSwitch";
import { modeLabel, money } from "../api/adapters";
import type { AccountMode, FeeConfig, ReconciliationConfig, RuleConfig, SettingsPayload } from "../types";

const defaultSimulationFees: FeeConfig = {
  feeProfile: "ths_simulation",
  commissionRate: 0.00031,
  minCommission: 0,
  stampDutyRate: 0.0005,
  transferFeeRate: 0.00001,
};

const defaultRealFees: FeeConfig = {
  feeProfile: "real_a_share",
  commissionRate: 0.00025,
  minCommission: 5,
  stampDutyRate: 0.0005,
  transferFeeRate: 0.00001,
};

const defaultReconciliation: ReconciliationConfig = {
  enabled: false,
  accountCapital: 0,
  totalAssets: 0,
  availableCash: 0,
  holdingValue: 0,
  holdingPnL: 0,
  todayPnL: 0,
};

export function SettingsPage({
  settings,
  rules,
  busy,
  mode,
  onSave,
  onRecalculateFees,
}: {
  settings: SettingsPayload;
  rules: RuleConfig | null;
  busy: string | null;
  mode: AccountMode;
  onSave: (payload: SettingsPayload) => Promise<void>;
  onRecalculateFees: (mode: AccountMode) => Promise<unknown>;
}) {
  const [form, setForm] = useState<SettingsPayload>(settings);
  const persistedMode = (settings.currentMode || mode || "simulation") as AccountMode;
  const activeMode = (form.currentMode || mode || "simulation") as AccountMode;
  const fees = useMemo(() => activeFees(form, activeMode, persistedMode), [activeMode, form, persistedMode]);
  const reconciliation = useMemo(() => activeReconciliation(form, activeMode, persistedMode), [activeMode, form, persistedMode]);
  const activeInitialCash = Number(activeMode === "real" ? form.realInitialCash ?? 5000 : form.initialCash ?? 10000);
  const saving = busy === "settings";
  const recalculating = busy === "fees";

  useEffect(() => setForm(settings), [settings]);

  function setValue(key: keyof SettingsPayload, value: unknown) {
    setForm(current => ({ ...current, [key]: value }));
  }

  function setMode(nextMode: AccountMode) {
    setForm(current => ({ ...current, currentMode: nextMode }));
  }

  function setFeeValue(key: keyof FeeConfig, value: number | string) {
    setForm(current => {
      const nextFees = { ...activeFees(current, activeMode, persistedMode), [key]: value };
      return {
        ...current,
        currentMode: activeMode,
        [activeMode === "real" ? "realFees" : "simulationFees"]: nextFees,
        ...(activeMode === persistedMode
          ? {
              feeProfile: nextFees.feeProfile,
              commissionRate: nextFees.commissionRate,
              minCommission: nextFees.minCommission,
              stampDutyRate: nextFees.stampDutyRate,
              transferFeeRate: nextFees.transferFeeRate,
            }
          : {}),
      };
    });
  }

  function setReconciliationValue(key: keyof ReconciliationConfig, value: number | boolean) {
    setForm(current => {
      const nextReconciliation = { ...activeReconciliation(current, activeMode, persistedMode), [key]: value };
      return {
        ...current,
        currentMode: activeMode,
        [activeMode === "real" ? "realThsReconciliation" : "simulationThsReconciliation"]: nextReconciliation,
        ...(activeMode === persistedMode ? { thsReconciliation: nextReconciliation } : {}),
      };
    });
  }

  function setInitialCash(value: number) {
    setForm(current => ({
      ...current,
      currentMode: activeMode,
      [activeMode === "real" ? "realInitialCash" : "initialCash"]: value,
      activeInitialCash: value,
    }));
  }

  function payloadForMode(extra: Partial<SettingsPayload> = {}): SettingsPayload {
    const nextFees = activeFees(form, activeMode, persistedMode);
    const nextReconciliation = activeReconciliation(form, activeMode, persistedMode);
    return {
      ...form,
      currentMode: activeMode,
      feeProfile: nextFees.feeProfile,
      commissionRate: nextFees.commissionRate,
      minCommission: nextFees.minCommission,
      stampDutyRate: nextFees.stampDutyRate,
      transferFeeRate: nextFees.transferFeeRate,
      thsReconciliation: nextReconciliation,
      [activeMode === "real" ? "realFees" : "simulationFees"]: nextFees,
      [activeMode === "real" ? "realThsReconciliation" : "simulationThsReconciliation"]: nextReconciliation,
      [activeMode === "real" ? "realInitialCash" : "initialCash"]: activeInitialCash,
      ...extra,
    };
  }

  async function saveModeSettings(extra: Partial<SettingsPayload> = {}) {
    await onSave(payloadForMode(extra));
  }

  async function saveFees(recalculateAfterSave = false) {
    await saveModeSettings();
    if (recalculateAfterSave) await onRecalculateFees(activeMode);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Card className="bg-slate-900/80">
        <SectionTitle
          title="交易系统配置"
          subtitle="模式、资产、费用和对账按账户独立；视频原版交易规则只读展示。"
          action={
            <Button onClick={() => saveModeSettings()} disabled={saving} variant="primary">
              <Save className="h-3.5 w-3.5" />
              {saving ? "保存中" : "保存当前配置"}
            </Button>
          }
        />
        <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950 p-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <div className="text-[10px] font-black text-slate-500">运行账户模式</div>
              <div className="mt-1 text-xs font-semibold text-slate-400">
                切换后，下面费用、对账和本金卡片都会联动到对应账户。
              </div>
            </div>
            <Badge tone={activeMode === "real" ? "red" : "cyan"}>{modeLabel(activeMode)}</Badge>
          </div>
          <ModeSwitch value={activeMode} onChange={setMode} />
          {activeMode !== mode && (
            <div className="mt-2 rounded border border-amber-900/70 bg-amber-950/25 px-3 py-2 text-[11px] font-bold text-amber-200">
              当前页面已切到 {modeLabel(activeMode)} 配置视图；点击保存后，工作台会同步切换并重新拉取该账户资产。
            </div>
          )}
        </div>
      </Card>

      <Card className="bg-slate-900/80">
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
          <Coins className="h-4 w-4 text-cyan-400" />
          <h3 className="text-sm font-black text-slate-100">{activeMode === "real" ? "实盘交易费用口径配置" : "模拟交易费用口径配置"}</h3>
        </div>
        <div className="mt-4 rounded border border-slate-800 bg-slate-950 p-3 text-xs text-slate-300">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span className="font-black">{feeProfileLabel(fees.feeProfile, activeMode)}</span>
            <span className="font-mono text-slate-500">
              佣金 {percentFee(fees.commissionRate)} / 最低 {numberValue(fees.minCommission).toFixed(2)} / 印花税 {percentFee(fees.stampDutyRate)} / 过户费 {percentFee(fees.transferFeeRate)}
            </span>
          </div>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Input label="券商佣金比例" step="0.00001" value={numberValue(fees.commissionRate)} onChange={value => setFeeValue("commissionRate", Number(value))} />
          <Input label="单笔佣金最低起征点" step="0.01" value={numberValue(fees.minCommission)} onChange={value => setFeeValue("minCommission", Number(value))} />
          <Input label="印花税比例" step="0.00001" value={numberValue(fees.stampDutyRate)} onChange={value => setFeeValue("stampDutyRate", Number(value))} />
          <Input label="过户费比例" step="0.00001" value={numberValue(fees.transferFeeRate)} onChange={value => setFeeValue("transferFeeRate", Number(value))} />
        </div>
        <div className="mt-4 flex flex-col justify-end gap-2 border-t border-slate-800 pt-3 sm:flex-row">
          <Button onClick={() => onRecalculateFees(activeMode)} disabled={recalculating} variant="ghost">
            <RefreshCw className={`h-3.5 w-3.5 ${recalculating ? "animate-spin" : ""}`} />
            按当前模式重算历史交易费用
          </Button>
          <Button onClick={() => saveFees(false)} disabled={saving} variant="primary">
            保存当前模式费用口径
          </Button>
          <Button onClick={() => saveFees(true)} disabled={saving || recalculating} variant="success">
            保存并重算
          </Button>
        </div>
      </Card>

      <Card className="bg-slate-900/80">
        <div className="flex items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-cyan-400" />
            <div>
              <h3 className="text-sm font-black text-slate-100">{activeMode === "real" ? "实盘同花顺对账" : "模拟同花顺对账"}</h3>
              <div className="mt-1 text-[11px] text-slate-500">仅用于手工对账，不改变交易流水权威数据。</div>
            </div>
          </div>
          <label className="inline-flex items-center gap-2 text-xs font-bold text-slate-300">
            <input
              type="checkbox"
              checked={Boolean(reconciliation.enabled)}
              onChange={event => setReconciliationValue("enabled", event.target.checked)}
              className="h-4 w-4 accent-cyan-500"
            />
            启用
          </label>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Input label="同花顺账户本金" value={numberValue(reconciliation.accountCapital)} onChange={value => setReconciliationValue("accountCapital", Number(value))} />
          <Input label="同花顺总资产" value={numberValue(reconciliation.totalAssets)} onChange={value => setReconciliationValue("totalAssets", Number(value))} />
          <Input label="同花顺可用资金" value={numberValue(reconciliation.availableCash)} onChange={value => setReconciliationValue("availableCash", Number(value))} />
          <Input label="总市值" value={numberValue(reconciliation.holdingValue)} onChange={value => setReconciliationValue("holdingValue", Number(value))} />
          <Input label="持仓总盈亏" value={numberValue(reconciliation.holdingPnL)} onChange={value => setReconciliationValue("holdingPnL", Number(value))} />
          <Input label="当日参考盈亏" value={numberValue(reconciliation.todayPnL)} onChange={value => setReconciliationValue("todayPnL", Number(value))} />
        </div>
        <div className="mt-4 flex flex-col gap-2 border-t border-slate-800 pt-3 text-xs sm:flex-row sm:items-center sm:justify-between">
          <span className="text-slate-500">
            当前纪律本金 <span className="font-mono font-bold text-slate-300">{activeInitialCash.toFixed(2)}</span>，
            资金偏移 <span className="font-mono font-bold text-cyan-300">{(numberValue(reconciliation.accountCapital) - activeInitialCash).toFixed(2)}</span>
          </span>
          <Button onClick={() => saveModeSettings()} disabled={saving} variant="primary">
            <CheckCircle2 className="h-3.5 w-3.5" />
            保存对账设置
          </Button>
        </div>
      </Card>

      <Card className="bg-slate-900/80">
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
          <SettingsIcon className="h-4 w-4 text-cyan-400" />
          <h3 className="text-sm font-black text-slate-100">{activeMode === "real" ? "实盘交易账户设置" : "模拟交易账户设置"}</h3>
        </div>
        <div className="mt-4">
          <Input
            label={activeMode === "real" ? "调整实盘初始总本金" : "调整模拟初始总本金"}
            value={activeInitialCash}
            onChange={value => setInitialCash(Number(value))}
          />
          <div className="mt-2 text-[11px] leading-5 text-slate-500">
            保存后，后端会按当前模式交易流水重新计算可用资金、持仓、资产和盈亏。
          </div>
        </div>
        <div className="mt-4 flex justify-end border-t border-slate-800 pt-3">
          <Button onClick={() => saveModeSettings()} disabled={saving} variant="primary">
            保存当前账户本金
          </Button>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="bg-slate-900/80">
          <SectionTitle title="行情与通知" />
          <div className="mt-4 grid grid-cols-2 gap-3">
            <Input label="行情源" type="text" value={String(form.quoteSource || form.quote_source || "自动切换")} onChange={value => setValue("quoteSource", value)} />
            <Input label="历史K线源" type="text" value={String(form.historySource || "自动切换")} onChange={value => setValue("historySource", value)} />
            <Input label="刷新频率(秒)" value={Number(form.refreshIntervalSeconds ?? 45)} onChange={value => setValue("refreshIntervalSeconds", Number(value))} />
            <Check label="自动刷新" checked={Boolean(form.autoRefresh ?? true)} onChange={value => setValue("autoRefresh", value)} />
            <Check label="声音通知" checked={Boolean(form.soundNotification)} onChange={value => setValue("soundNotification", value)} />
            <Check label="桌面通知" checked={Boolean(form.desktopNotification)} onChange={value => setValue("desktopNotification", value)} />
          </div>
        </Card>

        <Card className="bg-slate-900/80">
          <SectionTitle title="当前模式摘要" />
          <div className="mt-4 grid grid-cols-2 gap-3">
            <StatTile label="模式" value={modeLabel(activeMode)} tone={activeMode === "real" ? "red" : "cyan"} />
            <StatTile label="初始本金" value={money(activeInitialCash)} />
            <StatTile label="费用口径" value={feeProfileLabel(fees.feeProfile, activeMode)} tone="cyan" />
            <StatTile label="对账" value={reconciliation.enabled ? "已启用" : "未启用"} tone={reconciliation.enabled ? "green" : "slate"} />
          </div>
        </Card>
      </div>

      <Card className="bg-slate-900/80">
        <SectionTitle title="视频原版规则只读" subtitle="以下参数由当前后端规则版本控制，普通设置页不改规则版本。" />
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
          <StatTile label="成交额原始前N" value={rules?.turnoverTopN ?? 20} tone="cyan" />
          <StatTile label="回踩容差" value={`±${rules?.touchTolerancePct ?? 0.5} pct`} />
          <StatTile label="上午买入时段" value={`${rules?.morningBuyWindow?.start || "09:30"}-${rules?.morningBuyWindow?.end || "10:00"}`} />
          <StatTile label="尾盘买入时段" value={`${rules?.afternoonBuyWindow?.start || "14:30"}-${rules?.afternoonBuyWindow?.end || "15:00"}`} />
          <StatTile label="行情新鲜度阈值" value={`${rules?.quoteFreshnessSeconds ?? 60}秒`} />
          <StatTile label="一手股数" value={rules?.lotSize ?? 100} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge tone="slate">前20过滤后不补位</Badge>
          <Badge tone="slate">入选当天不能买</Badge>
          <Badge tone="slate">盘中MA5由后端计算</Badge>
          <Badge tone="slate">T+1和隔日卖出由后端判断</Badge>
        </div>
      </Card>

      <Card className="bg-slate-900/80">
        <SectionTitle title="备份与导出" />
        <div className="mt-3 rounded border border-slate-800 bg-slate-950/60 p-3 text-xs leading-5 text-slate-500">
          数据备份和导出以仓库 data 目录下的后端文件为准；前端提供交易 CSV 导出，完整备份请使用项目脚本或手工复制数据目录。
        </div>
      </Card>
    </div>
  );
}

function activeFees(settings: SettingsPayload, mode: AccountMode, persistedMode: AccountMode): FeeConfig {
  const fallback = mode === "real" ? defaultRealFees : defaultSimulationFees;
  const saved = mode === "real" ? settings.realFees : settings.simulationFees;
  const active = persistedMode === mode
    ? {
        feeProfile: settings.feeProfile,
        commissionRate: settings.commissionRate,
        minCommission: settings.minCommission,
        stampDutyRate: settings.stampDutyRate,
        transferFeeRate: settings.transferFeeRate,
      }
    : {};
  return { ...fallback, ...saved, ...active };
}

function activeReconciliation(settings: SettingsPayload, mode: AccountMode, persistedMode: AccountMode): ReconciliationConfig {
  const saved = mode === "real" ? settings.realThsReconciliation : settings.simulationThsReconciliation;
  const active = persistedMode === mode ? settings.thsReconciliation : {};
  return { ...defaultReconciliation, ...saved, ...active };
}

function numberValue(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function percentFee(value: unknown): string {
  const parsed = numberValue(value);
  if (parsed === 0) return "0%";
  return `${(parsed * 100).toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}%`;
}

function feeProfileLabel(profile: unknown, mode: AccountMode): string {
  const value = String(profile || "");
  if (value === "zero_fee") return "零费用模拟";
  if (value === "ths_simulation") return "同花顺模拟费用参数";
  if (value === "real_a_share") return "实盘A股费用参数";
  return mode === "real" ? "实盘自定义费用参数" : "模拟自定义费用参数";
}

function Input({
  label,
  value,
  onChange,
  type = "number",
  step = "0.01",
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

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex h-9 items-center gap-2 rounded border border-slate-800 bg-slate-950 px-3 text-xs font-bold text-slate-300">
      <input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} className="h-4 w-4 accent-cyan-500" />
      {label}
    </label>
  );
}
