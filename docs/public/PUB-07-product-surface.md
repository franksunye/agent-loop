# 07 · 产品脊柱与产品化纪律（Product Surface & Productization）

> **核心命题**：AOL 是 **System of Action**，必须**可感知、可见**。
> 一个跑在后台的 cron + 通知，不是产品；让用户**看见 Agent 在做什么、需要决策什么、
> 带来了什么结果**的界面，才是产品。本文定义产品化纪律与产品脊柱（UI/UE/UX 交付物）。
> 配套：[PUB-05-releases.md](PUB-05-releases.md)（版本与 OKR/KPI）· [PUB-02-architecture.md](PUB-02-architecture.md)（AOL Core）。

---

## 1. 两轨纪律（POC 轨 vs 产品轨）

我们做的是**通用、可开源、可云服务**的平台，因此「项目/脚本」形态不可作为正式交付。
正式版本必须**产品化**；技术验证/临时实现归入 POC。

| | POC 轨 | 产品轨 |
|---|--------|--------|
| 目的 | 验证「能不能做、效果好不好」 | 交付「用户可用、可感知、可复用」 |
| 形态 | 脚本 / notebook / headless 引擎 | 有 UI/UE/UX、有 onboarding、可独立部署 |
| 命名 | `poc-xxx`（**不进 SemVer 版本表**） | `vX.Y`（正式 tag + release notes） |
| 验收 | 技术指标（跑通 / 质量） | 产品 KPI（可感知 / 被使用 / ROI） |
| 寿命 | 用完即弃或转化为产品输入 | 长期维护、向后兼容 |

> **铁律**：要打 `vX.Y` tag 的版本，**必须包含 UI 表面 + UX 流程**，否则只能叫 `poc-`。

### 当前定位（重要）

现有 `cron + 企微卡片 + DRY_RUN` = **`poc-followup`**（headless 引擎）。

- 企微卡片是**通知渠道**，不是产品本体；它的职责是把人**拉回 Console 处置**。
- 产品轨第一个版本（`v1.0 Console MVP`）才是「第一个可见的 AOL」。

---

## 2. 产品脊柱（Product Spine）

AOL 的「可见性」由六块界面承载。每个产品版本至少让其中一块从无到有或变厚。

```text
S1 Agent Console     ← 看：Agent 今天做了什么
S2 Suggestion Inbox  ← 决策：同意 / 拒绝 / 修改
S3 Trace / Run View  ← 信任：为什么这么建议
S4 ROI Dashboard     ← 价值：带来了什么结果
S5 Agent / Flow Studio ← 控制：配置 Agent 与编排
S6 Tenant Admin      ← 规模：多租户 / 权限 / 计费
```

### S1 · Agent Console（总览）

- **回答**：我的 Agent 今天处理了什么？哪些待我处理？
- **要素**：今日活动流、按 Agent/状态筛选、待办计数、单条进入详情。
- **可感知 KPI**：用户能在一屏内回答「今天发生了什么 + 我要做什么」。

### S2 · Suggestion Inbox + Approval（处置）

- **回答**：这条建议我同意 / 拒绝 / 改？
- **要素**：建议卡片（原因摘要、优先级、主行动、沟通要点）、`同意 / 拒绝 / 修改` 操作、批量处理。
- **可感知 KPI**：建议在产品内被处置的比例（而非靠翻群）；审批时延中位数。

### S3 · Trace / Run View（信任）

- **回答**：Agent 为什么这么建议？依据是什么？
- **要素**：推理轨（enrich 查证 → LLM → 后处理）、引用证据可点开、失败可见。
- **可感知 KPI**：建议附查证可见率；「看得懂为什么」满意度。

### S4 · ROI Dashboard（价值）

- **回答**：Agent 带来了什么业务结果？
- **要素**：采纳率、响应率、转化提升、报价时延、回款周期；周报在产品内生成。
- **可感知 KPI**：管理层每周实际查看 / 引用看板的次数。

### S5 · Agent / Flow Studio（控制）

- **回答**：我能不能自己调 Agent、规则、SOP、编排？
- **要素**：Agent 注册/开关、规则与 SOP 配置、多 Agent flow 可视化与干预。
- **可感知 KPI**：非工程人员能在产品内调一条规则/话术并生效。

### S6 · Tenant Admin（规模）

- **回答**：多租户、权限、计费如何管理？
- **要素**：租户隔离、RBAC、审计日志、用量与计费、onboarding 向导。
- **可感知 KPI**：新租户自助 onboarding 完成率与时长。

---

## 3. 产品化 Definition of Done（每个 `vX.Y` 必须满足）

1. **UX 产出齐全**：用户故事 → 关键流程 → 线框/原型 → 复用设计系统组件（不是事后补 UI）。
2. **可感知**：用户能在产品内回答该版本对应脊柱的核心问题（见 S1–S6）。
3. **闭环**：该版本独立可用、可演示、可验证、可回滚。
4. **可观测**：关键动作有埋点，能支撑该版本的产品 KPI。
5. **可复用**：新增 Agent/界面尽量复用既有产品外壳与组件（度量 UI 复用率）。
6. **文档**：release notes + 本文件对应脊柱节 + 架构/路线图联动更新。

> POC 不要求以上各项；但 POC 的结论必须能**喂给**某个产品版本作为输入。

---

## 4. 技术栈含义（当前缺口）

现状只有 Python 引擎（headless），**缺一整条前端产品线**。产品轨起步需要：

- **前端**：Web Console（建议 Next.js + 设计系统，如 shadcn）。
- **API 层**：把现有引擎包成服务接口（Suggestion / Approval / Trace / Metrics）。
- **通知渠道**：企微/短信降级为「把人拉回 Console」的入口，不承载处置逻辑。

详细版本节奏、各版 OKR/KPI 与新增 UI 见 [PUB-05-releases.md](PUB-05-releases.md)。

---

## 参见

- [PUB-01-vision.md](PUB-01-vision.md) · [PUB-02-architecture.md](PUB-02-architecture.md) · [PUB-03-roadmap.md](PUB-03-roadmap.md) · [PUB-05-releases.md](PUB-05-releases.md)
