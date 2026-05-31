# Agent-Loop 文档

> 本目录是 agent-loop 的「共识层」。所有战略与设计先落成文字，再随市场反馈迭代。
> 文档是活的，欢迎 PR 修订。

## 一屏看懂

**一句话**：用最接地气的传统业务（防水维修工单跟进），撕开口子，构建服务行业的
**Field Service Agent Operating Layer（FS-AOL）**——FSM 之上的 System of Action。

| 维度 | 内容 |
|------|------|
| **目标** | 在 FSM 之上构建 AOL：一组持续协作的业务 Agent，自动推进获客→报价→成交→交付→回款 |
| **切入** | 现场服务工单的「跟进真空期」——痛点深、闭环短、容错高、可量化（Follow-up Agent 作楔子） |
| **路径** | Stage 0 闭环系统 → Stage 1 Agent Runtime → Stage 2 AOL Core → Stage 3 开源生态 |
| **产品化** | 两轨纪律：`poc-*` 验证（headless）/ `vX.Y` 产品轨（必有 UI+UX+可感知 KPI）。见 [PUB-07](public/PUB-07-product-surface.md) |
| **当下** | Stage 0：`poc-followup` 引擎已跑通并对 XLink 真实工单库（生产只读）验证；产品起点 = v1.0 Console MVP |

## 核心隐喻

> 工单完工 = `Event`；AI 生成的二次报价/关怀 = `Suggestion`；销售点「发送」= `Approval`。

整个系统就是把这三件事，做成任何行业（CRM / 招聘 / 医疗随访）都能复用的基础设施。

> **能复用的前提**：Agent 必须在**领域语言**里思考，而不是 XLink 的系统黑话
> （`status=403`）。领域语义层 = Agent 的语义层，是通用化的命门。见
> [04-domain-semantics](public/PUB-04-domain-semantics.md)。

## 文档分层（公开 / 本地私有）

### A. 公开文档（可进 Git）

| 文档 | 说明 |
|------|------|
| [PUB-01-vision.md](public/PUB-01-vision.md) | **为什么**：FS-AOL 愿景（System of Action）+ Follow-up 楔子论证 |
| [PUB-02-architecture.md](public/PUB-02-architecture.md) | **是什么**：FS-AOL 架构规格 v1.0（8 大组件 + 业务 Agent + 四原语） |
| [PUB-03-roadmap.md](public/PUB-03-roadmap.md) | **怎么走**：平台演进 Stage 0→3（闭环→Runtime→AOL Core→开源） |
| [PUB-04-domain-semantics.md](public/PUB-04-domain-semantics.md) | **用什么语言思考**：领域语义对齐（Agent 的语义层） |
| [PUB-changelog.md](public/PUB-changelog.md) | **版本摘要表**：每版一行，讨论功能放进哪个小版本 |
| [PUB-05-releases.md](public/PUB-05-releases.md) | **发哪些版**：两轨（POC vs 产品轨）+ 产品 OKR/KPI 总表 → Live |
| [PUB-06-llm-providers.md](public/PUB-06-llm-providers.md) | **用什么模型**：混元 Lite 日常 + DeepSeek 抽样验证 |
| [PUB-07-product-surface.md](public/PUB-07-product-surface.md) | **怎么变成产品**：两轨纪律 + 产品脊柱 S1–S6（UI/UX）+ 产品化 DoD |
| [PUB-13-action-spec-v02.md](public/PUB-13-action-spec-v02.md) | **跟进建议 JSON v0.2**（输出结构） |
| [sops/](../sops/README.md) | **L2 SOP**（v0.4 启用，当前为大纲） |
| [PUB-private-docs-template.md](public/PUB-private-docs-template.md) | 私有文档管理模板与边界 |

### B. 本地私有文档（企业内部，不进 Git）

命名与目录规则（双保险）：

- 目录：`docs/private/`
- 文件前缀：`PRIV-`
- Git 忽略：`.gitignore` 中 `docs/private/**` 与 `docs/PRIV-*.md`

示例（本地存在，不入库）：

- `docs/private/PRIV-xlink-data.md`
- `docs/private/PRIV-09-business-decisions.md`

维护原则：公开文档写“方法与架构”，私有文档写“企业规则、生产口径、内部 SOP、账号与运维细节”。

## 防误提交流程（推荐）

可将私有文档拦截脚本挂到本地 pre-commit：

```bash
ln -sf ../../scripts/check_no_private_docs.sh .git/hooks/pre-commit
```

脚本位置：`scripts/check_no_private_docs.sh`（拦截 `docs/private/**` 与 `docs/PRIV-*.md`）。

## 状态

- 版本：POC `poc-followup`（原 v0.1/v0.2）已跑通；产品轨起点 **v1.0 Console MVP** 待启动
- 阶段：Stage 0 闭环系统（FS-AOL 楔子）
- 最近更新：2026-05-31
