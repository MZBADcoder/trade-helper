# ADR-0001 — 实时行情推送架构（服务端代理 Massive/Polygon WebSocket）

日期：2026-02-09  
状态：Proposed

## 背景

- `PRD-0001` 需要在 Web Terminal 中展示股票与期权的实时更新能力。
- Massive/Polygon 提供 WebSocket 实时数据，但直接在浏览器连接会带来：
  - API Key 暴露风险
  - 订阅/配额不可控（每个浏览器都可能建立连接并订阅大量 symbols）
  - 多用户/多端扩展困难

## 目标

- API Key 不出服务端
- 统一鉴权、订阅上限、降级策略
- 在单机 Docker Compose 下可稳定运行，并为后续扩展留出空间

## 可选方案

### 方案 A：前端直连 Massive WebSocket

- 优点：实现最简单、延迟最低
- 缺点：
  - Key 暴露（难以接受）
  - 成本与订阅规模不可控
  - 断线重连、订阅管理在前端分散实现，难以统一治理

### 方案 B：服务端代理（推荐）

- 形态：
  - 新增 `realtime` 进程：连接 Massive WebSocket（stocks/options），维护订阅集合
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

1) `realtime` 进程负责 Massive WS 连接、重连、订阅管理与消息标准化（统一 envelope）。  
2) API 提供 `WS /api/v1/market-data/stream`：
   - 鉴权后允许订阅「watchlist + 当前选中合约」范围
   - 服务端强制订阅上限（ticker/合约数量）并返回可见错误提示  
3) 当 WS 不可用或超过重连阈值时，前端/后端自动切换为 REST polling（频率可配置）。  

## 影响与后果

- 需要新增一个可部署的 `realtime` 进程（Compose service）
- Redis 除 Celery broker 外可能承担实时广播（需要约定 channel 与消息格式）
- 需要定义：
  - 订阅协议（请求/响应）
  - 消息 envelope（`type/data/ts/source`）
  - 背压策略（丢弃、合并、采样、只推送最新）
