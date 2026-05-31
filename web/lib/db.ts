import { createClient, type Client } from "@libsql/client";

declare global {
  // eslint-disable-next-line no-var
  var __aolDb: Client | undefined;
  // eslint-disable-next-line no-var
  var __aolSchemaReady: Promise<void> | undefined;
}

/**
 * 链接层（见 docs/public/PUB-02-architecture.md）：
 * - 本地开发默认指向引擎写入的 sqlite 文件（仓库根 agent_loop_tracking.db）。
 * - 生产将 LIBSQL_URL/LIBSQL_AUTH_TOKEN 指向同一个 Turso 库即可，零后端改造。
 */
function makeClient(): Client {
  const url = process.env.LIBSQL_URL ?? "file:../agent_loop_tracking.db";
  const authToken = process.env.LIBSQL_AUTH_TOKEN;
  return createClient(authToken ? { url, authToken } : { url });
}

export const db: Client = globalThis.__aolDb ?? makeClient();
if (process.env.NODE_ENV !== "production") globalThis.__aolDb = db;

const OUTCOMES_SCHEMA = `
CREATE TABLE IF NOT EXISTS suggestion_outcomes (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  dedupe_key          TEXT NOT NULL,
  work_order_id       TEXT,
  decision            TEXT NOT NULL,
  note                TEXT,
  operator            TEXT,
  modified_suggestion TEXT,
  created_at          TEXT NOT NULL
)`;

/** 幂等建表：审批结果回写表（产品轨新增的链接层契约）。 */
export function ensureSchema(): Promise<void> {
  if (!globalThis.__aolSchemaReady) {
    globalThis.__aolSchemaReady = (async () => {
      await db.execute(OUTCOMES_SCHEMA);
      await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_outcomes_dedupe ON suggestion_outcomes(dedupe_key)"
      );
    })();
  }
  return globalThis.__aolSchemaReady;
}
