import { createClient, type Client } from "@libsql/client";
import {
  trackingBootstrapStatements,
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

function getDb(): Client {
  if (!globalThis.__aolDb) {
    globalThis.__aolDb = makeClient();
  }
  return globalThis.__aolDb;
}

/** Lazy client — avoids opening sqlite during `next build` when env is unset. */
export const db: Client = new Proxy({} as Client, {
  get(_target, prop, receiver) {
    const client = getDb();
    const value = Reflect.get(client, prop, receiver);
    return typeof value === "function" ? value.bind(client) : value;
  },
});
if (process.env.NODE_ENV !== "production") globalThis.__aolDb = getDb();

/** 表名：后缀来自 contracts/tables.json，前缀来自 AOL_TABLE_PREFIX。 */
export const TABLE_PREFIX = tablePrefix();
const _tables = tableNames(TABLE_PREFIX);
export const TABLE_LOGS = _tables.logs;
export const TABLE_TRACES = _tables.traces;
export const TABLE_OUTCOMES = _tables.outcomes;
export const TABLE_BLOCKERS = _tables.blockers;

/** 幂等建表：outcomes + blocker 回写表（DDL 真源 contracts/aol_schema.sql）。 */
export function ensureSchema(): Promise<void> {
  if (!globalThis.__aolSchemaReady) {
    globalThis.__aolSchemaReady = (async () => {
      for (const stmt of trackingBootstrapStatements(TABLE_PREFIX)) {
        await db.execute(stmt);
      }
    })();
  }
  return globalThis.__aolSchemaReady;
}
