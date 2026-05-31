# 06 · LLM 提供方策略（免费为主，付费验证）

> 对齐团队实践：[stockwise](https://github.com) 后端已用 **hunyuan-lite** 作为 free tier 低成本模型。
> fs-aol 日常开发/试点 **默认混元**；DeepSeek 等仅用于**抽样质量验证**。

## 三档模式（`LLM_PROVIDER`）

| 值 | 用途 | 成本 | 何时用 |
|----|------|------|--------|
| **heuristic** | 启发式规则，不调 API | 0 | 只验证捞取、水位线、trace 表结构、企微格式（`DRY_RUN` 可配合） |
| **hunyuan**（默认） | 腾讯混元 Lite | 免费额度 | 日常 E2E、试点 cron、大批量跑通 |
| **deepseek** | DeepSeek Chat | 按量付费 | 每周抽 N 单对比质量；向业务演示「最好效果」 |

`DRY_RUN=true` **只影响企微是否真发**（开发 E2E 默认，详见私有文档 `docs/private/PRIV-07-dev-e2e-consensus.md`），不自动关闭 LLM。要零 API 调用请显式 `LLM_PROVIDER=heuristic`。

## 混元配置（与 stockwise 一致）

| 项 | 值 |
|----|-----|
| Base URL | `https://api.hunyuan.cloud.tencent.com/v1` |
| Model | `hunyuan-lite` |
| Key 环境变量 | `HUNYUAN_API_KEY`（或回退 `LLM_API_KEY`） |
| 协议 | OpenAI SDK 兼容 |
| JSON 输出 | prompt 约束 + 解析兜底（混元未开 `response_format`） |

stockwise 参考实现：
- `backend/engine/models/hunyuan_chain.py`
- `backend/engine/llm_registry.py`（`TENCENT_HUNYUAN` / `HUNYUAN_API_KEY`）
- `backend/migrations/seed_model_access_policy.py`（`hunyuan-lite` → free tier）

## DeepSeek 配置（验证用）

```
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

启用 `response_format=json_object`，适合结构化 Action Spec。

## trace 中的区分

`reasoning_traces.mode` 会记录：
- `heuristic`
- `llm_hunyuan` / `llm_deepseek`

便于 SQL 对比同一工单在不同模型下的建议差异。

## 单工单 A/B 对比脚本

```bash
python scripts/compare_llm_single_order.py --order-num GD2026057898
python scripts/compare_llm_single_order.py --order-num GD2026059389 --round round2 --providers hunyuan
# 产出：tmp/llm-compare/<工单号>/<时间戳[-round]>/{enrich,prompt_user,hunyuan,deepseek}.*
```

DeepSeek Key：fs-aol `.env` 的 `LLM_API_KEY` / `DEEPSEEK_API_KEY`，或 `DEEPSEEK_ENV_FILE`（默认会尝试 `stockwise/backend/.env`）。对比脚本与主引擎均会走 `suggestion_polish` 后处理（`--no-polish` 可关）。

## 参见

- [PUB-05-releases.md](PUB-05-releases.md) · 私有文档 `docs/private/PRIV-xlink-data.md` · [PUB-13-action-spec-v02.md](PUB-13-action-spec-v02.md)
