"""FS-AOL 跟进引擎包（POC 引擎 poc-followup）。

分层（对齐 docs/public/PUB-02-architecture.md 的 FS-AOL 五层）：
- integration  事件摄取（L1/L2，防腐层落点）
- context      只读业务查证 enrich（L2）
- runtime      推理编排 + LLM + 启发式（L3）
- decision     建议后处理抛光（L4）
- action       企微卡片与推送（L5）
- tracking     幂等水位线 + 推理 trace（链接/事件层）
- app          主编排与 CLI 入口
"""

from __future__ import annotations

from .config import Config
from .app import main, run, reset_tracking

__all__ = ["Config", "main", "run", "reset_tracking"]
