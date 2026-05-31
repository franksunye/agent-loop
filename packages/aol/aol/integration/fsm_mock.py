"""离线 mock 事件源（CI / dry-run）：复用 domain 的固定夹具。"""

from __future__ import annotations

import os
from typing import List

from .. import domain
from ..domain import WorkOrder


def fetch_mock(processed_keys: set[str]) -> List[WorkOrder]:
    raw = os.getenv("FSM_EVENT_STATUSES", "").strip()
    if raw:
        statuses = [s.strip() for s in raw.split(",") if s.strip()]
        if any(s in ("206", "204", "205") for s in statuses):
            return domain.mock_follow_up_work_orders(
                list(processed_keys), event_statuses=statuses
            )
    return domain.mock_completed_work_orders(list(processed_keys))
