# PRD-0001 — 实时行情 / 数据观察（Stocks + Options，Massive.com）

> 目的：本文件用于把需求“聊清楚”，形成一致的项目范围、优先级与验收标准；**不涉及代码实现**。  
> 状态：草案  
> 最后更新：2026-02-09  
> 负责人：____

---

## 1. 项目一句话

- 我们要做的是：**一个自建的 Web Trader Terminal**，基于 `Massive.com` 提供「美股股票 + 美股期权」的**历史行情 + 实时行情**观察（K 线、快照、期权链），作为后续 `PRD-0002 IV Percentile 告警` 的数据与展示底座。

## 2. 背景与动机

- 现状/痛点：
  - 1) 前端已经有 Terminal 原型，但 `/demo` 的数据来源是本地模拟；`/terminal` 虽已有基础 bars 接口映射，但仍缺少“真正实时”的数据链路与期权观察能力。
  - 2) 若没有稳定的行情展示能力，后续 IV/告警类 feature 很难落地（缺少可信的数据入口与可视化载体）。
- 为什么现在做：
  - 这是后续所有量化/告警/策略模块的前置能力，应先把“数据链路 + 交互承载”打通。
- 不做的代价：
  - 继续依赖 mock 或零散脚本，导致需求与实现无法闭环（不可复用、不可扩展、难调试）。

## 3. 目标与非目标

### 3.1 目标（可量化）

- G1：终端核心页面（`/terminal`）**不再依赖 mock 数据**；股票 K 线与最新价格来自 Massive。
- G2：提供股票实时更新能力：watchlist 中的 `Last/Change/%Change/更新时间` 能做到**秒级或数秒级**刷新（取决于数据订阅与成本约束），并支持断线重连与降级策略。
- G3：提供期权基础观察能力：按 underlying 展示期权链（到期、行权价、Call/Put），至少展示 `Bid/Ask/Last/IV/Volume/OI`，并支持选中单合约查看详情与实时更新。
- G4：数据链路可观测：界面明确显示数据源（REST/WS）、连接状态、是否延迟行情（real-time vs delayed）、最后更新时间。

### 3.2 非目标（明确不做）

- NG1：不做真实交易下单、不接入券商账户。
- NG2：不做 IV 扫描/告警规则（由 `PRD-0002` 负责）。
- NG3：不做“全市场扫描/排行/筛股器”；仅围绕 watchlist 与当前选中标的展开。
- NG4：MVP 不做 tick 级历史落库与回放（实时主要用于驱动 UI；历史以 bars 为主）。

## 4. 用户与场景

### 4.1 用户画像

- 主要用户：我（交易者/开发者）
- 使用环境：
  - 开发：macOS
  - 部署：Linux 单机（Docker Compose）

### 4.2 典型场景（按频率排序）

1) 盘中我打开 `/terminal`，快速浏览 watchlist，查看哪些标的出现快速波动，并点开详情查看分时走势与指标。  
2) 我在某个标的下切换到 options 视图，按到期与行权价浏览期权链，筛选出 ATM 附近合约并观察报价与成交变化。  
3) Massive WebSocket 不稳定或网络抖动时，系统可自动降级为 REST 轮询（并提示“降级中/延迟”），避免 UI 失效。  

## 5. 核心流程（端到端）

1) 用户登录进入 `/terminal`。  
2) 用户维护 watchlist（添加/删除 ticker）。  
3) 系统展示每个 ticker 的基础信息与最新价格（来自 REST 快照或 WS 推送）。  
4) 用户点击某个 ticker，加载历史 bars（REST + 本地缓存/落库），并渲染 K 线与指标。  
5) 用户切换到 options 视图：系统加载到期列表与期权链快照；用户点击某个合约后进入合约详情，并开始订阅该合约实时更新。  
6) 若 WS 断开：自动重连；超过阈值则降级为 REST 轮询，并在 UI 显示状态。  

## 6. 功能需求（按优先级）

### 6.1 MVP（必须有）

- F1：登录/鉴权与 watchlist 管理
  - 说明：现有能力已覆盖，但 MVP 需保证端到端稳定可用。
  - 验收：
    - watchlist CRUD 可用
    - watchlist 在前端与后端一致（刷新不丢）

- F2：股票行情（历史 + 实时）
  - 历史 bars：
    - 支持 `day/week/month`（用于长周期）与 `minute`（用于分时/近实时）
    - 支持常用 lookback（例如：日线 ~1 年、分钟线 ~14 天，具体可配置）
  - 实时快照：
    - watchlist 行展示：`Last / Change / %Change / UpdatedAt`
    - 详情页展示：最近一次价格 + 当日高低 + 成交量（字段可随数据源调整）
  - 验收：
    - `/terminal` 任意 watchlist ticker 都能拉到 bars 并渲染
    - 选中 ticker 后，实时字段能持续更新（WS 或 polling）

- F3：期权行情（基础链 + 选中合约实时）
  - 期权链：
    - 支持按 underlying ticker 查询到期列表（expirations）
    - 支持按 expiration 展示 chain（strikes + call/put）
    - 至少展示：`Bid / Ask / Last / IV / Volume / OI`（若数据源缺字段，则显示 `-` 并标注来源限制）
  - 合约详情：
    - 用户点击合约进入详情（最小可用：合约标识、报价、成交、当日范围、更新时间）
    - 开始订阅该合约的实时 quotes/trades/秒级聚合（取决于 Massive 提供的 channel）
  - 验收：
    - 期权链能在合理时间内加载（避免一次加载全市场）
    - 选中合约后，报价更新可见（WS 或 polling）

- F4：系统状态与降级策略
  - 状态可见：
    - Massive REST 可用性（错误提示）
    - Massive WS 连接状态（Connected/Disconnected/Reconnecting/Degraded）
    - 数据延迟标识（real-time / delayed）
  - 降级：
    - WS 不可用时自动转 REST 轮询（频率可配置，默认 5-15 秒级）
  - 验收：
    - 手动断网/模拟 WS 失败时，UI 不“卡死”，能给出明确状态并继续提供基础数据

- F5：成本/配额保护（服务端）
  - 限制：
    - 同时订阅的股票 ticker 数量上限（例如：≤ 100）
    - 同时订阅的期权合约数量上限（例如：≤ 20；优先仅订阅“当前查看”的合约）
  - 验收：
    - 超限时给出提示，不会把系统拖垮或导致 WS 被封禁

### 6.2 Should Have（重要但可延期）

- S1：期权链筛选与视图优化（DTE、行权价范围、moneyness/ATM）
- S2：合约收藏（将合约加入关注列表，快速回访）
- S3：服务端指标计算（保证多端公式一致；前端仍可作为兜底）
- S4：历史期权 bars（按选中合约查询，并支持基础图表）

### 6.3 Nice to Have（锦上添花）

- N1：多窗口布局（同屏对比多个标的/多个到期）
- N2：链条可视化（skew / term structure / heatmap）

## 7. 数据、集成与依赖

### 7.1 数据源与形态

- 历史数据：Massive REST API（按需拉取 bars，并做本地缓存/落库）
- 实时数据：Massive WebSocket（股票与期权的实时推送）
- 大批量历史数据：Massive Flat Files（S3/对象存储，供离线回填/批处理；非 MVP 必需）

### 7.2 Flat Files 使用策略（预案，非 MVP 必需）

- 使用时机：
  - 当我们需要更长历史、更高吞吐、或需要“批量回填/重建指标”的能力时（例如后续 percentile 计算窗口扩大，或要做多标的批处理）。
- 基本特性：
  - Flat Files 同时包含「每日数据」与「完整历史数据集」，更适合离线回填/批处理，不适合用于实时展示链路。
  - 交付节奏为 T+1（次日约 11:00 AM ET 可用），因此只能作为历史数据补齐手段。
- 方式：
  - 通过 Flat Files 提供的 S3 端点读取数据，导入到本地存储（Postgres/分区表或专用时序库，后续再评估）。
  - 导入任务需可中断、可恢复、可校验（按日期分片/幂等写入）。

### 7.3 API Key 与鉴权

- Massive API Key **仅存服务端**（环境变量/密钥管理），前端不直连 Massive。
- 前端通过本系统的登录态访问 REST/WS（避免泄露第三方 Key，统一做权限与配额控制）。

## 8. 交互与界面（先定“信息结构”）

- 关键页面/视图：
  - 页面A：Trader Terminal（watchlist + detail）
  - 页面B：Options 视图（到期列表 + 期权链 + 合约详情）
  - 页面C：设置/状态（连接状态、降级策略、刷新频率等）
- 路由约定：
  - `/demo`：保持独立 demo（允许本地模拟数据）
  - `/terminal`：必须接入真实数据链路（本 PRD 的验收口径）

## 9. 非功能需求（NFR）

- 性能：
  - 首屏可用（watchlist + 基础快照）在合理时间内完成（目标：2 秒级，受网络与订阅影响）
  - 详情页 bars 加载有 loading 状态，避免阻塞 UI
- 可靠性：
  - WS 自动重连（指数退避 + 最大重试间隔）
  - REST 调用具备超时、重试、限流与缓存（避免被打爆）
- 安全：
  - 不在前端暴露 Massive API Key
  - 基础访问控制（至少登录后可用）；后续如做多用户需补齐配额/隔离策略
- 成本：
  - 订阅/请求量可控（上限与降级策略），并在 UI 提示当前订阅规模

## 10. 验收与指标（Definition of Done）

- [ ] `/terminal` 不依赖 mock：能展示至少 3 个 ticker 的历史 bars 与基础指标
- [ ] watchlist 行能展示并持续刷新最新价格（WS 或 polling），且在 UI 显示数据状态（Connected/Degraded）
- [ ] 期权链可用：能按 underlying + expiration 加载 chain，并展示最小字段集
- [ ] 选中 1 个期权合约后，合约详情能够持续更新（WS 或 polling）
- [ ] Massive WS 断开时能自动重连；连续失败时降级为 REST 轮询并给出可见提示

## 11. 风险与开放问题

- Q1：我们当前使用的 Massive 订阅计划是 **real-time 还是 delayed**？若是 delayed，UI 需明确展示“延迟行情”。
- Q2：实时行情我们更关注哪类事件？（trade/quote/秒级聚合）对 UI 来说哪个最关键？
- Q3：期权链 MVP 的“最小字段集”具体要哪些？是否需要 greeks（delta/gamma/vega/theta）？
- Q4：历史存储策略：bars 落库保留多久？是否需要按 watchlist 自动预拉取？
- Q5：单机部署下的吞吐目标：watchlist 上限、同时在线连接数是否仅考虑单用户？

## 12. 技术架构（草案）

### 12.1 方案对比

- 方案 A：前端直连 Massive WebSocket
  - 优点：实现最简单、延迟最低
  - 缺点：API Key 暴露；订阅/配额难控；多用户扩展困难；浏览器连接数受限
- 方案 B（推荐）：服务端代理 Massive WebSocket + 前端连接本系统 WS
  - 优点：Key 不暴露；统一鉴权/配额/降级；便于后续多用户与规则/告警复用
  - 缺点：需要维护一个长连接服务（状态/订阅管理、广播、重连）

### 12.2 推荐组件形态（基于 ARCHITECTURE-BASELINE，并由 ADR-0001 落地实时推送）

- 前端（Web）：React（现有）
- API（在线服务）：FastAPI（现有）
  - 负责：鉴权、watchlist、bars 查询、options chain 查询、对前端提供 WS endpoint（或反向代理到 realtime 服务）
- Worker（离线/可重试）：Celery workers（现有）
  - 负责：REST 拉取历史数据并落库、预拉取、数据修复任务（按需）
- Realtime 服务（新增，长连接进程）：
  - 负责：连接 Massive WebSocket（股票/期权），维护订阅集合，将消息推送给前端（或经 Redis 广播）
- Redis：
  - 现有用途：Celery broker
  - 新增用途：pub/sub 或 stream（用于跨进程广播实时消息、缓存快照）
- Postgres：
  - 现有用途：watchlist、bars 等持久化
  - 可选扩展：落库存储 options chain 快照/合约引用数据（按需）

### 12.3 数据流（简化）

1) 历史 bars：前端 → API →（命中本地则直接读库）否则 API/Worker → Massive REST → DB → API → 前端  
2) 实时行情：Massive WS → Realtime 服务 →（Redis 广播）→ API WS → 前端  
