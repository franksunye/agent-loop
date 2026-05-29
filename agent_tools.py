"""Agent 只读工具（展示轨 / v0.2.x）。

纪律：本模块仅只读 Mongo；不写 XLink。详见 docs/10-agent-steps-demo.md。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agent_cron_engine import Config
    from domain import WorkOrder

logger = logging.getLogger("agent-loop.tools")


@dataclass
class EnrichedContext:
    """enrich_work_order_context 的结构化返回（供 LLM 与 trace 使用）。"""

    work_order_id: str
    has_quote: Optional[bool] = None
    quote_count: int = 0
    has_signed_contract: Optional[bool] = None
    workflow_snippet: str = ""
    tool_notes: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_prompt_block(self) -> str:
        lines = ["【系统只读查询结果（请据此写 reason，勿编造）】"]
        if self.has_quote is not None:
            lines.append(f"- 是否已有报价：{'是' if self.has_quote else '否'}（{self.quote_count} 条）")
        if self.has_signed_contract is not None:
            lines.append(f"- 是否已有签约合同：{'是' if self.has_signed_contract else '否'}")
        if self.workflow_snippet:
            lines.append(f"- 流程摘要：{self.workflow_snippet}")
        for n in self.tool_notes:
            lines.append(f"- 备注：{n}")
        return "\n".join(lines)

    def to_step_dict(self) -> Dict[str, Any]:
        return {
            "tool": "enrich_work_order_context",
            "work_order_id": self.work_order_id,
            "has_quote": self.has_quote,
            "quote_count": self.quote_count,
            "has_signed_contract": self.has_signed_contract,
            "workflow_snippet": self.workflow_snippet,
            "tool_notes": self.tool_notes,
        }


def enrich_work_order_context(cfg: "Config", wo: "WorkOrder") -> EnrichedContext:
    """只读 enrich：报价 / 合同 /（可选）流程。

    v0.2.x 骨架：mongo 可用时仍返回占位，避免演示轨误报；
    实现见 docs/10 与后续 PR。
    """
    ctx = EnrichedContext(work_order_id=wo.work_order_id)
    if cfg.fsm_source != "mongo" or not cfg.fsm_mongo_url:
        ctx.tool_notes.append("enrich 跳过：FSM_SOURCE 非 mongo")
        return ctx

    try:
        from pymongo import MongoClient

        client = MongoClient(cfg.fsm_mongo_url, serverSelectionTimeoutMS=8000)
        db = client[cfg.fsm_mongo_db]
        sa_id = wo.work_order_id

        # 报价：order 上关联 serviceAppointment（字段名以实库为准，v0.2.x 校准）
        quote_filter: Dict[str, Any] = {"state": {"$ne": -1}}
        if sa_id:
            quote_filter["$or"] = [
                {"serviceAppointmentId": sa_id},
                {"serviceAppointmentIds": sa_id},
            ]
        quote_count = db["order"].count_documents(quote_filter)
        ctx.quote_count = quote_count
        ctx.has_quote = quote_count > 0

        # 合同：按工单 id（Contract.serviceAppointmentId）
        contract_filter: Dict[str, Any] = {
            "state": 1,
            "exts.contractStatus": "10",
            "serviceAppointmentId": sa_id,
        }
        signed_n = db["contract"].count_documents(contract_filter)
        ctx.has_signed_contract = signed_n > 0
        ctx.raw = {
            "quote_count": quote_count,
            "signed_contract_count": signed_n,
        }

        client.close()
    except Exception as e:
        logger.warning("enrich 失败: %s", e)
        ctx.tool_notes.append(f"enrich 异常: {type(e).__name__}: {e}")

    return ctx
