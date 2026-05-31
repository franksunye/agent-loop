"""无 LLM 时的确定性兜底推理（有 enrich 时尽量填满 v0.2 结构）。"""

from __future__ import annotations

from typing import Any, Optional

from .. import domain
from ..domain import FollowUpSuggestion, WorkOrder
from ..context.enrich import EnrichedContext


def heuristic_suggestion(wo: WorkOrder, enrich_ctx: Any = None) -> FollowUpSuggestion:
    """无 LLM 时的确定性兜底；有 enrich 时尽量填满 v0.2 结构。"""
    ctx: Optional[EnrichedContext] = enrich_ctx
    text = f"{wo.title} {wo.summary}"
    negative = any(k in text for k in ["不满", "担心", "投诉", "尽快", "复检", "问题", "偏低"])
    stale = wo.stale_days >= 7
    high_part = bool(
        ctx and any("屋面" in p or "屋顶" in p for p in (ctx.leak_sites or []))
    )
    low_channel = bool(ctx and ctx.channel_label and "抖音" in ctx.channel_label)

    if ctx and ctx.has_signed_contract:
        return FollowUpSuggestion(
            needs_follow_up=False,
            priority="低",
            customer_sentiment="中性",
            reason_summary="系统查证显示已有生效签约合同，建议先核对工单状态是否未更新。",
            priority_reasons=["已有生效签约合同"],
            situation=domain.FollowUpSituation(
                stage="待签约",
                quote_status="已有生效签约",
                amount_plan="见查证",
                channel_part=ctx.channel_label or ctx.source_type_label,
            ),
            action_plan=domain.FollowUpActionPlan(
                primary_action="核对工单状态与合同是否一致",
                talk_points=["确认系统合同与工单状态为何不一致"],
                avoid=["勿重复催促已签约客户"],
            ),
            evidence_refs=(ctx.evidence_lines or [])[:5],
        )

    quote_status = "无正式报价"
    amount_plan = ""
    if ctx and ctx.has_quote and ctx.quotes:
        quote_status = "已正式报价未签约"
        q0 = ctx.quotes[0]
        amt = q0.get("amount_yuan")
        amount_plan = f"{amt:.0f}元" if isinstance(amt, (int, float)) else ""
        pkgs = "、".join((q0.get("package_names") or [])[:2])
        if pkgs:
            amount_plan += f"；{pkgs}"

    priority = "高" if (high_part or stale) else ("低" if low_channel else "中")
    if high_part and ctx and ctx.quotes:
        q0 = ctx.quotes[0]
        amt = q0.get("amount_yuan")
        amt_s = f"{amt:.0f}元" if isinstance(amt, (int, float)) else "—"
        reason_summary = (
            f"待签约停留{wo.stale_days}天，屋面类高客单，已报价{amt_s}未支付，建议优先电话推进签约。"
        )
    elif ctx and ctx.has_quote:
        reason_summary = (
            f"待签约停留{wo.stale_days}天，已正式报价未支付，建议电话确认并推进签约。"
        )
    else:
        reason_summary = f"待签约停留{wo.stale_days}天，建议确认报价与签约意向。"

    priority_reasons = [f"停留{wo.stale_days}天"]
    if amount_plan:
        priority_reasons.append(f"报价情况：{amount_plan}")
    if high_part:
        priority_reasons.append("屋面/屋顶部位，客单价通常较高")
    if low_channel:
        priority_reasons.append("抖音渠道，建议先核实意向再重投入")
    if ctx and ctx.business_hints:
        priority_reasons.extend(ctx.business_hints[:1])

    talk_points = [
        "确认客户是否已看清正式报价与方案范围",
        "了解是否在比价、装修进度或付款安排上存在障碍",
    ]
    if amount_plan:
        talk_points.insert(0, f"围绕查证中的报价（{amount_plan.split('；')[0]}）确认认可度")

    return FollowUpSuggestion(
        needs_follow_up=True,
        priority=priority,
        customer_sentiment="消极" if negative else "中性",
        reason_summary=reason_summary,
        priority_reasons=priority_reasons[:4],
        situation=domain.FollowUpSituation(
            stage="待签约",
            quote_status=quote_status,
            amount_plan=amount_plan or "查证无报价",
            channel_part=(
                f"{(ctx.channel_label or ctx.source_type_label) if ctx else ''}；"
                f"{'、'.join(ctx.leak_sites) if ctx and ctx.leak_sites else ''}"
            ).strip("；"),
        ),
        action_plan=domain.FollowUpActionPlan(
            primary_action="电话确认报价并推进签约",
            talk_points=talk_points[:4],
            avoid=["勿承诺查证未出现的折扣、工期或增项"],
        ),
        evidence_refs=(ctx.evidence_lines[:5] if ctx else []),
    )
