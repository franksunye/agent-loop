"""运行配置（环境变量 → Config）。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .util import env_bool


@dataclass
class Config:
    # 开发环境 E2E 默认 true：企微仅预览、不打扰群；真发需显式 DRY_RUN=false
    dry_run: bool = field(default_factory=lambda: env_bool("DRY_RUN", True))

    # 工单数据源（v0.2 起默认 dev 真实库，mock 仅用于离线 CI）
    fsm_source: str = field(default_factory=lambda: os.getenv("FSM_SOURCE", "mongo").lower())
    fsm_mongo_url: str = field(default_factory=lambda: os.getenv("FSM_MONGO_URL", ""))
    fsm_mongo_db: str = field(default_factory=lambda: os.getenv("FSM_MONGO_DB", "xlinkdemo"))
    fsm_time_field: str = field(default_factory=lambda: os.getenv("FSM_TIME_FIELD", "updateTime"))
    lookback_hours: int = field(default_factory=lambda: int(os.getenv("FSM_LOOKBACK_HOURS", "24")))
    fsm_batch_limit: int = field(default_factory=lambda: int(os.getenv("FSM_BATCH_LIMIT", "50")))
    # 仅跟进 updateTime 在最近 N 天内（默认 14）；超过认为无意义
    fsm_max_age_days: int = field(default_factory=lambda: int(os.getenv("FSM_MAX_AGE_DAYS", "14")))
    fsm_stale_days: int = field(default_factory=lambda: int(os.getenv("FSM_STALE_DAYS", "0")))
    fsm_event_statuses: str = field(default_factory=lambda: os.getenv("FSM_EVENT_STATUSES", ""))
    # v0.2 试点：逗号分隔姓名（mongo 解析）或 userId；空=不过滤
    pilot_housekeepers: str = field(default_factory=lambda: os.getenv("FSM_PILOT_HOUSEKEEPERS", ""))
    pilot_housekeeper_ids: str = field(
        default_factory=lambda: os.getenv("FSM_PILOT_HOUSEKEEPER_IDS", "")
    )
    wecom_webhook_map: str = field(default_factory=lambda: os.getenv("WECOM_WEBHOOK_MAP", ""))
    # 运行期解析结果（run 启动时填充）
    resolved_pilot_ids: Optional[List[str]] = field(default=None, repr=False)
    pilot_id_to_name: Dict[str, str] = field(default_factory=dict, repr=False)

    # 追踪库（幂等水位线）
    tracking_source: str = field(
        default_factory=lambda: os.getenv("TRACKING_SOURCE", "local").lower()
    )
    tracking_local_path: str = field(
        default_factory=lambda: os.getenv("TRACKING_LOCAL_PATH", "data/agent_loop_tracking.db")
    )
    turso_url: str = field(default_factory=lambda: os.getenv("TURSO_URL", ""))
    turso_token: str = field(default_factory=lambda: os.getenv("TURSO_TOKEN", ""))

    # 推理提供方：heuristic（不走 API）| hunyuan（默认免费）| deepseek（质量验证）
    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "hunyuan").lower()
    )
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))
    hunyuan_api_key: str = field(default_factory=lambda: os.getenv("HUNYUAN_API_KEY", ""))

    # 推理模式：oneshot（默认试点）| steps（展示轨：enrich + LLM，见 docs/10）
    agent_mode: str = field(
        default_factory=lambda: os.getenv("AGENT_MODE", "oneshot").lower()
    )

    # 输出：群机器人 webhook + 可选企业应用消息（可信 IP 环境）
    wecom_webhook: str = field(default_factory=lambda: os.getenv("WECOM_WEBHOOK", ""))
    wecom_corp_id: str = field(default_factory=lambda: os.getenv("WECOM_CORP_ID", ""))
    wecom_agent_id: str = field(default_factory=lambda: os.getenv("WECOM_AGENT_ID", ""))
    wecom_agent_secret: str = field(default_factory=lambda: os.getenv("WECOM_AGENT_SECRET", ""))
    console_base_url: str = field(
        default_factory=lambda: os.getenv("CONSOLE_BASE_URL", "").rstrip("/")
    )

    def resolved_llm(self) -> tuple[str, str, str, str, bool]:
        """返回 (provider_label, api_key, base_url, model, use_json_mode)。"""
        p = self.llm_provider
        if p == "heuristic":
            return "heuristic", "", "", "", False
        if p == "hunyuan":
            key = self.hunyuan_api_key or self.llm_api_key
            # 避免 .env 里残留的 deepseek-chat 等被误用
            model = self.llm_model if "hunyuan" in (self.llm_model or "").lower() else "hunyuan-lite"
            base = self.llm_base_url or ""
            if base and "deepseek" in base.lower():
                base = ""
            return (
                "hunyuan",
                key,
                base or "https://api.hunyuan.cloud.tencent.com/v1",
                model,
                False,  # 混元用 prompt 约束 JSON，见 stockwise hunyuan_chain
            )
        if p in ("deepseek", "openai", "custom"):
            return (
                p,
                self.llm_api_key,
                self.llm_base_url or "https://api.deepseek.com/v1",
                self.llm_model or "deepseek-chat",
                True,
            )
        raise ValueError(f"未知 LLM_PROVIDER: {p}")
