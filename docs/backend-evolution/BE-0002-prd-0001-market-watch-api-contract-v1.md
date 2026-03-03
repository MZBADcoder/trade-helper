# BE-0002 - PRD-0001 股票行情接口合同（v1）

## 1. 范围

- 来源：`docs/prd/PRD-0001-market-watch.md`
- 仅覆盖股票接口合同与 WS 协议。
- 非股票扩展接口合同已移除。

## 2. REST 合同

### 2.1 `GET /api/v1/market-data/snapshots`

- Query：`tickers`（逗号分隔，最多 50 个唯一 ticker）
- Response：`{ items: [{ ticker, last, change, change_pct, open, high, low, volume, updated_at, market_status, source }] }`

### 2.2 `GET /api/v1/market-data/bars`

- Query：`ticker`（必填）、`timespan`、`multiplier`、`session`、`from`、`to`、`limit`
- Header：
  - `X-Data-Source`: `REST | DB | DB_AGG | DB_AGG_MIXED`
  - `X-Partial-Range`: `true | false`
- Response：bars 数组

### 2.3 `GET /api/v1/market-data/trading-days`

- Query：`end`、`count`
- Response：`{ items: ["YYYY-MM-DD", ...] }`

## 3. WS 合同

### 3.1 `WS /api/v1/market-data/stream`

- 鉴权：JWT
- 客户端消息：`subscribe/unsubscribe/ping`
- 服务端消息：
  - 行情：`type=data.market`
  - 状态：`type=system.status`
  - 心跳：`type=system.pong`
- 失败关闭语义：未授权、订阅超限、心跳超时

## 4. 错误码约定

- bars 参数错误：`MARKET_DATA_INVALID_*`
- snapshots 错误：`MARKET_DATA_INVALID_TICKERS` / `MARKET_DATA_TOO_MANY_TICKERS`
- 上游异常：`MARKET_DATA_UPSTREAM_UNAVAILABLE` / `MARKET_DATA_RATE_LIMITED`

## 5. 兼容性说明

- 本合同与当前前端终端页保持兼容。
- 后续字段新增优先采用“可选字段 + 不破坏旧字段”策略。
