import { Briefcase, GraduationCap } from "lucide-react";
import type { AccountMode } from "../../types";

const modes: Array<{ key: AccountMode; label: string; helper: string; icon: typeof GraduationCap }> = [
  { key: "simulation", label: "模拟训练", helper: "训练账户", icon: GraduationCap },
  { key: "real", label: "实盘记录", helper: "实盘账户", icon: Briefcase },
];

export function ModeSwitch({
  value,
  onChange,
  disabled = false,
  compact = false,
}: {
  value: AccountMode;
  onChange: (mode: AccountMode) => void;
  disabled?: boolean;
  compact?: boolean;
}) {
  return (
    <div className={`grid grid-cols-2 gap-1 rounded border border-slate-800 bg-slate-950 p-1 ${compact ? "" : "w-full"}`}>
      {modes.map(item => {
        const Icon = item.icon;
        const selected = value === item.key;
        return (
          <button
            key={item.key}
            type="button"
            disabled={disabled}
            onClick={() => onChange(item.key)}
            className={`min-w-0 rounded border px-2 py-2 text-left transition disabled:cursor-not-allowed disabled:opacity-60 ${
              selected
                ? item.key === "real"
                  ? "border-rose-500 bg-rose-600 text-white shadow-sm shadow-rose-950/35"
                  : "border-blue-500 bg-blue-600 text-white shadow-sm shadow-blue-950/35"
                : "border-transparent bg-transparent text-slate-500 hover:border-slate-800 hover:bg-slate-900 hover:text-slate-200"
            }`}
          >
            <div className="flex items-center gap-1.5">
              <Icon className={`h-3.5 w-3.5 shrink-0 ${selected ? "" : "text-slate-600"}`} />
              <span className="truncate text-xs font-black">{item.label}</span>
            </div>
            {!compact && <div className="mt-1 truncate text-[10px] font-bold opacity-70">{item.helper}</div>}
          </button>
        );
      })}
    </div>
  );
}
