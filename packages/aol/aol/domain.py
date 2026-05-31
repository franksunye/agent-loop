"""领域语义层 / XLink 防腐层（Anti-Corruption Layer）。

本模块是 fs-aol 引擎里**唯一**允许出现 XLink 系统语义（集合名、`status` 码、
区划码、`state`、`exts` 路径等）的地方。其余所有代码只说领域语言。

词汇真源对齐 `business_3_0/docs/12-domain-glossary.md`（领域 SSOT，FSL 对齐），
码表口径对齐 `business_3_0/web/lib/sa-list-display-map.ts` / `cloud-code-labels.ts`。

> 设计见 docs/04-domain-semantics.md。
> 纪律：要改 XLink 字段/码值的翻译，只改这一个文件；新增领域概念先在上游词汇表立项。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# XLink 库内时间为北京本地时间（无时区）；Runner 多为 UTC，必须显式校正。
_BJ_TZ = timezone(timedelta(hours=8))

ACTION_SPEC_VERSION = "v0.2"


def bj_now() -> datetime:
    return datetime.now(_BJ_TZ).replace(tzinfo=None)


# ======================================================================
# 系统语义常量与码表（仅本层可见）
# ======================================================================
SYSTEM_NAME = "xlink"
SA_COLLECTION = "serviceAppointment"

COMPLETED_STATUS = "403"
STATE_ACTIVE = 1

_STATUS_TO_TASK_TYPE: Dict[str, str] = {
    "101": "待接单", "102": "待接单", "103": "待接单",
    "104": "联系客户", "105": "预约上门",
    "200": "暂不上门", "201": "暂不上门", "202": "上门服务",
    "203": "待下单", "204": "上门跟进", "205": "跟进方案",
    "206": "跟进签约", "207": "待确认",
    "300": "现场服务", "301": "现场服务", "302": "现场服务",
    "401": "验收回款", "402": "验收回款", "403": "已完工", "407": "验收回款",
    "501": "待评价", "502": "待评价", "999": "跟进超时",
}

_STATUS_TO_GROUP: Dict[str, str] = {
    "101": "to_accept", "102": "to_accept", "103": "to_accept",
    "104": "need_contact", "105": "onsite", "202": "onsite",
}

_CITY_CODE_MAP: Dict[str, str] = {
    "110100": "北京", "120100": "天津", "310100": "上海", "440100": "广州",
    "440300": "深圳", "330100": "杭州", "510100": "成都", "320100": "南京",
    "420100": "武汉", "610100": "西安",
}


def _task_type(status: str) -> str:
    return _STATUS_TO_TASK_TYPE.get(str(status), f"状态{status}")


def _group(status: str) -> str:
    return _STATUS_TO_GROUP.get(str(status), "following")


def _city_name(code: Any) -> str:
    return _CITY_CODE_MAP.get(str(code), str(code) or "未知")


# ======================================================================
# 领域模型（Domain Models）
# ======================================================================
@dataclass
class WorkOrder:
    """工单领域读模型（glossary §1.1 / §3）。"""

    work_order_id: str
    order_num: str = ""
    title: str = ""
    task_type: str = ""
    group: str = "following"
    city: str = ""
    customer_name: str = ""
    phone: str = ""
    assignee: str = ""
    summary: str = ""
    completed_at: str = ""
    event_type: str = ""
    stale_days: int = 0
    housekeeper_id: str = ""
    housekeeper_name: str = ""
    source_ref: Dict[str, str] = field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        return self.task_type == "已完工"

    @property
    def dedupe_key(self) -> str:
        et = self.event_type or "UNKNOWN"
        return f"{et}:{self.work_order_id}"

    @property
    def followup_text(self) -> str:
        parts = [
            f"工单号：{self.order_num or self.work_order_id}",
            f"当前状态：{self.task_type}",
        ]
        if self.stale_days > 0:
            parts.append(f"已停留：{self.stale_days} 天")
        if self.event_type:
            parts.append(f"跟进事件：{event_type_label(self.event_type)}")
        parts.append(f"工单标题：{self.title or '(无)'}")
        if self.summary:
            parts.append(f"备注：{self.summary}")
        parts.append(f"城市：{self.city}")
        if self.housekeeper_name:
            parts.append(f"归属管家：{self.housekeeper_name}")
        return "\n".join(parts)


# LLM / 展示：中文优先
_PRIORITY_CN = {"high": "高", "medium": "中", "low": "低", "高": "高", "中": "中", "低": "低"}
_SENTIMENT_CN = {
    "positive": "积极", "neutral": "中性", "negative": "消极",
    "积极": "积极", "中性": "中性", "消极": "消极",
}


def _norm_priority(val: Any) -> str:
    key = str(val or "低").strip().lower()
    return _PRIORITY_CN.get(key, str(val or "低"))


def _norm_sentiment(val: Any) -> str:
    key = str(val or "中性").strip().lower()
    return _SENTIMENT_CN.get(key, str(val or "中性"))


def _pick(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d:
            return d[k]
    return default


def _as_str_list(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    s = str(val).strip()
    return [s] if s else []


@dataclass
class FollowUpSituation:
    """对系统查证的归纳（不得新增事实）。"""

    stage: str = ""
    quote_status: str = ""
    amount_plan: str = ""
    channel_part: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "商机阶段": self.stage,
            "报价状态": self.quote_status,
            "金额与方案": self.amount_plan,
            "渠道与部位": self.channel_part,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "FollowUpSituation":
        if not isinstance(d, dict):
            return cls()
        return cls(
            stage=str(_pick(d, "商机阶段", "stage", default="") or ""),
            quote_status=str(_pick(d, "报价状态", "quote_status", default="") or ""),
            amount_plan=str(_pick(d, "金额与方案", "金额与方案摘要", "amount_plan", default="") or ""),
            channel_part=str(_pick(d, "渠道与部位", "channel_part", default="") or ""),
        )


@dataclass
class FollowUpActionPlan:
    """可执行的跟进方案。"""

    primary_action: str = ""
    talk_points: List[str] = field(default_factory=list)
    avoid: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "主行动": self.primary_action,
            "沟通要点": self.talk_points,
            "避免事项": self.avoid,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "FollowUpActionPlan":
        if not isinstance(d, dict):
            primary = str(d or "") if d else ""
            return cls(primary_action=primary)
        return cls(
            primary_action=str(_pick(d, "主行动", "primary_action", "建议动作", default="") or ""),
            talk_points=_as_str_list(_pick(d, "沟通要点", "talk_points", default=[])),
            avoid=_as_str_list(_pick(d, "避免事项", "avoid", default=[])),
        )


@dataclass
class FollowUpSuggestion:
    """跟进建议 / Action Spec v0.2（docs/13-action-spec-v02.md）。"""

    spec_version: str = ACTION_SPEC_VERSION
    needs_follow_up: bool = False
    priority: str = "低"
    customer_sentiment: str = "中性"
    reason_summary: str = ""
    priority_reasons: List[str] = field(default_factory=list)
    situation: FollowUpSituation = field(default_factory=FollowUpSituation)
    action_plan: FollowUpActionPlan = field(default_factory=FollowUpActionPlan)
    evidence_refs: List[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        return self.reason_summary

    @property
    def suggested_action(self) -> str:
        return self.action_plan.primary_action

    def to_display_dict(self) -> Dict[str, Any]:
        return {
            "规格版本": self.spec_version,
            "需要跟进": self.needs_follow_up,
            "优先级": self.priority,
            "客户情绪": self.customer_sentiment,
            "原因摘要": self.reason_summary,
            "优先级依据": self.priority_reasons,
            "情况判断": self.situation.to_dict(),
            "跟进方案": self.action_plan.to_dict(),
            "引用查证": self.evidence_refs,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.to_display_dict()

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FollowUpSuggestion":
        defaults = cls()
        plan_raw = _pick(d, "跟进方案", "action_plan", default=None)
        if plan_raw is None:
            legacy_action = _pick(d, "建议动作", "suggested_action", default="")
            plan_raw = {"主行动": legacy_action} if legacy_action else {}

        situation_raw = _pick(d, "情况判断", "situation", default={})

        reason_summary = str(
            _pick(d, "原因摘要", "原因", "reason", default=defaults.reason_summary) or ""
        )

        return cls(
            spec_version=str(_pick(d, "规格版本", "spec_version", default=ACTION_SPEC_VERSION) or ACTION_SPEC_VERSION),
            needs_follow_up=bool(_pick(d, "需要跟进", "needs_follow_up", default=defaults.needs_follow_up)),
            priority=_norm_priority(_pick(d, "优先级", "priority", default=defaults.priority)),
            customer_sentiment=_norm_sentiment(
                _pick(d, "客户情绪", "customer_sentiment", default=defaults.customer_sentiment)
            ),
            reason_summary=reason_summary,
            priority_reasons=_as_str_list(_pick(d, "优先级依据", "priority_reasons", default=[])),
            situation=FollowUpSituation.from_dict(situation_raw),
            action_plan=FollowUpActionPlan.from_dict(plan_raw),
            evidence_refs=_as_str_list(_pick(d, "引用查证", "evidence_refs", default=[])),
        )


# ======================================================================
# 翻译：serviceAppointment(系统) → WorkOrder(领域)
# ======================================================================
def work_order_from_sa(doc: Dict[str, Any]) -> WorkOrder:
    status = str(doc.get("status", ""))
    wid = str(doc.get("_id", "") or doc.get("id", ""))
    exts = doc.get("exts") or {}
    return WorkOrder(
        work_order_id=wid,
        order_num=doc.get("orderNum", "") or "",
        title=doc.get("title", "") or "",
        task_type=_task_type(status),
        group=_group(status),
        city=_city_name(doc.get("city")),
        customer_name=doc.get("name", "") or "",
        phone=doc.get("phone", "") or "",
        assignee=doc.get("assignee", "") or "",
        summary=doc.get("describe", "") or "",
        completed_at=str(doc.get("updateTime", "") or doc.get("createTime", "")),
        event_type=event_type_for_status(status),
        housekeeper_id=str(exts.get("supervisorId", "") or ""),
        source_ref={"system": SYSTEM_NAME, "collection": SA_COLLECTION, "id": wid},
    )


def completed_query(
    lookback_hours: int,
    processed_ids: List[str],
    time_field: str = "updateTime",
) -> Dict[str, Any]:
    """构造「新完工 + 未处理」工单条件（v0.1 兼容）。"""
    return follow_up_events_query(
        event_statuses=[COMPLETED_STATUS],
        stale_days=0,
        lookback_hours=lookback_hours,
        processed_ids=processed_ids,
        time_field=time_field,
    )


# v0.2 Follow-up wedge（docs/08-follow-up-wedge-spec.md）
EVENT_STALE_SIGN_PENDING = "STALE_SIGN_PENDING"
EVENT_STALE_VISIT_NO_DEAL = "STALE_VISIT_NO_DEAL"
EVENT_PAYMENT_PENDING = "PAYMENT_PENDING"
EVENT_COMPLETED_CARE = "COMPLETED_CARE"

EVENT_TYPE_LABELS: Dict[str, str] = {
    EVENT_STALE_SIGN_PENDING: "待签约停滞",
    EVENT_STALE_VISIT_NO_DEAL: "上门未成交停滞",
    EVENT_PAYMENT_PENDING: "待支付停滞",
    EVENT_COMPLETED_CARE: "完工关怀",
}


def event_type_label(event_type: str) -> str:
    return EVENT_TYPE_LABELS.get(event_type or "", event_type or "跟进事件")


_STATUS_FOR_EVENT: Dict[str, str] = {
    "206": EVENT_STALE_SIGN_PENDING,
    "204": EVENT_STALE_VISIT_NO_DEAL,
    "205": EVENT_PAYMENT_PENDING,
    "403": EVENT_COMPLETED_CARE,
}

P0_FOLLOW_UP_STATUSES = ("206",)
P1_FOLLOW_UP_STATUSES = ("205", "403")


def event_type_for_status(status: str) -> str:
    return _STATUS_FOR_EVENT.get(str(status), f"STATUS_{status}")


def follow_up_events_query(
    *,
    event_statuses: List[str],
    stale_days: int = 0,
    max_age_days: int = 0,
    lookback_hours: int = 0,
    processed_ids: Optional[List[str]] = None,
    supervisor_ids: Optional[List[str]] = None,
    time_field: str = "updateTime",
) -> Dict[str, Any]:
    """follow-up 事件 Mongo 条件。"""
    q: Dict[str, Any] = {"status": {"$in": list(event_statuses)}, "state": STATE_ACTIVE}
    time_q: Dict[str, Any] = {}
    if max_age_days and max_age_days > 0:
        time_q["$gte"] = bj_now() - timedelta(days=max_age_days)
    if stale_days and stale_days > 0:
        time_q["$lt"] = bj_now() - timedelta(days=stale_days)
    if time_q:
        q[time_field] = time_q
    elif lookback_hours and lookback_hours > 0:
        since = bj_now() - timedelta(hours=lookback_hours)
        q[time_field] = {"$gte": since}
    if supervisor_ids:
        q["exts.supervisorId"] = {"$in": list(supervisor_ids)}
    if processed_ids:
        q["_id"] = {"$nin": list(processed_ids)}
    return q


SA_PROJECTION = {
    "_id": 1, "orderNum": 1, "city": 1, "serviceType": 1,
    "title": 1, "describe": 1, "name": 1, "phone": 1, "assignee": 1,
    "status": 1, "updateTime": 1, "createTime": 1, "exts": 1,
}


MOCK_SA_RECORDS: List[Dict[str, Any]] = [
    {
        "_id": "SA-MOCK-001", "orderNum": "GD20260529001", "status": "403", "state": 1,
        "city": "110100", "serviceType": "40", "title": "王先生的工单",
        "describe": "更换厨房龙头已完成，客户反馈水压偏低，建议后续检查总阀。",
        "name": "王先生", "phone": "138****1234", "updateTime": bj_now().isoformat(),
    },
    {
        "_id": "SA-MOCK-002", "orderNum": "GD20260529002", "status": "403", "state": 1,
        "city": "310100", "serviceType": "11", "title": "李女士的工单",
        "describe": "安装智能门锁完成，客户担心电池续航，问能否上门复检。",
        "name": "李女士", "phone": "139****5678", "updateTime": bj_now().isoformat(),
    },
    {
        "_id": "SA-MOCK-003", "orderNum": "GD20260529003", "status": "403", "state": 1,
        "city": "110100", "serviceType": "40", "title": "张先生的工单",
        "describe": "",
        "name": "张先生", "phone": "137****9012", "updateTime": bj_now().isoformat(),
    },
]


def mock_completed_work_orders(processed_keys: List[str]) -> List[WorkOrder]:
    processed = set(processed_keys)
    out: List[WorkOrder] = []
    for d in MOCK_SA_RECORDS:
        if d.get("status") != COMPLETED_STATUS:
            continue
        wo = work_order_from_sa(d)
        if wo.dedupe_key not in processed:
            out.append(wo)
    return out
