# Agent Console (web) · v1.0 console-mvp

产品轨第一个可见界面（FS-AOL 产品脊柱 **S1 总览 + S2 处置 + S3 信任轨**）。
Python 引擎在 GitHub Actions 里写入追踪库，本应用读取同一个库，让人**在产品内看见并处置**跟进建议。

- **栈**：Next.js (App Router) + Tailwind v4 + shadcn/ui + `@libsql/client`
- **链接层**：libSQL/Turso。本地默认直接读引擎的 `../agent_loop_tracking.db`；
  生产把 `LIBSQL_URL` 指向同一个 Turso 库即可，**零后端改造**。
- 设计与纪律见 [`../docs/public/PUB-07-product-surface.md`](../docs/public/PUB-07-product-surface.md)。

## 本地运行

```bash
pnpm install
pnpm dev          # http://localhost:3000
```

默认无需任何环境变量：直接读取仓库根的 `agent_loop_tracking.db`。
若该库为空，先让引擎跑一轮（仓库根）：

```bash
FSM_SOURCE=mock LLM_PROVIDER=heuristic AGENT_MODE=steps python agent_cron_engine.py
```

## 页面

| 路由 | 脊柱 | 说明 |
|------|------|------|
| `/` | S1 | 建议总览：处置率/优先级统计 + 列表 |
| `/suggestions/[key]` | S2 + S3 | 跟进方案 + 同意/拒绝/修改；推理与查证轨 |
| `POST /api/outcomes` | — | 审批回写 `suggestion_outcomes`（链接层契约） |

## 数据契约（链接层表）

- 读：`ai_follow_up_logs`（建议 JSON）、`reasoning_traces`（推理轨/查证）
- 写：`suggestion_outcomes`（同意/拒绝/修改 + 可选修改后方案）
