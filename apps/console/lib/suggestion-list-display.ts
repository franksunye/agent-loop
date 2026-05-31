import type { SuggestionDoc } from "./suggestions";
import type { SuggestionRow } from "./suggestions";
import type { PilotHousekeeper } from "./pilot-housekeepers";
import { eventTypeLabel } from "./labels";
import { housekeeperName } from "./pilot-housekeepers";

export function primaryAction(s: SuggestionDoc): string {
  const action = s.跟进方案?.主行动?.trim();
  if (action) return action;
  const summary = s.原因摘要?.trim();
  if (summary) return summary.length > 80 ? `${summary.slice(0, 79)}…` : summary;
  return "—";
}

export function quoteLine(s: SuggestionDoc): string {
  const sit = s.情况判断 ?? {};
  const parts: string[] = [];
  if (sit.报价状态) parts.push(sit.报价状态);
  if (sit.金额与方案) {
    const head = sit.金额与方案.split("；")[0]?.trim() ?? "";
    if (head) parts.push(head.length > 36 ? `${head.slice(0, 35)}…` : head);
  }
  return parts.join(" · ") || "—";
}

export function channelPartLine(s: SuggestionDoc): string {
  const raw = s.情况判断?.渠道与部位?.trim();
  if (!raw) return "—";
  const head = raw.split("；")[0]?.trim() ?? raw;
  return head.length > 32 ? `${head.slice(0, 31)}…` : head;
}

export function stageBadge(s: SuggestionDoc): string | null {
  const stage = s.情况判断?.商机阶段?.trim();
  return stage || null;
}

export interface PushTimeDisplay {
  date: string;
  time: string;
}

/** processed_at：本条「跟进建议」生成/推送时刻（Action 工件时间，≠ 工单滞留） */
export function formatPushTime(iso: string): PushTimeDisplay | null {
  if (!iso?.trim()) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return {
    date: d.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
    }),
    time: d.toLocaleString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }),
  };
}

export function formatSuggestionIssuedAt(iso: string): string {
  const t = formatPushTime(iso);
  return t ? `建议 ${t.date} ${t.time}` : "";
}

/** 工单在当前 FSM 状态的滞留天数（领域事实，非建议时间） */
export function extractStaleDays(s: SuggestionDoc): number | null {
  const haystack = [s.原因摘要, ...(s.优先级依据 ?? [])]
    .filter(Boolean)
    .join(" ");
  const m = haystack.match(/(?:停留|已停留)\s*(\d+)\s*天/);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) && n > 0 ? n : null;
}

/** L1 工单：事件、归属、滞留（不含建议推送时间） */
export function workOrderContextLine(
  r: SuggestionRow,
  pilots: PilotHousekeeper[],
  staleDays: number | null
): string {
  const parts = [eventTypeLabel(r.eventType)];
  if (r.city) parts.push(r.city);
  if (pilots.length) parts.push(housekeeperName(pilots, r.housekeeperId));
  if (staleDays) parts.push(`滞留 ${staleDays} 天`);
  return parts.join(" · ");
}

/** L2 分析：Agent 对商机的结构化判断（情况判断 + 优先级已在侧栏） */
export function analysisContextLine(s: SuggestionDoc): string {
  const parts: string[] = [];
  const quote = quoteLine(s);
  if (quote !== "—") parts.push(quote);
  const channel = channelPartLine(s);
  if (channel !== "—") parts.push(channel);
  return parts.join(" · ") || "—";
}

/** L4 反馈：管家回填（阻塞类型；处置结果由右侧 badge 表达） */
export function feedbackContextLine(blockerLabel: string): string {
  return `阻塞 · ${blockerLabel}`;
}
