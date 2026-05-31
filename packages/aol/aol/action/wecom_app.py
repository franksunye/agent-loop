"""企业微信应用消息（/cgi-bin/message/send，需企业可信 IP）。

与群机器人 webhook（wecom.py）并列：
- webhook：GHA cron 友好，发群 Markdown
- app：按成员 userid 发个人消息（textcard / text 等），须在可信 IP 环境调用

见 XLink EnterpriseWechatServiceImpl；本模块为 fs-aol 侧 Python 沉淀，cron 默认仍走 webhook。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from ..config import Config

logger = logging.getLogger("aol.action")

_QYAPI = "https://qyapi.weixin.qq.com/cgi-bin"
_TOKEN_CACHE: Dict[str, tuple[str, float]] = {}
_TOKEN_SKEW_SEC = 120


def app_message_configured(cfg: Config) -> bool:
    return bool(cfg.wecom_corp_id and cfg.wecom_agent_secret and cfg.wecom_agent_id)


def _token_cache_key(corp_id: str, secret: str) -> str:
    return f"{corp_id}:{secret[:12]}"


def get_access_token(corp_id: str, secret: str, *, force_refresh: bool = False) -> str:
    """获取应用 access_token（内存缓存，进程内复用）。"""
    if not corp_id or not secret:
        raise ValueError("wecom corp_id / agent secret 未配置")

    key = _token_cache_key(corp_id, secret)
    now = time.time()
    if not force_refresh and key in _TOKEN_CACHE:
        token, expires_at = _TOKEN_CACHE[key]
        if now < expires_at:
            return token

    import requests  # 懒加载

    resp = requests.get(
        f"{_QYAPI}/gettoken",
        params={"corpid": corp_id, "corpsecret": secret},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"gettoken failed: {data.get('errmsg')} ({data.get('errcode')})")

    token = str(data["access_token"])
    expires_in = int(data.get("expires_in", 7200))
    _TOKEN_CACHE[key] = (token, now + max(expires_in - _TOKEN_SKEW_SEC, 60))
    return token


def send_app_message(cfg: Config, body: Dict[str, Any]) -> bool:
    """发送应用消息。body 需含 touser、msgtype、agentid 等（见企微文档）。"""
    if not app_message_configured(cfg):
        logger.warning("[企微应用] 未配置 WECOM_CORP_ID / WECOM_AGENT_ID / WECOM_AGENT_SECRET，跳过")
        return False

    agent_id = int(cfg.wecom_agent_id)
    payload = dict(body)
    payload.setdefault("agentid", agent_id)
    payload.setdefault("safe", 0)

    if cfg.dry_run:
        logger.info(
            "[企微应用预览] 未发送（DRY_RUN） touser=%s msgtype=%s\n%s",
            payload.get("touser"),
            payload.get("msgtype"),
            payload,
        )
        return True

    import requests  # 懒加载

    token = get_access_token(cfg.wecom_corp_id, cfg.wecom_agent_secret)
    resp = requests.post(
        f"{_QYAPI}/message/send",
        params={"access_token": token},
        json=payload,
        timeout=15,
    )
    data = resp.json()
    ok = resp.ok and data.get("errcode") == 0
    if not ok:
        logger.error("企微应用消息失败：%s", resp.text[:400])
    return ok


def send_app_text(cfg: Config, *, touser: str, content: str) -> bool:
    return send_app_message(
        cfg,
        {
            "touser": touser,
            "msgtype": "text",
            "text": {"content": content},
        },
    )


def send_app_textcard(
    cfg: Config,
    *,
    touser: str,
    title: str,
    description: str,
    url: str,
    btntxt: str = "打开",
) -> bool:
    return send_app_message(
        cfg,
        {
            "touser": touser,
            "msgtype": "textcard",
            "textcard": {
                "title": title,
                "description": description,
                "url": url,
                "btntxt": btntxt,
            },
        },
    )


def send_follow_up_textcard(
    cfg: Config,
    *,
    touser: str,
    customer_name: str,
    primary_action: str,
    console_url: str,
    event_label: str = "",
    order_ref: str = "",
) -> bool:
    """跟进行动个人通知卡（与 compact Markdown 卡片语义对齐）。"""
    ctx = " · ".join(x for x in (event_label, order_ref) if x)
    gray = f"<div class=\"gray\">{ctx}</div>" if ctx else ""
    desc = (
        f"{gray}"
        f"<div class=\"normal\">{primary_action}</div>"
    )
    title = f"跟进行动 · {customer_name or '客户'}"
    return send_app_textcard(
        cfg,
        touser=touser,
        title=title,
        description=desc,
        url=console_url,
        btntxt="打开处置页",
    )
