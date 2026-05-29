# Agent-Loop · Agent-native 自动跟进引擎（POC）

用**最小成本**验证一个想法：在不改动现有 FSM 系统的前提下，让一个 AI Agent 定时
轮询「新完工工单」，自动判断是否需要人工跟进，并把结构化建议推送到企业微信群。

## 核心理念

- **零系统侵入**：只需向 FSM 库申请一个**只读账号**，现有系统无需改代码、无需发版。
- **主动轮询，而非被动 Webhook**：GitHub Actions 每小时唤醒一次，去库里捞增量。
- **天然幂等的拉取式状态机**：处理记录写入追踪库；推送失败的工单下一轮会被重新捞出重试，直到成功。
- **没有 30 秒断头台**：Actions 单次生命周期长达数十分钟，可从容串行处理堆积工单。

## 架构

```
GitHub Actions Cron  →  增量捞取(FSM 只读)  →  LLM 生成 Action Spec
                                                      ↓
企业微信群机器人  ←  推送 Markdown 卡片  ←  写入追踪库(幂等水位线)
```

全部逻辑收拢在一个文件 `agent_cron_engine.py` + 一个 `.github/workflows/agent_cron.yml`。

## 90 秒跑通（零依赖、零密钥）

`DRY_RUN` + 内置 mock 工单 + 本地 sqlite，仅用 Python 标准库即可跑完整链路：

```bash
DRY_RUN=true python agent_cron_engine.py
```

会打印每张样例工单的结构化跟进建议和将要发送的企微卡片预览，并在
`agent_loop_tracking.db` 中记录水位线。再次运行会因幂等而不重复处理（验证去重）。

## 接入真实环境（XLink）

1. 复制配置：`cp .env.example .env`，按注释填写。
2. 数据源 `FSM_SOURCE=mongo`（XLink 主路径），填写 `FSM_MONGO_URL`。
   - dev：`mongodb://<user>:<pwd>@112.126.77.6:27017/xlinkdemo?directConnection=true&authSource=admin`，`FSM_MONGO_DB=xlinkdemo`
   - prod：同上换 `xlink`，`FSM_MONGO_DB=xlink`
3. 追踪库 `TRACKING_SOURCE`：`local`（sqlite）或 `cloud`（复用团队 Turso）。
4. 安装可选依赖：`pip install pymongo`（cloud 追踪库再装 `libsql-client`）。
5. 配 `LLM_API_KEY`（兼容 OpenAI 协议）与 `WECOM_WEBHOOK`，去掉 `DRY_RUN`。

### XLink 工单口径（已用 dev 库只读验证）

| 项 | 值 | 说明 |
|----|----|------|
| 集合 | `serviceAppointment` | 工单主表 |
| 已完工 | `status = "403"` | 对应小程序菜单「已完工」(`orderState=done&status=403`) |
| 有效 | `state = 1` | 排除作废工单（`state=-1`） |
| 增量时间 | `updateTime` / `createTime` | BSON datetime，**北京本地时间无时区**（引擎已对 UTC Runner 做 +8 校正） |
| 文本 | `describe`（备注，稀疏）+ `title` | AI 跟进的主要输入；`describe` 多为空时回退轻量满意度回访 |
| 城市 | `city` | 行政区划码（`110100`=北京），引擎内置常见码→名映射 |
| 主键 | `_id` | 字符串，用于 `$nin` 去重 |

详见 [`docs/xlink-data.md`](docs/xlink-data.md)。

> 工单状态码并非只有 403，常见还有 104待联系 / 105待预约 / 203待下单 / 206待签约 /
> 204上门未成交 等。若要跟进其它阶段，改 `FSM_FINISHED_STATUS` 即可。

## GitHub Actions 部署

仓库 Settings 配置：

- **Secrets**：`FSM_DB_URL`、`TURSO_URL`、`TURSO_TOKEN`、`LLM_API_KEY`、`WECOM_WEBHOOK`
- **Variables**（可选）：`DRY_RUN`、`FSM_SOURCE`、`TRACKING_SOURCE`、`LLM_MODEL` 等

默认 cron 为北京时间 8:00–22:00 每小时一次，也可在 Actions 页手动触发（`workflow_dispatch`）。
建议先把 `DRY_RUN` 设为 `true` 在线上空跑验证流程，再切真实推送。

## 文件结构

```
agent-loop/
├── agent_cron_engine.py          # 单文件引擎：捞取 → 推理 → 追踪 → 推送
├── requirements.txt
├── .env.example
├── docs/xlink-data.md            # XLink 工单数据口径（连接 + 字段，已验证）
├── .github/workflows/agent_cron.yml
└── README.md
```
