"""阻塞类型口径（ADR-011）。"""

from __future__ import annotations

from typing import Dict, Optional

BLOCKER_LABELS: Dict[str, str] = {
    "UNKNOWN": "未知",
    "PRICE_OBJECTION": "价格异议",
    "TIMING_NOT_READY": "时机未到",
    "SOLUTION_CONCERN": "方案疑虑",
    "NO_RESPONSE": "无响应",
}

CHOICE_TO_BLOCKER: Dict[str, str] = {
    "A": "PRICE_OBJECTION",
    "B": "TIMING_NOT_READY",
    "C": "SOLUTION_CONCERN",
    "D": "NO_RESPONSE",
}

VALID_BLOCKER_TYPES = frozenset(BLOCKER_LABELS.keys())


def blocker_label(blocker_type: Optional[str]) -> str:
    if not blocker_type or blocker_type == "UNKNOWN":
        return "待采集"
    return BLOCKER_LABELS.get(blocker_type, blocker_type)
