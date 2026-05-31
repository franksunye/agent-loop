import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { SuggestionRow } from "@/lib/suggestions";
import type { PilotHousekeeper } from "@/lib/pilot-housekeepers";
import {
  decisionLabel,
  priorityClasses,
  decisionClasses,
  encodeKey,
} from "@/lib/labels";
import { blockerDisplay } from "@/lib/blockers";
import {
  primaryAction,
  stageBadge,
  extractStaleDays,
  workOrderContextLine,
  analysisContextLine,
  feedbackContextLine,
  formatSuggestionIssuedAt,
} from "@/lib/suggestion-list-display";

const ROW_GRID =
  "grid grid-cols-[3.25rem_minmax(0,1fr)_5.5rem] items-start gap-x-3 px-3 sm:grid-cols-[3.5rem_minmax(0,1fr)_5.5rem]";

/** 列表行内分层标签：工单 → 分析 → 行动 → 反馈 */
function LayerRow({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 gap-2 text-xs leading-relaxed", className)}>
      <span className="text-muted-foreground/60 w-7 shrink-0 select-none">{label}</span>
      <span className="min-w-0 flex-1">{children}</span>
    </div>
  );
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
        <div>跟进条目</div>
        <div className="text-right">处置</div>
      </div>
      <ul className="divide-y">
        {rows.map((r) => {
          const s = r.suggestion;
          const stage = stageBadge(s);
          const staleDays = extractStaleDays(s);
          const issuedAt = formatSuggestionIssuedAt(r.processedAt);
          const href = `/suggestions/${encodeKey(r.dedupeKey)}`;
          const blockerLabel = blockerDisplay(
            r.blocker?.blockerType,
            r.blocker?.note
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

                <div className="min-w-0 space-y-1.5">
                  {/* L0 锚点：工单号 + 商机阶段 */}
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

                  {/* L1 工单事实 */}
                  <LayerRow label="工单">
                    <span className="text-muted-foreground truncate">
                      {workOrderContextLine(r, pilots, staleDays)}
                    </span>
                  </LayerRow>

                  {/* L2 分析（情况判断） */}
                  <LayerRow label="分析">
                    <span className="text-muted-foreground truncate">
                      {analysisContextLine(s)}
                    </span>
                  </LayerRow>

                  {/* L3 行动 + 建议工件时间（与工单滞留分离） */}
                  <LayerRow label="行动" className="text-sm">
                    <span className="line-clamp-2 text-foreground">{primaryAction(s)}</span>
                  </LayerRow>
                  {issuedAt ? (
                    <p className="text-muted-foreground/80 pl-9 text-[11px] tabular-nums">
                      {issuedAt}
                    </p>
                  ) : null}

                  {/* L4 反馈 */}
                  <LayerRow label="反馈">
                    <span className="text-muted-foreground truncate">
                      {feedbackContextLine(blockerLabel)}
                    </span>
                  </LayerRow>
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
