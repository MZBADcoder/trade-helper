# ARCHITECTURE-BASELINE — 当前架构基线（Trader Helper）

日期：2026-02-09  
状态：Living Document（随项目演进更新，不作为单点决策记录）

## 1. 目标

- 记录当前默认架构、组件职责与边界约束，便于后续 PRD/ADR 对照：什么是“现在的共识”，什么是“需要新增 ADR 的变化”。

## 2. 当前技术栈（Baseline）

> 说明：MVP 技术栈已并入本基线；实时行情推送细节见 `ADR-0001`（当前已落地股票链路）。

- 前端：React（Vite）
- 在线 API：FastAPI
- 离线任务：Celery worker + Celery beat
- Broker/消息总线：Redis（Celery + WS 实时广播）
- 存储：Postgres
- 部署：单机 Docker Compose
- Python 依赖：poetry

## 3. 组件与职责

- `frontend`
  - 负责 UI 展示、交互、指标本地计算（当前 V1 方案）。
- `api`（FastAPI）
  - 负责鉴权、配置与查询（CRUD）、对前端提供稳定的 HTTP API 与 WS endpoint。
  - 原则：请求链路内避免重计算，复杂计算交给 worker。
- `realtime`（当前已启用，供 PRD-0001 股票实时推送使用）
  - 负责连接 Massive WebSocket，做订阅聚合、重连与消息标准化，并向内广播给 API（见 `ADR-0001`）。
- `worker`（Celery）
  - 负责可重试、可并发、可能耗时的任务：数据拉取/回填、扫描计算、告警发送等。
- `beat`（Celery Beat）
  - 负责按固定频率投递任务（例如定时扫描）。
- `redis`
  - 作为 Celery broker 与 WS 实时广播通道（pub/sub）。
  - 当前阶段不作为 `market-data/bars` 聚合查询缓存。
- `postgres`
  - 存储业务数据：用户、watchlist、历史 bars、告警历史等（按 feature 演进扩展）。

## 4. 后端分层与边界（DDD no-interfaces）

依赖方向必须为：

`api → application → infrastructure → domain`

关键约束：

- `domain/` 必须保持纯净：不依赖 FastAPI / Pydantic / SQLAlchemy / Redis / Celery。
- 不引入 `Protocol/ABC` 风格接口层；使用具体类 + 依赖注入（composition root 在 `application/container.py`）。
- API 层职责保持薄：校验 DTO → 调用 application service → 映射 DTO → 映射错误到 HTTP。
- ORM ↔ Domain 映射仅放在 `infrastructure/db/mappers.py`。

## 5. 典型数据流（现状）

- 历史 bars 查询：
  1) 前端请求 `GET /api/v1/market-data/bars`
  2) API 调用 market_data application service
  3) service 优先读库（命中覆盖区间则直接返回）
  4) 缺数据则调用 Massive REST 拉取并 upsert 落库，再返回

- 实时行情推送（已落地，见 `ADR-0001`）：
  1) `realtime` 进程连接 Massive WS，聚合 subscriptions，并输出标准化消息
  2) 通过 Redis（pub/sub 或 stream）广播最新消息/快照
  3) API 提供 `WS /api/v1/market-data/stream` 给前端订阅与转发
  4) WS 不可用时，降级为 REST polling（前后端协作实现）

## 6. 何时需要新增 ADR

- PRD 引入新组件/中间件/部署模型（例如新增“实时行情长连接进程”）
- 接口边界发生变化（例如前端直连第三方 WS vs 服务端代理）
- 数据一致性/幂等/去重策略变更
- 影响多模块协作或后续迁移成本的决策

## 7. 参考文档

- `/Users/mz/pmf/trader-helper/docs/adr/ADR-0001-realtime-market-data-streaming.md`
- `/Users/mz/pmf/trader-helper/backend/ARCHITECTURE.md`
- `/Users/mz/pmf/trader-helper/docs/README.md`
