import type { SuggestionDoc } from "./suggestions";

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

/** 引擎写入的 processed_at → 列表「推送」时间 */
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

/** 列表第二行：报价 · 渠道 · 阻塞（单行截断，避免加列） */
export function secondaryMetaLine(
  s: SuggestionDoc,
  blockerLabel: string
): string {
  const parts: string[] = [];
  const quote = quoteLine(s);
  if (quote !== "—") parts.push(quote);
  const channel = channelPartLine(s);
  if (channel !== "—") parts.push(channel);
  parts.push(`阻塞·${blockerLabel}`);
  return parts.join(" · ");
}

/** 从 LLM 摘要里提取「停留 N 天」（与 WeCom 卡 stale_days 口径对齐） */
export function extractStaleDays(s: SuggestionDoc): number | null {
  const haystack = [s.原因摘要, ...(s.优先级依据 ?? [])]
    .filter(Boolean)
    .join(" ");
  const m = haystack.match(/(?:停留|已停留)\s*(\d+)\s*天/);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) && n > 0 ? n : null;
}
