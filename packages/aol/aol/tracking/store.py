"""统一追踪库接口：local=sqlite，cloud=Turso（幂等水位线 + trace）。"""

from __future__ import annotations

import json
import logging
import os
import sqlite3

from ..config import Config
from ..domain import FollowUpSuggestion, WorkOrder, bj_now
from .schema import SCHEMA, SCHEMA_TRACES, TABLE_LOGS, TABLE_TRACES
from .trace import ReasoningTrace

logger = logging.getLogger("aol.tracking")


class TrackingStore:
    """统一追踪库接口：local=sqlite，cloud=Turso。"""

    @staticmethod
    def _migrate_trace_columns(conn: sqlite3.Connection) -> None:
        trace_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE_TRACES})")}
        if not trace_cols:
            return
        if "event_type" not in trace_cols:
            conn.execute(f"ALTER TABLE {TABLE_TRACES} ADD COLUMN event_type TEXT")
        trace_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE_TRACES})")}
        if "steps_json" not in trace_cols:
            conn.execute(f"ALTER TABLE {TABLE_TRACES} ADD COLUMN steps_json TEXT")

    @staticmethod
    def _migrate_sqlite_v02(conn: sqlite3.Connection) -> None:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE_LOGS})")}
        if not cols:
            return
        if "dedupe_key" in cols:
            return
        conn.execute(
            f"""
            CREATE TABLE {TABLE_LOGS}_v2 (
                dedupe_key TEXT PRIMARY KEY,
                work_order_id TEXT, event_type TEXT, order_num TEXT, city TEXT,
                housekeeper_id TEXT, suggestion TEXT, status TEXT, processed_at TEXT
            )
            """
        )
        conn.execute(
            f"""
            INSERT INTO {TABLE_LOGS}_v2
            SELECT
                'COMPLETED_CARE:' || work_order_id,
                work_order_id, 'COMPLETED_CARE', order_num, city,
                '', suggestion, status, processed_at
            FROM {TABLE_LOGS}
            """
        )
        conn.execute(f"DROP TABLE {TABLE_LOGS}")
        conn.execute(f"ALTER TABLE {TABLE_LOGS}_v2 RENAME TO {TABLE_LOGS}")

    def __init__(self, cfg: Config):
        self.cfg = cfg
        if cfg.tracking_source == "local":
            db_path = os.path.abspath(cfg.tracking_local_path)
            self._conn = sqlite3.connect(db_path)
            self._conn.execute(SCHEMA)
            self._migrate_sqlite_v02(self._conn)
            self._conn.execute(SCHEMA_TRACES)
            self._migrate_trace_columns(self._conn)
            self._conn.commit()
            self._turso = None
            logger.info("追踪库 sqlite: %s", db_path)
        elif cfg.tracking_source == "cloud":
            from libsql_client import create_client_sync  # 懒加载

            # Python libsql_client 对 libsql:// 会走 wss 握手，Turso 返回 400 并挂起线程；
            # 改用 https:// 走 HTTP 传输（与 JS @libsql/client 的默认行为一致，稳定）。
            turso_url = cfg.turso_url
            if turso_url.startswith("libsql://"):
                turso_url = "https://" + turso_url[len("libsql://"):]
            self._turso = create_client_sync(url=turso_url, auth_token=cfg.turso_token)
            self._turso.execute(SCHEMA)
            self._turso.execute(SCHEMA_TRACES)
            self._conn = None
        else:
            raise ValueError(f"未知 TRACKING_SOURCE: {cfg.tracking_source}")

    def get_processed_dedupe_keys(self) -> set[str]:
        if self._conn is not None:
            rows = self._conn.execute(f"SELECT dedupe_key FROM {TABLE_LOGS}").fetchall()
            return {r[0] for r in rows}
        res = self._turso.execute(f"SELECT dedupe_key FROM {TABLE_LOGS}")
        return {r[0] for r in res.rows}

    def mark_processed(self, wo: WorkOrder, suggestion: FollowUpSuggestion, status: str) -> None:
        now = bj_now().isoformat()
        payload = json.dumps(suggestion.to_dict(), ensure_ascii=False)
        row = (
            wo.dedupe_key, wo.work_order_id, wo.event_type, wo.order_num, wo.city,
            wo.housekeeper_id, payload, status, now,
        )
        sql = (
            f"INSERT OR REPLACE INTO {TABLE_LOGS} "
            "(dedupe_key, work_order_id, event_type, order_num, city, housekeeper_id, "
            "suggestion, status, processed_at) VALUES (?,?,?,?,?,?,?,?,?)"
        )
        if self._conn is not None:
            self._conn.execute(sql, row)
            self._conn.commit()
        else:
            self._turso.execute(sql, list(row))

    def log_reasoning_trace(self, t: ReasoningTrace) -> None:
        parsed = json.dumps(t.parsed, ensure_ascii=False) if t.parsed is not None else None
        row = (
            t.work_order_id, t.event_type, t.mode, t.model, t.prompt_system, t.prompt_user,
            t.raw_response, parsed, t.prompt_tokens, t.completion_tokens,
            t.total_tokens, t.latency_ms, t.status, t.error, t.steps_json or None, t.created_at,
        )
        sql = (
            f"INSERT INTO {TABLE_TRACES} "
            "(work_order_id, event_type, mode, model, prompt_system, prompt_user, raw_response, parsed, "
            "prompt_tokens, completion_tokens, total_tokens, latency_ms, status, error, steps_json, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        )
        if self._conn is not None:
            self._conn.execute(sql, row)
            self._conn.commit()
        else:
            self._turso.execute(sql, list(row))

    def clear_all_data(self) -> int:
        """清空水位线与 trace 表数据，保留 db 文件（E2E 可重复 + GUI 可刷新）。"""
        if self._conn is None:
            raise RuntimeError("clear_all_data 仅支持 TRACKING_SOURCE=local")
        total = 0
        for table in (TABLE_LOGS, TABLE_TRACES):
            cur = self._conn.execute(f"DELETE FROM {table}")
            total += cur.rowcount
        self._conn.execute(
            "DELETE FROM sqlite_sequence WHERE name=?", (TABLE_TRACES,)
        )
        self._conn.commit()
        return total

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
        elif self._turso is not None:
            self._turso.close()
