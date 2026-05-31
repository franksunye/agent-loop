#!/usr/bin/env python3
"""同一工单、同一 enrich 输入，对比 hunyuan vs deepseek 的 v0.2 跟进建议。

用法（生产只读 + 两模型 API Key）:
  python scripts/compare_llm_single_order.py --order-num GD2026057898
  python scripts/compare_llm_single_order.py --order-num GD2026059389 --out-dir tmp/llm-compare

产出目录（默认 tmp/llm-compare/<order_num>/<timestamp>/）:
  enrich.json, prompt_user.txt, hunyuan.json, deepseek.json,
  hunyuan_card.md, deepseek_card.md, README.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
_PKG = ROOT / "packages" / "aol"
for p in (str(_PKG), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def _prod_mongo_url() -> str:
    cfg_path = Path("/Users/yesun/Code/xlink/code/cloud/src/main/resources/config_prod.properties")
    text = cfg_path.read_text(encoding="utf-8")
    pwd = re.search(r"mongodb\.auth='xlink:([^']+)@admin'", text).group(1)
    return (
        f"mongodb://xlink:{quote_plus(pwd)}@112.126.77.6:27017/xlink"
        f"?directConnection=true&authSource=admin"
    )


def _load_work_order(order_num: str) -> Tuple[Any, Any]:
    from datetime import datetime as dt

    from pymongo import MongoClient

    from aol import domain
    from aol.config import Config
    from aol.integration.fsm_mongo import resolve_pilot_housekeepers, _enrich_housekeeper_names

    client = MongoClient(_prod_mongo_url(), serverSelectionTimeoutMS=8000)
    db = client["xlink"]
    doc = db["serviceAppointment"].find_one({"orderNum": order_num, "state": 1})
    if not doc:
        raise SystemExit(f"未找到工单: {order_num}")
    wo = domain.work_order_from_sa(doc)
    ut = doc.get("updateTime")
    if isinstance(ut, dt):
        wo.stale_days = max(0, (domain.bj_now() - ut.replace(tzinfo=None)).days)
    cfg = Config()
    cfg.fsm_mongo_url = _prod_mongo_url()
    cfg.fsm_mongo_db = "xlink"
    cfg.fsm_source = "mongo"
    resolve_pilot_housekeepers(cfg, db)
    _enrich_housekeeper_names(db, [wo])
    client.close()
    return wo, cfg


def _run_provider(
    provider: str,
    wo: Any,
    user_prompt: str,
    enrich_ctx: Any,
    *,
    hunyuan_key: str,
    deepseek_key: str,
    use_polish: bool = True,
) -> Dict[str, Any]:
    from aol.config import Config
    from aol.runtime.llm import llm_follow_up
    from aol.runtime.prompts import SYSTEM_PROMPT
    from aol import domain

    cfg = Config()
    cfg.llm_provider = provider
    cfg.agent_mode = "steps"
    if provider == "hunyuan":
        cfg.hunyuan_api_key = hunyuan_key
        cfg.llm_api_key = hunyuan_key
        cfg.llm_base_url = "https://api.hunyuan.cloud.tencent.com/v1"
        cfg.llm_model = "hunyuan-lite"
    else:
        cfg.hunyuan_api_key = ""
        cfg.llm_api_key = deepseek_key
        cfg.llm_base_url = "https://api.deepseek.com/v1"
        cfg.llm_model = "deepseek-chat"

    prov, api_key, base_url, model, json_mode = cfg.resolved_llm()
    if not api_key:
        return {"error": f"缺少 {provider} API Key"}

    suggestion, trace = llm_follow_up(
        cfg, wo, prov, api_key, base_url, model, json_mode, user_prompt,
        domain.bj_now().isoformat(),
        enrich_ctx=enrich_ctx if use_polish else None,
    )
    from aol.action.card import build_card_markdown, enrich_output_from_trace

    enrich_out = enrich_output_from_trace(trace)
    card = ""
    if suggestion:
        card = build_card_markdown(wo, suggestion, enrich_output=enrich_out)

    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "json_mode": json_mode,
        "status": trace.status,
        "error": trace.error,
        "latency_ms": trace.latency_ms,
        "total_tokens": trace.total_tokens,
        "prompt_tokens": trace.prompt_tokens,
        "completion_tokens": trace.completion_tokens,
        "raw_response": trace.raw_response,
        "parsed": trace.parsed,
        "wecom_card_markdown": card,
        "prompt_system": _SYSTEM_PROMPT,
    }


def _resolve_deepseek_key() -> str:
    key = os.getenv("LLM_API_KEY", "").strip()
    if key:
        return key
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    # 可选：团队其它项目 .env（不提交本仓库）
    for ext in (
        os.getenv("DEEPSEEK_ENV_FILE", "").strip(),
        "/Users/yesun/Code/stockwise/backend/.env",
        "/Users/yesun/Code/stockwise/.env",
    ):
        if not ext:
            continue
        p = Path(ext)
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for prefix in (
                "DEEPSEEK_API_KEY=",
                "LLM_PROVIDER__DEEPSEEK_OFFICIAL__API_KEY=",
            ):
                if line.startswith(prefix):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _score(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """简易质量启发式（便于闭环对比，非业务真理）。"""
    if not parsed or parsed.get("error"):
        return {"score": 0, "notes": ["调用失败"]}
    plan = parsed.get("跟进方案") or {}
    pts = plan.get("沟通要点") or []
    basis = parsed.get("优先级依据") or []
    refs = parsed.get("引用查证") or []
    notes = []
    score = 0
    if parsed.get("原因摘要"):
        score += 2
    if len(basis) >= 2:
        score += 2
    elif basis:
        score += 1
        notes.append("优先级依据偏少")
    if len(pts) >= 3:
        score += 3
    elif len(pts) >= 2:
        score += 2
    else:
        notes.append("沟通要点不足")
    if len(refs) >= 2:
        score += 2
    if plan.get("主行动") and "建议" not in str(plan.get("主行动"))[:6]:
        score += 1
    elif plan.get("主行动"):
        notes.append("主行动偏软（含「建议」等虚词）")
    summary = str(parsed.get("原因摘要", ""))
    if any(c.isdigit() for c in summary) and ("停留" in summary or "天" in summary):
        score += 1
    else:
        notes.append("原因摘要未点停留天数或金额")
    return {"score": score, "max": 10, "notes": notes}


def main() -> None:
    ap = argparse.ArgumentParser(description="单工单 LLM 对比 hunyuan vs deepseek")
    ap.add_argument("--order-num", default="GD2026057898", help="工单号")
    ap.add_argument("--out-dir", default="tmp/llm-compare", help="输出根目录")
    ap.add_argument("--round", default="", help="子目录标记，如 round2")
    ap.add_argument(
        "--providers",
        default="hunyuan,deepseek",
        help="逗号分隔：hunyuan,deepseek",
    )
    ap.add_argument("--no-polish", action="store_true", help="跳过后处理（对比用）")
    args = ap.parse_args()

    hunyuan_key = os.getenv("HUNYUAN_API_KEY", "") or os.getenv("LLM_API_KEY", "")
    deepseek_key = _resolve_deepseek_key()
    if not hunyuan_key:
        raise SystemExit("需要 HUNYUAN_API_KEY（agent-loop/.env）")

    wo, _cfg = _load_work_order(args.order_num)
    from agent_tools import enrich_work_order_context

    cfg_probe = type("C", (), {"fsm_source": "mongo", "fsm_mongo_url": _prod_mongo_url(), "fsm_mongo_db": "xlink"})()
    enrich_ctx = enrich_work_order_context(cfg_probe, wo)
    user_prompt = f"工单号: {wo.order_num}\n{wo.followup_text}\n\n{enrich_ctx.to_prompt_block()}"

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    sub = f"{ts}-{args.round}" if args.round else ts
    out = Path(args.out_dir) / args.order_num / sub
    out.mkdir(parents=True, exist_ok=True)
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]

    _write_json(out / "enrich.json", enrich_ctx.to_step_dict())
    (out / "prompt_user.txt").write_text(user_prompt, encoding="utf-8")

    results: Dict[str, Any] = {}
    for prov in providers:
        if prov == "deepseek" and not deepseek_key:
            results[prov] = {"error": "未配置 DeepSeek API Key（LLM_API_KEY 或 DEEPSEEK_API_KEY）"}
            _write_json(out / f"{prov}.json", results[prov])
            continue
        print(f"调用 {prov}…", flush=True)
        key = hunyuan_key if prov == "hunyuan" else deepseek_key
        results[prov] = _run_provider(
            prov, wo, user_prompt, enrich_ctx,
            hunyuan_key=hunyuan_key, deepseek_key=key,
            use_polish=not args.no_polish,
        )
        _write_json(out / f"{prov}.json", results[prov])
        card = results[prov].get("wecom_card_markdown") or ""
        if card:
            (out / f"{prov}_card.md").write_text(card, encoding="utf-8")

    h_score = _score(results.get("hunyuan", {}).get("parsed") or {})
    d_score = _score(results.get("deepseek", {}).get("parsed") or {}) if results.get("deepseek", {}).get("parsed") else {"score": 0, "notes": ["未运行"]}

    readme = f"""# LLM 对比 · {args.order_num}

生成时间：{ts}

## 输入

- 工单：`{args.order_num}`（生产 `xlink` 只读）
- 同一 `prompt_user.txt` + `enrich.json`
- 系统提示词：v0.2 Action Spec（见各 JSON 内 `prompt_system` 或代码）

## 文件

| 文件 | 说明 |
|------|------|
| enrich.json | 只读查证结果 |
| prompt_user.txt | 送入模型的用户消息 |
| hunyuan.json / deepseek.json | 完整调用结果 |
| hunyuan_card.md / deepseek_card.md | 企微预览卡片 |

## 简易评分（启发式 /10）

| 模型 | 分 | 备注 |
|------|-----|------|
| hunyuan | {h_score.get('score')} | {'; '.join(h_score.get('notes') or []) or '—'} |
| deepseek | {d_score.get('score')} | {'; '.join(d_score.get('notes') or []) or '—'} |

## 下一步

1. 人工审阅两份 `*_card.md` 与 `parsed` 内「沟通要点」「优先级依据」
2. 将更好的一方样例补进 `_SYSTEM_PROMPT` few-shot
3. 混元试点 / DeepSeek 演示按此结论分工（见 docs/06-llm-providers.md）
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    print(f"完成 → {out}")


if __name__ == "__main__":
    main()
