import { db, ensureSchema, TABLE_LOGS, TABLE_TRACES, TABLE_OUTCOMES, TABLE_BLOCKERS } from "./db";
import type { BlockerType } from "./blockers";

export type Decision = "approved" | "rejected" | "modified" | "followed_up";

/** Action Spec v0.2 — 键名对齐 contracts/suggestion.schema.json */
export interface SuggestionDoc {
  规格版本?: string;
  需要跟进?: boolean;
  优先级?: string;
  客户情绪?: string;
  原因摘要?: string;
  优先级依据?: string[];
  情况判断?: {
    商机阶段?: string;
    报价状态?: string;
    金额与方案?: string;
    渠道与部位?: string;
  };
  跟进方案?: {
    主行动?: string;
    沟通要点?: string[];
    避免事项?: string[];
  };
  引用查证?: string[];
}

export interface OutcomeRow {
  id: number;
  dedupeKey: string;
  workOrderId: string;
  decision: Decision;
  note: string;
  operator: string;
  modifiedSuggestion: SuggestionDoc | null;
  createdAt: string;
}

export interface BlockerRow {
  id: number;
  dedupeKey: string;
  workOrderId: string;
  blockerType: BlockerType;
  note: string;
  source: string;
  operator: string;
  createdAt: string;
}

export interface SuggestionRow {
  dedupeKey: string;
  workOrderId: string;
  eventType: string;
  orderNum: string;
  city: string;
  housekeeperId: string;
  status: string;
  processedAt: string;
  /** 工单进入当前状态时 updateTime（北京本地），展示时现算滞留天数 */
  stateAt: string | null;
  suggestion: SuggestionDoc;
  outcome: OutcomeRow | null;
  blocker: BlockerRow | null;
}

export interface TraceStep {
  step?: number;
  kind?: string;
  name?: string;
  latency_ms?: number;
  status?: string;
  output?: Record<string, unknown>;
}

export interface TraceRow {
  workOrderId: string;
  mode: string;
  model: string;
  status: string;
  error: string;
  latencyMs: number;
  totalTokens: number;
  promptSystem: string;
  promptUser: string;
  rawResponse: string;
  parsed: SuggestionDoc | null;
  steps: TraceStep[];
  enrich: Record<string, unknown> | null;
  createdAt: string;
}

function parseJson<T>(value: unknown, fallback: T): T {
  if (typeof value !== "string" || !value.trim()) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function str(value: unknown): string {
  return value == null ? "" : String(value);
}

function mapOutcome(row: Record<string, unknown>): OutcomeRow {
  return {
    id: Number(row.id),
    dedupeKey: str(row.dedupe_key),
    workOrderId: str(row.work_order_id),
    decision: str(row.decision) as Decision,
    note: str(row.note),
    operator: str(row.operator),
    modifiedSuggestion: parseJson<SuggestionDoc | null>(row.modified_suggestion, null),
    createdAt: str(row.created_at),
  };
}

function mapBlocker(row: Record<string, unknown>): BlockerRow {
  return {
    id: Number(row.id),
    dedupeKey: str(row.dedupe_key),
    workOrderId: str(row.work_order_id),
    blockerType: str(row.blocker_type) as BlockerType,
    note: str(row.note),
    source: str(row.source),
    operator: str(row.operator),
    createdAt: str(row.created_at),
  };
}

async function latestOutcomes(): Promise<Map<string, OutcomeRow>> {
  const res = await db.execute(
    `SELECT o.* FROM ${TABLE_OUTCOMES} o
     JOIN (SELECT dedupe_key, MAX(id) AS mid FROM ${TABLE_OUTCOMES} GROUP BY dedupe_key) m
       ON o.id = m.mid`
  );
  const map = new Map<string, OutcomeRow>();
  for (const row of res.rows as unknown as Record<string, unknown>[]) {
    const o = mapOutcome(row);
    map.set(o.dedupeKey, o);
  }
  return map;
}

async function latestBlockers(): Promise<Map<string, BlockerRow>> {
  const res = await db.execute(
    `SELECT b.* FROM ${TABLE_BLOCKERS} b
     JOIN (SELECT dedupe_key, MAX(id) AS mid FROM ${TABLE_BLOCKERS} GROUP BY dedupe_key) m
       ON b.id = m.mid`
  );
  const map = new Map<string, BlockerRow>();
  for (const row of res.rows as unknown as Record<string, unknown>[]) {
    const b = mapBlocker(row);
    map.set(b.dedupeKey, b);
  }
  return map;
}

function mapSuggestion(
  row: Record<string, unknown>,
  outcomes: Map<string, OutcomeRow>,
  blockers: Map<string, BlockerRow>
): SuggestionRow {
  const dedupeKey = str(row.dedupe_key);
  return {
    dedupeKey,
    workOrderId: str(row.work_order_id),
    eventType: str(row.event_type),
    orderNum: str(row.order_num),
    city: str(row.city),
    housekeeperId: str(row.housekeeper_id),
    status: str(row.status),
    processedAt: str(row.processed_at),
    stateAt: str(row.state_at).trim() || null,
    suggestion: parseJson<SuggestionDoc>(row.suggestion, {}),
    outcome: outcomes.get(dedupeKey) ?? null,
    blocker: blockers.get(dedupeKey) ?? null,
  };
}

export async function listSuggestions(options?: {
  housekeeperId?: string;
}): Promise<SuggestionRow[]> {
  await ensureSchema();
  const hk = options?.housekeeperId?.trim();
  const sql = hk
    ? `SELECT * FROM ${TABLE_LOGS} WHERE housekeeper_id = ? ORDER BY processed_at DESC LIMIT 500`
    : `SELECT * FROM ${TABLE_LOGS} ORDER BY processed_at DESC LIMIT 500`;
  const args = hk ? [hk] : [];
  const [res, outcomes, blockers] = await Promise.all([
    db.execute({ sql, args }),
    latestOutcomes(),
    latestBlockers(),
  ]);
  return (res.rows as unknown as Record<string, unknown>[]).map((r) =>
    mapSuggestion(r, outcomes, blockers)
  );
}

export async function getSuggestion(
  dedupeKey: string
): Promise<SuggestionRow | null> {
  await ensureSchema();
  const [res, outcomes, blockers] = await Promise.all([
    db.execute({
      sql: `SELECT * FROM ${TABLE_LOGS} WHERE dedupe_key = ? LIMIT 1`,
      args: [dedupeKey],
    }),
    latestOutcomes(),
    latestBlockers(),
  ]);
  const row = (res.rows as unknown as Record<string, unknown>[])[0];
  return row ? mapSuggestion(row, outcomes, blockers) : null;
}

export async function getLatestBlocker(
  dedupeKey: string
): Promise<BlockerRow | null> {
  await ensureSchema();
  const res = await db.execute({
    sql: `SELECT * FROM ${TABLE_BLOCKERS} WHERE dedupe_key = ? ORDER BY id DESC LIMIT 1`,
    args: [dedupeKey],
  });
  const row = (res.rows as unknown as Record<string, unknown>[])[0];
  return row ? mapBlocker(row) : null;
}

export async function recordBlocker(input: {
  dedupeKey: string;
  workOrderId: string;
  blockerType: BlockerType;
  note?: string;
  operator?: string;
  source?: string;
}): Promise<void> {
  await ensureSchema();
  await db.execute({
    sql: `INSERT INTO ${TABLE_BLOCKERS}
      (dedupe_key, work_order_id, blocker_type, note, source, operator, created_at)
      VALUES (?,?,?,?,?,?,?)`,
    args: [
      input.dedupeKey,
      input.workOrderId,
      input.blockerType,
      input.note ?? "",
      input.source ?? "housekeeper_selected",
      input.operator ?? "console",
      new Date().toISOString(),
    ],
  });
}

export async function getTrace(workOrderId: string): Promise<TraceRow | null> {
  const res = await db.execute({
    sql: `SELECT * FROM ${TABLE_TRACES} WHERE work_order_id = ? ORDER BY id DESC LIMIT 1`,
    args: [workOrderId],
  });
  const row = (res.rows as unknown as Record<string, unknown>[])[0];
  if (!row) return null;
  const steps = parseJson<TraceStep[]>(row.steps_json, []);
  const enrichStep = steps.find((s) => s.name === "enrich_work_order_context");
  return {
    workOrderId: str(row.work_order_id),
    mode: str(row.mode),
    model: str(row.model),
    status: str(row.status),
    error: str(row.error),
    latencyMs: Number(row.latency_ms ?? 0),
    totalTokens: Number(row.total_tokens ?? 0),
    promptSystem: str(row.prompt_system),
    promptUser: str(row.prompt_user),
    rawResponse: str(row.raw_response),
    parsed: parseJson<SuggestionDoc | null>(row.parsed, null),
    steps,
    enrich: (enrichStep?.output as Record<string, unknown>) ?? null,
    createdAt: str(row.created_at),
  };
}

export async function recordOutcome(input: {
  dedupeKey: string;
  workOrderId: string;
  decision: Decision;
  note?: string;
  operator?: string;
  modifiedSuggestion?: SuggestionDoc | null;
}): Promise<void> {
  await ensureSchema();
  await db.execute({
    sql: `INSERT INTO ${TABLE_OUTCOMES}
      (dedupe_key, work_order_id, decision, note, operator, modified_suggestion, created_at)
      VALUES (?,?,?,?,?,?,?)`,
    args: [
      input.dedupeKey,
      input.workOrderId,
      input.decision,
      input.note ?? "",
      input.operator ?? "console",
      input.modifiedSuggestion
        ? JSON.stringify(input.modifiedSuggestion)
        : null,
      new Date().toISOString(),
    ],
  });
}

export interface DashboardStats {
  total: number;
  needFollow: number;
  pending: number;
  approved: number;
  rejected: number;
  modified: number;
  followedUp: number;
  handledRate: number;
  adoptionRate: number;
  exposureCount: number;
  blockerCaptureRate: number;
  unknownBlockerRate: number;
  byPriority: Record<string, number>;
}

const ADOPTED: Decision[] = ["approved", "modified", "followed_up"];

export function computeStats(rows: SuggestionRow[]): DashboardStats {
  const needFollowRows = rows.filter((r) => r.suggestion.需要跟进 !== false);
  let approved = 0;
  let rejected = 0;
  let modified = 0;
  let followedUp = 0;
  let adopted = 0;
  let capturedBlockers = 0;
  let exposureCount = 0;
  const byPriority: Record<string, number> = {};
  for (const r of needFollowRows) {
    const p = r.suggestion.优先级 || "未定";
    byPriority[p] = (byPriority[p] ?? 0) + 1;
    if (r.status === "sent") exposureCount += 1;
    const d = r.outcome?.decision;
    if (d === "approved") approved += 1;
    else if (d === "rejected") rejected += 1;
    else if (d === "modified") modified += 1;
    else if (d === "followed_up") followedUp += 1;
    if (d && ADOPTED.includes(d)) adopted += 1;
    const bt = r.blocker?.blockerType;
    if (bt && bt !== "UNKNOWN") capturedBlockers += 1;
  }
  const handled = approved + rejected + modified + followedUp;
  const total = needFollowRows.length;
  const blockerCaptureRate = total
    ? Math.round((capturedBlockers / total) * 100)
    : 0;
  return {
    total: rows.length,
    needFollow: total,
    pending: total - handled,
    approved,
    rejected,
    modified,
    followedUp,
    handledRate: total ? Math.round((handled / total) * 100) : 0,
    adoptionRate: total ? Math.round((adopted / total) * 100) : 0,
    exposureCount: exposureCount || total,
    blockerCaptureRate,
    unknownBlockerRate: total ? 100 - blockerCaptureRate : 0,
    byPriority,
  };
}
