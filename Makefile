.PHONY: smoke dev cron install dev-local seed-local

PY ?= python3
ifeq ($(wildcard .venv/bin/python),)
else
  PY := .venv/bin/python
endif

smoke:
	bash scripts/smoke.sh

dev:
	pnpm --filter console dev

# 本地 v0.2.x 闭环：mock 206 → sqlite → Console
seed-local:
	bash scripts/dev-local.sh seed

dev-local: seed-local
	pnpm --filter console dev

cron:
	$(PY) run_cron.py

install:
	$(PY) -m pip install -e packages/aol
	pnpm install
