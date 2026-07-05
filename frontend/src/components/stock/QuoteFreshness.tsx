import { AlertCircle, CheckCircle2 } from "lucide-react";
import { Badge } from "../common/Primitives";

export function QuoteFreshness({
  age,
  stale,
  updatedAt,
}: {
  age?: number | null;
  stale?: boolean;
  updatedAt?: string | null;
}) {
  const ageText =
    typeof age === "number" && Number.isFinite(age)
      ? age < 60
        ? `${Math.round(age)}秒`
        : `${Math.round(age / 60)}分钟`
      : "-";
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge tone={stale ? "red" : "green"}>
        {stale ? <AlertCircle className="mr-1 h-3 w-3" /> : <CheckCircle2 className="mr-1 h-3 w-3" />}
        {stale ? "过期" : "新鲜"}
      </Badge>
      <span className="font-mono text-[11px] text-slate-500">年龄 {ageText}</span>
      {updatedAt && <span className="font-mono text-[11px] text-slate-500">{updatedAt}</span>}
    </div>
  );
}
