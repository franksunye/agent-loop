# FS-AOL Monorepo

Field Service Agent Operating Layer — Python 跟进引擎 + Next.js 审批 Console，共享 Turso 追踪库与跨语言契约。

GitHub: [franksunye/fs-aol](https://github.com/franksunye/fs-aol)

## Layout

```
fs-aol/
├── apps/console/          # Next.js 审批面板（Vercel Root Directory）
├── data/                  # 本地 sqlite 追踪库（gitignore *.db；见 data/.gitkeep）
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
# Python 引擎（零依赖冒烟，v0.1 403 路径）
make smoke

# 本地 v0.2.x 业务闭环（mock 206 + 四位管家 + sqlite + Console）
make seed-local          # 写入 data/agent_loop_tracking.db
cp apps/console/.env.local.sqlite.example apps/console/.env.local
make dev                 # http://localhost:3000

# 或一键脚本
bash scripts/dev-local.sh
```

## Local v0.2.x loop (recommended for feature testing)

| Step | Command |
|------|---------|
| 1. Seed mock 206 data | `make seed-local` |
| 2. Console env | `cp apps/console/.env.local.sqlite.example apps/console/.env.local` |
| 3. Start UI | `make dev` → http://localhost:3000 |
| 4. Test filter | 管家收件箱切换 → URL `?hk=...`，各管家 1 条 |
| 5. Test actions | 详情：阻塞 A/B/C/D、已跟进、同意/拒绝 |
| 6. Re-run engine | `FSM_SOURCE=mock FSM_EVENT_STATUSES=206 TRACKING_LOCAL_PATH=data/agent_loop_tracking.db make cron` |

引擎与 Console **必须共用同一库**：默认 `data/agent_loop_tracking.db`（`LIBSQL_URL=file:../../data/agent_loop_tracking.db`）。

```bash
# 旧：仅 v0.1 冒烟
FSM_SOURCE=mock LLM_PROVIDER=heuristic DRY_RUN=true python run_cron.py
```

## Common commands

| Command | Description |
|---------|-------------|
| `make smoke` | 离线 DRY_RUN 回归，对比 `scripts/smoke_baseline.txt` |
| `make seed-local` | mock 206 写入 `data/agent_loop_tracking.db`（v0.2 闭环） |
| `make dev-local` | seed-local + 启动 Console |
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
