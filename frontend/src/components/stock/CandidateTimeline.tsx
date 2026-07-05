import { Clock3 } from "lucide-react";
import { dateTime, pct, price } from "../../api/adapters";
import { EmptyState } from "../common/Primitives";
import type { CandidateEvent } from "../../types";

export function CandidateTimeline({ events }: { events: CandidateEvent[] }) {
  if (!events.length) return <EmptyState title="暂无候选事件" detail="候选状态变化会在后端产生事件后显示。" />;
  return (
    <div className="space-y-2">
      {events.map((event, index) => {
        const eventTime = event.event_time || event.eventTime;
        return (
          <div key={`${event.event_type || "event"}_${eventTime || index}`} className="rounded border border-slate-800 bg-slate-950/60 p-2">
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <Clock3 className="h-3.5 w-3.5 shrink-0 text-cyan-300" />
                <span className="truncate text-[11px] font-black text-slate-200">{event.event_type || "CANDIDATE_EVENT"}</span>
              </div>
              <time className="shrink-0 font-mono text-[10px] text-slate-500">{dateTime(eventTime)}</time>
            </div>
            <div className="mt-1 text-[11px] leading-4 text-slate-500">
              {[event.reason, event.price ? `价 ${price(event.price)}` : "", event.ma5 ? `MA5 ${price(event.ma5)}` : "", event.deviation ? `偏离 ${pct(event.deviation)}` : ""]
                .filter(Boolean)
                .join(" · ") || "后端事件已记录"}
            </div>
          </div>
        );
      })}
    </div>
  );
}
