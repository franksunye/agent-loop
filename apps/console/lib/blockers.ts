/** 阻塞类型口径（ADR-011，对齐 packages/aol/aol/blocker_types.py） */

export type BlockerType =
  | "UNKNOWN"
  | "PRICE_OBJECTION"
  | "TIMING_NOT_READY"
  | "SOLUTION_CONCERN"
  | "NO_RESPONSE";

export const BLOCKER_LABELS: Record<BlockerType, string> = {
  UNKNOWN: "未知",
  PRICE_OBJECTION: "价格异议",
  TIMING_NOT_READY: "时机未到",
  SOLUTION_CONCERN: "方案疑虑",
  NO_RESPONSE: "无响应",
};

export const CHOICE_TO_BLOCKER: Record<string, BlockerType> = {
  A: "PRICE_OBJECTION",
  B: "TIMING_NOT_READY",
  C: "SOLUTION_CONCERN",
  D: "NO_RESPONSE",
};

export const BLOCKER_CHOICES = [
  { choice: "A", label: "A 价格异议", type: "PRICE_OBJECTION" as BlockerType },
  { choice: "B", label: "B 时机未到", type: "TIMING_NOT_READY" as BlockerType },
  { choice: "C", label: "C 方案疑虑", type: "SOLUTION_CONCERN" as BlockerType },
  { choice: "D", label: "D 无响应", type: "NO_RESPONSE" as BlockerType },
];

export const VALID_BLOCKER_TYPES = new Set<string>(
  Object.keys(BLOCKER_LABELS)
);

export function blockerDisplay(type?: string | null, note?: string | null): string {
  if (!type || type === "UNKNOWN") return "待采集";
  const label = BLOCKER_LABELS[type as BlockerType] ?? type;
  return note ? `${label} — ${note}` : label;
}

export function choiceToBlockerType(choice: string): BlockerType | null {
  return CHOICE_TO_BLOCKER[choice.toUpperCase()] ?? null;
}
