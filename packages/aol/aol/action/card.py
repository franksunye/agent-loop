"""输出层：把跟进建议渲染为企业微信 markdown 卡片。"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional
from urllib.parse import quote

from .. import domain
from ..domain import FollowUpSuggestion, WorkOrder
from ..blocker_types import BLOCKER_LABELS
from ..tracking.store import BlockerFeedback
from ..tracking.trace import ReasoningTrace

_PRIORITY_EMOJI = {"高": "🔴", "中": "🟡", "低": "🟢", "high": "🔴", "medium": "🟡", "low": "🟢"}


def enrich_output_from_trace(trace: ReasoningTrace) -> Optional[Dict[str, Any]]:
    if not trace.steps_json:
        return None
    try:
        steps = json.loads(trace.steps_json)
    except json.JSONDecodeError:
        return None
    for st in steps:
        if st.get("name") == "enrich_work_order_context":
            out = st.get("output")
            return out if isinstance(out, dict) else None
    return None


def _truncate(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _blocker_line(blocker: Optional[BlockerFeedback]) -> str:
    if blocker and blocker.blocker_type and blocker.blocker_type != "UNKNOWN":
        label = BLOCKER_LABELS.get(blocker.blocker_type, blocker.blocker_type)
        note = f" — {_truncate(blocker.note, 24)}" if blocker.note else ""
        return f"> **阻塞信息**：{label}{note}\n"
    return "> **阻塞信息**：待采集\n"


def _console_link(base_url: str, dedupe_key: str) -> str:
    if not base_url:
        return ""
    path = quote(dedupe_key, safe="")
    return f"{base_url.rstrip('/')}/suggestions/{path}"


def _build_compact_card(
    wo: WorkOrder,
    s: FollowUpSuggestion,
    *,
    dedupe_key: Optional[str],
    console_base_url: str,
    blocker: Optional[BlockerFeedback],
) -> str:
    """移动端 action 通知卡：把人拉回 Console，详情在处置页。"""
    emoji = _PRIORITY_EMOJI.get(s.priority, "⚪")
    customer = wo.customer_name or "客户"
    ref = wo.order_num or wo.work_order_id
    event = domain.event_type_label(wo.event_type)
    city = wo.city or "—"
    stale = f" · 停留 {wo.stale_days} 天" if wo.stale_days else ""
    action = _truncate(s.action_plan.primary_action or s.reason_summary or "查看处置页", 56)
    link = _console_link(console_base_url, dedupe_key or wo.dedupe_key)
    footer = f"\n> [打开处置页]({link})\n" if link else ""

    return (
        f"### {emoji} 跟进行动 · {customer}\n"
        f"> {event} · {city}{stale}\n"
        f"> 工单 `{ref}`\n"
        f"> **现在做什么**：{action}\n"
        f"{_blocker_line(blocker)}"
        f"{footer}"
    )


def _build_verbose_card(
    wo: WorkOrder,
    s: FollowUpSuggestion,
    *,
    enrich_output: Optional[Dict[str, Any]],
    dedupe_key: Optional[str],
    console_base_url: str,
    blocker: Optional[BlockerFeedback],
) -> str:
    """完整预览卡：DRY_RUN / 内审用，不用于管家移动端通知。"""
    emoji = _PRIORITY_EMOJI.get(s.priority, "⚪")
    hk = wo.housekeeper_name or "未分配管家"
    stale_line = f"> **停留**：{wo.stale_days} 天\n" if wo.stale_days else ""
    verdict = (enrich_output or {}).get("business_verdict") or ""
    enrich_line = f"> **结论**：{verdict}\n" if verdict else ""
    evidence = (enrich_output or {}).get("evidence_lines") or []
    if not evidence and s.evidence_refs:
        evidence = s.evidence_refs
    evidence_block = "".join(f"> - {line}\n" for line in evidence[:4])

    basis_block = "".join(f"> - {x}\n" for x in (s.priority_reasons or [])[:4])
    talk_block = "".join(
        f"> {i + 1}. {p}\n" for i, p in enumerate((s.action_plan.talk_points or [])[:4])
    )
    avoid_block = ""
    if s.action_plan.avoid:
        avoid_block = "> **避免**：" + "；".join(s.action_plan.avoid[:2]) + "\n"

    sit = s.situation
    situation_line = ""
    if sit.quote_status or sit.amount_plan:
        situation_line = (
            f"> **情况**：{sit.quote_status}"
            + (f" · {sit.amount_plan}" if sit.amount_plan else "")
            + "\n"
        )

    link = _console_link(console_base_url, dedupe_key or wo.dedupe_key)
    footer = f"\n> [打开 Console 处置]({link})\n" if link else ""

    return (
        f"### {emoji} 跟进行动 · {wo.city}\n"
        f"> **管家**：{hk}\n"
        f"> **工单号**：{wo.order_num or wo.work_order_id}\n"
        f"> **状态**：{wo.task_type}\n"
        f"{stale_line}"
        f"> **事件**：{domain.event_type_label(wo.event_type)}\n"
        f"{enrich_line}"
        f"{evidence_block}"
        f"{_blocker_line(blocker)}"
        f"> **客户**：{wo.customer_name}（{wo.phone}）\n"
        f"> **优先级**：<font color=\"warning\">{s.priority}</font>\n"
        f"> **客户情绪**：{s.customer_sentiment}\n"
        f"{situation_line}"
        f"> **原因摘要**：{s.reason_summary}\n"
        f"> **主行动**：{s.action_plan.primary_action}\n"
        f"{basis_block}"
        f"> **沟通要点**：\n{talk_block}"
        f"{avoid_block}"
        f"{footer}"
    )


def build_card_markdown(
    wo: WorkOrder,
    s: FollowUpSuggestion,
    *,
    enrich_output: Optional[Dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
    console_base_url: str = "",
    blocker: Optional[BlockerFeedback] = None,
    compact: bool = True,
) -> str:
    """渲染企微 markdown。默认 compact=True（移动端 action 通知）；内审可 compact=False。"""
    if compact:
        return _build_compact_card(
            wo,
            s,
            dedupe_key=dedupe_key,
            console_base_url=console_base_url,
            blocker=blocker,
        )
    return _build_verbose_card(
        wo,
        s,
        enrich_output=enrich_output,
        dedupe_key=dedupe_key,
        console_base_url=console_base_url,
        blocker=blocker,
    )
