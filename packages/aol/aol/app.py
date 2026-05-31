"""Agent-Loop 主编排：DB 增量轮询 → 推理 → 追踪库 → 企微推送。

链路：GitHub Actions Cron → 增量捞取候选工单 → 推理生成跟进建议
     → 写入追踪库（幂等水位线）→ 企业微信群机器人推送。

领域语义纪律（见 docs/04-domain-semantics.md）：系统码翻译全部收拢在 domain.py（防腐层），
本编排层只说领域语言（WorkOrder / 跟进建议）。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Optional

# ---- 可选依赖：缺失时不影响 dry-run + mock + local 链路 ----
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv 是可选的
    pass

from . import domain
from .config import Config
from .util import env_bool
from .integration.fetch import fetch_completed_work_orders
from .integration.fsm_mongo import resolve_event_statuses
from .tracking.store import TrackingStore
from .runtime.reasoner import reason_follow_up
from .action.card import build_card_markdown, enrich_output_from_trace
from .action.wecom import send_wecom_card

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("agent-loop")


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


def run(cfg: Optional[Config] = None) -> int:
    cfg = cfg or Config()
    prov, _, _, model, _ = cfg.resolved_llm()
    statuses = resolve_event_statuses(cfg)
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
                        enrich_output_from_trace(trace)
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
    if args.reset_tracking or env_bool("TRACKING_RESET"):
        reset_tracking(cfg)
    return run(cfg)


if __name__ == "__main__":
    sys.exit(main())
