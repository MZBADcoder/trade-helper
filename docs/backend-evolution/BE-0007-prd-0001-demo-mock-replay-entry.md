# BE-0007 — PRD-0001 Demo Mock 回放入口

## 1. Context

- Source PRD: `docs/prd/PRD-0001-market-watch.md`
- Related ADR:
  - `docs/adr/ARCHITECTURE-BASELINE.md`
  - `docs/adr/ADR-0001-realtime-market-data-streaming.md`
- ADR 影响：
  - 无新增 ADR。该能力仍沿用“服务端提供 REST/WS 给前端”的既有模式，只是将 `/demo` 的数据源从前端本地模拟改为后端 mock 回放。

## 2. Goal

- 为 `/demo` 提供一个**稳定、免登录、与交易时段解耦**的测试入口。
- 后端统一生成 mock bars / snapshot / websocket 增量，前端不再自己拼装本地 demo 数据。
- 当前阶段固定只支持 `AMD`，后续若要扩展多个 ticker，再单独评估复杂度与契约。

## 3. Scope

### 3.1 In Scope

- 新增 `/api/v1/demo/*` REST/WS 接口。
- 固定回放最近一个已完成交易日的 `10:00-10:30 ET` 窗口。
- 首屏 REST 返回完整 30 根 `1m` bars。
- WS 按既有 envelope（`type/ts/source/data`）循环推送 `quote/trade/aggregate`。

### 3.2 Out of Scope

- 不接 Massive，不做真实行情回放。
- 不做多 ticker demo watchlist。
- 不把 `/demo` 接入登录/用户态。

## 4. API 清单

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/api/v1/demo/watchlist` | 返回固定 watchlist（当前仅 `AMD`） | No |
| GET | `/api/v1/demo/market-data/bars` | 返回固定 30 分钟窗口的 mock `1m` bars | No |
| GET | `/api/v1/demo/market-data/snapshots` | 返回当前 replay step 对应的 snapshot | No |
| WS | `/api/v1/demo/market-data/stream` | 循环推送 mock `quote/trade/aggregate` | No |

## 5. Contract 约束

### 5.1 Watchlist

- 响应固定为：
  - `[{ "ticker": "AMD", "created_at": null }]`

### 5.2 Bars

- 仅接受：
  - `ticker=AMD`
  - `timespan=minute`
  - `multiplier=1`
- 其他请求返回 `400`：
  - `code=DEMO_MARKET_DATA_INVALID_REQUEST`
- 响应 header：
  - `X-Data-Source: DEMO_MOCK`
  - `X-Partial-Range: false`

### 5.3 Snapshots

- 仅接受 `tickers=AMD`
- 返回字段对齐正式 `market-data/snapshots` 契约，`source=DEMO_MOCK`

### 5.4 WebSocket

- 首条消息：
  - `system.status`
  - `latency=real-time`
  - `connection_state=connected`
  - `message` 说明当前 replay 日期与固定时间窗口
- 增量消息：
  - `market.quote`
  - `market.trade`
  - `market.aggregate`
- `data.replay_index` 表示当前窗口内第几根 bar，用于前端识别循环回放重置点。

## 6. 数据生成策略

- 交易日：
  - 基于 `TradingCalendar.align_on_or_before()` 取最近一个**已完成**交易日。
- 时间窗口：
  - 固定 `10:00-10:30 ET`
- 价格生成：
  - 使用可复现 seed（`trade_date + ticker + window`）驱动的“随机震荡 + 正弦波”组合。
- 结果要求：
  - 同一交易日内 bars、snapshot、ws 增量完全可复现。
  - 不追求拟真成交明细，只保证走势连续、字段完整、便于联调。

## 7. 实现落点

- `backend/app/application/demo_market/service.py`
  - 回放窗口计算
  - mock bars / snapshot / ws payload 生成
- `backend/app/api/v1/endpoints/demo_market_data.py`
  - demo REST
- `backend/app/api/v1/endpoints/demo_market_data_stream.py`
  - demo WS
- `backend/tests/app/application/test_demo_market_data_service.py`
  - 服务层稳定性测试
- `backend/tests/app/api/test_demo_market_data_endpoints.py`
  - demo REST 合同测试
- `backend/tests/app/api/test_demo_market_data_stream_endpoint.py`
  - demo WS 合同测试

## 8. Acceptance

- `/demo` 不登录也能拉到 `AMD` watchlist / bars / snapshot
- bars 固定为 30 根 `1m`
- WS 可持续循环推送，不依赖 Massive 开盘状态
- 现有 `backend` 边界检查与 `pytest` 全部通过
