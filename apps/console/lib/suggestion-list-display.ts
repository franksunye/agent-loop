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

export function formatProcessedAt(iso: string): string {
  if (!iso?.trim()) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}
