#!/usr/bin/env python3
"""GHA / 本地 cron 入口（薄壳）：委托给 aol.app。

运行：
    python run_cron.py                 # 按 .env / 环境变量配置运行
    DRY_RUN=true python run_cron.py    # 零依赖冒烟（mock + heuristic + local）

若未 `pip install -e packages/aol`，自动把包目录加入 sys.path（便于本地直接跑）。
"""

from __future__ import annotations

import os
import sys

_PKG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "packages", "aol")
if os.path.isdir(_PKG) and _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from aol.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
