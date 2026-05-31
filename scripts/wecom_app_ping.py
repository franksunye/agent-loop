#!/usr/bin/env python3
"""手动验证企业微信应用消息（需可信 IP + .env 中 WECOM_CORP_* / WECOM_AGENT_*）。

示例：
  DRY_RUN=false python scripts/wecom_app_ping.py --touser YOUR_QW_USERID
  DRY_RUN=false python scripts/wecom_app_ping.py --touser YOUR_QW_USERID --url https://console.xiulian.com.cn/
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "packages", "aol"))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass

from aol.config import Config
from aol.action.wecom_app import app_message_configured, send_app_textcard


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a WeCom app textcard ping")
    parser.add_argument("--touser", required=True, help="企业成员 userid")
    parser.add_argument(
        "--url",
        default=os.getenv("CONSOLE_BASE_URL", "https://console.xiulian.com.cn"),
        help="textcard 跳转 URL",
    )
    parser.add_argument("--title", default="FS-AOL 应用消息测试")
    args = parser.parse_args()

    cfg = Config()
    if not app_message_configured(cfg):
        print(
            "缺少 WECOM_CORP_ID / WECOM_AGENT_ID / WECOM_AGENT_SECRET，见 .env.example",
            file=sys.stderr,
        )
        return 1

    ok = send_app_textcard(
        cfg,
        touser=args.touser,
        title=args.title,
        description=(
            '<div class="gray">wecom_app.py · scripts/wecom_app_ping.py</div>'
            '<div class="normal">应用消息链路验证。点击下方打开 Console。</div>'
        ),
        url=args.url.rstrip("/") + "/",
        btntxt="打开 Console",
    )
    print("sent" if ok else "failed", "dry_run=", cfg.dry_run)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
