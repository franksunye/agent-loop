# Agent-Loop 文档

> 本目录是 agent-loop 的「共识层」。所有战略与设计先落成文字，再随市场反馈迭代。
> 文档是活的，欢迎 PR 修订。

## 一屏看懂

**一句话**：用最接地气的传统业务（防水维修工单跟进），喂养一个最具前瞻性的
Agent-native 底层架构。

| 维度 | 内容 |
|------|------|
| **目标** | 把「事件 → AI 建议 → 人工一键审批 → 执行」做成通用的 Agent-native 工作流运行时 |
| **切入** | 现场服务工单完工后的「跟进真空期」——痛点深、闭环短、容错高、可量化 |
| **路径** | 黑盒验证 → 白盒内聚 → 抽象解耦开源 |
| **当下** | 阶段 1（黑盒验证）的最小引擎已跑通，并对 XLink 真实工单库验证 |

## 核心隐喻

> 工单完工 = `Event`；AI 生成的二次报价/关怀 = `Suggestion`；销售点「发送」= `Approval`。

整个系统就是把这三件事，做成任何行业（CRM / 招聘 / 医疗随访）都能复用的基础设施。

> **能复用的前提**：Agent 必须在**领域语言**里思考，而不是 XLink 的系统黑话
> （`status=403`）。领域语义层 = Agent 的语义层，是通用化的命门。见
> [04-domain-semantics](04-domain-semantics.md)。

## 文档导航

| 文档 | 说明 |
|------|------|
| [01-vision.md](01-vision.md) | **为什么**从「跟进行动引擎」撕口子（业务+战略论证） |
| [02-architecture.md](02-architecture.md) | **是什么**：目标架构（三层运行时）与四大原语 |
| [03-roadmap.md](03-roadmap.md) | **怎么走**：三阶段战略三阶段（黑盒→白盒→开源） |
| [04-domain-semantics.md](04-domain-semantics.md) | **用什么语言思考**：领域语义对齐（Agent 的语义层） |
| [05-releases.md](05-releases.md) | **发哪些版**：可发布小版本迭代 → Phase1/2 Live |
| [06-llm-providers.md](06-llm-providers.md) | **用什么模型**：混元 Lite 日常 + DeepSeek 抽样验证 |
| [07-dev-e2e-consensus.md](07-dev-e2e-consensus.md) | **开发 E2E 约定**：默认不真发企微，真发需显式说明 |
| [08-follow-up-wedge-spec.md](08-follow-up-wedge-spec.md) | **v0.2 SSOT**：Follow-up wedge / 试点管家 |
| [09-business-decisions.md](09-business-decisions.md) | **业务 ADR**：206 only、14 天窗、知识分层 |
| [xlink-data.md](xlink-data.md) | XLink 工单数据口径（连接 / 字段 / 已验证查询） |
| [sops/](../sops/README.md) | **L2 SOP**（v0.4 启用，当前为大纲） |

## 状态

- 版本：**v0.1.0 已发布** · **v0.2 开发中**
- 阶段：Phase 1 黑盒验证
- 最近更新：2026-05-29
