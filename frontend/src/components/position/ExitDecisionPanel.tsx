import { Clock3 } from "lucide-react";
import { positionStatusLabel } from "../../api/adapters";
import { Badge, Button } from "../common/Primitives";
import type { Position } from "../../types";

export function ExitDecisionPanel({
  position,
  onSell,
  onDefer,
}: {
  position: Position;
  onSell: (position: Position) => void;
  onDefer: (position: Position) => void;
}) {
  const state = String(position.originalExitState || "");
  const needsMorningExit = state === "MORNING_EXIT_DUE";
  const needsAfternoonExit = state === "AFTERNOON_EXIT_DUE" || state === "LIMIT_UP_OPENED_EXIT_DUE";
  const deferred = state === "DEFERRED_TO_AFTERNOON" || Boolean(position.deferExitDecision);
  const tone = needsMorningExit || needsAfternoonExit ? "red" : deferred ? "amber" : position.isTodayBuy ? "slate" : "cyan";

  return (
    <div className="rounded border border-slate-800 bg-slate-950/70 p-3">
      <div className="flex items-center justify-between gap-3">
        <Badge tone={tone}>{positionStatusLabel(position)}</Badge>
        <span className="flex items-center gap-1 font-mono text-[10px] text-slate-500">
          <Clock3 className="h-3 w-3" />
          {position.nextOriginalActionTime || position.nextActionTime || "-"}
        </span>
      </div>
      <div className="mt-2 text-[11px] leading-5 text-slate-500">{position.originalExitMessage || position.advice || "等待后端下一动作提示"}</div>
      {position.executionBlocked && <div className="mt-2 text-[11px] font-bold text-amber-300">{position.executionBlockReason || "执行受阻"}</div>}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button onClick={() => onSell(position)} disabled={position.availableQuantity <= 0} variant={needsMorningExit || needsAfternoonExit ? "danger" : "ghost"}>
          记录卖出
        </Button>
        {needsMorningExit && (
          <Button onClick={() => onDefer(position)} variant="ghost">
            延迟至14:30后处理
          </Button>
        )}
      </div>
    </div>
  );
}
