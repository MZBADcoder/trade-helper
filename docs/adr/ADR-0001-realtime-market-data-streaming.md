# ADR-0001 — 实时行情推送架构（服务端代理 Polygon WebSocket）

日期：2026-02-09  
状态：Proposed

## 背景

- `PRD-0001` 需要在 Web Terminal 中展示股票与期权的实时更新能力。
- Polygon 提供 WebSocket 实时数据，但直接在浏览器连接会带来：
  - API Key 暴露风险
  - 订阅/配额不可控（每个浏览器都可能建立连接并订阅大量 symbols）
  - 多用户/多端扩展困难

## 目标

- API Key 不出服务端
- 统一鉴权、订阅上限、降级策略
- 在单机 Docker Compose 下可稳定运行，并为后续扩展留出空间
- 为多实例部署预留广播能力（Redis Pub/Sub）与负载均衡策略

## 可选方案

### 方案 A：前端直连 Polygon WebSocket

- 优点：实现最简单、延迟最低
- 缺点：
  - Key 暴露（难以接受）
  - 成本与订阅规模不可控
  - 断线重连、订阅管理在前端分散实现，难以统一治理

### 方案 B：服务端代理（推荐）

- 形态：
  - 新增 `realtime` 进程：连接 Polygon WebSocket（stocks/options），维护订阅集合
  - 使用 Redis 作为广播通道（pub/sub 或 stream）
  - API 对前端提供 WebSocket endpoint（鉴权后订阅/转发）
- 优点：
  - Key 安全、统一限流与配额
  - 更符合现有架构（API/worker/redis/postgres）
  - 易于将实时能力复用到告警/扫描任务
- 缺点：
  - 需要维护长连接进程与订阅状态
  - 需要处理背压、断线重连、消息扇出

### 方案 C：仅 REST 轮询（降级/过渡）

- 优点：实现简单，不需要长连接
- 缺点：实时性差；请求量大；成本可能更高；体验不佳

## 决策（建议）

采用 **方案 B：服务端代理**，并将 **方案 C** 作为自动降级路径：

1) `realtime` 进程负责 Polygon WS 连接、重连、订阅管理与消息标准化（统一 envelope）。  
2) API 提供 `WS /api/v1/market-data/stream`：
   - 鉴权后允许订阅「watchlist + 当前选中合约」范围
   - 服务端强制订阅上限（ticker/合约数量）并返回可见错误提示  
3) 当 WS 不可用或超过重连阈值时，前端/后端自动切换为 REST polling（频率可配置）。  

## 关键设计补充

- **上游连接策略**：每类资产（stocks/options）保持最少必要的 Polygon 上游连接，集中订阅与复用，避免每个客户端独立连上游。  
- **消息分发**：`realtime` 进程将上游消息统一封装为 `type/data/ts/source`，通过 Redis Pub/Sub 广播至 API 实例，再由 API 对各自 WebSocket 客户端扇出。  
- **鉴权与安全**：
  - WebSocket 连接建立时必须携带 JWT（query/header），服务端校验后再允许订阅。
  - 心跳/空闲检测机制，清理断线连接。
- **扩展性**：
  - 负载均衡器支持 WebSocket 升级连接。
  - API 实例无状态；横向扩展依赖 Redis 广播与统一订阅策略。

## 批量历史 + 实时协同加载（端到端案例）

以用户打开 `/terminal` 并查看 `AAPL` 分钟线为例：

1. **页面初始化（REST 批量加载）**
   - 前端先请求 `GET /api/v1/market-data/bars?ticker=AAPL&timespan=minute&from=...&to=...` 拉取一段历史 K 线（例如最近 300 根）。
   - 同时请求 `GET /api/v1/market-data/snapshots?tickers=AAPL,NVDA,...` 批量加载 watchlist 最新快照，先把列表与图表首屏渲染出来。
2. **建立实时通道（WebSocket）**
   - 前端携带 JWT 连接 `WS /api/v1/market-data/stream`，发送订阅指令（`AAPL` + 当前页面关注合约）。
   - API 校验订阅权限与上限，注册连接并开始接收该用户所需实时流。
3. **实时增量对齐历史窗口**
   - `realtime` 进程从 Polygon 收到 `AAPL` tick/quote/trade 后，标准化为统一 envelope 并通过 Redis 广播。
   - API 将增量消息推给前端；前端按时间戳把增量并入当前图表：
     - 若属于当前分钟，更新最后一根 K 线（OHLCV）；
     - 若跨分钟，封口上一根并新增一根。
4. **一致性修正与降级**
   - 若检测到消息丢失、重连或时间窗口断裂，前端触发一次小窗口 REST 补拉（例如最近 5-30 分钟 bars）进行纠偏。
   - 若 WS 不可用，则自动切换为 `snapshots + bars` 轮询模式，保证“可用优先，实时性降级”。

该协同模式保证：**REST 负责首屏和补洞的一致性，WS 负责低延迟增量更新**，两者配合可在复杂网络环境下仍维持稳定体验。

### 服务端时序（含缓存命中/未命中）

1. 前端请求 `bars/snapshots` 后，API 优先查 Redis：
   - **命中**：直接返回，降低首屏延迟；
   - **未命中**：调用 Polygon REST 拉取后回填 Redis（带 TTL）再返回。
2. 前端 WS 订阅成功后，API 不再依赖高频 REST 刷新最新价，而由 WS 增量驱动 UI 更新。
3. 若 WS 中断：
   - 前端进入短周期 REST 轮询；
   - WS 恢复后执行一次“短窗口 bars 补拉”完成数据对齐，再切回增量模式。

### 统一时间语义（避免图表抖动）

- REST 返回的 `updated_at` 与 WS envelope 的 `ts` 统一使用 UTC ISO8601。
- 前端按“事件时间优先”合并数据，丢弃过旧消息（`event_ts < last_applied_ts`）。
- 同一分钟内允许多次覆盖最后一根 bar；跨分钟后封口前一根并新建下一根。

## 影响与后果

- 需要新增一个可部署的 `realtime` 进程（Compose service）
- Redis 除 Celery broker 外可能承担实时广播（需要约定 channel 与消息格式）
- 需要定义：
  - 订阅协议（请求/响应）
  - 消息 envelope（`type/data/ts/source`）
  - 背压策略（丢弃、合并、采样、只推送最新）
