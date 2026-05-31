import Link from "next/link";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import type { SuggestionRow } from "@/lib/suggestions";
import type { PilotHousekeeper } from "@/lib/pilot-housekeepers";
import {
  eventTypeLabel,
  decisionLabel,
  priorityClasses,
  decisionClasses,
  encodeKey,
} from "@/lib/labels";
import { blockerDisplay } from "@/lib/blockers";
import { housekeeperName } from "@/lib/pilot-housekeepers";
import {
  primaryAction,
  stageBadge,
  formatPushTime,
  extractStaleDays,
  secondaryMetaLine,
} from "@/lib/suggestion-list-display";

const ROW_GRID =
  "grid grid-cols-[3.25rem_minmax(0,1fr)_5.5rem] items-start gap-x-3 px-3 sm:grid-cols-[3.5rem_minmax(0,1fr)_5.5rem]";

function orderContextLine(
  r: SuggestionRow,
  pilots: PilotHousekeeper[],
  pushTime: ReturnType<typeof formatPushTime>,
  staleDays: number | null
): string {
  const parts = [eventTypeLabel(r.eventType)];
  if (r.city) parts.push(r.city);
  if (pilots.length) parts.push(housekeeperName(pilots, r.housekeeperId));
  if (pushTime) parts.push(`${pushTime.date} ${pushTime.time}`);
  if (staleDays) parts.push(`停留 ${staleDays} 天`);
  return parts.join(" · ");
}

export function SuggestionInboxTable({
  rows,
  pilots,
  emptyMessage,
}: {
  rows: SuggestionRow[];
  pilots: PilotHousekeeper[];
  emptyMessage: ReactNode;
}) {
  if (rows.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center px-4 text-center text-muted-foreground">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="w-full">
      <div
        className={`${ROW_GRID} text-muted-foreground hidden border-b py-2 text-xs font-medium sm:grid`}
      >
        <div>优先级</div>
        <div>工单 · 跟进</div>
        <div className="text-right">处置</div>
      </div>
      <ul className="divide-y">
        {rows.map((r) => {
          const s = r.suggestion;
          const stage = stageBadge(s);
          const pushTime = formatPushTime(r.processedAt);
          const staleDays = extractStaleDays(s);
          const href = `/suggestions/${encodeKey(r.dedupeKey)}`;
          const meta = secondaryMetaLine(
            s,
            blockerDisplay(r.blocker?.blockerType, r.blocker?.note)
          );

          return (
            <li key={r.dedupeKey}>
              <Link
                href={href}
                className={`${ROW_GRID} group block py-3 transition-colors hover:bg-muted/50`}
              >
                <div className="pt-0.5">
                  <Badge className={priorityClasses(s.优先级)}>
                    {s.优先级 || "—"}
                  </Badge>
                </div>

                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="font-mono text-sm font-medium group-hover:underline">
                      {r.orderNum || r.workOrderId}
                    </span>
                    {stage ? (
                      <Badge variant="outline" className="text-[10px] font-normal">
                        {stage}
                      </Badge>
                    ) : null}
                  </div>
                  <p className="text-muted-foreground truncate text-xs">
                    {orderContextLine(r, pilots, pushTime, staleDays)}
                  </p>
                  <p className="text-sm leading-snug line-clamp-2">
                    {primaryAction(s)}
                  </p>
                  <p className="text-muted-foreground truncate text-xs">{meta}</p>
                </div>

                <div className="flex justify-end pt-0.5">
                  <Badge className={decisionClasses(r.outcome?.decision)}>
                    {decisionLabel(r.outcome?.decision)}
                  </Badge>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
