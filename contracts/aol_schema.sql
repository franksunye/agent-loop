-- AOL tracking layer DDL (authoritative SSOT for Python engine + Console)
-- Substitute {{AOL_TABLE_PREFIX}} at runtime (default: aol_ via AOL_TABLE_PREFIX env)

CREATE TABLE IF NOT EXISTS {{AOL_TABLE_PREFIX}}follow_up_logs (
    dedupe_key      TEXT PRIMARY KEY,
    work_order_id   TEXT,
    event_type      TEXT,
    order_num       TEXT,
    city            TEXT,
    housekeeper_id  TEXT,
    suggestion      TEXT,
    status          TEXT,
    processed_at    TEXT
);

CREATE TABLE IF NOT EXISTS {{AOL_TABLE_PREFIX}}reasoning_traces (
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
);

CREATE TABLE IF NOT EXISTS {{AOL_TABLE_PREFIX}}suggestion_outcomes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key          TEXT NOT NULL,
    work_order_id       TEXT,
    decision            TEXT NOT NULL,
    note                TEXT,
    operator            TEXT,
    modified_suggestion TEXT,
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_{{AOL_TABLE_PREFIX}}suggestion_outcomes_dedupe
    ON {{AOL_TABLE_PREFIX}}suggestion_outcomes(dedupe_key);
