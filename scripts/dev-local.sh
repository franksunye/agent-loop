#!/usr/bin/env bash
# 本地 v0.2.x 闭环演示：mock 206 + 本地 sqlite + Console
#
# 用法：
#   scripts/dev-local.sh seed     # 写入 data/agent_loop_tracking.db
#   scripts/dev-local.sh console  # 启动 Console（另开终端）
#   scripts/dev-local.sh          # seed 后打印说明
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

DB_PATH="${AOL_DEV_DB_PATH:-/tmp/fs-aol-dev.db}"
mkdir -p "$ROOT/data"

seed() {
  echo "[dev-local] 写入 mock 206（四位管家）→ $DB_PATH"
  FSM_SOURCE=mock \
  FSM_EVENT_STATUSES=206 \
  AGENT_MODE=steps \
  LLM_PROVIDER=heuristic \
  DRY_RUN=true \
  CONSOLE_BASE_URL=http://localhost:3000 \
  TRACKING_SOURCE=local \
  TRACKING_LOCAL_PATH="$DB_PATH" \
  "$PY" run_cron.py --reset-tracking
  echo "[dev-local] 完成。建议列表应有 4 条（每位管家 1 条）。"
}

console_hint() {
  cat <<EOF

── Console 本地开发 ──

1. 复制本地配置（若尚未）：
   cp apps/console/.env.local.sqlite.example apps/console/.env.local

2. 启动 Console：
   cd apps/console && pnpm dev
   或：make dev

3. 打开 http://localhost:3000
   - 右上角「管家收件箱」切换四位管家（各 1 条）
   - 详情页：阻塞 A/B/C/D、已跟进、推理 trace

4. 再跑一轮引擎（验证 prior context / 已跟进再入池）：
   TRACKING_LOCAL_PATH=$DB_PATH make cron
   （需先在 Console 某单点「已跟进」）

EOF
}

case "${1:-}" in
  seed) seed; console_hint ;;
  console)
    if [ ! -f apps/console/.env.local ]; then
      cp apps/console/.env.local.sqlite.example apps/console/.env.local
      echo "[dev-local] 已创建 apps/console/.env.local（sqlite 模式）"
    fi
    exec pnpm --filter console dev
    ;;
  *)
    seed
    console_hint
    ;;
esac
