"""输出层：企业微信群机器人推送（含按管家路由 webhook）。"""

from __future__ import annotations

import logging
from typing import Dict

from ..config import Config
from ..util import parse_csv

logger = logging.getLogger("aol.action")


def parse_webhook_map(raw: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in parse_csv(raw):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if k and v:
            out[k] = v
    return out


def webhook_for_housekeeper(cfg: Config, housekeeper_id: str) -> str:
    m = parse_webhook_map(cfg.wecom_webhook_map)
    return m.get(housekeeper_id, "") or cfg.wecom_webhook


def send_wecom_card(cfg: Config, markdown: str, *, housekeeper_id: str = "") -> bool:
    webhook = webhook_for_housekeeper(cfg, housekeeper_id) if housekeeper_id else cfg.wecom_webhook
    if cfg.dry_run or not webhook:
        tag = ""
        if housekeeper_id and cfg.wecom_webhook_map:
            tag = f" [webhook→{housekeeper_id[:8]}…]" if webhook else " [无专属 webhook，未发]"
        logger.info("[企微预览] 未发送（DRY_RUN 或缺少 webhook）%s：\n%s", tag, markdown)
        return True

    import requests  # 懒加载

    resp = requests.post(
        webhook,
        json={"msgtype": "markdown", "markdown": {"content": markdown}},
        timeout=15,
    )
    ok = resp.ok and resp.json().get("errcode") == 0
    if not ok:
        logger.error("企微推送失败：%s", resp.text[:300])
    return ok
