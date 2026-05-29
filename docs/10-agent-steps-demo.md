# 10 · Agent 多步骤展示轨（Demo Track）

> **与主轨关系**：v0.2 **试点**默认 `AGENT_MODE=oneshot`（不改变推送量与 KPI）。  
> **展示轨**用 `AGENT_MODE=steps` 证明：先查再建议，非一次性猜测。

## 1. 目标

| 观众问题 | 展示轨回答 |
|----------|-----------|
| 你们 Agent 只会一次出答案吗？ | 固定 **3 步剧本**，trace 可见每一步 |
| 建议依据是什么？ | **只读 tool** 返回报价/合同等事实，LLM 必须引用 |
| 会不会乱动系统？ | 仅只读 enrich；写操作在 v1.1 approval 之后 |

## 2. 固定剧本（v0.2.x）

```text
Step 0  摄取（已有）     → WorkOrder + event_type
Step 1  tool: enrich    → EnrichedContext（只读 Mongo）
Step 2  LLM 综合        → FollowUpSuggestion
Step 3  输出            → 企微预览 + reasoning_traces（含 steps_json）
```

不是开放 ReAct 循环；每单 **最多 1 次 tool + 1 次 LLM**。

## 3. 工具：`enrich_work_order_context`

**实现**：`agent_tools.py`（骨架 → v0.2.x 补全查询）

| 子查询 | 集合 | 目的 |
|--------|------|------|
| 是否已报价 | `order` | A/B 渠道（见业务字典） |
| 是否已签约 | `contract` | `contractStatus=10` 等 |
| （可选）流程摘要 | `workflowNode` | 最近节点备注 |

返回结构化 `EnrichedContext`，写入 trace `steps_json`。

## 4. Demo 脚本（ repeatable ）

### Demo A · 应跟进

- 条件：206，14 天内，有报价、无签约（tool 验证）
- 预期：`needs_follow_up=true`，`suggested_action` ∈ SOP 动作桶
- 展示点：卡片 / 日志中可见 tool 输出摘要

### Demo B · 不应硬跟

- 条件：tool 显示已签约，或业务标记丢单
- 预期：`needs_follow_up=false` 或「先核对系统状态」
- 展示点：对比 one-shot 胡催签约

运行示例：

```bash
AGENT_MODE=steps FSM_BATCH_LIMIT=1 LLM_PROVIDER=hunyuan \
  python agent_cron_engine.py --reset-tracking
sqlite3 agent_loop_tracking.db \
  "SELECT mode, substr(prompt_user,1,200) FROM reasoning_traces ORDER BY id DESC LIMIT 1;"
```

## 5. 配置

| 变量 | 默认 | 说明 |
|------|------|------|
| `AGENT_MODE` | `oneshot` | `steps` 开启展示轨 |
| `SOP_VERSION` | 空 | v0.4 拼入 sops/ |

## 6. 验收（并进主链前）

- [ ] `steps` 模式 trace 含 `steps_json`（至少 enrich 一步）
- [ ] enrich 实现后：同单重复跑 tool 结果一致
- [ ] 盲评 ≥15 单：步骤版「更可信」优于 oneshot
- [ ] P95 延迟可接受（ enrich + 1 LLM &lt; 30s ）
- [ ] 无严重 tool/事实幻觉（契约测试）

## 7. 版本归属

| 版本 | 内容 |
|------|------|
| **v0.2.x** | `AGENT_MODE` + enrich 骨架 → 只读 enrich 实现 |
| **v0.4** | SOP 场景引用 tool 字段 |
| **v0.5** | 对比 oneshot / steps 采纳率 |
| **v1.1** | `evidence_refs` ← tool 输出 |

## 参见

- [09-business-decisions.md](09-business-decisions.md) · [08-follow-up-wedge-spec.md](08-follow-up-wedge-spec.md)
- [agent_tools.py](../agent_tools.py)
