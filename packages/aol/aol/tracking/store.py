"""统一追踪库接口：local=sqlite，cloud=Turso（幂等水位线 + trace）。"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..config import Config
from ..domain import FollowUpSuggestion, WorkOrder, bj_now
from ..blocker_types import BLOCKER_LABELS
from .schema import (
    SCHEMA,
    SCHEMA_BLOCKERS,
    SCHEMA_BLOCKERS_INDEX,
    SCHEMA_OUTCOMES,
    SCHEMA_OUTCOMES_INDEX,
    SCHEMA_TRACES,
    TABLE_BLOCKERS,
    TABLE_LOGS,
    TABLE_OUTCOMES,
    TABLE_TRACES,
)
from .trace import ReasoningTrace

logger = logging.getLogger("aol.tracking")

_DECISION_LABELS = {
    "approved": "已同意",
    "rejected": "已拒绝",
    "modified": "已修改",
    "followed_up": "已跟进",
}


@dataclass
class BlockerFeedback:
    dedupe_key: str
    work_order_id: str
    blocker_type: str
    note: str
    source: str
    operator: str
    created_at: str


@dataclass
class OutcomeRecord:
    dedupe_key: str
    work_order_id: str
    decision: str
    note: str
    operator: str
    created_at: str


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

    def _ensure_extended_schema(self) -> None:
        stmts = (
            SCHEMA_OUTCOMES,
            SCHEMA_OUTCOMES_INDEX,
            SCHEMA_BLOCKERS,
            SCHEMA_BLOCKERS_INDEX,
        )
        if self._conn is not None:
            for stmt in stmts:
                self._conn.execute(stmt)
            self._conn.commit()
        else:
            for stmt in stmts:
                self._turso.execute(stmt)

    def __init__(self, cfg: Config):
        self.cfg = cfg
        if cfg.tracking_source == "local":
            db_path = os.path.abspath(cfg.tracking_local_path)
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
            self._conn = sqlite3.connect(db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute(SCHEMA)
            self._migrate_sqlite_v02(self._conn)
            self._conn.execute(SCHEMA_TRACES)
            self._migrate_trace_columns(self._conn)
            self._ensure_extended_schema()
            self._conn.commit()
            self._turso = None
            logger.info("追踪库 sqlite: %s", db_path)
        elif cfg.tracking_source == "cloud":
            from libsql_client import create_client_sync  # 懒加载

            turso_url = cfg.turso_url
            if turso_url.startswith("libsql://"):
                turso_url = "https://" + turso_url[len("libsql://"):]
            self._conn = None
            self._turso = create_client_sync(url=turso_url, auth_token=cfg.turso_token)
            self._turso.execute(SCHEMA)
            self._turso.execute(SCHEMA_TRACES)
            self._ensure_extended_schema()
        else:
            raise ValueError(f"未知 TRACKING_SOURCE: {cfg.tracking_source}")

    def _row_to_dict(self, row: Any) -> Dict[str, Any]:
        if isinstance(row, sqlite3.Row):
            return {k: row[k] for k in row.keys()}
        if isinstance(row, dict):
            return row
        if hasattr(row, "_asdict"):
            return row._asdict()
        # libsql tuple rows with column names from execute
        return dict(row) if isinstance(row, dict) else {}

    def _fetchone_dict(self, sql: str, args: tuple = ()) -> Optional[Dict[str, Any]]:
        if self._conn is not None:
            cur = self._conn.execute(sql, args)
            row = cur.fetchone()
            if row is None:
                return None
            return {k: row[k] for k in row.keys()}
        res = self._turso.execute(sql, list(args))
        if not res.rows:
            return None
        row = res.rows[0]
        if hasattr(res, "columns") and res.columns:
            return {res.columns[i]: row[i] for i in range(len(row))}
        if isinstance(row, dict):
            return row
        return {"dedupe_key": row[0]} if row else None

    def _fetchall_dicts(self, sql: str, args: tuple = ()) -> list[Dict[str, Any]]:
        if self._conn is not None:
            cur = self._conn.execute(sql, args)
            return [{k: r[k] for k in r.keys()} for r in cur.fetchall()]
        res = self._turso.execute(sql, list(args))
        if not res.rows:
            return []
        if hasattr(res, "columns") and res.columns:
            return [
                {res.columns[i]: row[i] for i in range(len(row))}
                for row in res.rows
            ]
        return [dict(r) if isinstance(r, dict) else {} for r in res.rows]

    def get_processed_dedupe_keys(self) -> set[str]:
        rows = self._fetchall_dicts(f"SELECT dedupe_key FROM {TABLE_LOGS}")
        return {str(r["dedupe_key"]) for r in rows if r.get("dedupe_key")}

    def get_reprocessable_dedupe_keys(self) -> set[str]:
        """最新 outcome 为 followed_up 的 dedupe_key，允许再次入池。"""
        sql = f"""
            SELECT o.dedupe_key FROM {TABLE_OUTCOMES} o
            JOIN (
                SELECT dedupe_key, MAX(id) AS mid FROM {TABLE_OUTCOMES} GROUP BY dedupe_key
            ) m ON o.id = m.mid
            WHERE o.decision = 'followed_up'
        """
        rows = self._fetchall_dicts(sql)
        return {str(r["dedupe_key"]) for r in rows if r.get("dedupe_key")}

    def effective_processed_keys(self) -> set[str]:
        return self.get_processed_dedupe_keys() - self.get_reprocessable_dedupe_keys()

    def get_latest_blocker(self, dedupe_key: str) -> Optional[BlockerFeedback]:
        row = self._fetchone_dict(
            f"""
            SELECT * FROM {TABLE_BLOCKERS}
            WHERE dedupe_key = ?
            ORDER BY id DESC LIMIT 1
            """,
            (dedupe_key,),
        )
        if not row:
            return None
        return BlockerFeedback(
            dedupe_key=str(row.get("dedupe_key", "")),
            work_order_id=str(row.get("work_order_id", "")),
            blocker_type=str(row.get("blocker_type", "UNKNOWN")),
            note=str(row.get("note") or ""),
            source=str(row.get("source") or "housekeeper_selected"),
            operator=str(row.get("operator") or ""),
            created_at=str(row.get("created_at") or ""),
        )

    def save_blocker(
        self,
        *,
        dedupe_key: str,
        work_order_id: str,
        blocker_type: str,
        note: str = "",
        source: str = "housekeeper_selected",
        operator: str = "console",
    ) -> None:
        now = bj_now().isoformat()
        row = (
            dedupe_key,
            work_order_id,
            blocker_type,
            note,
            source,
            operator,
            now,
        )
        sql = (
            f"INSERT INTO {TABLE_BLOCKERS} "
            "(dedupe_key, work_order_id, blocker_type, note, source, operator, created_at) "
            "VALUES (?,?,?,?,?,?,?)"
        )
        if self._conn is not None:
            self._conn.execute(sql, row)
            self._conn.commit()
        else:
            self._turso.execute(sql, list(row))

    def get_latest_outcome(self, dedupe_key: str) -> Optional[OutcomeRecord]:
        row = self._fetchone_dict(
            f"""
            SELECT * FROM {TABLE_OUTCOMES}
            WHERE dedupe_key = ?
            ORDER BY id DESC LIMIT 1
            """,
            (dedupe_key,),
        )
        if not row:
            return None
        return OutcomeRecord(
            dedupe_key=str(row.get("dedupe_key", "")),
            work_order_id=str(row.get("work_order_id", "")),
            decision=str(row.get("decision", "")),
            note=str(row.get("note") or ""),
            operator=str(row.get("operator") or ""),
            created_at=str(row.get("created_at") or ""),
        )

    def build_prior_context(self, dedupe_key: str) -> str:
        """拼装上一轮处置/阻塞（只读），供推理 prompt 使用。"""
        lines: list[str] = []
        outcome = self.get_latest_outcome(dedupe_key)
        if outcome and outcome.decision:
            label = _DECISION_LABELS.get(outcome.decision, outcome.decision)
            line = f"- 处置：{label}"
            if outcome.note:
                line += f"（{outcome.note}）"
            lines.append(line)
        blocker = self.get_latest_blocker(dedupe_key)
        if blocker and blocker.blocker_type != "UNKNOWN":
            label = BLOCKER_LABELS.get(blocker.blocker_type, blocker.blocker_type)
            line = f"- 阻塞：{label}"
            if blocker.note:
                line += f" — 「{blocker.note}」"
            lines.append(line)
        if not lines:
            return ""
        return "## 上一轮处置（只读）\n" + "\n".join(lines)

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
        for table in (TABLE_LOGS, TABLE_TRACES, TABLE_OUTCOMES, TABLE_BLOCKERS):
            cur = self._conn.execute(f"DELETE FROM {table}")
            total += cur.rowcount
        self._conn.execute(
            "DELETE FROM sqlite_sequence WHERE name IN (?, ?, ?)",
            (TABLE_TRACES, TABLE_OUTCOMES, TABLE_BLOCKERS),
        )
        self._conn.commit()
        return total

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
        elif self._turso is not None:
            self._turso.close()
