import Link from "next/link";
import type { ReactNode } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  quoteLine,
  channelPartLine,
  stageBadge,
  formatProcessedAt,
} from "@/lib/suggestion-list-display";

export function SuggestionInboxTable({
  rows,
  pilots,
  emptyMessage,
}: {
  rows: SuggestionRow[];
  pilots: PilotHousekeeper[];
  emptyMessage: ReactNode;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-[72px]">优先级</TableHead>
          <TableHead className="min-w-[140px]">工单</TableHead>
          <TableHead className="min-w-[180px]">主行动</TableHead>
          <TableHead className="hidden md:table-cell min-w-[160px]">报价</TableHead>
          <TableHead className="hidden lg:table-cell min-w-[120px]">渠道 · 部位</TableHead>
          <TableHead className="hidden sm:table-cell w-[100px]">阻塞</TableHead>
          <TableHead className="w-[88px] text-right">处置</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.length === 0 ? (
          <TableRow>
            <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
              {emptyMessage}
            </TableCell>
          </TableRow>
        ) : (
          rows.map((r) => {
            const s = r.suggestion;
            const stage = stageBadge(s);
            const when = formatProcessedAt(r.processedAt);
            return (
              <TableRow key={r.dedupeKey} className="group align-top">
                <TableCell className="pt-3">
                  <Badge className={priorityClasses(s.优先级)}>
                    {s.优先级 || "—"}
                  </Badge>
                </TableCell>
                <TableCell className="pt-3">
                  <Link
                    href={`/suggestions/${encodeKey(r.dedupeKey)}`}
                    className="block space-y-1"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-medium group-hover:underline">
                        {r.orderNum || r.workOrderId}
                      </span>
                      {stage ? (
                        <Badge variant="outline" className="text-[10px] font-normal">
                          {stage}
                        </Badge>
                      ) : null}
                    </div>
                    <div className="text-muted-foreground text-xs leading-relaxed">
                      {eventTypeLabel(r.eventType)}
                      {r.city ? ` · ${r.city}` : ""}
                      {pilots.length
                        ? ` · ${housekeeperName(pilots, r.housekeeperId)}`
                        : ""}
                      {when ? ` · ${when}` : ""}
                    </div>
                  </Link>
                </TableCell>
                <TableCell className="pt-3">
                  <Link
                    href={`/suggestions/${encodeKey(r.dedupeKey)}`}
                    className="text-sm leading-snug line-clamp-2 group-hover:underline"
                  >
                    {primaryAction(s)}
                  </Link>
                  <p className="text-muted-foreground mt-1 line-clamp-1 text-xs md:hidden">
                    {quoteLine(s)}
                  </p>
                </TableCell>
                <TableCell className="hidden pt-3 md:table-cell">
                  <p className="text-sm leading-snug line-clamp-2">{quoteLine(s)}</p>
                </TableCell>
                <TableCell className="hidden pt-3 lg:table-cell">
                  <p className="text-muted-foreground text-sm leading-snug line-clamp-2">
                    {channelPartLine(s)}
                  </p>
                </TableCell>
                <TableCell className="hidden pt-3 sm:table-cell">
                  <span className="text-muted-foreground text-xs leading-snug line-clamp-2">
                    {blockerDisplay(r.blocker?.blockerType, r.blocker?.note)}
                  </span>
                </TableCell>
                <TableCell className="pt-3 text-right">
                  <Badge className={decisionClasses(r.outcome?.decision)}>
                    {decisionLabel(r.outcome?.decision)}
                  </Badge>
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
