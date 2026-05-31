"""追踪库表名与 DDL（本地 sqlite 与云端 Turso 共用一致命名）。

表名前缀：多项目共用一个 Turso 库时用于清晰区分（默认 aol_ = FS-AOL）。
"""

from __future__ import annotations

import os

TABLE_PREFIX = os.getenv("AOL_TABLE_PREFIX", "aol_")
TABLE_LOGS = f"{TABLE_PREFIX}follow_up_logs"
TABLE_TRACES = f"{TABLE_PREFIX}reasoning_traces"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABLE_LOGS} (
    dedupe_key      TEXT PRIMARY KEY,
    work_order_id   TEXT,
    event_type      TEXT,
    order_num       TEXT,
    city            TEXT,
    housekeeper_id  TEXT,
    suggestion      TEXT,
    status          TEXT,
    processed_at    TEXT
)
"""

# 推理 trace 表：每次 LLM/启发式推理落一条，增强可检测性（observability）
SCHEMA_TRACES = f"""
CREATE TABLE IF NOT EXISTS {TABLE_TRACES} (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id     TEXT,
    event_type        TEXT,
    mode              TEXT,
    model             TEXT,
    prompt_system     TEXT,
    prompt_user       TEXT,
    raw_response      TEXT,
    parsed            TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    latency_ms        INTEGER,
    status            TEXT,
    error             TEXT,
    steps_json        TEXT,
    created_at        TEXT
)
"""
