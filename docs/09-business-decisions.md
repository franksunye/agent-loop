# 09 · 业务决策记录（ADR）

> **目的**：把研讨与数据验证达成的管理经验写成 SSOT，供产品、运营、工程共用。  
> **纪律**：规则层（L1）走配置与代码，不靠 LLM 猜测；变更须附数据依据与复审日期。

## 索引

| ID | 决策 | 状态 | 复审 |
|----|------|------|------|
| [ADR-001](#adr-001-follow-up-wedge-切口) | Follow-up Action Engine 为首个 Agent 切口 | 已采纳 | — |
| [ADR-002](#adr-002-仅跟进-status206) | 仅跟进 206 待签约，不跟 204 | 已采纳 | 2026-06-30 |
| [ADR-003](#adr-003-14-天时间窗) | 仅 `updateTime` 最近 14 天内的 206 | 已采纳 | 2026-06-30 |
| [ADR-004](#adr-004-四位管家试点) | 试点四位管家 + 可选分群 webhook | 已采纳 | 试点结束后 |
| [ADR-005](#adr-005-人类审批再触达) | suggestion → approval，默认不自动触客 | 已采纳 | v1.0 前 |
| [ADR-006](#adr-006-知识分层节奏) | L1 规则 now，L2 SOP 试点后，L3 案例有度量后 | 已采纳 | v0.4 前 |
| [ADR-007](#adr-007-agent-展示轨) | 多步骤展示轨 `AGENT_MODE=steps`，默认仍 oneshot | 已采纳 | v0.2.x |

---

## ADR-001: Follow-up wedge 切口

**背景**：Agent 化需选高频、ROI 清晰、容错高、可 approval 的场景。

**决策**：以 **Follow-up Action Engine** 为第一个 Agentic wedge——`wait → follow-up`，沉淀 `event / action / approval` 基础设施。

**依据**：研讨共识表（高频、跟进=收入、数据结构清晰、可逐步 autonomous）。

**影响**：POC 不追求改 XLink FSM；只读摄取 + 企微/未来 CRM 卡片。

---

## ADR-002: 仅跟进 status=206

**背景**：原摄取含 206（待签约）与 204（上门未成交）；生产池子 900+ / 人。

**决策**：**`FSM_EVENT_STATUSES=206`**；204 不纳入管家跟进。

**依据（业务）**：上门未成交无需管家跟进，由其他流程或视为失活商机。

**依据（数据）**：生产四位管家 206+204 合并池远大于仅 206；204 对李俊达等占比较高但与签约主路径无关。

**配置**：`domain.P0_FOLLOW_UP_STATUSES = ("206",)`

**复审**：确认 204 是否有独立角色需另开 event（非本引擎）。

---

## ADR-003: 14 天时间窗

**背景**：`FSM_STALE_DAYS=7`（至少 7 天未更新）仍命中数百条/人，多为 90 天～1 年以上老单。

**决策**：**超过 2 周未更新的 206 不再跟进**；`FSM_MAX_AGE_DAYS=14`（`updateTime >= 现在-14天`）。默认取消「最少停滞 7 天」（`FSM_STALE_DAYS=0`）。

**依据（业务）**：超过 2 周再跟意义不大，机会已凉。

**依据（数据，生产 xlink，四位管家，仅 206）**：

| 管家 | 14 天内 206 | 原「7d+未更新」206 |
|------|------------|-------------------|
| 刘沐泽 | 13 | 714 |
| 李小军 | 5 | 672 |
| 刘清瑞 | 8 | 748 |
| 李俊达 | 12 | 363 |

**配置**：`FSM_MAX_AGE_DAYS=14`

**可选增强**：若需「至少卡 2～3 天再提醒」，设 `FSM_STALE_DAYS=2` 形成 2～14 天带。

**复审**：试点 2 周后看 14 天内单的采纳率与推进率，是否收紧为 7 天或放宽。

---

## ADR-004: 四位管家试点

**背景**：全量管家 × 全量 206 不可试点；需可衡量 ROI。

**决策**：试点 **刘沐泽、李小军、刘清瑞、李俊达**；`FSM_PILOT_HOUSEKEEPERS` 或 `FSM_PILOT_HOUSEKEEPER_IDS`；可选 `WECOM_WEBHOOK_MAP` 分群。

**依据（数据）**：生产只读业绩与停滞单量（见 [08-follow-up-wedge-spec.md](08-follow-up-wedge-spec.md)）。

**生产 userId**：见 08 文档。

**纪律**：`FSM_BATCH_LIMIT` 控每轮 LLM/推送量；开发库姓名可能对不上，dev E2E 用 ID。

**复审**：试点结束后决定是否扩管家或扩城市。

---

## ADR-005: 人类审批再触达

**背景**：自动触客风险高，管理层难接受。

**决策**：引擎只产出 **Suggestion**；默认 `DRY_RUN=true` 企微预览；真发与触客需显式配置与审批（v1.1+ 回写 approval）。

**依据**：研讨 Human-in-the-Loop；01-vision Phase 1 黑盒验证。

**复审**：v1.0 Live 前安全与合规签字。

---

## ADR-006: 知识分层节奏

**背景**：是否将管理经验全部做成 LLM 知识库？

**决策**：

| 层 | 内容 | 时机 |
|----|------|------|
| **L1 规则** | 206 only、14 天、管家、幂等 | **现在**（08/09 + env） |
| **L2 SOP** | 分场景话术与建议动作 | **v0.4**，试点有采纳反馈后 |
| **L3 案例** | 历史推进率、有效动作 | **v0.5+**，度量与回灌后 |

**纪律**：L1 不进 prompt 让模型猜；L2 以 `sops/` 版本化拼入 system prompt（见 [sops/README.md](../sops/README.md)）。

**复审**：v0.4 启动前评估试点样本是否够写 SOP v1。

---

## ADR-007: Agent 展示轨

**背景**：早期 POC 需展示非 one-shot：多步骤 + 工具调用，且可审计。

**决策**：

- 主轨试点默认 **`AGENT_MODE=oneshot`**（不改变 KPI）。
- 展示轨 **`AGENT_MODE=steps`**：固定剧本 `enrich（只读 tool）→ 1×LLM → 卡片`。
- 步骤写入 `reasoning_traces.steps_json`；详见 [10-agent-steps-demo.md](10-agent-steps-demo.md)。

**纪律**：工具仅只读；不做开放 ReAct；写操作留给 v1.1 approval 之后。

**复审**：enrich 实现 + 盲评通过后，再考虑默认 steps。

---

## 变更流程

1. 业务/运营提出口径变化 → 在本文件新增 ADR 或修订条目。  
2. 用生产只读数据验证影响面（条数、管家分布）。  
3. 同步更新 `08-follow-up-wedge-spec.md`、`.env.example`、`domain.py` 常量（若涉及系统码）。  
4. PR 注明「口径版本」与是否影响历史报表。

## 参见

- [08-follow-up-wedge-spec.md](08-follow-up-wedge-spec.md) · [05-releases.md](05-releases.md) · [01-vision.md](01-vision.md)
