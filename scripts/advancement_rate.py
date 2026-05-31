#!/usr/bin/env python3
"""只读推进率：Turso/SQLite 建议 vs Mongo 7 日后是否离开 206。

用法（仓库根目录）：
  python scripts/advancement_rate.py
  python scripts/advancement_rate.py --limit 50 --window-days 7

依赖：与 run_cron 相同的环境变量（TRACKING_*、FSM_MONGO_*）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "aol"))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass

from aol.config import Config  # noqa: E402
from aol.tracking.schema import TABLE_LOGS  # noqa: E402
from aol.tracking.store import TrackingStore  # noqa: E402


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
        return dt
    except ValueError:
        return None


def _fetch_recent_logs(store: TrackingStore, limit: int) -> list[dict]:
    sql = f"""
        SELECT dedupe_key, work_order_id, event_type, processed_at, status
        FROM {TABLE_LOGS}
        ORDER BY processed_at DESC
        LIMIT ?
    """
    return store._fetchall_dicts(sql, (limit,))  # noqa: SLF001


def _mongo_status_map(cfg: Config, work_order_ids: list[str]) -> dict[str, str]:
    if not work_order_ids:
        return {}
    try:
        from pymongo import MongoClient
    except ImportError:
        print("[advancement] pymongo 未安装，跳过 Mongo 对照", file=sys.stderr)
        return {}

    if not cfg.fsm_mongo_url:
        print("[advancement] FSM_MONGO_URL 未配置，跳过 Mongo 对照", file=sys.stderr)
        return {}

    client = MongoClient(cfg.fsm_mongo_url, serverSelectionTimeoutMS=8000)
    db = client[cfg.fsm_mongo_db]
    out: dict[str, str] = {}
    for doc in db.serviceAppointment.find(
        {"_id": {"$in": work_order_ids}},
        {"_id": 1, "status": 1},
    ):
        out[str(doc["_id"])] = str(doc.get("status", ""))
    client.close()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="7 日离开 206 粗率（只读）")
    parser.add_argument("--limit", type=int, default=100, help="最近 N 条 follow_up_logs")
    parser.add_argument("--window-days", type=int, default=7, help="观察窗口（天）")
    args = parser.parse_args()

    cfg = Config()
    store = TrackingStore(cfg)
    try:
        rows = _fetch_recent_logs(store, args.limit)
    finally:
        store.close()

    now = datetime.now(timezone(timedelta(hours=8)))
    eligible: list[dict] = []
    for row in rows:
        if row.get("event_type") != "STALE_SIGN_PENDING" and "206" not in str(row.get("dedupe_key", "")):
            # follow-up wedge uses STALE_SIGN_PENDING event type for 206
            pass
        processed = _parse_ts(str(row.get("processed_at") or ""))
        if not processed:
            continue
        if (now - processed).days < args.window_days:
            continue
        eligible.append(row)

    wo_ids = [str(r.get("work_order_id") or "") for r in eligible if r.get("work_order_id")]
    status_map = _mongo_status_map(cfg, wo_ids)

    advanced = 0
    still_206 = 0
    unknown = 0
    details: list[dict] = []
    for row in eligible:
        wo_id = str(row.get("work_order_id") or "")
        status = status_map.get(wo_id)
        if status is None:
            unknown += 1
            left = None
        elif status == "206":
            still_206 += 1
            left = False
        else:
            advanced += 1
            left = True
        details.append(
            {
                "dedupe_key": row.get("dedupe_key"),
                "work_order_id": wo_id,
                "processed_at": row.get("processed_at"),
                "mongo_status": status,
                "left_206": left,
            }
        )

    denom = len(eligible) - unknown
    rate = round(advanced / denom * 100, 1) if denom else 0.0
    report = {
        "window_days": args.window_days,
        "sample_eligible": len(eligible),
        "advanced": advanced,
        "still_206": still_206,
        "mongo_unknown": unknown,
        "advancement_rate_pct": rate,
        "details": details[:20],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
