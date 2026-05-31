#!/usr/bin/env bash
# 接 Turso：用现有 sqlite 文件建库（schema + 数据一并迁移），输出环境变量。
#
# 前置：turso auth login 已完成（见 turso auth whoami）。
# 用法：
#   bash scripts/turso_setup.sh [db_name] [sqlite_file]
#   默认：db_name=fs-aol  sqlite_file=data/agent_loop_tracking.db
#
# 输出的 TURSO_URL / TURSO_TOKEN 同时用于：
#   - 引擎（.env）：TURSO_URL / TURSO_TOKEN + TRACKING_SOURCE=cloud
#   - Console（apps/console/.env.local）：LIBSQL_URL / LIBSQL_AUTH_TOKEN
set -euo pipefail

DB_NAME="${1:-fs-aol}"
SQLITE_FILE="${2:-data/agent_loop_tracking.db}"
export PATH="$HOME/.turso:$PATH"

if ! turso auth whoami >/dev/null 2>&1; then
  echo "ERROR: 未登录 Turso，请先运行：turso auth login" >&2
  exit 1
fi

if turso db show "$DB_NAME" >/dev/null 2>&1; then
  echo "ℹ 数据库 $DB_NAME 已存在，跳过创建（如需重建请先 turso db destroy $DB_NAME）。" >&2
else
  echo "→ 从 $SQLITE_FILE 创建 Turso 库 $DB_NAME ..." >&2
  turso db create "$DB_NAME" --from-file "$SQLITE_FILE"
fi

URL="$(turso db show --url "$DB_NAME")"
TOKEN="$(turso db tokens create "$DB_NAME")"

echo "==== 复制以下值（勿提交到 git）===="
echo "TURSO_URL=$URL"
echo "TURSO_TOKEN=$TOKEN"
echo "===================================="
