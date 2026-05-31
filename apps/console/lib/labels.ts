export const EVENT_TYPE_LABELS: Record<string, string> = {
  STALE_SIGN_PENDING: "待签约停滞",
  STALE_VISIT_NO_DEAL: "上门未成交停滞",
  PAYMENT_PENDING: "待支付停滞",
  COMPLETED_CARE: "完工关怀",
};

export function eventTypeLabel(eventType: string): string {
  return EVENT_TYPE_LABELS[eventType] || eventType || "跟进事件";
}

export const STATUS_LABELS: Record<string, string> = {
  sent: "已推送",
  skipped_no_follow_up: "无需跟进",
  send_failed: "推送失败",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status || "—";
}

export const DECISION_LABELS: Record<string, string> = {
  approved: "已同意",
  rejected: "已拒绝",
  modified: "已修改",
  followed_up: "已跟进",
};

export function decisionLabel(decision?: string | null): string {
  if (!decision) return "待处置";
  return DECISION_LABELS[decision] || decision;
}

/** 优先级 → badge 颜色类（基于 shadcn token / 自定义优先级色）。 */
export function priorityClasses(priority?: string): string {
  switch (priority) {
    case "高":
      return "border-transparent bg-red-500/15 text-red-400";
    case "中":
      return "border-transparent bg-amber-500/15 text-amber-400";
    case "低":
      return "border-transparent bg-emerald-500/15 text-emerald-400";
    default:
      return "border-transparent bg-muted text-muted-foreground";
  }
}

export function decisionClasses(decision?: string | null): string {
  switch (decision) {
    case "approved":
      return "border-transparent bg-emerald-500/15 text-emerald-400";
    case "rejected":
      return "border-transparent bg-red-500/15 text-red-400";
    case "modified":
      return "border-transparent bg-blue-500/15 text-blue-400";
    case "followed_up":
      return "border-transparent bg-violet-500/15 text-violet-400";
    default:
      return "border-transparent bg-amber-500/15 text-amber-400";
  }
}

export function encodeKey(key: string): string {
  return encodeURIComponent(key);
}
