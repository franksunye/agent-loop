"""领域语义层 / XLink 防腐层（Anti-Corruption Layer）。

本模块是 agent-loop 里**唯一**允许出现 XLink 系统语义（集合名、`status` 码、
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


def bj_now() -> datetime:
    return datetime.now(_BJ_TZ).replace(tzinfo=None)


# ======================================================================
# 系统语义常量与码表（仅本层可见）
# ======================================================================
SYSTEM_NAME = "xlink"
SA_COLLECTION = "serviceAppointment"

# 工单已完工：XLink status 码（小程序菜单「已完工」=status=403）
COMPLETED_STATUS = "403"
# 有效数据状态：1=有效，-1=作废
STATE_ACTIVE = 1

# status 码 → 领域任务类型 taskType（对齐 sa-list-display-map.STATUS_TO_TASK_TYPE）
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

# status 码 → 领域队列桶 group（对齐 sa-list-display-map.STATUS_TO_GROUP）
_STATUS_TO_GROUP: Dict[str, str] = {
    "101": "to_accept", "102": "to_accept", "103": "to_accept",
    "104": "need_contact", "105": "onsite", "202": "onsite",
}  # 其余默认 following

# 行政区划码 → 城市名（展示用，未命中回退原码）
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
# 领域模型（Domain Models）— 引擎其余部分只认这些
# ======================================================================
@dataclass
class WorkOrder:
    """工单领域读模型（glossary §1.1 / §3）。

    顶层字段为领域语言；不暴露任何 XLink 系统码。`work_order_id` 用于跨边界引用与去重。
    """

    work_order_id: str
    order_num: str = ""
    title: str = ""
    task_type: str = ""          # 领域任务类型，如「已完工」
    group: str = "following"     # 队列桶
    city: str = ""               # 城市名（已翻译）
    customer_name: str = ""      # 过渡展示，终局对齐 Account/Contact
    phone: str = ""
    assignee: str = ""           # 过渡展示，终局对齐 ServiceResource
    summary: str = ""            # 工单备注/描述（跟进文本来源；对齐 context/activity 正文）
    completed_at: str = ""
    event_type: str = ""         # v0.2：follow-up 事件类型
    stale_days: int = 0          # v0.2：在当前 status 停留天数
    housekeeper_id: str = ""     # v0.2：exts.supervisorId
    source_ref: Dict[str, str] = field(default_factory=dict)  # 溯源：{system, collection, id}

    @property
    def is_completed(self) -> bool:
        return self.task_type == "已完工"

    @property
    def followup_text(self) -> str:
        parts = [f"工单标题：{self.title or '(无)'}"]
        if self.summary:
            parts.append(f"备注：{self.summary}")
        parts.append(f"城市：{self.city}")
        return "\n".join(parts)


@dataclass
class FollowUpSuggestion:
    """跟进建议 / Action Spec 雏形（glossary：被采纳后即一条 WorkOrderActivity）。

    全部领域语言；未来演进为强类型 Action Spec 协议，引用领域 id。
    """

    needs_follow_up: bool = False
    priority: str = "low"                  # high | medium | low
    reason: str = ""
    suggested_action: str = ""
    customer_sentiment: str = "neutral"    # positive | neutral | negative

    def to_dict(self) -> Dict[str, Any]:
        return {
            "needs_follow_up": self.needs_follow_up,
            "priority": self.priority,
            "reason": self.reason,
            "suggested_action": self.suggested_action,
            "customer_sentiment": self.customer_sentiment,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FollowUpSuggestion":
        defaults = cls()
        return cls(
            needs_follow_up=bool(d.get("needs_follow_up", defaults.needs_follow_up)),
            priority=str(d.get("priority", defaults.priority)),
            reason=str(d.get("reason", defaults.reason)),
            suggested_action=str(d.get("suggested_action", defaults.suggested_action)),
            customer_sentiment=str(d.get("customer_sentiment", defaults.customer_sentiment)),
        )


# ======================================================================
# 翻译：serviceAppointment(系统) → WorkOrder(领域)
# ======================================================================
def work_order_from_sa(doc: Dict[str, Any]) -> WorkOrder:
    """把一条原始 serviceAppointment 文档翻译为领域 WorkOrder。"""
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


# ======================================================================
# 系统查询构造（已完工工单的增量捞取条件，仅本层知道码值）
# ======================================================================
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

_STATUS_FOR_EVENT: Dict[str, str] = {
    "206": EVENT_STALE_SIGN_PENDING,
    "204": EVENT_STALE_VISIT_NO_DEAL,
    "205": EVENT_PAYMENT_PENDING,
    "403": EVENT_COMPLETED_CARE,
}

P0_FOLLOW_UP_STATUSES = ("206", "204")
P1_FOLLOW_UP_STATUSES = ("205", "403")


def event_type_for_status(status: str) -> str:
    return _STATUS_FOR_EVENT.get(str(status), f"STATUS_{status}")


def follow_up_events_query(
    *,
    event_statuses: List[str],
    stale_days: int = 0,
    lookback_hours: int = 0,
    processed_ids: Optional[List[str]] = None,
    time_field: str = "updateTime",
) -> Dict[str, Any]:
    """follow-up 事件 Mongo 条件：停滞（stale_days）或增量（lookback_hours）。"""
    q: Dict[str, Any] = {"status": {"$in": list(event_statuses)}, "state": STATE_ACTIVE}
    if stale_days and stale_days > 0:
        since = bj_now() - timedelta(days=stale_days)
        q[time_field] = {"$lt": since}
    elif lookback_hours and lookback_hours > 0:
        since = bj_now() - timedelta(hours=lookback_hours)
        q[time_field] = {"$gte": since}
    if processed_ids:
        q["_id"] = {"$nin": list(processed_ids)}
    return q


# 投影（拉取所需系统字段）
SA_PROJECTION = {
    "_id": 1, "orderNum": 1, "city": 1, "serviceType": 1,
    "title": 1, "describe": 1, "name": 1, "phone": 1, "assignee": 1,
    "status": 1, "updateTime": 1, "createTime": 1, "exts": 1,
}


# ======================================================================
# Mock：原始 serviceAppointment 形状的样例（走同一翻译器，确保 ACL 被验证）
# ======================================================================
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
        "describe": "安装智能门锁完成，老人不熟悉操作，客户担心电池续航，问能否上门复检。",
        "name": "李女士", "phone": "139****5678", "updateTime": bj_now().isoformat(),
    },
    {
        "_id": "SA-MOCK-003", "orderNum": "GD20260529003", "status": "403", "state": 1,
        "city": "110100", "serviceType": "40", "title": "张先生的工单",
        "describe": "",  # 真实数据 describe 多为空，验证空文本兜底
        "name": "张先生", "phone": "137****9012", "updateTime": bj_now().isoformat(),
    },
]


def mock_completed_work_orders(processed_ids: List[str]) -> List[WorkOrder]:
    processed = set(processed_ids)
    return [
        work_order_from_sa(d)
        for d in MOCK_SA_RECORDS
        if d.get("status") == COMPLETED_STATUS and str(d.get("_id")) not in processed
    ]
