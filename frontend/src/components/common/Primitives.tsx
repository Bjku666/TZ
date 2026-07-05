import type { ButtonHTMLAttributes, ReactNode } from "react";
import { stateTone } from "../../api/adapters";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded border border-slate-800 bg-slate-950/55 p-4 shadow-sm ${className}`}>{children}</section>;
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded border border-slate-800 bg-slate-900/70 ${className}`}>{children}</div>;
}

export function SectionTitle({
  title,
  subtitle,
  action,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-w-0 items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="truncate text-sm font-black text-slate-100">{title}</h2>
        {subtitle && <p className="mt-1 text-xs font-medium text-slate-500">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function StatTile({ label, value, tone = "slate" }: { label: string; value: ReactNode; tone?: "slate" | "cyan" | "green" | "red" | "amber" }) {
  const color =
    tone === "cyan"
      ? "text-cyan-300"
      : tone === "green"
        ? "text-emerald-300"
        : tone === "red"
          ? "text-rose-300"
          : tone === "amber"
            ? "text-amber-300"
            : "text-slate-100";
  return (
    <div className="min-w-0 rounded border border-slate-800 bg-slate-950/70 px-3 py-2">
      <div className="truncate text-[11px] font-bold text-slate-500">{label}</div>
      <div className={`mt-1 truncate font-mono text-sm font-black ${color}`}>{value}</div>
    </div>
  );
}

export function Button({
  children,
  className = "",
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "success" | "muted" }) {
  const variants = {
    primary: "border-cyan-500/50 bg-cyan-600 text-white hover:bg-cyan-500",
    ghost: "border-slate-700 bg-slate-900 text-slate-300 hover:border-cyan-700 hover:text-cyan-200",
    danger: "border-rose-500/50 bg-rose-950/70 text-rose-200 hover:bg-rose-900",
    success: "border-emerald-500/50 bg-emerald-950/70 text-emerald-200 hover:bg-emerald-900",
    muted: "border-slate-800 bg-slate-950 text-slate-500 hover:text-slate-300",
  }[variant];
  return (
    <button
      {...props}
      className={`inline-flex h-8 items-center justify-center gap-1.5 rounded border px-3 text-xs font-bold transition disabled:cursor-not-allowed disabled:opacity-50 ${variants} ${className}`}
    >
      {children}
    </button>
  );
}

export function IconButton({ children, className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  return (
    <button
      {...props}
      className={`inline-flex h-8 w-8 items-center justify-center rounded border border-slate-800 bg-slate-950 text-slate-400 transition hover:border-cyan-700 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {children}
    </button>
  );
}

export function Badge({
  children,
  tone = "slate",
  className = "",
}: {
  children: ReactNode;
  tone?: "slate" | "cyan" | "green" | "red" | "amber";
  className?: string;
}) {
  const variants = {
    slate: "border-slate-700 bg-slate-950 text-slate-300",
    cyan: "border-cyan-800 bg-cyan-950/70 text-cyan-300",
    green: "border-emerald-800 bg-emerald-950/70 text-emerald-300",
    red: "border-rose-800 bg-rose-950/70 text-rose-300",
    amber: "border-amber-800 bg-amber-950/70 text-amber-300",
  };
  return <span className={`inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-bold ${variants[tone]} ${className}`}>{children}</span>;
}

export function StateBadge({ state }: { state: string }) {
  return <Badge tone={stateTone[state] || "slate"}>{state}</Badge>;
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="rounded border border-dashed border-slate-800 bg-slate-950/30 p-6 text-center">
      <div className="text-sm font-bold text-slate-300">{title}</div>
      {detail && <div className="mt-1 text-xs text-slate-500">{detail}</div>}
    </div>
  );
}

export function Field({
  label,
  value,
  mono = false,
  tone = "slate",
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
  tone?: "slate" | "cyan" | "green" | "red" | "amber";
}) {
  const color =
    tone === "cyan"
      ? "text-cyan-300"
      : tone === "green"
        ? "text-emerald-300"
        : tone === "red"
          ? "text-rose-300"
          : tone === "amber"
            ? "text-amber-300"
            : "text-slate-200";
  return (
    <div className="min-w-0">
      <div className="truncate text-[10px] font-bold text-slate-500">{label}</div>
      <div className={`mt-0.5 truncate text-xs font-bold ${mono ? "font-mono" : ""} ${color}`}>{value}</div>
    </div>
  );
}
