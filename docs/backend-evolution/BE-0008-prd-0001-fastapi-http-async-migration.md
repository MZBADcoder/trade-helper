# BE-0008 - PRD-0001 FastAPI HTTP 异步化迁移

日期：2026-03-01

## 1. 背景

- 现有后端使用 FastAPI 作为在线 API 框架，但 HTTP 主链路实际仍是同步实现：
  - API endpoint 为同步 `def`
  - SQLAlchemy 使用同步 `Session`
  - 认证限流与 Massive REST client 为同步 I/O
- WebSocket 链路已经是异步实现，导致在线 API 形成“HTTP 同步栈 + WS 异步栈”的不一致状态。
- 本次迁移目标是让在线 HTTP 请求真正使用 FastAPI 的异步执行模型，同时保持现有 DDD + No Interfaces 分层不变。

## 2. 本次范围

- `api -> application -> infrastructure -> domain` 中，与在线 HTTP 请求直接相关的链路全部异步化
- `/demo` HTTP 接口一并异步化
- Celery 保持同步 task 入口，但内部统一桥接异步 application service

不在本次范围：

- WebSocket Pub/Sub 架构重写
- Domain 规则重构
- Massive SDK 全量替换
- PostgreSQL schema / Alembic 迁移策略调整

## 3. 关键决策

### 3.1 数据库访问统一迁到 AsyncSession

- `infrastructure/db/session.py` 改为 `create_async_engine + async_sessionmaker`
- `infrastructure/db/uow.py` 改为 `async with uow`
- repository 全部改为 `AsyncSession` + `await execute/get/flush/commit`

### 3.2 HTTP 入口统一改为 async def

- 所有非 WS HTTP endpoint 统一改为 `async def`
- `api/deps.get_current_user` 改为异步依赖
- application service 公有方法改为异步调用形式

### 3.3 Massive REST 先使用异步适配层，不在 API 层直接桥接线程池

- 当前 Massive Python SDK 未确认存在官方原生 async REST client
- 本次在 `infrastructure/clients/massive.py` 内部使用 `asyncio.to_thread` 封装同步 SDK
- API / application 不再直接感知线程池桥接细节

### 3.4 TradingCalendar 保持同步查询接口，但节假日覆盖刷新前置为异步

- `TradingCalendar` 新增异步 holiday cache refresh
- 交易日判断、交易时长计算等纯规则仍保持同步函数
- application service 在进入主流程前先刷新节假日缓存，避免在同步计算中触发阻塞 I/O

### 3.5 Celery 保持同步 task 壳，内部执行异步 service

- task 入口仍为同步 `def`
- task 内通过 `asyncio.run(...)` 调用异步 application service
- 避免为 Celery 继续保留一套同步 service 实现

## 4. 本次落地结果

- HTTP 在线接口已异步化：
  - `auth`
  - `watchlist`
  - `market-data`
  - `options`
  - `demo`
  - `health`
- WebSocket 链路已移除对同步 service 的 `run_in_threadpool` 依赖，直接 await 异步认证与 watchlist 查询
- Redis 登录限流已迁移到 `redis.asyncio`
- `/demo` HTTP 与 replay service 的公开入口已改为异步形式
- 测试层已补齐 `pytest-asyncio`

## 5. 验证结果

- 边界检查：
  - `python3 scripts/check_boundaries.py --root . --package app`
- 单元测试：
  - `poetry run python3 -m pytest -q`

当前结果：全部通过。

## 6. 剩余事项

- 继续跟踪 Massive 官方 SDK；若后续提供原生 async REST client，可替换当前 `to_thread` 适配层
- 增加真实 Postgres / Redis 的异步集成测试，验证连接池、事务回滚与资源释放行为
