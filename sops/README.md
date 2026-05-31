# SOP 知识库（L2 · v0.4 启用）

> **当前阶段（v0.2）**：仅大纲占位，**不**默认拼入 LLM prompt。  
> 规则层（L1）见 [docs/09-business-decisions.md](../docs/09-business-decisions.md)。  
> 运营经验（部位/渠道价值，已进 enrich「业务提示」）见 [docs/12-business-knowledge-follow-up.md](../docs/12-business-knowledge-follow-up.md)。

## 版本约定

| 文件 | 状态 | 启用方式 |
|------|------|----------|
| [206-sign-pending-v1-outline.md](206-sign-pending-v1-outline.md) | 大纲 | `SOP_VERSION=` 空（默认） |
| `206-sign-pending-v1.md` | 待业务填写 | 未来 `SOP_VERSION=v1` |

## 维护纪律

- 每条 SOP 场景需：**触发条件 / 建议动作 / 避免事项 / 样例（可选）**
- 变更走 ADR 或 09 文档复审日期
- 禁止在 `run_cron.py` / `packages/aol` 编排层硬编码业务 if-else；场景逻辑进 SOP 或 `domain.py` 码表

## 参见

- [docs/06-llm-providers.md](../docs/06-llm-providers.md) · [docs/05-releases.md](../docs/05-releases.md) v0.4
