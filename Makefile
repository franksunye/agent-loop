.PHONY: smoke dev cron install

PY ?= python3
ifeq ($(wildcard .venv/bin/python),)
else
  PY := .venv/bin/python
endif

smoke:
	bash scripts/smoke.sh

dev:
	pnpm --filter console dev

cron:
	$(PY) run_cron.py

install:
	$(PY) -m pip install -e packages/aol
	pnpm install
