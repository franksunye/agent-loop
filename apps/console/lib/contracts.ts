import fs from "node:fs";
import path from "node:path";

/** Shared contract paths (repo root contracts/). */
export function contractsDir(): string {
  return path.join(process.cwd(), "../../contracts");
}

export interface TablesManifest {
  prefixEnv: string;
  defaultPrefix: string;
  logs: string;
  traces: string;
  outcomes: string;
}

let _manifest: TablesManifest | undefined;

export function loadTablesManifest(): TablesManifest {
  if (!_manifest) {
    const raw = fs.readFileSync(
      path.join(contractsDir(), "tables.json"),
      "utf8"
    );
    _manifest = JSON.parse(raw) as TablesManifest;
  }
  return _manifest;
}

export function tablePrefix(): string {
  const manifest = loadTablesManifest();
  return process.env[manifest.prefixEnv] ?? manifest.defaultPrefix;
}

export function tableNames(prefix = tablePrefix()): {
  logs: string;
  traces: string;
  outcomes: string;
} {
  const m = loadTablesManifest();
  return {
    logs: `${prefix}${m.logs}`,
    traces: `${prefix}${m.traces}`,
    outcomes: `${prefix}${m.outcomes}`,
  };
}

/** Render contracts/aol_schema.sql with the active table prefix. */
export function renderSchemaSql(prefix = tablePrefix()): string {
  const raw = fs.readFileSync(
    path.join(contractsDir(), "aol_schema.sql"),
    "utf8"
  );
  return raw.replace(/\{\{AOL_TABLE_PREFIX\}\}/g, prefix);
}

/** Split rendered DDL into executable statements (CREATE TABLE / INDEX). */
export function schemaStatements(prefix = tablePrefix()): string[] {
  return renderSchemaSql(prefix)
    .split(";")
    .map((chunk) =>
      chunk
        .split("\n")
        .filter((line) => line.trim() && !line.trim().startsWith("--"))
        .join("\n")
        .trim()
    )
    .filter((s) => s.length > 0)
    .map((s) => s + ";");
}

/** Console-only bootstrap: outcomes table + dedupe index. */
export function outcomesBootstrapStatements(prefix = tablePrefix()): string[] {
  const { outcomes } = tableNames(prefix);
  return schemaStatements(prefix).filter(
    (stmt) => stmt.includes(outcomes) || stmt.includes(`idx_${outcomes}`)
  );
}
