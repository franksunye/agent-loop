import type { Decision, SuggestionRow } from "./suggestions";
import type { PilotHousekeeper } from "./pilot-housekeepers";
import { housekeeperName } from "./pilot-housekeepers";
import { resolveStaleDays } from "./suggestion-list-display";

export type SuggestionSortKey =
  | "latest"
  | "housekeeper"
  | "stale"
  | "priority"
  | "disposition";

const ALL_SORT_KEYS: SuggestionSortKey[] = [
  "latest",
  "housekeeper",
  "stale",
  "priority",
  "disposition",
];

const PRIORITY_RANK: Record<string, number> = { 高: 0, 中: 1, 低: 2 };
const DECISION_RANK: Record<Decision, number> = {
  approved: 0,
  modified: 1,
  followed_up: 2,
  rejected: 3,
};

function rankDecision(v?: Decision | null): number {
  return v ? DECISION_RANK[v] ?? 9 : 8;
}

function processedMs(row: SuggestionRow): number {
  const t = new Date(row.processedAt).getTime();
  return Number.isFinite(t) ? t : 0;
}

function cmpLatest(a: SuggestionRow, b: SuggestionRow): number {
  return processedMs(b) - processedMs(a);
}

function cmpText(a: string, b: string): number {
  return a.localeCompare(b, "zh-CN");
}

export function parseSuggestionSortKey(raw?: string | null): SuggestionSortKey {
  return (ALL_SORT_KEYS as string[]).includes(raw ?? "")
    ? (raw as SuggestionSortKey)
    : "latest";
}

export function sortSuggestions(
  rows: SuggestionRow[],
  sortKey: SuggestionSortKey,
  pilots: PilotHousekeeper[]
): SuggestionRow[] {
  const next = [...rows];
  next.sort((a, b) => {
    if (sortKey === "housekeeper") {
      const na = housekeeperName(pilots, a.housekeeperId);
      const nb = housekeeperName(pilots, b.housekeeperId);
      const c = cmpText(na, nb);
      return c !== 0 ? c : cmpLatest(a, b);
    }
    if (sortKey === "stale") {
      const sa = resolveStaleDays(a) ?? -1;
      const sb = resolveStaleDays(b) ?? -1;
      if (sb !== sa) return sb - sa;
      return cmpLatest(a, b);
    }
    if (sortKey === "priority") {
      const pa = PRIORITY_RANK[a.suggestion.优先级 ?? ""] ?? 9;
      const pb = PRIORITY_RANK[b.suggestion.优先级 ?? ""] ?? 9;
      if (pa !== pb) return pa - pb;
      return cmpLatest(a, b);
    }
    if (sortKey === "disposition") {
      const da = rankDecision(a.outcome?.decision ?? null);
      const db = rankDecision(b.outcome?.decision ?? null);
      if (da !== db) return da - db;
      return cmpLatest(a, b);
    }
    return cmpLatest(a, b);
  });
  return next;
}
