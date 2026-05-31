"""推理编排：oneshot（单次）与 steps（enrich + LLM 展示轨）。"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from ..config import Config
from ..domain import FollowUpSuggestion, WorkOrder, bj_now
from ..tracking.trace import ReasoningTrace
from ..context.enrich import enrich_work_order_context
from .heuristic import heuristic_suggestion
from .llm import llm_follow_up


def reason_follow_up(cfg: Config, wo: WorkOrder) -> Tuple[Optional[FollowUpSuggestion], ReasoningTrace]:
    """对一个工单生成跟进建议，并返回完整推理 trace。"""
    if cfg.agent_mode == "steps":
        return reason_follow_up_steps(cfg, wo)
    return reason_follow_up_oneshot(cfg, wo)


def reason_follow_up_steps(cfg: Config, wo: WorkOrder) -> Tuple[Optional[FollowUpSuggestion], ReasoningTrace]:
    """展示轨：enrich（tool）→ LLM，步骤写入 trace.steps_json。"""
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
        s = heuristic_suggestion(wo, enrich_ctx)
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

    suggestion, trace = llm_follow_up(
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


def reason_follow_up_oneshot(cfg: Config, wo: WorkOrder) -> Tuple[Optional[FollowUpSuggestion], ReasoningTrace]:
    """默认试点：单次 LLM / 启发式。"""
    now = bj_now().isoformat()
    provider, api_key, base_url, model, json_mode = cfg.resolved_llm()

    if provider == "heuristic" or not api_key:
        s = heuristic_suggestion(wo, None)
        trace = ReasoningTrace(
            work_order_id=wo.work_order_id, event_type=wo.event_type, mode="heuristic",
            model="heuristic", prompt_user=wo.followup_text,
            raw_response=json.dumps(s.to_display_dict(), ensure_ascii=False),
            parsed=s.to_display_dict(), status="ok", created_at=now,
        )
        return s, trace

    user_prompt = f"工单号: {wo.order_num}\n{wo.followup_text}"
    return llm_follow_up(
        cfg, wo, provider, api_key, base_url, model, json_mode, user_prompt, now,
        enrich_ctx=None,
    )
