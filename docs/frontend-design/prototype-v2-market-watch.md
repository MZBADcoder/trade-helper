# 前端原型 V2（Market Watch 增量设计）

## 0. Context

- Source PRD：`docs/prd/PRD-0001-market-watch.md`
- Related ADR：
  - `docs/adr/ARCHITECTURE-BASELINE.md`
  - `docs/adr/ADR-0001-realtime-market-data-streaming.md`
- Related BE：
  - `docs/backend-evolution/BE-0001-prd-0001-market-watch-api-breakdown.md`
  - `docs/backend-evolution/BE-0002-prd-0001-market-watch-api-contract-v1.md`
  - `docs/backend-evolution/BE-0005-prd-0001-market-data-hybrid-fetch-strategy.md`

> 本文档在 `prototype-v1.md` 的基础上，只定义 PRD-0001（market-watch）新增/调整的前端设计，不覆盖 PRD-0002（IV 告警）。

## 0.1 执行状态更新（2026-02-16）

- 当前迭代仅推进 Stock 数据主线前端能力。
- options 相关前端开发进入 HOLD（包括 options workspace 深化、联调与验收）。
- 本文中的 options 设计内容保留为下一阶段恢复时的基线，不作为当前迭代必做项。

---

## 1. 本轮设计目标

对齐 PRD-0001 的新增范围，补齐 `/terminal` 在真实行情场景下的前端能力：

1. Watchlist 行情从“静态列表”升级为“实时可更新列表”（Last/Change/%Change/UpdatedAt）。
2. 详情区支持「首屏 REST + 增量 WS + 断线降级轮询」的数据体验。
3. 新增 options 观察视图（到期列表 + 期权链 + 合约详情，HOLD）。
4. 增加系统状态可视化（连接状态、数据来源、延迟标识）。

---

## 2. 范围与非范围

### 2.1 In Scope

- `/terminal` 页面结构升级（watchlist / stock detail / options / status）。
- 新增实时状态组件：连接状态、最后更新时间、降级提示。
- 新增 WS 订阅生命周期（建立、续订、退订、重连）。

### 2.2 Out of Scope

- 不做策略、告警、扫描器 UI。
- 不做真实交易下单 UI。
- 不做 demo 路由改造（`/demo` 仍保持本地模拟用途）。
- options 相关交互深化与联调（expirations/chain/contract detail）在当前迭代 HOLD。

---

## 3. 信息架构（V2）

### 3.1 路由

- `/`：保持不变
- `/login`：保持不变
- `/demo`：保持不变
- `/terminal`：新增 market-watch 子布局（本次核心）

### 3.2 `/terminal` 页面分区

1. **左侧 Watchlist Panel**
   - ticker 列表、添加/删除
   - 行内展示 `Last / Change / %Change / UpdatedAt`
2. **中部 Detail Workspace**
   - 顶部 symbol header + 时间粒度切换（PMF 阶段 minute 收敛到 `5m/15m/60m`）
   - 主图（K 线 + 指标）
   - 当前价、日内高低、成交量、数据来源
3. **右侧 Options Workspace（可折叠）**
   - expiration selector
   - chain table（按 strike + call/put）
   - contract quick detail
4. **全局 Status Bar（底部）**
   - WS 状态：Connected / Reconnecting / Degraded / Disconnected
   - 数据延迟：real-time / delayed
   - 最后成功同步时间 + 最近错误摘要

---

## 4. 核心交互流程（V2）

### 4.1 首次进入 terminal

1. 拉取 `watchlist`。
2. 批量请求 `snapshots` 填充 watchlist 行数据。
3. 加载当前选中 ticker 的 `bars`。
4. 建立 `market-data/stream` WS 连接并订阅 watchlist symbols。
5. 首屏完成后状态栏显示 `Connected` 与 `source`。

### 4.2 用户切换 ticker

1. 若 ticker 未在当前订阅集中，发送 `subscribe`。
2. 请求该 ticker 的 `bars`（minute/day 由当前时间粒度决定）。
   - 对齐 BE-0005：minute 聚合粒度先收敛到 `multiplier in {5,15,60}`（必要时保留 `1m` 为回源/调试用，不作为默认 UI 选项）。
3. 重置 detail 区临时状态，保留 watchlist 实时流。
4. 当第一条该 ticker WS 增量到达后，更新 detail “最后更新时间”。

### 4.3 用户打开 options 视图（HOLD，下一阶段恢复）

1. 请求 `options/expirations?underlying=`。
2. 默认选择最近可交易到期，加载 `options/chain`。
3. 点击链上合约后，请求 `options/contracts/{option_ticker}`。
4. 将选中合约加入 WS 订阅（若超限，显示“已达订阅上限”并禁止继续订阅）。

### 4.4 断线与降级

1. WS 断开后进入 `Reconnecting`，指数退避重试。
2. 超过阈值（如 10s）自动切 `Degraded`：
   - snapshots 轮询：2~5s
   - bars 补拉：15~30s
3. WS 恢复后先补拉短窗口 bars，再切回纯增量。
4. 全过程在状态栏与 detail header 给出显式提示。

---

## 5. 前端模块拆分建议

- `entities/market-stream`
  - 维护 WS 连接状态、订阅集合、重连策略、降级状态机
- `entities/market-snapshot`
  - watchlist 行数据缓存与批量更新
- `entities/options-chain`
  - 到期列表、链表分页游标、筛选条件状态
- `features/terminal-symbol-select`
  - ticker 选中切换与详情联动
- `features/options-contract-select`
  - 合约选中、详情加载、订阅管理
- `widgets/market-status-bar`
  - 统一显示连接、延迟、最后更新时间、错误
- `widgets/options-chain-table`
  - chain 渲染、排序、空字段兜底（`-`）

---

## 6. API 映射（按 BE-0002）

### 6.1 REST

- `GET /api/v1/watchlist`
- `GET /api/v1/market-data/snapshots?tickers=`
- `GET /api/v1/market-data/bars`
- `GET /api/v1/options/expirations?underlying=`
- `GET /api/v1/options/chain?underlying=&expiration=`
- `GET /api/v1/options/contracts/{option_ticker}`

### 6.2 WebSocket

- `WS /api/v1/market-data/stream`
- 客户端消息：`subscribe / unsubscribe / ping`
- 服务端消息：按 `type` 路由（如 `market.quote`, `market.aggregate`, `system.status`）

### 6.3 UI 字段兜底策略

- `iv/volume/open_interest` 缺失：显示 `-`，并保留 tooltip“上游字段不可用”。
- `source` 非 `WS`：在详情区标记 “REST/Delayed”。
- 错误码映射：沿用 BE-0002 的 error code -> 前端统一 i18n 文案。

---

## 7. 状态模型（前端）

### 7.1 连接状态机

- `idle` -> `connecting` -> `connected`
- `connected` -> `reconnecting` -> `connected`
- `reconnecting` 超时 -> `degraded`
- `degraded` + WS 恢复 -> `recovering` -> `connected`
- 任意状态遇到鉴权失败 -> `auth_error`

### 7.2 数据一致性策略

- symbol 维度维护 `lastAppliedTs`，仅接受更新消息中更新的时间戳。
- 重连后执行“先补拉后增量”以避免图表缺口。
- 多来源并发更新（REST/WS）时，以 `event_ts` 新者覆盖旧者。

---

## 8. 视觉与交互补充

1. **Watchlist 行颜色语义**：
   - `change > 0` 绿色，`< 0` 红色，`= 0` 中性色。
2. **状态栏优先级**：
   - `auth_error` > `degraded` > `reconnecting` > `connected`。
3. **Options 表格性能约束**：
   - 单次最多渲染 200 行，超过使用分页/虚拟滚动。
4. **空态设计**：
   - 无 watchlist：提示“先添加 ticker”。
   - 无 options 数据：提示“选择到期日或调整 strike 区间”。

---

## 9. 验收标准（前端设计层）

- `/terminal` 当前阶段优先承载股票观察能力，并保留 options 区域占位与恢复接口。
- 用户可以感知连接与延迟状态，断线后界面仍有可用数据。
- options 视图“到期 -> 链 -> 合约详情”闭环为下一阶段验收项（当前 HOLD）。
- 关键字段与错误场景有明确兜底显示，不出现空白区域无提示。

---

## 10. 与 V1 的差异总结

1. 从“股票详情标签管理”扩展到“market-watch 工作台”。
2. 新增实时状态体系（WS + Degraded polling）。
3. options 观察交互与数据结构已设计但当前阶段 HOLD。
4. 当前阶段 API 依赖优先 `auth/watchlist/bars/snapshots/stream`，options 相关依赖待恢复。
