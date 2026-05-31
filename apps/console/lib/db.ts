import { createClient, type Client } from "@libsql/client";
import {
  outcomesBootstrapStatements,
  tableNames,
  tablePrefix,
} from "./contracts";

declare global {
  // eslint-disable-next-line no-var
  var __aolDb: Client | undefined;
  // eslint-disable-next-line no-var
  var __aolSchemaReady: Promise<void> | undefined;
}

/**
 * 链接层（见 docs/public/PUB-02-architecture.md）：
 * - 本地开发默认指向引擎写入的 sqlite 文件（仓库根 agent_loop_tracking.db，相对 apps/console 为 ../../）。
 * - 生产将 LIBSQL_URL/LIBSQL_AUTH_TOKEN 指向同一个 Turso 库即可，零后端改造。
 */
function makeClient(): Client {
  const url = process.env.LIBSQL_URL ?? "file:../../agent_loop_tracking.db";
  const authToken = process.env.LIBSQL_AUTH_TOKEN;
  return createClient(authToken ? { url, authToken } : { url });
}

export const db: Client = globalThis.__aolDb ?? makeClient();
if (process.env.NODE_ENV !== "production") globalThis.__aolDb = db;

/** 表名：后缀来自 contracts/tables.json，前缀来自 AOL_TABLE_PREFIX。 */
export const TABLE_PREFIX = tablePrefix();
const _tables = tableNames(TABLE_PREFIX);
export const TABLE_LOGS = _tables.logs;
export const TABLE_TRACES = _tables.traces;
export const TABLE_OUTCOMES = _tables.outcomes;

/** 幂等建表：审批结果回写表（DDL 真源 contracts/aol_schema.sql）。 */
export function ensureSchema(): Promise<void> {
  if (!globalThis.__aolSchemaReady) {
    globalThis.__aolSchemaReady = (async () => {
      for (const stmt of outcomesBootstrapStatements(TABLE_PREFIX)) {
        await db.execute(stmt);
      }
    })();
  }
  return globalThis.__aolSchemaReady;
}
