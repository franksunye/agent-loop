# 08 · Follow-up Action Engine 规格（v0.2 SSOT）

> 研讨共识：这是第一个 **Agentic wedge**——高频、ROI 清晰、wait→follow-up 明确、
> 可 approval、可演进为 event/action/approval 基础设施。

## 1. 产品定义

在工单处于 **需要人推进** 的状态且超过 SLA 时，为归属管家生成 **可审批的 Action Spec**。
默认 **不自动触客**；人类采纳后计入闭环，用于衡量推进率/签约贡献。

```text
Event → Reasoning → Suggestion(Action Spec) → Approval → Action（逐步放开）
```

## 2. Event 目录（Phase 1 / v0.2）

### 业务口径（已定）

- **纳入**：`status=206`（待签约 / 跟进签约）——管家主战场，直接关联签约收入。
- **不纳入**：`status=204`（上门未成交）——**无需管家跟进**（销售/其他流程处理，或视为已失活商机）。

默认配置：`FSM_EVENT_STATUSES=206`

| 优先级 | event_type | 触发 | 业务意图 |
|--------|------------|------|----------|
| **P0** | `STALE_SIGN_PENDING` | `status=206` 且 **最近 14 天内有更新** | 待签约推进 |
| — | ~~`STALE_VISIT_NO_DEAL`~~ | ~~`status=204`~~ | **v0.2 排除** |
| P1 | `PAYMENT_PENDING` | `status=205` 且停留 ≥ N 天 | 催首付（后续） |
| P1 | `COMPLETED_CARE` | `status=403` 完工后 T+N | 满意度/复购（v0.1） |

**归属**：`serviceAppointment.exts.supervisorId` = 管家 `user._id`  
**去重**：追踪库键 `(event_type, work_order_id)`  
**时间窗**：`updateTime` 在最近 **14 天**内（`FSM_MAX_AGE_DAYS=14`）；超过 2 周不再跟进。  
可选 `FSM_STALE_DAYS`：要求至少停滞 N 天（默认 0，不启用）。

## 3. Action Spec 输出（v0.2 最小扩展）

在 `FollowUpSuggestion` 之上增加事件上下文（引擎内部可扁平存储）：

| 字段 | 说明 |
|------|------|
| `event_type` | 上表枚举 |
| `stale_days` | 在当前 status 停留天数 |
| `housekeeper_id` | `exts.supervisorId` |
| `needs_follow_up` | bool |
| `priority` | high / medium / low |
| `reason` | 因果说明 |
| `suggested_action` | 具体一步 |
| `customer_sentiment` | positive / neutral / negative |

v1.1 再拆独立 `action_spec` / `approval` 表与 JSON Schema。

## 4. 推理输入（只读）

1. 工单：`orderNum, title, describe, status→taskType, city, 联系人`
2. 停滞：`updateTime` → `stale_days`
3. （v0.4）关联 `order` / `contract`、`workflowNode`

## 5. 试点管家（生产只读，206 且 updateTime 在 14 天内）

| 管家 | **14 天内 206**（引擎池） | 原「停滞 7d+」全量 206 |
|------|-------------------------|----------------------|
| 刘沐泽 | **13** | 714 |
| 李小军 | **5** | 672 |
| 刘清瑞 | **8** | 748 |
| 李俊达 | **12** | 363 |

业务规则：**超过 2 周未更新的 206 不再跟进**（已无意义）。

口径见 `xlink/docs/z.其它/业务字典-生产统计口径.md`；工单归属 `exts.supervisorId`。

### 生产 userId（`exts.supervisorId`）

| 管家 | userId |
|------|--------|
| 刘沐泽 | `3439283044423912324` |
| 李小军 | `7897213176257951252` |
| 刘清瑞 | `2699508216270113110` |
| 李俊达 | `8680761575588344623` |

### 环境变量（试点过滤 / 分送）

```bash
FSM_EVENT_STATUSES=206
FSM_MAX_AGE_DAYS=14
FSM_PILOT_HOUSEKEEPERS=刘沐泽,李小军,刘清瑞,李俊达
# FSM_PILOT_HOUSEKEEPER_IDS=...
# WECOM_WEBHOOK_MAP=userId:https://qyapi.weixin.qq.com/...
```

未配置 `FSM_PILOT_*` 时不过滤管家（全量，需 `FSM_BATCH_LIMIT` 控量）。

## 6. 成功指标（v0.2 试点）

| 指标 | 定义 |
|------|------|
| 曝光 | 推送 / 预览条数 |
| 采纳 | 人工标记「已跟进」 |
| 推进 | 7 天内 **离开 206**（签约或状态推进）的比例 |

## 7. 与 v0.1 差异

| v0.1 | v0.2 |
|------|------|
| 仅 `403` 完工 | P0：**仅 `206` 待签约** 停滞 |
| 无管家路由 | 按 `supervisorId` 分送 |
| 扁平建议 | 带 `event_type` + `stale_days` |

## 参见

- [05-releases.md](05-releases.md) · [xlink-data.md](xlink-data.md) · [07-dev-e2e-consensus.md](07-dev-e2e-consensus.md)
