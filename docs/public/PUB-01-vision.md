# 01 · 愿景与战略切入点

## 一句话愿景

> **Field Service Agent Operating Layer（FS-AOL）是服务行业的 System of Action。**
>
> 它建立在 FSM 之上，通过一组持续协作的业务 Agent，帮助服务型企业自动推进
> 从获客、报价、成交、交付到回款的完整生命周期，让每一家中小企业都拥有
> 一支**数字运营团队**。

当我们开始讨论 Qualification / Estimate / Follow-up / Closing 这些 Agent 时，
本质上已经不再是在设计一个 FSM 模块，而是在**定义一种新的软件架构**。

---

## 从「记录业务」到「运营业务」

| | 传统软件 | 未来软件 |
|---|---|---|
| 范式 | **System of Record** | **System of Action** |
| 职责 | 保存事实 | 推动行动 |
| 回答 | 记录发生了什么 | 决定下一步应该发生什么 |

- 过去 20 年，`CRM / ERP / FSM` 改变了企业**记录**业务的方式。
- 未来 20 年，**Agent Operating Layer** 将改变企业**运营**业务的方式。

FSM 告诉你「发生了什么」；AOL 告诉你「下一步做什么，并帮你完成它」。

---

## 核心使命（Mission）

帮助每一家服务型企业拥有一支**数字运营团队**。

- 不是一个 AI 助手；
- 不是一个聊天机器人；
- 而是一组能够**持续推进业务流程**的 Agent。

### 未来的组织形态

```text
今天                  未来
老板                  老板
 ↓                     ↓
销售                  Agent Team
 ↓                     ↓
客服                  员工
 ↓
调度
 ↓
施工
```

- **员工负责**：判断、沟通、执行、关系建立。
- **Agent 负责**：跟踪、分析、决策建议、流程推进。

---

## 产品定位：Agent Layer Above FSM

```text
                      AOL（驱动行动）
────────────────────────────────────────
  Qualification · Estimate · Follow-up · Closing
  Scheduling · Dispatch · Procurement · Collection
────────────────────────────────────────
                      FSM（存储事实）
  Customer · Lead · Quote · Job · Invoice
```

- **FSM 负责**：存储事实。
- **AOL 负责**：驱动行动。

---

## 长期架构（五层）

| 层 | 名称 | 职责 |
|---|------|------|
| L1 | **System of Record（数据层）** | Customer / Lead / Quote / Job / Invoice / Payment；来源可为自有 FSM、第三方 FSM、CRM、ERP、Excel |
| L2 | **Context Layer（业务上下文层）** | 统一客户画像、统一项目画像、统一时间线、统一业务状态 |
| L3 | **Agent Runtime（运行时）** | 启动 / 暂停 Agent、Agent 通信、Agent 记忆、状态管理 |
| L4 | **Decision Layer（决策层）** | 优先级排序、成交预测、风险识别、策略推荐、资源分配 |
| L5 | **Action Layer（执行层）** | 发微信 / 短信、生成报价、创建任务 / 工单、通知员工 |

> 数据在最底层，行动在最顶层。AOL 的价值在于把「事实」逐层升华为「被执行的决策」。

---

## Agent 演进路线

### 第一代 · 获客到成交（销售域）

| Agent | 目标 | 输入 | 输出 |
|-------|------|------|------|
| **Qualification** | 识别高价值客户 | 电话 / 微信 / 表单 / 广告线索 | 客户等级、成交概率、跟进建议 |
| **Estimate** | 生成专业报价 | 现场信息 / 图片 / 视频 / 工程规范 | 报价单、材料单、风险说明 |
| **Follow-up** | 防止客户流失 | 沟通记录 / 报价记录 / 客户行为 | 下一步行动、推荐话术、自动提醒 |
| **Closing** | 提升成交率 | 报价历史 / 跟进历史 / 客户特征 | 成交策略、折扣建议、升级建议 |

### 第二代 · 进入交付域

- **Scheduling Agent**：排班、资源协调
- **Dispatch Agent**：派工、路线优化
- **Procurement Agent**：材料采购、库存预测
- **Collection Agent**：催款、回款预测

### 第三代 · 跨 Agent 协作（完整闭环）

```text
Qualification → Estimate → Follow-up → Closing → Dispatch → Collection
```

形成从线索到回款的完整业务闭环。

---

## AOL Core（未来平台资产）

真正的长期产品资产是支撑多 Agent 协作的运行时内核：

| 组件 | 职责 | 示例 |
|------|------|------|
| **Event Bus** | 业务事件总线 | `LeadCreated` / `QuoteSent` / `CustomerSilent` / `JobCompleted` / `PaymentReceived` |
| **Memory** | 长期业务记忆 | 客户偏好、成交规律、历史案例、区域经验 |
| **Workflow Engine** | Agent 协作编排 | Agent→Agent / Agent→Human / Human→Agent |
| **Approval Engine** | 关键审批 | 大额报价、特殊折扣、退款申请 |
| **Metrics Engine** | 衡量 Agent 价值 | 成交率、回访率、报价速度、回款周期 |

---

## 战略切入点：不要「毕其功于一役」

愿景虽大，落地必须克制。企业级软件（B2B SaaS）的 Agent 化最忌讳宏大叙事——
高昂的试错成本 + Agent 的不确定性，会迅速透支管理层的信任。

正确做法：**选一个痛点极深、闭环极短、容错极高、收益可量化的场景先撕开口子**，
用两周证明价值，再逐步沉淀底层资产。

我们选择的第一个楔子是 **Follow-up Agent（跟进行动引擎）**。

### 为什么是 Follow-up

**1. 痛点极深、闭环极短（易于证明）**

防水维修等现场服务行业，大量流失发生在**勘查/施工完毕后的「跟进真空期」**：

- **现状**：师傅上门看完、拍照、回去了。但核心信息——
  *「建议注浆，但业主嫌贵想先观察」*、*「3 号裂缝涉及邻里纠纷，需物业协调」*
  ——因为口音、字迹、遗忘，沉淀在系统角落，无人跟进。
- **Agent 切入**：工单进入待签约/停滞的瞬间引擎启动，自动提取非结构化文本与系统查证，
  生成精准的**下一步行动建议**（推进签约 / 自动起草二次报价 / 提醒协调邻里）。
- **可量化闭环**：建议是否被采纳？二次触达转化率提升多少？工单流转缩短多少？
  **一两周内就能用数据向公司证明转化与效率提升。**

**2. 完美的 Human-in-the-Loop 缓冲带**

引擎只在后台生成 `Suggestion`，由客服/销售/主管点「同意/发送/执行」，
**不直接联系客户、不直接扣款**。

- **对公司**：零安全风险，高管不担心 AI 胡说得罪客户。
- **对 Agent**：规划错了，人类一键拒绝即可，不造成业务灾难，容错率极高。

### Follow-up 是 AOL 的第一块拼图

我们不是在做「防水维修跟进工具」，而是在用最接地气的业务，
打磨 AOL 的最小可用内核：

> 工单事件 = `Event` → AI 建议 = `Suggestion` → 人工点发送 = `Approval` → 系统执行 = `Action`

这正是上文 AOL Core（Event Bus / Memory / Workflow / Approval / Metrics）的最小竖切。
Follow-up 跑通后，同一套运行时即可接入 Qualification、Estimate、Closing 等后续 Agent，
并最终复用到 CRM、招聘（面试后跟进）、医疗（出院随访）等所有服务行业。

---

## 终局判断

再往前推 5～10 年，FS-AOL 的终局不是「AI 功能」，而是成为服务行业的「操作系统」：

> **FSM 记录世界发生了什么，而 AOL 决定接下来应该发生什么。**

---

## 衡量成功（Stage 0 → Stage 1）

- **业务指标**：AI 提醒的跟进，多捞回 X 个订单 / 提升 Y% 转化率 / 缩短 Z% 流转时间。
- **信任指标**：业务部门主动要求「把这个建议接进我们的操作界面」。
- **架构指标**：同一运行时能以最小改动接入第二个 Agent（验证 AOL 的可复用性）。
