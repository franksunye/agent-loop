#!/usr/bin/env bash
# Offline deterministic smoke / regression guard for the fs-aol engine.
#
# Runs the engine against the built-in mock FSM source (no network, no mongo,
# no LLM, fresh temp tracking db) and compares the normalized suggestion output
# against scripts/smoke_baseline.txt. Used to prove refactors keep behavior identical.
#
# Usage:
#   scripts/smoke.sh           # run and diff against baseline (exit 1 on drift)
#   scripts/smoke.sh --update  # regenerate the baseline
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASELINE="$SCRIPT_DIR/smoke_baseline.txt"

cd "$REPO_ROOT"

# Prefer repo venv if present.
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PY="$REPO_ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

# Entry point: run_cron.py (GHA + local cron)
ENTRY=(run_cron.py)

TMPDB="$(mktemp -t aolsmoke.XXXXXX).db"
trap 'rm -f "$TMPDB"' EXIT

# Deterministic offline config. Exported vars win over .env (load_dotenv override=False).
normalize() {
  FSM_SOURCE=mock \
  DRY_RUN=true \
  AGENT_MODE=oneshot \
  LLM_PROVIDER=heuristic \
  TRACKING_SOURCE=local \
  TRACKING_LOCAL_PATH="$TMPDB" \
  "$PY" -u "${ENTRY[@]}" 2>&1 \
    | grep -E '工单 .* →' \
    | sed -E 's/^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:,]+ \[[A-Z]+\] //; s/ \| [a-z_]+ [0-9]+tok [0-9]+ms$//'
}

OUT="$(normalize)"

if [ "${1:-}" = "--update" ]; then
  printf '%s\n' "$OUT" > "$BASELINE"
  echo "[smoke] baseline updated: $BASELINE ($(printf '%s\n' "$OUT" | grep -c '工单') orders)"
  exit 0
fi

if [ ! -f "$BASELINE" ]; then
  echo "[smoke] no baseline found; run: scripts/smoke.sh --update" >&2
  exit 2
fi

if diff <(printf '%s\n' "$OUT") "$BASELINE" >/tmp/smoke.diff 2>&1; then
  echo "[smoke] OK — output matches baseline ($(printf '%s\n' "$OUT" | grep -c '工单') orders)"
else
  echo "[smoke] DRIFT — engine output differs from baseline:" >&2
  cat /tmp/smoke.diff >&2
  exit 1
fi
