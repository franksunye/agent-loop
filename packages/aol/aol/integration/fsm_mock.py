"""离线 mock 事件源（CI / dry-run）：复用 domain 的固定夹具。"""

from __future__ import annotations

from typing import List

from .. import domain
from ..domain import WorkOrder


def fetch_mock(processed_keys: set[str]) -> List[WorkOrder]:
    return domain.mock_completed_work_orders(list(processed_keys))
