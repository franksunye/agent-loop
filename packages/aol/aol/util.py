"""跨层通用小工具（无内部依赖）。"""

from __future__ import annotations

import os
from typing import List


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def parse_csv(raw: str) -> List[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]
