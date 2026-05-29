#!/usr/bin/env python3
"""Agent-Loop POC：DB 增量轮询版自动跟进引擎（单文件实现）。

链路：GitHub Actions Cron → 增量捞取「新完工工单」→ LLM 生成结构化跟进 Action
     → 写入追踪库（幂等水位线）→ 企业微信群机器人推送。

针对 XLink 真实数据（已用 dev 库 `xlinkdemo` 只读验证）：
- 工单集合：MongoDB `serviceAppointment`
- 已完工口径：`status="403"`（菜单「已完工」=orderState=done&status=403），且 `state=1`（排除作废 -1）
- 时间字段：`createTime`/`updateTime` 为 BSON datetime（北京本地时间，无时区）
- 自由文本：`describe`（备注，稀疏）+ `title`；`city` 为行政区划码（110100=北京）

设计目标：用最小成本证明价值。
- DRY_RUN=true 时不连任何外部服务，用内置 mock 工单把全链路跑通并打印结果。
- 数据源（FSM）与追踪库（Tracking）均可切换，所有第三方依赖按需懒加载。

运行：
    python agent_cron_engine.py                # 按 .env 配置运行
    DRY_RUN=true python agent_cron_engine.py   # 零依赖冒烟验证
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

# ---- 可选依赖：缺失时不影响 dry-run + mock + local 链路 ----
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv 是可选的
    pass


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("agent-loop")

# 北京时区（XLink 库内时间为北京本地时间，GitHub Runner 为 UTC，必须显式校正）
_BJ_TZ = timezone(timedelta(hours=8))

# 常见行政区划码 → 城市名（仅展示用，未命中则回退原码）
_CITY_CODE_MAP = {
    "110100": "北京",
    "120100": "天津",
    "310100": "上海",
    "440100": "广州",
    "440300": "深圳",
    "330100": "杭州",
    "510100": "成都",
    "320100": "南京",
    "420100": "武汉",
    "610100": "西安",
}


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _bj_now() -> datetime:
    """北京本地时间（naive），用于与库内 naive datetime 比较。"""
    return datetime.now(_BJ_TZ).replace(tzinfo=None)


def _city_label(code: str) -> str:
    return _CITY_CODE_MAP.get(str(code), str(code) or "未知")


# ======================================================================
# 0. 配置
# ======================================================================
@dataclass
class Config:
    dry_run: bool = field(default_factory=lambda: _env_bool("DRY_RUN", False))

    # FSM 工单数据源
    fsm_source: str = field(default_factory=lambda: os.getenv("FSM_SOURCE", "mock").lower())
    fsm_db_url: str = field(default_factory=lambda: os.getenv("FSM_DB_URL", ""))
    fsm_mongo_url: str = field(default_factory=lambda: os.getenv("FSM_MONGO_URL", ""))
    fsm_mongo_db: str = field(default_factory=lambda: os.getenv("FSM_MONGO_DB", "xlink"))
    fsm_mongo_collection: str = field(
        default_factory=lambda: os.getenv("FSM_MONGO_COLLECTION", "serviceAppointment")
    )
    # 已完工口径（已验证：403=已完工）
    fsm_finished_status: str = field(default_factory=lambda: os.getenv("FSM_FINISHED_STATUS", "403"))
    fsm_time_field: str = field(default_factory=lambda: os.getenv("FSM_TIME_FIELD", "updateTime"))
    lookback_hours: int = field(default_factory=lambda: int(os.getenv("FSM_LOOKBACK_HOURS", "24")))
    fsm_batch_limit: int = field(default_factory=lambda: int(os.getenv("FSM_BATCH_LIMIT", "50")))

    # 追踪库（幂等水位线）
    tracking_source: str = field(
        default_factory=lambda: os.getenv("TRACKING_SOURCE", "local").lower()
    )
    tracking_local_path: str = field(
        default_factory=lambda: os.getenv("TRACKING_LOCAL_PATH", "agent_loop_tracking.db")
    )
    turso_url: str = field(default_factory=lambda: os.getenv("TURSO_URL", ""))
    turso_token: str = field(default_factory=lambda: os.getenv("TURSO_TOKEN", ""))

    # LLM（兼容 OpenAI 协议）
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))

    # 输出
    wecom_webhook: str = field(default_factory=lambda: os.getenv("WECOM_WEBHOOK", ""))


# ======================================================================
# 1. 增量数据捕获层
# ======================================================================
@dataclass
class Job:
    """对齐 XLink serviceAppointment 的工单视图。"""

    id: str
    order_num: str = ""
    city: str = ""            # 行政区划码或名称
    service_type: str = ""
    title: str = ""
    describe: str = ""        # 备注/描述（AI 跟进主要文本来源）
    customer_name: str = ""
    phone: str = ""
    status: str = ""
    finished_at: str = ""

    @property
    def city_label(self) -> str:
        return _city_label(self.city)

    @property
    def followup_text(self) -> str:
        parts = [f"工单标题：{self.title or '(无)'}"]
        if self.describe:
            parts.append(f"备注：{self.describe}")
        parts.append(f"服务类型编码：{self.service_type or '(无)'}")
        parts.append(f"城市：{self.city_label}")
        return "\n".join(parts)


_MOCK_JOBS = [
    Job(
        id="SA-MOCK-001",
        order_num="GD20260529001",
        city="110100",
        service_type="40",
        title="王先生的工单",
        describe="更换厨房龙头已完成，客户反馈水压偏低，建议后续检查总阀。",
        customer_name="王先生",
        phone="138****1234",
        status="403",
        finished_at=_bj_now().isoformat(),
    ),
    Job(
        id="SA-MOCK-002",
        order_num="GD20260529002",
        city="310100",
        service_type="11",
        title="李女士的工单",
        describe="安装智能门锁完成，老人不熟悉操作，客户担心电池续航，问能否上门复检。",
        customer_name="李女士",
        phone="139****5678",
        status="403",
        finished_at=_bj_now().isoformat(),
    ),
    Job(
        id="SA-MOCK-003",
        order_num="GD20260529003",
        city="110100",
        service_type="40",
        title="张先生的工单",
        describe="",  # 真实数据里 describe 多为空，验证空文本兜底
        customer_name="张先生",
        phone="137****9012",
        status="403",
        finished_at=_bj_now().isoformat(),
    ),
]


def fetch_processed_ids(store: "TrackingStore") -> set[str]:
    """从追踪库读出已处理 job_id，作为差集水位线，确保每单只跟进一次。"""
    return set(store.get_processed_job_ids())


def fetch_incremental_jobs(cfg: Config, processed_ids: set[str]) -> List[Job]:
    """按配置切换数据源，捞取「新完工 + 未处理」工单。"""
    if cfg.fsm_source == "mock":
        jobs = [j for j in _MOCK_JOBS if j.id not in processed_ids]
    elif cfg.fsm_source == "mongo":
        jobs = _fetch_from_mongo(cfg, processed_ids)
    elif cfg.fsm_source == "postgres":
        jobs = _fetch_from_postgres(cfg, processed_ids)
    else:
        raise ValueError(f"未知 FSM_SOURCE: {cfg.fsm_source}")

    logger.info("增量捞取到 %d 条待处理工单（已处理 %d 条）", len(jobs), len(processed_ids))
    return jobs


def _fetch_from_mongo(cfg: Config, processed_ids: set[str]) -> List[Job]:
    """XLink 主路径：从 serviceAppointment 捞取已完工工单。

    已验证口径（dev xlinkdemo）：status=403 且 state=1。
    """
    from pymongo import MongoClient  # 懒加载

    client = MongoClient(cfg.fsm_mongo_url, serverSelectionTimeoutMS=8000)
    try:
        coll = client[cfg.fsm_mongo_db][cfg.fsm_mongo_collection]
        query: Dict[str, Any] = {"status": cfg.fsm_finished_status, "state": 1}
        if cfg.lookback_hours > 0:
            since = _bj_now() - timedelta(hours=cfg.lookback_hours)
            query[cfg.fsm_time_field] = {"$gte": since}
        if processed_ids:
            query["_id"] = {"$nin": list(processed_ids)}

        projection = {
            "_id": 1, "orderNum": 1, "city": 1, "serviceType": 1,
            "title": 1, "describe": 1, "name": 1, "phone": 1,
            "status": 1, cfg.fsm_time_field: 1,
        }
        cursor = (
            coll.find(query, projection)
            .sort(cfg.fsm_time_field, -1)
            .limit(cfg.fsm_batch_limit)
        )
        jobs: List[Job] = []
        for d in cursor:
            jobs.append(
                Job(
                    id=str(d.get("_id")),
                    order_num=d.get("orderNum", ""),
                    city=d.get("city", ""),
                    service_type=str(d.get("serviceType", "")),
                    title=d.get("title", ""),
                    describe=d.get("describe", "") or "",
                    customer_name=d.get("name", ""),
                    phone=d.get("phone", ""),
                    status=str(d.get("status", "")),
                    finished_at=str(d.get(cfg.fsm_time_field, "")),
                )
            )
        return jobs
    finally:
        client.close()


def _fetch_from_postgres(cfg: Config, processed_ids: set[str]) -> List[Job]:
    """备用路径：若某些数据源为 PostgreSQL（spec 原始设定）。"""
    import psycopg2  # 懒加载

    conn = psycopg2.connect(cfg.fsm_db_url)
    try:
        cur = conn.cursor()
        base = (
            "SELECT id, order_num, city, service_type, title, describe, name, phone, status, finished_at "
            "FROM service_appointment WHERE status = %s "
            f"AND finished_at >= NOW() - INTERVAL '{cfg.lookback_hours} hours'"
        )
        params: List[Any] = [cfg.fsm_finished_status]
        if processed_ids:
            ids = list(processed_ids)
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"{base} AND id::text NOT IN ({placeholders})", params + ids)
        else:
            cur.execute(base, params)
        rows = cur.fetchall()
        cur.close()
        return [
            Job(id=str(r[0]), order_num=r[1] or "", city=r[2] or "", service_type=str(r[3] or ""),
                title=r[4] or "", describe=r[5] or "", customer_name=r[6] or "", phone=r[7] or "",
                status=str(r[8] or ""), finished_at=str(r[9]))
            for r in rows
        ]
    finally:
        conn.close()


# ======================================================================
# 2. 追踪库（幂等水位线）
# ======================================================================
_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_follow_up_logs (
    job_id        TEXT PRIMARY KEY,
    order_num     TEXT,
    city          TEXT,
    action_spec   TEXT,
    status        TEXT,
    processed_at  TEXT
)
"""


class TrackingStore:
    """统一追踪库接口：local=sqlite，cloud=Turso。"""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        if cfg.tracking_source == "local":
            self._conn = sqlite3.connect(cfg.tracking_local_path)
            self._conn.execute(_SCHEMA)
            self._conn.commit()
            self._turso = None
        elif cfg.tracking_source == "cloud":
            from libsql_client import create_client_sync  # 懒加载

            self._turso = create_client_sync(url=cfg.turso_url, auth_token=cfg.turso_token)
            self._turso.execute(_SCHEMA)
            self._conn = None
        else:
            raise ValueError(f"未知 TRACKING_SOURCE: {cfg.tracking_source}")

    def get_processed_job_ids(self) -> List[str]:
        if self._conn is not None:
            rows = self._conn.execute("SELECT job_id FROM ai_follow_up_logs").fetchall()
            return [r[0] for r in rows]
        res = self._turso.execute("SELECT job_id FROM ai_follow_up_logs")
        return [r[0] for r in res.rows]

    def mark_processed(self, job: Job, action_spec: Dict[str, Any], status: str) -> None:
        now = _bj_now().isoformat()
        spec_json = json.dumps(action_spec, ensure_ascii=False)
        row = (job.id, job.order_num, job.city, spec_json, status, now)
        sql = (
            "INSERT OR REPLACE INTO ai_follow_up_logs "
            "(job_id, order_num, city, action_spec, status, processed_at) VALUES (?,?,?,?,?,?)"
        )
        if self._conn is not None:
            self._conn.execute(sql, row)
            self._conn.commit()
        else:
            self._turso.execute(sql, list(row))

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
        elif self._turso is not None:
            self._turso.close()


# ======================================================================
# 3. 核心推理层（LLM → 结构化 Action Spec）
# ======================================================================
_SYSTEM_PROMPT = """你是家装售后服务的跟进助理。根据已完工工单的标题与备注，
判断是否需要人工跟进，并给出结构化建议。只输出 JSON，不要多余文字。
JSON 字段：
- needs_follow_up: bool        是否需要跟进
- priority: "high"|"medium"|"low"
- reason: string               一句话原因
- suggested_action: string     建议的具体动作
- customer_sentiment: "positive"|"neutral"|"negative"
"""


def build_action_spec(cfg: Config, job: Job) -> Dict[str, Any]:
    """调用 LLM 生成结构化跟进建议；dry-run 或无 key 时用启发式 stub。"""
    if cfg.dry_run or not cfg.llm_api_key:
        return _stub_action_spec(job)

    from openai import OpenAI  # 懒加载

    client = OpenAI(api_key=cfg.llm_api_key, base_url=cfg.llm_base_url)
    user_prompt = f"工单号: {job.order_num}\n{job.followup_text}"
    resp = client.chat.completions.create(
        model=cfg.llm_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = resp.choices[0].message.content or "{}"
    try:
        spec = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("LLM 返回非法 JSON，回退 stub：%s", content[:200])
        spec = _stub_action_spec(job)
    return _validate_spec(spec)


def _stub_action_spec(job: Job) -> Dict[str, Any]:
    """无 LLM 时的确定性兜底：基于关键词的简单启发式。"""
    text = f"{job.title} {job.describe}"
    negative = any(k in text for k in ["不满", "担心", "投诉", "尽快", "复检", "问题", "偏低"])
    pending = any(k in text for k in ["下次", "补装", "后续", "复检", "建议"])
    no_text = not job.describe.strip()
    return _validate_spec(
        {
            # 备注为空的工单也建议轻量回访（验证服务质量）
            "needs_follow_up": negative or pending or no_text,
            "priority": "high" if negative else ("medium" if pending else "low"),
            "reason": (
                "检测到客户顾虑或遗留事项" if (negative or pending)
                else ("无备注，建议回访确认满意度" if no_text else "服务正常完成")
            ),
            "suggested_action": (
                "电话回访并确认遗留事项处理时间" if (negative or pending)
                else "电话回访确认客户满意度"
            ),
            "customer_sentiment": "negative" if negative else "neutral",
        }
    )


def _validate_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """轻量校验/补全字段。优先用 pydantic，缺失则降级为字典补全。"""
    try:
        from pydantic import BaseModel

        class ActionSpec(BaseModel):
            needs_follow_up: bool = False
            priority: str = "low"
            reason: str = ""
            suggested_action: str = ""
            customer_sentiment: str = "neutral"

        return ActionSpec(**spec).model_dump()
    except Exception:
        defaults = {
            "needs_follow_up": False,
            "priority": "low",
            "reason": "",
            "suggested_action": "",
            "customer_sentiment": "neutral",
        }
        return {**defaults, **{k: spec.get(k, v) for k, v in defaults.items()}}


# ======================================================================
# 4. 输出层（企业微信群机器人）
# ======================================================================
_PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}


def build_card_markdown(job: Job, spec: Dict[str, Any]) -> str:
    emoji = _PRIORITY_EMOJI.get(spec["priority"], "⚪")
    return (
        f"### {emoji} 工单跟进建议 · {job.city_label}\n"
        f"> **工单号**：{job.order_num or job.id}\n"
        f"> **客户**：{job.customer_name}（{job.phone}）\n"
        f"> **优先级**：<font color=\"warning\">{spec['priority']}</font>\n"
        f"> **客户情绪**：{spec['customer_sentiment']}\n"
        f"> **原因**：{spec['reason']}\n"
        f"> **建议动作**：{spec['suggested_action']}"
    )


def send_wecom_card(cfg: Config, markdown: str) -> bool:
    if cfg.dry_run or not cfg.wecom_webhook:
        logger.info("[DRY-RUN] 企微卡片预览：\n%s", markdown)
        return True

    import requests  # 懒加载

    resp = requests.post(
        cfg.wecom_webhook,
        json={"msgtype": "markdown", "markdown": {"content": markdown}},
        timeout=15,
    )
    ok = resp.ok and resp.json().get("errcode") == 0
    if not ok:
        logger.error("企微推送失败：%s", resp.text[:300])
    return ok


# ======================================================================
# 主循环
# ======================================================================
def run() -> int:
    cfg = Config()
    logger.info(
        "启动 agent-loop | dry_run=%s fsm=%s tracking=%s finished_status=%s",
        cfg.dry_run, cfg.fsm_source, cfg.tracking_source, cfg.fsm_finished_status,
    )

    store = TrackingStore(cfg)
    try:
        processed_ids = fetch_processed_ids(store)
        jobs = fetch_incremental_jobs(cfg, processed_ids)

        if not jobs:
            logger.info("本轮无新工单，结束。")
            return 0

        success = 0
        for job in jobs:
            try:
                spec = build_action_spec(cfg, job)
                logger.info("工单 %s → %s", job.order_num or job.id,
                            json.dumps(spec, ensure_ascii=False))

                if spec["needs_follow_up"]:
                    card = build_card_markdown(job, spec)
                    sent = send_wecom_card(cfg, card)
                    status = "sent" if sent else "send_failed"
                else:
                    status = "skipped_no_follow_up"

                # 只有成功送达（或明确无需跟进）才记入水位线，
                # 发送失败的留待下轮重试 —— 天然的拉取式状态机。
                if status != "send_failed":
                    store.mark_processed(job, spec, status)
                    success += 1
                else:
                    logger.warning("工单 %s 推送失败，下轮重试。", job.order_num or job.id)
            except Exception:
                logger.exception("工单 %s 处理异常，下轮重试。", job.order_num or job.id)

        logger.info("本轮完成：成功 %d / 共 %d", success, len(jobs))
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(run())
