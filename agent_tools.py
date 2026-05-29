"""Agent 只读工具（v0.2 steps）：生产级业务查证。

仅报价 B（工单正式报价）+ 签约合同 + 工单渗漏部位/方案摘要。纪律：只读 Mongo。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agent_cron_engine import Config
    from domain import WorkOrder

logger = logging.getLogger("agent-loop.tools")

_QUOTE_B_MARKS = {
    "$or": [
        {"bjProducts": {"$exists": True, "$nin": [None, ""]}},
        {"exts.bjdPDFurl": {"$exists": True, "$nin": [None, ""]}},
    ],
}
_SIGNED_CONTRACT = {"state": 1, "exts.contractStatus": "10"}

_PAY_STATE = {0: "未支付", 1: "已支付", 2: "已付首付款"}
_SOURCE_TYPE = {"1": "雨虹自引单", "2": "平台派单", "5": "修链自获客"}

# L1.5 业务经验（docs/12-business-knowledge-follow-up.md · ADR-010）
_HIGH_VALUE_PART_KEYWORDS = ("屋顶", "屋面", "金属屋面")
_GOOD_CHANNEL_KEYWORDS = ("400", "官网", "雨虹防水官网", "400热线", "400电话")
_LOW_CHANNEL_KEYWORDS = ("抖音",)


@dataclass
class EnrichedContext:
    work_order_id: str
    quote_count: int = 0
    has_quote: Optional[bool] = None
    has_signed_contract: Optional[bool] = None
    signed_contract_count: int = 0
    business_verdict: str = ""
    evidence_lines: List[str] = field(default_factory=list)
    leak_sites: List[str] = field(default_factory=list)
    source_type_label: str = ""
    channel_label: str = ""
    business_hints: List[str] = field(default_factory=list)
    quotes: List[Dict[str, Any]] = field(default_factory=list)
    contracts: List[Dict[str, Any]] = field(default_factory=list)
    recent_activity: str = ""
    tool_notes: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def _finalize(self) -> None:
        self.has_quote = self.quote_count > 0
        self.business_hints = _build_business_hints(
            self.leak_sites, self.channel_label, self.source_type_label,
        )
        self.evidence_lines = self._build_evidence_lines()
        self.business_verdict = self._compute_verdict()

    def _compute_verdict(self) -> str:
        if self.has_signed_contract and self.contracts:
            c = self.contracts[0]
            amt = c.get("amount_yuan")
            amt_s = f"{amt:.0f}元" if isinstance(amt, (int, float)) else "—"
            return (
                f"【结论】已有生效签约（{c.get('contract_num', '—')}，{amt_s}）"
                f"→ 不宜按「待签约」硬催，建议先核对工单状态"
            )
        if self.has_quote and self.quotes:
            q = self.quotes[0]
            amt = q.get("amount_yuan")
            amt_s = f"{amt:.0f}元" if isinstance(amt, (int, float)) else "—"
            parts = "、".join(q.get("repair_parts") or self.leak_sites or []) or "—"
            return f"【结论】已正式报价 {amt_s}（{parts}）→ 可推进签约/回访确认"
        if self.has_quote is False:
            sites = "、".join(self.leak_sites) if self.leak_sites else "—"
            return f"【结论】系统无工单正式报价（渗漏部位：{sites}）→ 建议确认是否线下报价未录入"
        return ""

    def _build_evidence_lines(self) -> List[str]:
        lines: List[str] = []
        if self.channel_label:
            lines.append(f"获客渠道：{self.channel_label}")
        elif self.source_type_label:
            lines.append(f"线索来源（粗）：{self.source_type_label}")
        if self.leak_sites:
            lines.append(f"渗漏/维修部位：{'、'.join(self.leak_sites)}")
        for i, q in enumerate(self.quotes[:2]):
            prefix = "正式报价" if i == 0 else "报价(较早)"
            amt = q.get("amount_yuan")
            amt_s = f"{amt:.0f}元" if isinstance(amt, (int, float)) else "—"
            pay = q.get("pay_state_label") or "—"
            loc = q.get("construction_location") or ""
            desc = (q.get("part_description") or "")[:80]
            pkgs = "、".join(q.get("package_names") or [])[:60]
            wr = q.get("warranty_label") or ""
            area = q.get("maintain_area") or ""
            line = f"{prefix}：{amt_s}（{pay}）"
            if pkgs:
                line += f"；方案：{pkgs}"
            if wr:
                line += f"；质保：{wr}"
            if area:
                line += f"；维修面积：{area}"
            if loc:
                line += f"；位置：{loc}"
            lines.append(line)
            if desc:
                lines.append(f"  部位说明：{desc}")
        for c in self.contracts[:1]:
            amt = c.get("amount_yuan")
            amt_s = f"{amt:.0f}元" if isinstance(amt, (int, float)) else "—"
            part = c.get("maintain_part") or "—"
            lines.append(
                f"生效签约：{c.get('contract_num', '—')}，{amt_s}，维修部位：{part}"
            )
        if self.recent_activity:
            lines.append(f"最近流程：{self.recent_activity[:120]}")
        lines.extend(self.business_hints)
        return lines

    def to_prompt_block(self) -> str:
        lines = [
            "【系统查证 · 只读事实（reason 与 suggested_action 必须与此一致，禁止编造）】",
        ]
        if self.business_verdict:
            lines.append(self.business_verdict)
        lines.extend(self.evidence_lines)
        for n in self.tool_notes:
            lines.append(f"备注：{n}")
        return "\n".join(lines)

    def to_step_dict(self) -> Dict[str, Any]:
        return {
            "tool": "enrich_work_order_context",
            "work_order_id": self.work_order_id,
            "quote_channel": "B",
            "quote_count": self.quote_count,
            "has_quote": self.has_quote,
            "has_signed_contract": self.has_signed_contract,
            "signed_contract_count": self.signed_contract_count,
            "business_verdict": self.business_verdict,
            "evidence_lines": self.evidence_lines,
            "leak_sites": self.leak_sites,
            "source_type_label": self.source_type_label,
            "channel_label": self.channel_label,
            "business_hints": self.business_hints,
            "quotes": self.quotes,
            "contracts": self.contracts,
            "recent_activity": self.recent_activity,
            "tool_notes": self.tool_notes,
        }


def _fmt_time(val: Any) -> str:
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    return str(val or "")[:10]


def _money(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _resolve_channel_path(db: Any, channel: Any) -> str:
    if not channel:
        return ""
    values = channel if isinstance(channel, list) else [channel]
    names: List[str] = []
    for v in values:
        key = str(v).strip()
        if not key:
            continue
        row = db["code"].find_one({"type": "channel", "value": key}, {"name": 1})
        names.append(str((row or {}).get("name") or key))
    return " / ".join(names) if names else ""


def _build_business_hints(
    leak_sites: List[str],
    channel_label: str,
    source_type_label: str,
) -> List[str]:
    """运营经验提示（ADR-010）；与查证事实分行，供 LLM 调优先级。"""
    hints: List[str] = []
    parts_text = " ".join(leak_sites)
    if any(k in parts_text for k in _HIGH_VALUE_PART_KEYWORDS):
        hints.append("业务提示：屋面/屋顶类部位客单价高，宜优先跟进、优先排期")
    ch = channel_label or ""
    if any(k in ch for k in _GOOD_CHANNEL_KEYWORDS):
        hints.append("业务提示：品牌渠道（400/官网）客户质量较好，可积极推进签约")
    if any(k in ch for k in _LOW_CHANNEL_KEYWORDS):
        hints.append(
            "业务提示：抖音渠道咨询多、随机性强，建议先核实意向与报价匹配度再重投入"
        )
    return hints


class _CodeCache:
    def __init__(self, db: Any) -> None:
        self._db = db
        self._cache: Dict[str, str] = {}

    def label(self, code_id: Any) -> str:
        key = str(code_id or "").strip()
        if not key:
            return ""
        if key in self._cache:
            return self._cache[key]
        row = self._db["code"].find_one({"_id": key}, {"name": 1})
        if not row:
            # value 在不同 type 下会重复（如 "3"），仅查维修部位相关码表
            row = self._db["code"].find_one(
                {"value": key, "type": {"$in": ["allPartsOne", "parts"]}},
                {"name": 1},
            )
        name = str((row or {}).get("name") or key)
        self._cache[key] = name
        return name


def _flatten_leak_codes(raw: Any) -> List[str]:
    ids: List[str] = []

    def walk(x: Any) -> None:
        if x is None:
            return
        if isinstance(x, str):
            ids.append(x)
        elif isinstance(x, (list, tuple)):
            for i in x:
                walk(i)

    walk(raw)
    return ids


def _parse_bj_quote_row(item: Dict[str, Any], codes: _CodeCache) -> Dict[str, Any]:
    repair_ids = item.get("repairParts") or []
    if isinstance(repair_ids, str):
        repair_ids = [repair_ids]
    repair_parts = [codes.label(i) for i in repair_ids if codes.label(i)]

    packages: List[str] = []
    pp = item.get("projPackages")
    if isinstance(pp, dict):
        for pkg in pp.get("data") or []:
            if isinstance(pkg, dict) and pkg.get("name"):
                packages.append(str(pkg["name"]))

    ag = item.get("agelimit")
    ag_max = item.get("agelimitMax")
    warranty = ""
    if ag is not None:
        warranty = f"{ag}年" if ag == ag_max or ag_max is None else f"{ag}-{ag_max}年"

    return {
        "repair_parts": repair_parts,
        "construction_location": str(item.get("constructionLocation") or ""),
        "part_description": str(item.get("partDescription") or ""),
        "package_names": packages,
        "warranty_label": warranty,
        "maintain_area": str(item.get("maintainAreaNum") or ""),
        "line_amount_yuan": _money(item.get("totalAmount")),
    }


def _parse_order_doc(doc: Dict[str, Any], codes: _CodeCache) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "order_number": str(doc.get("orderNumber") or doc.get("_id") or ""),
        "amount_yuan": _money(doc.get("totalPrice")),
        "pay_state_label": _PAY_STATE.get(int(doc.get("payState") or 0), "未知"),
        "quote_date": _fmt_time(doc.get("createTime")),
        "repair_parts": [],
        "construction_location": "",
        "part_description": "",
        "package_names": [],
        "warranty_label": "",
        "maintain_area": "",
    }
    bp_raw = doc.get("bjProducts")
    if not bp_raw:
        return out
    try:
        bp = json.loads(bp_raw) if isinstance(bp_raw, str) else bp_raw
    except json.JSONDecodeError:
        return out
    if not isinstance(bp, dict):
        return out
    order_list = bp.get("orderList") or []
    if not order_list:
        return out
    # 取金额最大的一行作为展示主方案（多单时）
    best = max(
        (x for x in order_list if isinstance(x, dict)),
        key=lambda x: float(x.get("totalAmount") or 0),
        default=None,
    )
    if best:
        parsed = _parse_bj_quote_row(best, codes)
        out.update({k: parsed.get(k, out.get(k)) for k in parsed})
        if parsed.get("line_amount_yuan") and not out.get("amount_yuan"):
            out["amount_yuan"] = parsed["line_amount_yuan"]
    return out


def enrich_work_order_context(cfg: "Config", wo: "WorkOrder") -> EnrichedContext:
    ctx = EnrichedContext(work_order_id=wo.work_order_id)
    if cfg.fsm_source != "mongo" or not cfg.fsm_mongo_url:
        ctx.tool_notes.append("enrich 跳过：FSM_SOURCE 非 mongo")
        ctx._finalize()
        return ctx

    sa_id = wo.work_order_id
    if not sa_id:
        ctx.tool_notes.append("缺少工单 id")
        ctx._finalize()
        return ctx

    try:
        from pymongo import MongoClient

        client = MongoClient(cfg.fsm_mongo_url, serverSelectionTimeoutMS=8000)
        db = client[cfg.fsm_mongo_db]
        codes = _CodeCache(db)

        sa = db["serviceAppointment"].find_one(
            {"_id": sa_id},
            {
                "channel": 1,
                "exts.sourceType": 1,
                "exts.leakagesite": 1,
                "exts.leakagesite_copy": 1,
                "describe": 1,
            },
        )
        if sa:
            ctx.channel_label = _resolve_channel_path(db, sa.get("channel"))
            exts = sa.get("exts") or {}
            st = str(exts.get("sourceType") or "")
            ctx.source_type_label = _SOURCE_TYPE.get(st, f"来源码{st}" if st else "")
            leak_raw = exts.get("leakagesite_copy") or exts.get("leakagesite")
            leak_ids = _flatten_leak_codes(leak_raw)
            ctx.leak_sites = list(dict.fromkeys(codes.label(i) for i in leak_ids if codes.label(i)))

        sa_match = {
            "$or": [
                {"serviceAppointmentId": sa_id},
                {"serviceAppointmentIds": sa_id},
            ],
        }
        b_filter = {"state": {"$ne": -1}, "type": 1, "$and": [sa_match, _QUOTE_B_MARKS]}
        order_docs = list(
            db["order"]
            .find(
                b_filter,
                {
                    "orderNumber": 1,
                    "totalPrice": 1,
                    "payState": 1,
                    "createTime": 1,
                    "bjProducts": 1,
                },
            )
            .sort("createTime", -1)
            .limit(3)
        )
        ctx.quote_count = len(order_docs)
        ctx.quotes = [_parse_order_doc(d, codes) for d in order_docs]

        contract_docs = list(
            db["contract"]
            .find(
                {**_SIGNED_CONTRACT, "serviceAppointmentId": sa_id},
                {
                    "contractNum": 1,
                    "afterRefundMoney": 1,
                    "maintainPart": 1,
                    "exts.contractStatus": 1,
                },
            )
            .limit(2)
        )
        ctx.signed_contract_count = len(contract_docs)
        ctx.has_signed_contract = ctx.signed_contract_count > 0
        ctx.contracts = [
            {
                "contract_num": str(c.get("contractNum") or ""),
                "amount_yuan": _money(c.get("afterRefundMoney")),
                "maintain_part": str(c.get("maintainPart") or ""),
            }
            for c in contract_docs
        ]

        wn = db["workflowNode"].find_one(
            {"serviceAppointmentId": sa_id},
            {"nodeName": 1, "remark": 1, "createTime": 1},
            sort=[("createTime", -1)],
        )
        if wn:
            name = wn.get("nodeName") or wn.get("name") or "流程节点"
            remark = (wn.get("remark") or "").strip()
            ctx.recent_activity = f"{name}" + (f"：{remark}" if remark else "")

        ctx.raw = {"db": cfg.fsm_mongo_db, "quote_count": ctx.quote_count}
        client.close()
    except Exception as e:
        logger.warning("enrich 失败: %s", e)
        ctx.tool_notes.append(f"enrich 异常: {type(e).__name__}: {e}")

    ctx._finalize()
    return ctx
