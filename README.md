# FS-AOL Monorepo (agent-loop)

Field Service Agent Operating Layer — Python 跟进引擎 + Next.js 审批 Console，共享 Turso 追踪库与跨语言契约。

## Layout

```
agent-loop/
├── apps/console/          # Next.js 审批面板（Vercel Root Directory）
├── packages/aol/          # Python 引擎（pip install -e packages/aol）
├── contracts/             # 跨语言 SSOT：DDL + Action Spec JSON Schema
├── docs/public/           # 架构 / 规格公开文档
├── run_cron.py            # GHA / 本地 cron 入口
├── scripts/smoke.sh       # 离线回归护栏（mock + heuristic）
├── Makefile               # 常用命令快捷入口
└── pnpm-workspace.yaml    # apps/* 工作区
```

## Prerequisites

- Python 3.10+，可选 `.venv`
- Node 20+，`pnpm`（`corepack enable`）
- Turso 凭证（Console 云库 / GHA cron）：`LIBSQL_URL` + `LIBSQL_AUTH_TOKEN`（Console）或 `TURSO_URL` + `TURSO_TOKEN`（引擎）

## Quick start

```bash
# Python 引擎（零依赖冒烟）
make smoke
# 或
FSM_SOURCE=mock LLM_PROVIDER=heuristic DRY_RUN=true python run_cron.py

# Console 本地开发（默认 http://localhost:3000，可 PORT=3477）
pnpm install
cp apps/console/.env.example apps/console/.env.local   # 填 LIBSQL_URL 等
make dev
```

## Common commands

| Command | Description |
|---------|-------------|
| `make smoke` | 离线 DRY_RUN 回归，对比 `scripts/smoke_baseline.txt` |
| `make dev` | 启动 Console（`pnpm --filter console dev`） |
| `make cron` | 本地跑一轮 cron（读 `.env`） |
| `make install` | `pip install -e packages/aol` + `pnpm install` |

## Contracts (single source of truth)

| File | Purpose |
|------|---------|
| `contracts/aol_schema.sql` | Turso/sqlite 表 DDL（`{{AOL_TABLE_PREFIX}}` 占位） |
| `contracts/tables.json` | 表名后缀（Python + Console 共用） |
| `contracts/suggestion.schema.json` | Action Spec v0.2 中文键 JSON Schema |

表名前缀环境变量：`AOL_TABLE_PREFIX`（默认 `aol_`）。

## Deployment

- **GHA cron**：`.github/workflows/agent_cron.yml` → `python run_cron.py`（生产 mongo 只读，默认 `DRY_RUN=true`）
- **Vercel Console**：Root Directory = `apps/console`，配置 `LIBSQL_URL` / `LIBSQL_AUTH_TOKEN`

## Docs

战略与架构见 [`docs/README.md`](docs/README.md) · [`docs/public/PUB-02-architecture.md`](docs/public/PUB-02-architecture.md)
