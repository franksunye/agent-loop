"""LLM 推理（OpenAI 兼容）→ 领域跟进建议，含 JSON 容错与后处理抛光。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

from ..config import Config
from ..domain import FollowUpSuggestion, WorkOrder
from ..tracking.trace import ReasoningTrace
from .prompts import SYSTEM_PROMPT
from .heuristic import heuristic_suggestion

logger = logging.getLogger("aol.runtime")


def parse_llm_json(content: str) -> FollowUpSuggestion:
    text = (content or "").strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    return FollowUpSuggestion.from_dict(json.loads(text))


def llm_follow_up(
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

    trace = ReasoningTrace(
        work_order_id=wo.work_order_id, event_type=wo.event_type, mode=f"llm_{provider}",
        model=model, prompt_system=SYSTEM_PROMPT, prompt_user=user_prompt, created_at=now,
    )
    client = OpenAI(api_key=api_key, base_url=base_url)
    t0 = time.perf_counter()
    try:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
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
            s = parse_llm_json(content)
            if enrich_ctx is not None:
                from ..decision.polish import polish_suggestion

                s = polish_suggestion(wo, enrich_ctx, s)
                trace.mode = f"{trace.mode}+polish"
        except json.JSONDecodeError:
            logger.warning("LLM 返回非法 JSON，回退启发式：%s", content[:200])
            s = heuristic_suggestion(wo, enrich_ctx)
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
