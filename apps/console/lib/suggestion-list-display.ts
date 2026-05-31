import type { SuggestionDoc } from "./suggestions";
import type { SuggestionRow } from "./suggestions";
import type { PilotHousekeeper } from "./pilot-housekeepers";
import { eventTypeLabel } from "./labels";
import { housekeeperName } from "./pilot-housekeepers";

/** 列表四层标签 — 与详情页「跟进方案 / 情况判断 / 处置」及 trace「生成跟进建议」对齐 */
export const INBOX_LAYER_LABELS = {
  workOrder: "工单",
  situation: "情况判断",
  actionPlan: "跟进方案",
  disposition: "处置",
} as const;

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

/** Mongo updateTime（北京本地 naive）→ UTC ms，与引擎 fsm_mongo 口径一致 */
function parseStateAtUtcMs(raw: string): number | null {
  const s = raw.trim().replace("Z", "").slice(0, 19).replace(" ", "T");
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/.exec(s);
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  const h = Number(m[4]);
  const mi = Number(m[5]);
  const se = Number(m[6]);
  return Date.UTC(y, mo - 1, d, h - 8, mi, se);
}

/** 由 state_at 现算滞留天数（随日历推进自动 +1，非入库快照） */
export function computeStaleDaysFromStateAt(stateAt: string | null | undefined): number | null {
  if (!stateAt?.trim()) return null;
  const startMs = parseStateAtUtcMs(stateAt);
  if (startMs == null) return null;
  const delta = Date.now() - startMs;
  if (delta < 0) return 0;
  return Math.floor(delta / 86_400_000);
}

/** 滞留天数：优先 state_at 现算；旧行无 state_at 时回退 LLM 摘要 */
export function resolveStaleDays(
  row: Pick<SuggestionRow, "stateAt" | "suggestion">
): number | null {
  const fromState = computeStaleDaysFromStateAt(row.stateAt);
  if (fromState != null) return fromState;
  return extractStaleDays(row.suggestion);
}

/** 从 LLM 摘要里提取「停留 N 天」（仅旧行回退；新行应读 state_at 现算） */
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

/** L4 处置：管家回填阻塞（decision 由右侧 badge 表达） */
export function dispositionContextLine(blockerLabel: string): string {
  return `阻塞 · ${blockerLabel}`;
}
