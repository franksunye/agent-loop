// 把本地 sqlite（引擎旧表名）迁移到目标 libSQL/Turso 库（aol_ 前缀新表）。
// 用法（在 apps/console 下）：
//   SRC_URL=file:../../data/agent_loop_tracking.db \
//   LIBSQL_URL=libsql://... LIBSQL_AUTH_TOKEN=... \
//   node scripts/migrate-to-turso.mjs
import { createClient } from "@libsql/client";

const SRC_URL = process.env.SRC_URL || "file:../../data/agent_loop_tracking.db";
const DST_URL = process.env.LIBSQL_URL;
const DST_TOKEN = process.env.LIBSQL_AUTH_TOKEN;
const P = process.env.AOL_TABLE_PREFIX || "aol_";

if (!DST_URL) {
  console.error("ERROR: 需要 LIBSQL_URL（目标 Turso 库）");
  process.exit(1);
}

const T_LOGS = `${P}follow_up_logs`;
const T_TRACES = `${P}reasoning_traces`;
const T_OUTCOMES = `${P}suggestion_outcomes`;

const src = createClient({ url: SRC_URL });
const dst = createClient(
  DST_TOKEN ? { url: DST_URL, authToken: DST_TOKEN } : { url: DST_URL }
);

const SCHEMAS = [
  `CREATE TABLE IF NOT EXISTS ${T_LOGS} (
     dedupe_key TEXT PRIMARY KEY, work_order_id TEXT, event_type TEXT,
     order_num TEXT, city TEXT, housekeeper_id TEXT, suggestion TEXT,
     status TEXT, processed_at TEXT)`,
  `CREATE TABLE IF NOT EXISTS ${T_TRACES} (
     id INTEGER PRIMARY KEY AUTOINCREMENT, work_order_id TEXT, event_type TEXT,
     mode TEXT, model TEXT, prompt_system TEXT, prompt_user TEXT, raw_response TEXT,
     parsed TEXT, prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER,
     latency_ms INTEGER, status TEXT, error TEXT, steps_json TEXT, created_at TEXT)`,
  `CREATE TABLE IF NOT EXISTS ${T_OUTCOMES} (
     id INTEGER PRIMARY KEY AUTOINCREMENT, dedupe_key TEXT NOT NULL, work_order_id TEXT,
     decision TEXT NOT NULL, note TEXT, operator TEXT, modified_suggestion TEXT,
     created_at TEXT NOT NULL)`,
];

async function tableExists(client, name) {
  const r = await client.execute({
    sql: "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
    args: [name],
  });
  return r.rows.length > 0;
}

async function copy(srcTable, dstTable, cols) {
  if (!(await tableExists(src, srcTable))) {
    console.log(`· 源无表 ${srcTable}，跳过`);
    return 0;
  }
  const rows = (await src.execute(`SELECT ${cols.join(",")} FROM ${srcTable}`)).rows;
  await dst.execute(`DELETE FROM ${dstTable}`);
  const placeholders = cols.map(() => "?").join(",");
  for (const row of rows) {
    await dst.execute({
      sql: `INSERT INTO ${dstTable} (${cols.join(",")}) VALUES (${placeholders})`,
      args: cols.map((c) => row[c] ?? null),
    });
  }
  console.log(`✓ ${srcTable} → ${dstTable}: ${rows.length} 行`);
  return rows.length;
}

for (const s of SCHEMAS) await dst.execute(s);

await copy("ai_follow_up_logs", T_LOGS, [
  "dedupe_key", "work_order_id", "event_type", "order_num", "city",
  "housekeeper_id", "suggestion", "status", "processed_at",
]);
await copy("reasoning_traces", T_TRACES, [
  "work_order_id", "event_type", "mode", "model", "prompt_system", "prompt_user",
  "raw_response", "parsed", "prompt_tokens", "completion_tokens", "total_tokens",
  "latency_ms", "status", "error", "steps_json", "created_at",
]);
await copy("suggestion_outcomes", T_OUTCOMES, [
  "dedupe_key", "work_order_id", "decision", "note", "operator",
  "modified_suggestion", "created_at",
]);

console.log("迁移完成。");
