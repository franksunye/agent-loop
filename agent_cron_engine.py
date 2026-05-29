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
def fetch_completed_work_orders(cfg: Config, processed_ids: set[str]) -> List[WorkOrder]:
    """捞取「新完工 + 未处理」工单，输出领域 WorkOrder 列表。"""
    pid = list(processed_ids)
    if cfg.fsm_source == "mock":
        work_orders = domain.mock_completed_work_orders(pid)
    elif cfg.fsm_source == "mongo":
        work_orders = _fetch_from_mongo(cfg, pid)
    else:
        raise ValueError(f"未知 FSM_SOURCE: {cfg.fsm_source}")

    logger.info("捞取到 %d 个新完工工单（已处理 %d 个）", len(work_orders), len(processed_ids))
    return work_orders


def _fetch_from_mongo(cfg: Config, processed_ids: List[str]) -> List[WorkOrder]:
    """XLink 主路径：从 serviceAppointment 拉原始行，经防腐层翻译为 WorkOrder。"""
    from pymongo import MongoClient  # 懒加载

    if not cfg.fsm_mongo_url:
        raise ValueError(
            "FSM_SOURCE=mongo 需要配置 FSM_MONGO_URL（见 .env.example / docs/xlink-data.md）"
        )
    client = MongoClient(cfg.fsm_mongo_url, serverSelectionTimeoutMS=8000)
    try:
        coll = client[cfg.fsm_mongo_db][domain.SA_COLLECTION]
        query = domain.completed_query(cfg.lookback_hours, processed_ids, cfg.fsm_time_field)
        cursor = (
            coll.find(query, domain.SA_PROJECTION)
            .sort(cfg.fsm_time_field, -1)
            .limit(cfg.fsm_batch_limit)
        )
        return [domain.work_order_from_sa(doc) for doc in cursor]
    finally:
        client.close()


# ======================================================================
# 2. 追踪库（幂等水位线 + 可检测性 trace）
# ======================================================================
_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_follow_up_logs (
    work_order_id  TEXT PRIMARY KEY,
    order_num      TEXT,
    city           TEXT,
    suggestion     TEXT,
    status         TEXT,
    processed_at   TEXT
)
"""

# 推理 trace 表：每次 LLM/启发式推理落一条，增强可检测性（observability）
_SCHEMA_TRACES = """
CREATE TABLE IF NOT EXISTS reasoning_traces (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id     TEXT,
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
    created_at        TEXT
)
"""


@dataclass
class ReasoningTrace:
    """一次推理的完整可追溯记录（LLM 或启发式或报错）。"""

    work_order_id: str
    mode: str                      # llm | heuristic | llm_fallback_heuristic
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
    created_at: str = ""


class TrackingStore:
    """统一追踪库接口：local=sqlite，cloud=Turso。"""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        if cfg.tracking_source == "local":
            db_path = os.path.abspath(cfg.tracking_local_path)
            self._conn = sqlite3.connect(db_path)
            self._conn.execute(_SCHEMA)
            self._conn.execute(_SCHEMA_TRACES)
            self._conn.commit()
            self._turso = None
            logger.info("追踪库 sqlite: %s", db_path)
        elif cfg.tracking_source == "cloud":
            from libsql_client import create_client_sync  # 懒加载

            self._turso = create_client_sync(url=cfg.turso_url, auth_token=cfg.turso_token)
            self._turso.execute(_SCHEMA)
            self._turso.execute(_SCHEMA_TRACES)
            self._conn = None
        else:
            raise ValueError(f"未知 TRACKING_SOURCE: {cfg.tracking_source}")

    def get_processed_work_order_ids(self) -> List[str]:
        if self._conn is not None:
            rows = self._conn.execute("SELECT work_order_id FROM ai_follow_up_logs").fetchall()
            return [r[0] for r in rows]
        res = self._turso.execute("SELECT work_order_id FROM ai_follow_up_logs")
        return [r[0] for r in res.rows]

    def mark_processed(self, wo: WorkOrder, suggestion: FollowUpSuggestion, status: str) -> None:
        now = bj_now().isoformat()
        payload = json.dumps(suggestion.to_dict(), ensure_ascii=False)
        row = (wo.work_order_id, wo.order_num, wo.city, payload, status, now)
        sql = (
            "INSERT OR REPLACE INTO ai_follow_up_logs "
            "(work_order_id, order_num, city, suggestion, status, processed_at) VALUES (?,?,?,?,?,?)"
        )
        if self._conn is not None:
            self._conn.execute(sql, row)
            self._conn.commit()
        else:
            self._turso.execute(sql, list(row))

    def log_reasoning_trace(self, t: ReasoningTrace) -> None:
        parsed = json.dumps(t.parsed, ensure_ascii=False) if t.parsed is not None else None
        row = (
            t.work_order_id, t.mode, t.model, t.prompt_system, t.prompt_user,
            t.raw_response, parsed, t.prompt_tokens, t.completion_tokens,
            t.total_tokens, t.latency_ms, t.status, t.error, t.created_at,
        )
        sql = (
            "INSERT INTO reasoning_traces "
            "(work_order_id, mode, model, prompt_system, prompt_user, raw_response, parsed, "
            "prompt_tokens, completion_tokens, total_tokens, latency_ms, status, error, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
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
        for table in ("ai_follow_up_logs", "reasoning_traces"):
            cur = self._conn.execute(f"DELETE FROM {table}")
            total += cur.rowcount
        self._conn.execute("DELETE FROM sqlite_sequence WHERE name='reasoning_traces'")
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
_SYSTEM_PROMPT = """你是家装售后服务的跟进助理。根据已完工工单的标题与备注，
判断是否需要人工跟进，并给出结构化建议。只输出 JSON，不要多余文字。
JSON 字段：
- needs_follow_up: bool        是否需要跟进
- priority: "high"|"medium"|"low"
- reason: string               一句话原因
- suggested_action: string     建议的具体动作
- customer_sentiment: "positive"|"neutral"|"negative"
"""


def _parse_llm_json(content: str) -> FollowUpSuggestion:
    text = (content or "").strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    return FollowUpSuggestion.from_dict(json.loads(text))


def reason_follow_up(cfg: Config, wo: WorkOrder) -> Tuple[Optional[FollowUpSuggestion], ReasoningTrace]:
    """对一个完工工单生成跟进建议，并返回完整推理 trace。

    返回 (suggestion, trace)：
    - LLM_PROVIDER=heuristic 或缺少 API key：走启发式。
    - hunyuan / deepseek：trace 记录 prompt / 原始返回 / token / 耗时。
    - 调用报错：suggestion=None，trace.status=error（调用方据此重试，不误记水位线）。
    """
    now = bj_now().isoformat()
    provider, api_key, base_url, model, json_mode = cfg.resolved_llm()

    if provider == "heuristic" or not api_key:
        s = _heuristic_suggestion(wo)
        trace = ReasoningTrace(
            work_order_id=wo.work_order_id, mode="heuristic", model="heuristic",
            prompt_user=wo.followup_text, raw_response=json.dumps(s.to_dict(), ensure_ascii=False),
            parsed=s.to_dict(), status="ok", created_at=now,
        )
        return s, trace

    from openai import OpenAI  # 懒加载

    user_prompt = f"工单号: {wo.order_num}\n{wo.followup_text}"
    trace = ReasoningTrace(
        work_order_id=wo.work_order_id, mode=f"llm_{provider}", model=model,
        prompt_system=_SYSTEM_PROMPT, prompt_user=user_prompt, created_at=now,
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
            "temperature": 0.2,
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
        try:
            s = _parse_llm_json(content)
        except json.JSONDecodeError:
            logger.warning("LLM 返回非法 JSON，回退启发式：%s", content[:200])
            s = _heuristic_suggestion(wo)
            trace.mode = "llm_fallback_heuristic"
        trace.parsed = s.to_dict()
        return s, trace
    except Exception as e:
        trace.latency_ms = int((time.perf_counter() - t0) * 1000)
        trace.status = "error"
        trace.error = f"{type(e).__name__}: {e}"
        return None, trace


def _heuristic_suggestion(wo: WorkOrder) -> FollowUpSuggestion:
    """无 LLM 时的确定性兜底：基于关键词的简单启发式。"""
    text = f"{wo.title} {wo.summary}"
    negative = any(k in text for k in ["不满", "担心", "投诉", "尽快", "复检", "问题", "偏低"])
    pending = any(k in text for k in ["下次", "补装", "后续", "复检", "建议"])
    no_text = not wo.summary.strip()
    return FollowUpSuggestion(
        needs_follow_up=negative or pending or no_text,
        priority="high" if negative else ("medium" if pending else "low"),
        reason=(
            "检测到客户顾虑或遗留事项" if (negative or pending)
            else ("无备注，建议回访确认满意度" if no_text else "服务正常完成")
        ),
        suggested_action=(
            "电话回访并确认遗留事项处理时间" if (negative or pending)
            else "电话回访确认客户满意度"
        ),
        customer_sentiment="negative" if negative else "neutral",
    )


# ======================================================================
# 4. 输出层（企业微信群机器人）
# ======================================================================
_PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}


def build_card_markdown(wo: WorkOrder, s: FollowUpSuggestion) -> str:
    emoji = _PRIORITY_EMOJI.get(s.priority, "⚪")
    return (
        f"### {emoji} 工单跟进建议 · {wo.city}\n"
        f"> **工单号**：{wo.order_num or wo.work_order_id}\n"
        f"> **客户**：{wo.customer_name}（{wo.phone}）\n"
        f"> **优先级**：<font color=\"warning\">{s.priority}</font>\n"
        f"> **客户情绪**：{s.customer_sentiment}\n"
        f"> **原因**：{s.reason}\n"
        f"> **建议动作**：{s.suggested_action}"
    )


def send_wecom_card(cfg: Config, markdown: str) -> bool:
    if cfg.dry_run or not cfg.wecom_webhook:
        logger.info("[企微预览] 未发送（DRY_RUN 或缺少 webhook）：\n%s", markdown)
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
    logger.info(
        "启动 agent-loop | dry_run=%s fsm=%s tracking=%s llm=%s/%s",
        cfg.dry_run, cfg.fsm_source, cfg.tracking_source, prov, model,
    )

    store = TrackingStore(cfg)
    try:
        processed_ids = set(store.get_processed_work_order_ids())
        work_orders = fetch_completed_work_orders(cfg, processed_ids)

        if not work_orders:
            logger.info("本轮无新完工工单，结束。")
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
                    "工单 %s → %s | %s %dtok %dms",
                    ref, json.dumps(suggestion.to_dict(), ensure_ascii=False),
                    trace.mode, trace.total_tokens, trace.latency_ms,
                )

                if suggestion.needs_follow_up:
                    card = build_card_markdown(wo, suggestion)
                    sent = send_wecom_card(cfg, card)
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
