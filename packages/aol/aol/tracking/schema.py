"""追踪库表名与 DDL（本地 sqlite 与云端 Turso 共用一致命名）。

DDL 真源：仓库根 contracts/aol_schema.sql
表名后缀：contracts/tables.json
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path


def _repo_root() -> Path:
    # packages/aol/aol/tracking/schema.py → repo root
    return Path(__file__).resolve().parents[4]


@lru_cache(maxsize=1)
def _tables_manifest() -> dict[str, str]:
    path = _repo_root() / "contracts" / "tables.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "logs": data["logs"],
        "traces": data["traces"],
        "outcomes": data["outcomes"],
    }


TABLE_PREFIX = os.getenv("AOL_TABLE_PREFIX", "aol_")
_SUFFIX = _tables_manifest()
TABLE_LOGS = f"{TABLE_PREFIX}{_SUFFIX['logs']}"
TABLE_TRACES = f"{TABLE_PREFIX}{_SUFFIX['traces']}"
TABLE_OUTCOMES = f"{TABLE_PREFIX}{_SUFFIX['outcomes']}"


def _render_schema_sql(prefix: str = TABLE_PREFIX) -> str:
    raw = (_repo_root() / "contracts" / "aol_schema.sql").read_text(encoding="utf-8")
    return raw.replace("{{AOL_TABLE_PREFIX}}", prefix)


def _split_statements(sql: str) -> list[str]:
    parts: list[str] = []
    for chunk in sql.split(";"):
        lines = [
            ln
            for ln in chunk.splitlines()
            if ln.strip() and not ln.strip().startswith("--")
        ]
        stmt = "\n".join(lines).strip()
        if stmt:
            parts.append(stmt + ";")
    return parts


def _statement_for_table(sql: str, table_name: str) -> str:
    for stmt in _split_statements(sql):
        if table_name in stmt:
            return stmt
    raise ValueError(f"DDL for table {table_name!r} not found in contracts/aol_schema.sql")


_rendered = _render_schema_sql()
SCHEMA = _statement_for_table(_rendered, TABLE_LOGS)
SCHEMA_TRACES = _statement_for_table(_rendered, TABLE_TRACES)
SCHEMA_OUTCOMES = _statement_for_table(_rendered, TABLE_OUTCOMES)

# Index on outcomes (Console ensureSchema also runs this)
_OUTCOMES_INDEX = re.compile(
    rf"CREATE INDEX IF NOT EXISTS idx_{re.escape(TABLE_OUTCOMES)}_dedupe\b",
    re.IGNORECASE,
)
SCHEMA_OUTCOMES_INDEX = next(
    (s for s in _split_statements(_rendered) if _OUTCOMES_INDEX.search(s)),
    f"CREATE INDEX IF NOT EXISTS idx_{TABLE_OUTCOMES}_dedupe ON {TABLE_OUTCOMES}(dedupe_key);",
)
