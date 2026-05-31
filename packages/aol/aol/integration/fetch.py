"""事件摄取分发：根据 FSM_SOURCE 选择 mock / mongo。"""

from __future__ import annotations

import logging
from typing import List

from ..config import Config
from ..domain import WorkOrder
from .fsm_mock import fetch_mock
from .fsm_mongo import fetch_from_mongo

logger = logging.getLogger("aol.integration")


def fetch_completed_work_orders(cfg: Config, processed_keys: set[str]) -> List[WorkOrder]:
    """捞取 follow-up 事件候选工单（v0.2：按 dedupe_key 去重）。"""
    if cfg.fsm_source == "mock":
        work_orders = fetch_mock(processed_keys)
    elif cfg.fsm_source == "mongo":
        work_orders = fetch_from_mongo(cfg, processed_keys)
    else:
        raise ValueError(f"未知 FSM_SOURCE: {cfg.fsm_source}")

    logger.info("捞取到 %d 条待跟进（已处理 %d 个 dedupe_key）", len(work_orders), len(processed_keys))
    return work_orders
