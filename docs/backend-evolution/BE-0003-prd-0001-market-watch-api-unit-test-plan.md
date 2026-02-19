# BE-0003 - PRD-0001 新增/修改接口 Unit Test 设计（基于 BE-0002/BE-0005）

## 0. 执行状态更新（2026-02-19）

- 当前迭代继续优先 Stock 主线 API 测试；options API 测试仍为 HOLD。
- `GET /api/v1/market-data/bars` 已接入 BE-0005 混合策略的 header 语义：
  - `X-Data-Source` 支持 `REST|DB|DB_AGG|DB_AGG_MIXED`
  - `X-Partial-Range` 保留 `true|false`
- API 测试已覆盖最小回归路径（snapshots 成功/限额、bars symbol 二选一、bars header 枚举）。
- WS 协议测试已落地：鉴权失败 close code、watchlist 权限、订阅上限与三类股票消息推送。

## 1. 目标与范围

本文定义 API 层（FastAPI `api/v1/endpoints/*`）unit test 设计，覆盖：

- 新增 REST：
  - `GET /api/v1/market-data/snapshots`
  - `GET /api/v1/options/expirations`（HOLD）
  - `GET /api/v1/options/chain`（HOLD）
  - `GET /api/v1/options/contracts/{option_ticker}`（HOLD）
- 修改 REST：
  - `GET /api/v1/market-data/bars`（参数校验、symbol 二选一、header 语义）
- 新增 WS：
  - `WS /api/v1/market-data/stream`（已实现并纳入回归）

约定：

- 不触达真实 Massive/Redis/DB
- 通过 dependency override 注入 fake service（具体类）
- 重点验证：入参校验、错误码映射、DTO 映射、header 合同

## 2. 现有测试基线（已落地）

测试文件：

- `backend/tests/app/api/test_market_data_endpoints.py`
- `backend/tests/app/api/test_market_data_stream_endpoint.py`

已覆盖：

- `test_snapshots_returns_contract_payload`
- `test_snapshots_rejects_too_many_tickers`
- `test_bars_requires_exactly_one_symbol`
- `test_bars_success_sets_contract_headers`

辅助夹具：

- `backend/tests/app/api/conftest.py` 中 `FakeMarketDataService.list_bars_with_meta`

## 3. 分层建议

### 3.1 API Handler 级 unit tests（优先）

- 覆盖入参校验、错误映射、header 与 DTO
- fake service 不出网、不触库

### 3.2 合同级 API tests（可选增强）

- 用 ASGI client 验证 query/path 解析行为（`alias="from"`、日期格式、limit 上限）
- 对未来错误码细化变更更敏感

### 3.3 WS 协议 tests（现状 + 待补）

- 已覆盖：
  - 鉴权失败 close code（`4401`）
  - 订阅权限错误码（`STREAM_SYMBOL_NOT_ALLOWED`）
  - 订阅上限错误码（`STREAM_SUBSCRIPTION_LIMIT_EXCEEDED`）
  - `market.quote` / `market.trade` / `market.aggregate` 推送
- 待补：
  - 心跳超时关闭语义（`4408`）

## 4. 接口测试清单（更新版）

### 4.1 `GET /api/v1/market-data/snapshots`

成功路径：

- `tickers=AAPL,NVDA` 返回 `200` + `items[*]` 字段完整

参数校验：

- 空 `tickers`
- 非法 ticker
- 去重后 > 50

错误映射：

- `MARKET_DATA_RATE_LIMITED` -> `429`
- `MARKET_DATA_UPSTREAM_UNAVAILABLE` -> `502`

### 4.2 `GET /api/v1/options/expirations`（HOLD）

- 保留原计划，待 Stock 主线里程碑后恢复

### 4.3 `GET /api/v1/options/chain`（HOLD）

- 保留原计划，待 Stock 主线里程碑后恢复

### 4.4 `GET /api/v1/options/contracts/{option_ticker}`（HOLD）

- 保留原计划，待 Stock 主线里程碑后恢复

### 4.5 `GET /api/v1/market-data/bars`（BE-0005 对齐）

成功路径：

- `ticker` 路径与 `option_ticker` 路径均可用
- 返回 `X-Data-Source`、`X-Partial-Range`

header 合同：

- `X-Data-Source ∈ {REST, DB, DB_AGG, DB_AGG_MIXED}`
- `X-Partial-Range ∈ {true, false}`

参数校验（重点）：

- `timespan` 非法 -> `400 MARKET_DATA_INVALID_TIMESPAN`
- `multiplier` 越界 -> `400 MARKET_DATA_INVALID_RANGE`
- `from >= to` -> `400 MARKET_DATA_INVALID_RANGE`
- 缺失 symbol -> `400 MARKET_DATA_SYMBOL_REQUIRED`
- `ticker` 与 `option_ticker` 同时出现 -> `400 MARKET_DATA_SYMBOL_CONFLICT`
- 超大窗口 -> `413 MARKET_DATA_RANGE_TOO_LARGE`

错误映射：

- 上游不可用 -> `502 MARKET_DATA_UPSTREAM_UNAVAILABLE`

## 5. 下一轮补测优先级

1. 先补 `bars` 参数校验未覆盖项（非法 timespan、非法 multiplier、from/to 反序、413 场景）。
2. 再补 `snapshots` 的非法 ticker 与上游错误映射。
3. HOLD 解除后恢复 `options/*` API 单测。
4. 最后补 `WS /market-data/stream` 的心跳超时（`4408`）与异常中断恢复语义测试。

## 6. 完成标准

- `market-data/snapshots` 与 `market-data/bars` 覆盖成功路径 + 关键失败路径
- `bars` header 合同（含 `DB_AGG_MIXED`）有稳定断言
- `WS /market-data/stream` 覆盖鉴权、权限、上限与三类股票消息推送
- options 当前阶段不回归；扩展覆盖待 HOLD 解除后补齐
- 测试代码保持 No Interfaces（不引入 `Protocol/ABC`）
