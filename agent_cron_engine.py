#!/usr/bin/env python3
"""兼容垫片（R1 过渡）：引擎已拆分为 packages/aol。

历史入口 `python agent_cron_engine.py` 仍可用，委托给 aol.app。
新代码请改用 `python run_cron.py` 或 `from aol.app import main`。
该垫片将在 monorepo 收尾（R4）后删除。
"""

from __future__ import annotations

import os
import sys

_PKG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "packages", "aol")
if os.path.isdir(_PKG) and _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from aol.app import Config, main, reset_tracking, run  # noqa: E402,F401

if __name__ == "__main__":
    sys.exit(main())
