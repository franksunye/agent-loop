"""推理可追溯记录（observability）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


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
