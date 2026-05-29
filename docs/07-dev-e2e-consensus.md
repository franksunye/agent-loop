# 07 · 开发环境 E2E 共识

> 团队约定：**开发环境跑 E2E，默认不真正发送企微消息。**

## 为什么

完整闭环里有多段能力，复杂度与风险不同：

| 环节 | 难度 | 开发 E2E 是否默认真跑 |
|------|------|------------------------|
| dev 库捞取 + 领域翻译 | 中 | ✅ 要真跑 |
| 幂等水位线 + trace 落库 | 中 | ✅ 要真跑 |
| LLM 推理（混元免费档） | 低～中 | ✅ 要真跑（或 heuristic 测非 LLM 段） |
| **企微发消息** | **低** | ❌ **默认不真发** |

发消息只是输出层的一个功能，实现简单、验证也快。**不应为了证明「引擎能跑」，就每次 E2E 都往真实群里刷卡片。**

## 默认行为

```bash
DRY_RUN=true   # 默认（代码与 .env.example 一致）
```

- 仍会：连 dev Mongo、捞真实工单、调 LLM（若配置了 key）、写 `reasoning_traces`、写水位线（预览模式下视为发送成功，避免下轮重复刷屏）。
- 不会：调用企微 webhook 真发；日志里打印 **`[企微预览]`** 卡片内容。

`DRY_RUN` **不**关闭 LLM。零 API 请用 `LLM_PROVIDER=heuristic`。

## 何时真发消息

仅当**明确说明**要做「发送真实消息」验证时，例如：

- 验收企微 Markdown 排版、@人、频率上限
- 业务方在**试点群**里肉眼确认

操作：

```bash
DRY_RUN=false
WECOM_WEBHOOK=<试点群 webhook>   # 勿用生产大群做日常开发
FSM_BATCH_LIMIT=3                # 控量，避免刷屏
```

并在 Runbook / PR 里写清：**本次会真发 N 条**。

## v0.2 开发 E2E 标准路径（推荐）

1. **`FSM_SOURCE=mongo`** + dev `xlinkdemo`（`.env` 已配置；mock 仅离线 CI）
2. **`FSM_LOOKBACK_HOURS`**：dev 库完工单 `updateTime` 可能较旧，建议 `2160`（90 天）；
   设 `0` 表示不按时间过滤（慎用，会捞很多条）
3. **`FSM_BATCH_LIMIT=3`**：控制混元调用量
4. `LLM_PROVIDER=hunyuan`（或 `heuristic` 测非 LLM）
5. **`DRY_RUN=true`**（企微预览）
6. **`--reset-tracking`**（每次要「从头验一遍」时加上，见下节）
7. 查 `reasoning_traces` + 日志里的 `[企微预览]`
8. （可选、单独一次）`DRY_RUN=false` + 试点群，验证真发

## 重复跑 E2E：幂等 vs 可重复验证

生产逻辑：**已处理工单不会再次捞取**（`ai_follow_up_logs` 水位线）。  
开发 E2E：**需要能反复验同一批 mock/样本**，否则第二轮会显示「0 条」误以为没写入。

**推荐做法**（二选一）：

```bash
# 方式 A：命令行（推荐）
python agent_cron_engine.py --reset-tracking

# 方式 B：环境变量（脚本/CI）
TRACKING_RESET=1 python agent_cron_engine.py
```

会 **DELETE** `ai_follow_up_logs` 与 `reasoning_traces` 的全部行（**不删 db 文件**），
再跑完整链路；SQLiteStudio 等 GUI 保持连接后点刷新即可看到新数据。
仅 **`TRACKING_SOURCE=local`** 时允许，防止误清 Turso。

**mock 固定 3 单**时，每次 E2E 建议：

```bash
python agent_cron_engine.py --reset-tracking   # 先清空
# 再配 DRY_RUN=true FSM_SOURCE=mock LLM_PROVIDER=hunyuan ...
python agent_cron_engine.py
```

日志会打印追踪库绝对路径，便于用 GUI 打开正确的 db 文件。

## 与版本 / 环境的关系

| 环境 | 企微 |
|------|------|
| 本地开发 E2E | 默认预览（`DRY_RUN=true`） |
| v0.3 GHA pilot | 试点群可 `DRY_RUN=false`，需 Runbook 写明 |
| v1.0 Live | 生产群 + 告警；与开发默认分离 |

## 参见

- [05-releases.md](05-releases.md) v0.2 · [06-llm-providers.md](06-llm-providers.md)
