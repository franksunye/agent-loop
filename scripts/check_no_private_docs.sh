#!/usr/bin/env bash
set -euo pipefail

# Block private docs from being committed.
staged="$(git diff --cached --name-only)"
if [[ -z "${staged}" ]]; then
  exit 0
fi

violations="$(printf '%s\n' "${staged}" | rg '^(docs/private/|docs/PRIV-.*\.md$)' || true)"
if [[ -n "${violations}" ]]; then
  echo "ERROR: Private docs cannot be committed:"
  printf '%s\n' "${violations}"
  echo "Move enterprise-only content under docs/private/ and keep local-only."
  exit 1
fi
