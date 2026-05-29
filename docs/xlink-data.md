# XLink 工单数据口径（agent-loop 专用）

本文件沉淀 agent-loop 读取 XLink 工单数据的口径，均已在 dev 库 `xlinkdemo` 只读验证。
通用的 XLink 数据读取规范以团队 skills 为准：

- `xlink-prod-data-analyze`（生产只读分析：报价/合同/勘察/管家业绩）
- `xlink-cloud-dev-verify`（dev 只读核验）
- 连接信息：`/Users/yesun/Code/xlink/docs/z.其它/mongodb-connection-info.md`
- 统计字典 SSOT：`/Users/yesun/Code/xlink/docs/z.其它/业务字典-生产统计口径.md`

## 连接

| 环境 | URI | DB | 账号 |
|------|-----|----|------|
| dev | `mongodb://112.126.77.6:27017/xlinkdemo?directConnection=true&authSource=admin` | `xlinkdemo` | `xlinkdemo` / `xlink*123` |
| prod | `mongodb://112.126.77.6:27017/xlink?directConnection=true&authSource=admin` | `xlink` | 见 `cloud/.../config_prod.properties` |

- 务必 `directConnection=true`（副本集私网 IP `172.17.108.115` 本地不可达）。
- `serverSelectionTimeoutMS=8000`。
- **只读**：绝不 insert/update/delete。POC 仅需 DBA 提供只读账号即可上线。

## 工单集合 `serviceAppointment`

工单实体定义见 `cloud/src/main/java/com/fsgo/entity/basic/ServiceAppointment.java`。

### 关键字段

| 字段 | 类型 | 含义 |
|------|------|------|
| `_id` | String | 工单主键（字符串，非 ObjectId） |
| `orderNum` | String | 工单号，如 `GD20241100106` |
| `status` | String | 工单业务状态码（见下表） |
| `stage` | String | 业务周期阶段 |
| `state` | Int | 数据状态：`1`=有效，`-1`=作废 |
| `city` | String | 行政区划码（`110100`=北京） |
| `serviceType` | String | 服务类型编码 |
| `title` | String | 工单标题（常自动生成，如「X先生的工单」） |
| `describe` | String | 备注/描述（**稀疏**，多数为空） |
| `name` / `phone` | String | 联系人姓名 / 电话 |
| `createTime` / `updateTime` | Date | 创建 / 最近更新时间（**北京本地时间，无时区**） |

### 工单状态码（实测分布，dev）

`201`、`104`待联系、`204`上门未成交、`403`已完工、`203`待下单、`205`待支付首付款、
`206`待签约、`200`暂时不需要上门、`300`、`402`、`407` 等。

来源佐证：
- 小程序菜单树 `business/tmp/api_samples/change-role-menu-tree.json`：
  「已完工」→ `serviceAppointments?orderState=done&status=403&type=SANode`
- 前端注释 `business/subpackages/serviceAppointment/serviceAppointment.vue`：
  104待联系 / 105待预约 / 203待下单 / 206待签约 / 205待支付首付款 / 200 / 204。

### agent-loop「新完工工单」查询

```javascript
db.serviceAppointment.find({
  status: "403",                 // 已完工
  state: 1,                      // 排除作废(-1)
  updateTime: { $gte: <北京时间-N小时> },
  _id: { $nin: [<已处理ID>] }    // 追踪库水位线去重
}).sort({ updateTime: -1 }).limit(50)
```

### 实测数据点（dev `xlinkdemo`，2026-05-29）

- `serviceAppointment` 总量 3677
- `status="403"` 共 350：`state=1` 有 345，`state=-1` 作废 5
- `status="403"` 中 `describe` 非空仅约 20 条 → 备注稀疏，跟进文本以 `title`+`describe` 为主，
  空备注时引擎回退「轻量满意度回访」
- **最近一条 `status=403` 的 `updateTime` 约在 2026-03-26** → 默认 `FSM_LOOKBACK_HOURS=24`
  在 dev 会捞到 **0 条**；本地 E2E 建议 `2160`（90 天）或 `FSM_LOOKBACK_HOURS=0`（仅开发）

## 待确认 / 后续增强

- **更丰富的跟进文本**：`serviceAppointment.describe` 偏空，真实服务记录/沟通备注可能在
  `workflowNode`（流程节点）或关联 `order`/`contract`。后续可在捞取后按 `_id` 关联补全。
- **生产口径校验**：上线前在 prod `xlink` 复核 `status=403` 量级与时间字段，再开真实推送。
