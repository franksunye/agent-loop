#!/usr/bin/env python3
"""Agent-Loop POC：DB 增量轮询版自动跟进引擎（单文件编排）。

链路：GitHub Actions Cron → 增量捞取「已完工工单」→ LLM 生成跟进建议
     → 写入追踪库（幂等水位线）→ 企业微信群机器人推送。

领域语义纪律（见 docs/04-domain-semantics.md）：
- 所有 XLink 系统知识（serviceAppointment / status=403 / 区划码 / state / exts）
  收拢在 `domain.py`（防腐层）；**本文件只说领域语言**（WorkOrder / 跟进建议）。
- mock 与真实数据走同一个翻译器，保证防腐层始终被验证。

数据源（FSM）与追踪库（Tracking）均可切换，第三方依赖按需懒加载。

运行：
    python agent_cron_engine.py                # 按 .env 配置运行
    DRY_RUN=true python agent_cron_engine.py   # 零依赖冒烟验证
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
from datetime import datetime
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import domain
from domain import FollowUpSuggestion, WorkOrder, bj_now

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


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# ======================================================================
# 0. 配置
# ======================================================================
@dataclass
class Config:
    # 开发环境 E2E 默认 true：企微仅预览、不打扰群；真发需显式 DRY_RUN=false
    dry_run: bool = field(default_factory=lambda: _env_bool("DRY_RUN", True))

    # 工单数据源（v0.2 起默认 dev 真实库，mock 仅用于离线 CI）
    fsm_source: str = field(default_factory=lambda: os.getenv("FSM_SOURCE", "mongo").lower())
    fsm_mongo_url: str = field(default_factory=lambda: os.getenv("FSM_MONGO_URL", ""))
    fsm_mongo_db: str = field(default_factory=lambda: os.getenv("FSM_MONGO_DB", "xlinkdemo"))
    fsm_time_field: str = field(default_factory=lambda: os.getenv("FSM_TIME_FIELD", "updateTime"))
    lookback_hours: int = field(default_factory=lambda: int(os.getenv("FSM_LOOKBACK_HOURS", "24")))
    fsm_batch_limit: int = field(default_factory=lambda: int(os.getenv("FSM_BATCH_LIMIT", "50")))
    # 仅跟进 updateTime 在最近 N 天内（默认 14）；超过认为无意义
    fsm_max_age_days: int = field(default_factory=lambda: int(os.getenv("FSM_MAX_AGE_DAYS", "14")))
    fsm_stale_days: int = field(default_factory=lambda: int(os.getenv("FSM_STALE_DAYS", "0")))
    fsm_event_statuses: str = field(default_factory=lambda: os.getenv("FSM_EVENT_STATUSES", ""))
    # v0.2 试点：逗号分隔姓名（mongo 解析）或 userId；空=不过滤
    pilot_housekeepers: str = field(default_factory=lambda: os.getenv("FSM_PILOT_HOUSEKEEPERS", ""))
    pilot_housekeeper_ids: str = field(
        default_factory=lambda: os.getenv("FSM_PILOT_HOUSEKEEPER_IDS", "")
    )
    wecom_webhook_map: str = field(default_factory=lambda: os.getenv("WECOM_WEBHOOK_MAP", ""))
    # 运行期解析结果（run 启动时填充）
    resolved_pilot_ids: Optional[List[str]] = field(default=None, repr=False)
    pilot_id_to_name: Dict[str, str] = field(default_factory=dict, repr=False)

    # 追踪库（幂等水位线）
    tracking_source: str = field(
        default_factory=lambda: os.getenv("TRACKING_SOURCE", "local").lower()
    )
    tracking_local_path: str = field(
        default_factory=lambda: os.getenv("TRACKING_LOCAL_PATH", "agent_loop_tracking.db")
    )
    turso_url: str = field(default_factory=lambda: os.getenv("TURSO_URL", ""))
    turso_token: str = field(default_factory=lambda: os.getenv("TURSO_TOKEN", ""))

    # 推理提供方：heuristic（不走 API）| hunyuan（默认免费）| deepseek（质量验证）
    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "hunyuan").lower()
    )
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))
    hunyuan_api_key: str = field(default_factory=lambda: os.getenv("HUNYUAN_API_KEY", ""))

    # 推理模式：oneshot（默认试点）| steps（展示轨：enrich + LLM，见 docs/10）
    agent_mode: str = field(
        default_factory=lambda: os.getenv("AGENT_MODE", "oneshot").lower()
    )

    # 输出
    wecom_webhook: str = field(default_factory=lambda: os.getenv("WECOM_WEBHOOK", ""))

    def resolved_llm(self) -> tuple[str, str, str, str, bool]:
        """返回 (provider_label, api_key, base_url, model, use_json_mode)。"""
        p = self.llm_provider
        if p == "heuristic":
            return "heuristic", "", "", "", False
        if p == "hunyuan":
            key = self.hunyuan_api_key or self.llm_api_key
            # 避免 .env 里残留的 deepseek-chat 等被误用
            model = self.llm_model if "hunyuan" in (self.llm_model or "").lower() else "hunyuan-lite"
            base = self.llm_base_url or ""
            if base and "deepseek" in base.lower():
                base = ""
            return (
                "hunyuan",
                key,
                base or "https://api.hunyuan.cloud.tencent.com/v1",
                model,
                False,  # 混元用 prompt 约束 JSON，见 stockwise hunyuan_chain
            )
        if p in ("deepseek", "openai", "custom"):
            return (
                p,
                self.llm_api_key,
                self.llm_base_url or "https://api.deepseek.com/v1",
                self.llm_model or "deepseek-chat",
                True,
            )
        raise ValueError(f"未知 LLM_PROVIDER: {p}")


# ======================================================================
# 1. 事件摄取层（= 领域防腐层落点）
#    返回领域对象 WorkOrder，系统码翻译全部在 domain.py 完成。
# ======================================================================
def _is_v02_ingestion(cfg: Config) -> bool:
    return (
        bool((cfg.fsm_event_statuses or "").strip())
        or cfg.fsm_stale_days > 0
        or cfg.fsm_max_age_days > 0
    )


def fetch_completed_work_orders(cfg: Config, processed_keys: set[str]) -> List[WorkOrder]:
    """捞取 follow-up 事件候选工单（v0.2：按 dedupe_key 去重）。"""
    if cfg.fsm_source == "mock":
        work_orders = domain.mock_completed_work_orders(list(processed_keys))
    elif cfg.fsm_source == "mongo":
        work_orders = _fetch_from_mongo(cfg, processed_keys)
    else:
        raise ValueError(f"未知 FSM_SOURCE: {cfg.fsm_source}")

    logger.info("捞取到 %d 条待跟进（已处理 %d 个 dedupe_key）", len(work_orders), len(processed_keys))
    return work_orders


def _resolve_event_statuses(cfg: Config) -> List[str]:
    raw = (cfg.fsm_event_statuses or "").strip()
    if raw:
        return [s.strip() for s in raw.split(",") if s.strip()]
    return [domain.COMPLETED_STATUS]


def _parse_csv(raw: str) -> List[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


def _parse_webhook_map(raw: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in _parse_csv(raw):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if k and v:
            out[k] = v
    return out


def resolve_pilot_housekeepers(cfg: Config, db) -> None:
    """解析试点管家 userId；写入 cfg.resolved_pilot_ids / pilot_id_to_name。

    若配置了 FSM_PILOT_HOUSEKEEPERS（生产常用），则忽略 FSM_PILOT_HOUSEKEEPER_IDS，
    避免 dev 残留 ID 与生产姓名试点混用。
    """
    names = _parse_csv(cfg.pilot_housekeepers)
    ids = [] if names else _parse_csv(cfg.pilot_housekeeper_ids)
    id_to_name: Dict[str, str] = {}

    for uid in ids:
        row = db["user"].find_one({"_id": uid}, {"_id": 1, "name": 1})
        id_to_name[uid] = str((row or {}).get("name") or uid)

    for name in names:
        row = db["user"].find_one({"name": name, "state": 1}, {"_id": 1, "name": 1})
        if not row and "牧" in name:
            row = db["user"].find_one(
                {"name": name.replace("牧", "沐"), "state": 1}, {"_id": 1, "name": 1}
            )
        if not row:
            logger.warning("试点管家未找到（将跳过）: %s", name)
            continue
        uid = str(row["_id"])
        ids.append(uid)
        id_to_name[uid] = str(row.get("name") or name)

    cfg.resolved_pilot_ids = list(dict.fromkeys(ids)) if ids else None
    cfg.pilot_id_to_name = id_to_name
    if cfg.resolved_pilot_ids:
        logger.info(
            "试点管家过滤: %s",
            ", ".join(f"{id_to_name.get(i, i)}({i})" for i in cfg.resolved_pilot_ids),
        )
    elif names or cfg.pilot_housekeeper_ids:
        logger.warning("试点管家配置无效，本轮不捞取工单。")
        cfg.resolved_pilot_ids = []


def _webhook_for_housekeeper(cfg: Config, housekeeper_id: str) -> str:
    m = _parse_webhook_map(cfg.wecom_webhook_map)
    return m.get(housekeeper_id, "") or cfg.wecom_webhook


def _enrich_housekeeper_names(db, work_orders: List[WorkOrder]) -> None:
    ids = list({wo.housekeeper_id for wo in work_orders if wo.housekeeper_id})
    if not ids:
        return
    name_map: Dict[str, str] = {}
    for doc in db["user"].find({"_id": {"$in": ids}}, {"_id": 1, "name": 1}):
        name_map[str(doc["_id"])] = str(doc.get("name") or "")
    for wo in work_orders:
        wo.housekeeper_name = name_map.get(wo.housekeeper_id) or "未分配管家"


def _fetch_from_mongo(cfg: Config, processed_keys: set[str]) -> List[WorkOrder]:
    """XLink 主路径：从 serviceAppointment 拉原始行，经防腐层翻译为 WorkOrder。"""
    from pymongo import MongoClient  # 懒加载

    if not cfg.fsm_mongo_url:
        raise ValueError(
            "FSM_SOURCE=mongo 需要配置 FSM_MONGO_URL（见 .env.example / docs/xlink-data.md）"
        )
    statuses = _resolve_event_statuses(cfg)
    stale_days = cfg.fsm_stale_days if cfg.fsm_stale_days > 0 else 0
    max_age = cfg.fsm_max_age_days if cfg.fsm_max_age_days > 0 else 0
    lookback = cfg.lookback_hours if (stale_days <= 0 and max_age <= 0) else 0
    mongo_exclude: List[str] = []
    if not _is_v02_ingestion(cfg):
        mongo_exclude = [k.split(":", 1)[1] for k in processed_keys if ":" in k]
    client = MongoClient(cfg.fsm_mongo_url, serverSelectionTimeoutMS=8000)
    try:
        db = client[cfg.fsm_mongo_db]
        if cfg.resolved_pilot_ids is None:
            resolve_pilot_housekeepers(cfg, db)
        if cfg.resolved_pilot_ids is not None and len(cfg.resolved_pilot_ids) == 0:
            return []
        supervisor_ids = cfg.resolved_pilot_ids
        coll = db[domain.SA_COLLECTION]
        query = domain.follow_up_events_query(
            event_statuses=statuses,
            stale_days=stale_days,
            max_age_days=max_age,
            lookback_hours=lookback,
            processed_ids=mongo_exclude,
            supervisor_ids=supervisor_ids,
            time_field=cfg.fsm_time_field,
        )
        cursor = (
            coll.find(query, domain.SA_PROJECTION)
            .sort(cfg.fsm_time_field, -1)
            .limit(cfg.fsm_batch_limit)
        )
        work_orders = [domain.work_order_from_sa(doc) for doc in cursor]
        now = domain.bj_now()
        for wo in work_orders:
            if not wo.completed_at:
                continue
            try:
                raw = wo.completed_at
                if isinstance(raw, datetime):
                    ut = raw.replace(tzinfo=None) if raw.tzinfo else raw
                else:
                    s = str(raw).replace("Z", "")[:26].replace(" ", "T")
                    ut = datetime.fromisoformat(s)
                wo.stale_days = max(0, (now - ut).days)
            except (TypeError, ValueError):
                pass
        _enrich_housekeeper_names(db, work_orders)
        if _is_v02_ingestion(cfg):
            work_orders = [wo for wo in work_orders if wo.dedupe_key not in processed_keys]
        return work_orders
    finally:
        client.close()


# ======================================================================
# 2. 追踪库（幂等水位线 + 可检测性 trace）
# ======================================================================
# 表名前缀：多项目共用一个 Turso 库时用于清晰区分（默认 aol_ = FS-AOL）。
# 本地 sqlite 与云端 Turso 保持一致命名。
TABLE_PREFIX = os.getenv("AOL_TABLE_PREFIX", "aol_")
TABLE_LOGS = f"{TABLE_PREFIX}follow_up_logs"
TABLE_TRACES = f"{TABLE_PREFIX}reasoning_traces"

_SCHEMA = f"""
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
_SCHEMA_TRACES = f"""
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


@dataclass
class ReasoningTrace:
    """一次推理的完整可追溯记录（LLM 或启发式或报错）。"""

    work_order_id: str
    mode: str                      # llm | heuristic | llm_fallback_heuristic
    event_type: str = ""
    model: str = ""
    prompt_system: str = ""
    prompt_user: str = ""
    raw_response: str = ""
    parsed: Optional[Dict[str, Any]] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    status: str = "ok"             # ok | error
    error: str = ""
    steps_json: str = ""
    created_at: str = ""


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
            self._conn.execute(_SCHEMA)
            self._migrate_sqlite_v02(self._conn)
            self._conn.execute(_SCHEMA_TRACES)
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
            self._turso.execute(_SCHEMA)
            self._turso.execute(_SCHEMA_TRACES)
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


# ======================================================================
# 3. 推理层（LLM → 领域跟进建议 FollowUpSuggestion）
# ======================================================================
_SYSTEM_PROMPT = """你是雨虹防水维修（渗漏治理）业务的跟进行动助理。
场景：工单「待签约」——通常已勘查并可能有正式报价，需输出 **可审批的跟进方案**（非一句空话）。

纪律：
1. 只依据用户消息「系统查证」写内容；禁止编造金额、部位、渠道、合同。
2. 已有生效签约合同 → 「需要跟进」=false，「报价状态」=已有生效签约。
3. 「引用查证」每条必须能在系统查证中找到对应句；不得虚构。
4. 「沟通要点」2～4 条，像电话提纲（问什么、确认什么），不要写「尽快联系」 alone。
5. 「优先级依据」2～4 条，引用停留天数、金额、渠道、业务提示等。
6. 「业务提示」可影响优先级，不可替代查证；查证中无「业务提示」行则不得编造。
7. 沟通要点须贴合本单部位与渠道，勿照抄示例中的「屋面」等字样。
8. 「客户情绪」默认「中性」；仅当查证出现明确情绪线索时才用「积极/消极」。

只输出一个 JSON 对象，中文键名，中文枚举。规格见 docs/13-action-spec-v02.md。

必填结构：
{
  "规格版本": "v0.2",
  "需要跟进": true,
  "优先级": "中",
  "客户情绪": "中性",
  "原因摘要": "1～2句，管家扫一眼即懂",
  "优先级依据": ["依据1", "依据2"],
  "情况判断": {
    "商机阶段": "待签约",
    "报价状态": "已正式报价未签约 | 无正式报价 | 已有生效签约",
    "金额与方案": "仅写查证出现的金额与方案要点",
    "渠道与部位": "仅写查证出现的渠道与渗漏部位"
  },
  "跟进方案": {
    "主行动": "一句话主行动",
    "沟通要点": ["要点1", "要点2", "要点3"],
    "避免事项": ["勿承诺查证未出现的优惠/工期"]
  },
  "引用查证": ["摘自查证的短句1", "短句2"]
}

## 优质输出示例（仅学结构与语气；当前工单以系统查证为准，勿抄本例数字）

{
  "规格版本": "v0.2",
  "需要跟进": true,
  "优先级": "高",
  "客户情绪": "中性",
  "原因摘要": "已正式报价40653元，停留4天，屋面类客单价高，需推进签约。",
  "优先级依据": [
    "已停留4天，待签约停滞",
    "正式报价40653元，金额较高",
    "屋面/屋顶类部位客单价高，业务提示优先跟进"
  ],
  "情况判断": {
    "商机阶段": "待签约",
    "报价状态": "已正式报价未签约",
    "金额与方案": "正式报价40653元；方案：X5-P-热施工、X5-金属屋面；质保5年",
    "渠道与部位": "渠道：小红书；部位：屋面（具体位置见查证）"
  },
  "跟进方案": {
    "主行动": "电话回访客户，确认报价是否接受，推动签约。",
    "沟通要点": [
      "确认客户是否收到正式报价单，对金额和方案有无疑问",
      "强调质保年限与工艺要点，解答客户顾虑",
      "询问期望施工时间，屋面单可说明优先排期"
    ],
    "避免事项": ["勿承诺查证未出现的优惠或折扣"]
  },
  "引用查证": ["已正式报价 40653元（屋面）", "方案与质保见查证", "业务提示：屋面优先跟进"]
}
"""


def _parse_llm_json(content: str) -> FollowUpSuggestion:
    text = (content or "").strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    return FollowUpSuggestion.from_dict(json.loads(text))


def reason_follow_up(cfg: Config, wo: WorkOrder) -> Tuple[Optional[FollowUpSuggestion], ReasoningTrace]:
    """对一个工单生成跟进建议，并返回完整推理 trace。"""
    if cfg.agent_mode == "steps":
        return _reason_follow_up_steps(cfg, wo)
    return _reason_follow_up_oneshot(cfg, wo)


def _reason_follow_up_steps(cfg: Config, wo: WorkOrder) -> Tuple[Optional[FollowUpSuggestion], ReasoningTrace]:
    """展示轨：enrich（tool）→ LLM，步骤写入 trace.steps_json。"""
    import time

    from agent_tools import enrich_work_order_context

    now = bj_now().isoformat()
    steps: List[Dict[str, Any]] = []
    t0 = time.perf_counter()
    enrich_ctx = enrich_work_order_context(cfg, wo)
    steps.append({
        "step": 1,
        "kind": "tool",
        "name": "enrich_work_order_context",
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "status": "ok",
        "output": enrich_ctx.to_step_dict(),
    })
    enrich_block = enrich_ctx.to_prompt_block()
    user_prompt = f"工单号: {wo.order_num}\n{wo.followup_text}\n\n{enrich_block}"

    provider, api_key, base_url, model, json_mode = cfg.resolved_llm()
    if provider == "heuristic" or not api_key:
        s = _heuristic_suggestion(wo, enrich_ctx)
        steps.append({"step": 2, "kind": "heuristic", "name": "suggest", "status": "ok"})
        trace = ReasoningTrace(
            work_order_id=wo.work_order_id, event_type=wo.event_type,
            mode="steps_heuristic", model="heuristic",
            prompt_user=user_prompt,
            raw_response=json.dumps(s.to_display_dict(), ensure_ascii=False),
            parsed=s.to_display_dict(), status="ok", created_at=now,
            steps_json=json.dumps(steps, ensure_ascii=False),
        )
        return s, trace

    suggestion, trace = _llm_follow_up(
        cfg, wo, provider, api_key, base_url, model, json_mode, user_prompt, now,
        enrich_ctx=enrich_ctx,
    )
    trace.mode = f"steps_llm_{provider}"
    steps.append({
        "step": 2,
        "kind": "llm",
        "name": "suggest",
        "latency_ms": trace.latency_ms,
        "status": trace.status,
    })
    trace.steps_json = json.dumps(steps, ensure_ascii=False)
    return suggestion, trace


def _reason_follow_up_oneshot(cfg: Config, wo: WorkOrder) -> Tuple[Optional[FollowUpSuggestion], ReasoningTrace]:
    """默认试点：单次 LLM / 启发式。"""
    now = bj_now().isoformat()
    provider, api_key, base_url, model, json_mode = cfg.resolved_llm()

    if provider == "heuristic" or not api_key:
        s = _heuristic_suggestion(wo, None)
        trace = ReasoningTrace(
            work_order_id=wo.work_order_id, event_type=wo.event_type, mode="heuristic",
            model="heuristic", prompt_user=wo.followup_text,
            raw_response=json.dumps(s.to_display_dict(), ensure_ascii=False),
            parsed=s.to_display_dict(), status="ok", created_at=now,
        )
        return s, trace

    user_prompt = f"工单号: {wo.order_num}\n{wo.followup_text}"
    return _llm_follow_up(
        cfg, wo, provider, api_key, base_url, model, json_mode, user_prompt, now,
        enrich_ctx=None,
    )


def _llm_follow_up(
    cfg: Config,
    wo: WorkOrder,
    provider: str,
    api_key: str,
    base_url: str,
    model: str,
    json_mode: bool,
    user_prompt: str,
    now: str,
    enrich_ctx: Any = None,
) -> Tuple[Optional[FollowUpSuggestion], ReasoningTrace]:
    from openai import OpenAI
    import time

    trace = ReasoningTrace(
        work_order_id=wo.work_order_id, event_type=wo.event_type, mode=f"llm_{provider}",
        model=model, prompt_system=_SYSTEM_PROMPT, prompt_user=user_prompt, created_at=now,
    )
    client = OpenAI(api_key=api_key, base_url=base_url)
    t0 = time.perf_counter()
    try:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.15,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        trace.latency_ms = int((time.perf_counter() - t0) * 1000)
        content = resp.choices[0].message.content or "{}"
        trace.raw_response = content
        usage = getattr(resp, "usage", None)
        if usage:
            trace.prompt_tokens = usage.prompt_tokens or 0
            trace.completion_tokens = usage.completion_tokens or 0
            trace.total_tokens = usage.total_tokens or 0
        trace.status = "ok"
        try:
            s = _parse_llm_json(content)
            if enrich_ctx is not None:
                from suggestion_polish import polish_suggestion

                s = polish_suggestion(wo, enrich_ctx, s)
                trace.mode = f"{trace.mode}+polish"
        except json.JSONDecodeError:
            logger.warning("LLM 返回非法 JSON，回退启发式：%s", content[:200])
            s = _heuristic_suggestion(wo, enrich_ctx)
            trace.mode = "llm_fallback_heuristic"
        trace.parsed = s.to_display_dict()
        if trace.status == "ok":
            trace.raw_response = json.dumps(s.to_display_dict(), ensure_ascii=False)
        return s, trace
    except Exception as e:
        trace.latency_ms = int((time.perf_counter() - t0) * 1000)
        trace.status = "error"
        trace.error = f"{type(e).__name__}: {e}"
        return None, trace


def _heuristic_suggestion(wo: WorkOrder, enrich_ctx: Any = None) -> FollowUpSuggestion:
    """无 LLM 时的确定性兜底；有 enrich 时尽量填满 v0.2 结构。"""
    from agent_tools import EnrichedContext

    ctx: Optional[EnrichedContext] = enrich_ctx
    text = f"{wo.title} {wo.summary}"
    negative = any(k in text for k in ["不满", "担心", "投诉", "尽快", "复检", "问题", "偏低"])
    stale = wo.stale_days >= 7
    high_part = bool(
        ctx and any("屋面" in p or "屋顶" in p for p in (ctx.leak_sites or []))
    )
    low_channel = bool(ctx and ctx.channel_label and "抖音" in ctx.channel_label)

    if ctx and ctx.has_signed_contract:
        return FollowUpSuggestion(
            needs_follow_up=False,
            priority="低",
            customer_sentiment="中性",
            reason_summary="系统查证显示已有生效签约合同，建议先核对工单状态是否未更新。",
            priority_reasons=["已有生效签约合同"],
            situation=domain.FollowUpSituation(
                stage="待签约",
                quote_status="已有生效签约",
                amount_plan="见查证",
                channel_part=ctx.channel_label or ctx.source_type_label,
            ),
            action_plan=domain.FollowUpActionPlan(
                primary_action="核对工单状态与合同是否一致",
                talk_points=["确认系统合同与工单状态为何不一致"],
                avoid=["勿重复催促已签约客户"],
            ),
            evidence_refs=(ctx.evidence_lines or [])[:5],
        )

    quote_status = "无正式报价"
    amount_plan = ""
    if ctx and ctx.has_quote and ctx.quotes:
        quote_status = "已正式报价未签约"
        q0 = ctx.quotes[0]
        amt = q0.get("amount_yuan")
        amount_plan = f"{amt:.0f}元" if isinstance(amt, (int, float)) else ""
        pkgs = "、".join((q0.get("package_names") or [])[:2])
        if pkgs:
            amount_plan += f"；{pkgs}"

    priority = "高" if (high_part or stale) else ("低" if low_channel else "中")
    if high_part and ctx and ctx.quotes:
        q0 = ctx.quotes[0]
        amt = q0.get("amount_yuan")
        amt_s = f"{amt:.0f}元" if isinstance(amt, (int, float)) else "—"
        reason_summary = (
            f"待签约停留{wo.stale_days}天，屋面类高客单，已报价{amt_s}未支付，建议优先电话推进签约。"
        )
    elif ctx and ctx.has_quote:
        reason_summary = (
            f"待签约停留{wo.stale_days}天，已正式报价未支付，建议电话确认并推进签约。"
        )
    else:
        reason_summary = f"待签约停留{wo.stale_days}天，建议确认报价与签约意向。"

    priority_reasons = [f"停留{wo.stale_days}天"]
    if amount_plan:
        priority_reasons.append(f"报价情况：{amount_plan}")
    if high_part:
        priority_reasons.append("屋面/屋顶部位，客单价通常较高")
    if low_channel:
        priority_reasons.append("抖音渠道，建议先核实意向再重投入")
    if ctx and ctx.business_hints:
        priority_reasons.extend(ctx.business_hints[:1])

    talk_points = [
        "确认客户是否已看清正式报价与方案范围",
        "了解是否在比价、装修进度或付款安排上存在障碍",
    ]
    if amount_plan:
        talk_points.insert(0, f"围绕查证中的报价（{amount_plan.split('；')[0]}）确认认可度")

    return FollowUpSuggestion(
        needs_follow_up=True,
        priority=priority,
        customer_sentiment="消极" if negative else "中性",
        reason_summary=reason_summary,
        priority_reasons=priority_reasons[:4],
        situation=domain.FollowUpSituation(
            stage="待签约",
            quote_status=quote_status,
            amount_plan=amount_plan or "查证无报价",
            channel_part=(
                f"{ctx.channel_label or ctx.source_type_label}；"
                f"{'、'.join(ctx.leak_sites) if ctx else ''}"
            ).strip("；"),
        ),
        action_plan=domain.FollowUpActionPlan(
            primary_action="电话确认报价并推进签约",
            talk_points=talk_points[:4],
            avoid=["勿承诺查证未出现的折扣、工期或增项"],
        ),
        evidence_refs=(ctx.evidence_lines[:5] if ctx else []),
    )


# ======================================================================
# 4. 输出层（企业微信群机器人）
# ======================================================================
_PRIORITY_EMOJI = {"高": "🔴", "中": "🟡", "低": "🟢", "high": "🔴", "medium": "🟡", "low": "🟢"}


def _enrich_output_from_trace(trace: ReasoningTrace) -> Optional[Dict[str, Any]]:
    if not trace.steps_json:
        return None
    try:
        steps = json.loads(trace.steps_json)
    except json.JSONDecodeError:
        return None
    for st in steps:
        if st.get("name") == "enrich_work_order_context":
            out = st.get("output")
            return out if isinstance(out, dict) else None
    return None


def build_card_markdown(
    wo: WorkOrder,
    s: FollowUpSuggestion,
    *,
    enrich_output: Optional[Dict[str, Any]] = None,
) -> str:
    emoji = _PRIORITY_EMOJI.get(s.priority, "⚪")
    hk = wo.housekeeper_name or "未分配管家"
    stale_line = f"> **停留**：{wo.stale_days} 天\n" if wo.stale_days else ""
    verdict = (enrich_output or {}).get("business_verdict") or ""
    enrich_line = f"> **结论**：{verdict}\n" if verdict else ""
    evidence = (enrich_output or {}).get("evidence_lines") or []
    if not evidence and s.evidence_refs:
        evidence = s.evidence_refs
    evidence_block = "".join(f"> - {line}\n" for line in evidence[:4])

    basis_block = "".join(f"> - {x}\n" for x in (s.priority_reasons or [])[:4])
    talk_block = "".join(
        f"> {i + 1}. {p}\n" for i, p in enumerate((s.action_plan.talk_points or [])[:4])
    )
    avoid_block = ""
    if s.action_plan.avoid:
        avoid_block = "> **避免**：" + "；".join(s.action_plan.avoid[:2]) + "\n"

    sit = s.situation
    situation_line = ""
    if sit.quote_status or sit.amount_plan:
        situation_line = (
            f"> **情况**：{sit.quote_status}"
            + (f" · {sit.amount_plan}" if sit.amount_plan else "")
            + "\n"
        )

    return (
        f"### {emoji} 跟进行动 · {wo.city}\n"
        f"> **管家**：{hk}\n"
        f"> **工单号**：{wo.order_num or wo.work_order_id}\n"
        f"> **状态**：{wo.task_type}\n"
        f"{stale_line}"
        f"> **事件**：{domain.event_type_label(wo.event_type)}\n"
        f"{enrich_line}"
        f"{evidence_block}"
        f"> **客户**：{wo.customer_name}（{wo.phone}）\n"
        f"> **优先级**：<font color=\"warning\">{s.priority}</font>\n"
        f"> **客户情绪**：{s.customer_sentiment}\n"
        f"{situation_line}"
        f"> **原因摘要**：{s.reason_summary}\n"
        f"> **主行动**：{s.action_plan.primary_action}\n"
        f"{basis_block}"
        f"> **沟通要点**：\n{talk_block}"
        f"{avoid_block}"
    )


def send_wecom_card(cfg: Config, markdown: str, *, housekeeper_id: str = "") -> bool:
    webhook = _webhook_for_housekeeper(cfg, housekeeper_id) if housekeeper_id else cfg.wecom_webhook
    if cfg.dry_run or not webhook:
        tag = ""
        if housekeeper_id and cfg.wecom_webhook_map:
            tag = f" [webhook→{housekeeper_id[:8]}…]" if webhook else " [无专属 webhook，未发]"
        logger.info("[企微预览] 未发送（DRY_RUN 或缺少 webhook）%s：\n%s", tag, markdown)
        return True

    import requests  # 懒加载

    resp = requests.post(
        webhook,
        json={"msgtype": "markdown", "markdown": {"content": markdown}},
        timeout=15,
    )
    ok = resp.ok and resp.json().get("errcode") == 0
    if not ok:
        logger.error("企微推送失败：%s", resp.text[:300])
    return ok


# ======================================================================
# E2E：重置追踪库（幂等去重与可重复验证）
# ======================================================================
def reset_tracking(cfg: Config) -> None:
    """清空本地 sqlite 表数据（不删文件），便于 E2E 反复跑且 GUI 工具可刷新。

    仅允许 TRACKING_SOURCE=local，避免误清 Turso 上的共享数据。
    """
    if cfg.tracking_source != "local":
        raise SystemExit(
            "reset-tracking 仅支持 TRACKING_SOURCE=local。"
            "云库请手动运维或换 TRACKING_LOCAL_PATH 指向临时文件。"
        )
    path = os.path.abspath(cfg.tracking_local_path)
    store = TrackingStore(cfg)
    try:
        n = store.clear_all_data()
    finally:
        store.close()
    logger.info("已清空追踪表数据（%d 行，可重复 E2E）: %s", n, path)


# ======================================================================
# 主循环
# ======================================================================
def run(cfg: Optional[Config] = None) -> int:
    cfg = cfg or Config()
    prov, _, _, model, _ = cfg.resolved_llm()
    statuses = _resolve_event_statuses(cfg)
    pilot_label = (cfg.pilot_housekeepers or cfg.pilot_housekeeper_ids or "全部").strip()
    logger.info(
        "启动 agent-loop | dry_run=%s fsm=%s tracking=%s llm=%s/%s | "
        "events=%s max_age_days=%d stale_days=%d | pilot=%s | agent=%s",
        cfg.dry_run, cfg.fsm_source, cfg.tracking_source, prov, model,
        ",".join(statuses), cfg.fsm_max_age_days, cfg.fsm_stale_days, pilot_label,
        cfg.agent_mode,
    )

    store = TrackingStore(cfg)
    try:
        processed_keys = store.get_processed_dedupe_keys()
        work_orders = fetch_completed_work_orders(cfg, processed_keys)

        if not work_orders:
            logger.info("本轮无待跟进事件，结束。")
            return 0

        success = 0
        for wo in work_orders:
            ref = wo.order_num or wo.work_order_id
            try:
                suggestion, trace = reason_follow_up(cfg, wo)
                store.log_reasoning_trace(trace)  # 每次推理都落 trace（含失败）

                if suggestion is None:
                    logger.warning("工单 %s 推理失败(%s)，下轮重试。", ref, trace.error)
                    continue

                logger.info(
                    "工单 %s [%s] → %s | %s %dtok %dms",
                    ref,
                    domain.event_type_label(wo.event_type),
                    json.dumps(suggestion.to_display_dict(), ensure_ascii=False),
                    trace.mode,
                    trace.total_tokens,
                    trace.latency_ms,
                )

                if suggestion.needs_follow_up:
                    enrich_out = (
                        _enrich_output_from_trace(trace)
                        if cfg.agent_mode == "steps"
                        else None
                    )
                    card = build_card_markdown(wo, suggestion, enrich_output=enrich_out)
                    sent = send_wecom_card(cfg, card, housekeeper_id=wo.housekeeper_id)
                    status = "sent" if sent else "send_failed"
                else:
                    status = "skipped_no_follow_up"

                # 仅成功送达（或明确无需跟进）才记入水位线，
                # 推送失败留待下轮重试 —— 天然的拉取式状态机。
                if status != "send_failed":
                    store.mark_processed(wo, suggestion, status)
                    success += 1
                else:
                    logger.warning("工单 %s 推送失败，下轮重试。", ref)
            except Exception:
                logger.exception("工单 %s 处理异常，下轮重试。", ref)

        logger.info("本轮完成：成功 %d / 共 %d", success, len(work_orders))
        return 0
    finally:
        store.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent-Loop 跟进行动引擎")
    parser.add_argument(
        "--reset-tracking",
        action="store_true",
        help="运行前清空本地 sqlite 表数据（保留 db 文件，E2E 重复验证用）",
    )
    args = parser.parse_args()
    cfg = Config()
    if args.reset_tracking or _env_bool("TRACKING_RESET"):
        reset_tracking(cfg)
    return run(cfg)


if __name__ == "__main__":
    sys.exit(main())
