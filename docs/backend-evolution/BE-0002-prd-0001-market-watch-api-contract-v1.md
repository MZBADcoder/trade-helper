# BE-0002 - PRD-0001 行情接口合同设计（v1）

## 1. 背景与范围

- 来源 PRD：
  - `docs/prd/PRD-0001-market-watch.md`
- 关联 ADR：
  - `docs/adr/ARCHITECTURE-BASELINE.md`
  - `docs/adr/ADR-0001-realtime-market-data-streaming.md`
- 范围边界：
  - 本文仅定义接口合同（HTTP/WS 入参、出参、错误码、鉴权与配额语义）。
  - 不包含实现细节（不涉及 repository、cache key、worker 代码）。
  - 覆盖 BE-0001 已识别的新增/调整接口，作为前后端联调基线。

## 2. 接口变更清单

### 2.1 新增接口

| Method | Path | 用途 | 鉴权 | 优先级 |
|---|---|---|---|---|
| GET | `/api/v1/market-data/snapshots` | 批量获取 ticker 最新快照（watchlist 首屏/轮询兜底） | Yes | P0 |
| GET | `/api/v1/options/expirations` | 获取某 underlying 可选到期日列表 | Yes | P0 |
| GET | `/api/v1/options/chain` | 获取某 underlying + expiration 的期权链快照 | Yes | P0 |
| GET | `/api/v1/options/contracts/{option_ticker}` | 获取单个期权合约详情与行情快照 | Yes | P1 |
| WS | `/api/v1/market-data/stream` | 订阅股票/期权实时增量消息 | Yes | P0 |

### 2.2 调整接口

| Method | Path | 变更内容 | 兼容性 | 优先级 |
|---|---|---|---|---|
| GET | `/api/v1/market-data/bars` | 固化参数枚举、窗口限制、错误码与分页语义 | Compatible（新增校验不破坏已有成功路径） | P1 |
| GET | `/api/v1/market-data/bars` | 明确支持 `ticker`（股票）与 `option_ticker`（期权）二选一 | Compatible（保持 ticker 路径可用） | P2 |

### 2.3 废弃接口

当前版本无废弃接口。

## 3. 合同细节

### 3.1 通用约定

- 鉴权：除 `health/auth` 外，全部接口要求 Bearer JWT。
- 时间格式：统一 UTC ISO8601（示例：`2026-02-10T14:31:22Z`）。
- REST 错误响应统一结构：

```json
{
  "error": {
    "code": "MARKET_DATA_INVALID_RANGE",
    "message": "from must be earlier than to",
    "details": {
      "from": "2026-02-11T00:00:00Z",
      "to": "2026-02-10T00:00:00Z"
    }
  }
}
```

- 错误码命名：`<DOMAIN>_<SCENARIO>`，全大写下划线。

### 3.2 `GET /api/v1/market-data/snapshots`

#### 请求

Query 参数：

- `tickers`：必填，逗号分隔 ticker 列表（例：`AAPL,NVDA,TSLA`）
  - 去重后数量上限：`50`
  - 单个 ticker 格式：`^[A-Z.]{1,15}$`

#### 响应（200）

```json
{
  "items": [
    {
      "ticker": "AAPL",
      "last": 203.12,
      "change": -0.85,
      "change_pct": -0.42,
      "open": 204.01,
      "high": 205.30,
      "low": 201.98,
      "volume": 48923112,
      "updated_at": "2026-02-10T14:31:22Z",
      "market_status": "open",
      "source": "REST"
    }
  ]
}
```

#### 错误码

- `400 MARKET_DATA_INVALID_TICKERS`
- `400 MARKET_DATA_TOO_MANY_TICKERS`
- `401 AUTH_UNAUTHORIZED`
- `429 MARKET_DATA_RATE_LIMITED`
- `502 MARKET_DATA_UPSTREAM_UNAVAILABLE`

### 3.3 `GET /api/v1/options/expirations`

#### 请求

Query 参数：

- `underlying`：必填，例如 `AAPL`
- `limit`：可选，默认 `12`，最大 `36`
- `include_expired`：可选，默认 `false`

#### 响应（200）

```json
{
  "underlying": "AAPL",
  "expirations": [
    {
      "date": "2026-02-21",
      "days_to_expiration": 11,
      "contract_count": 184
    }
  ],
  "source": "REST",
  "updated_at": "2026-02-10T14:32:10Z"
}
```

#### 错误码

- `400 OPTIONS_INVALID_UNDERLYING`
- `400 OPTIONS_INVALID_LIMIT`
- `401 AUTH_UNAUTHORIZED`
- `404 OPTIONS_UNDERLYING_NOT_FOUND`
- `502 OPTIONS_UPSTREAM_UNAVAILABLE`

### 3.4 `GET /api/v1/options/chain`

#### 请求

Query 参数：

- `underlying`：必填
- `expiration`：必填，格式 `YYYY-MM-DD`
- `strike_from`：可选，decimal
- `strike_to`：可选，decimal
- `option_type`：可选，`call|put|all`，默认 `all`
- `limit`：可选，默认 `200`，最大 `500`
- `cursor`：可选，服务端返回的游标

#### 响应（200）

```json
{
  "underlying": "AAPL",
  "expiration": "2026-02-21",
  "items": [
    {
      "option_ticker": "O:AAPL260221C00210000",
      "option_type": "call",
      "strike": 210,
      "bid": 1.23,
      "ask": 1.28,
      "last": 1.25,
      "iv": 0.312,
      "volume": 1532,
      "open_interest": 10421,
      "updated_at": "2026-02-10T14:33:02Z",
      "source": "REST"
    }
  ],
  "next_cursor": "eyJvZmZzZXQiOjIwMH0="
}
```

#### 错误码

- `400 OPTIONS_INVALID_EXPIRATION`
- `400 OPTIONS_INVALID_STRIKE_RANGE`
- `400 OPTIONS_INVALID_CURSOR`
- `401 AUTH_UNAUTHORIZED`
- `404 OPTIONS_CHAIN_NOT_FOUND`
- `502 OPTIONS_UPSTREAM_UNAVAILABLE`

### 3.5 `GET /api/v1/options/contracts/{option_ticker}`

#### 请求

Path 参数：

- `option_ticker`：必填，Polygon 期权代码（例：`O:AAPL260221C00210000`）

Query 参数：

- `include_greeks`：可选，默认 `true`

#### 响应（200）

```json
{
  "option_ticker": "O:AAPL260221C00210000",
  "underlying": "AAPL",
  "expiration": "2026-02-21",
  "option_type": "call",
  "strike": 210,
  "multiplier": 100,
  "quote": {
    "bid": 1.23,
    "ask": 1.28,
    "last": 1.25,
    "updated_at": "2026-02-10T14:33:02Z"
  },
  "session": {
    "open": 1.51,
    "high": 1.58,
    "low": 1.11,
    "volume": 1532,
    "open_interest": 10421
  },
  "greeks": {
    "delta": 0.45,
    "gamma": 0.03,
    "theta": -0.08,
    "vega": 0.11,
    "iv": 0.312
  },
  "source": "REST"
}
```

#### 错误码

- `400 OPTIONS_INVALID_TICKER`
- `401 AUTH_UNAUTHORIZED`
- `404 OPTIONS_CONTRACT_NOT_FOUND`
- `502 OPTIONS_UPSTREAM_UNAVAILABLE`

### 3.6 `GET /api/v1/market-data/bars`（补充合同）

#### 请求

Query 参数（v1 固化）：

- `timespan`：`minute|day|week|month`
- `multiplier`：正整数，默认 `1`，上限 `60`
- `from` / `to`：ISO8601，且 `from < to`
- `limit`：可选，默认 `500`，最大 `5000`
- `ticker`：股票代码，与 `option_ticker` 二选一
- `option_ticker`：期权代码，与 `ticker` 二选一

#### 响应（200，不变）

保持现有 bars 列表结构，仅新增响应 header：

- `X-Data-Source: CACHE|REST|DB`
- `X-Partial-Range: true|false`

#### 错误码

- `400 MARKET_DATA_INVALID_TIMESPAN`
- `400 MARKET_DATA_INVALID_RANGE`
- `400 MARKET_DATA_SYMBOL_REQUIRED`
- `400 MARKET_DATA_SYMBOL_CONFLICT`
- `413 MARKET_DATA_RANGE_TOO_LARGE`
- `401 AUTH_UNAUTHORIZED`
- `502 MARKET_DATA_UPSTREAM_UNAVAILABLE`

### 3.7 `WS /api/v1/market-data/stream`

#### 握手与鉴权

- URL：`/api/v1/market-data/stream`
- JWT 载体（浏览器）：`query token` 或 `cookie` 或 `Sec-WebSocket-Protocol`
- JWT 载体（非浏览器）：可选 `Authorization` header
- 认证失败：关闭连接，close code `4401`

#### 客户端 -> 服务端消息

```json
{
  "action": "subscribe",
  "symbols": ["AAPL", "O:AAPL260221C00210000"],
  "channels": ["trade", "quote", "aggregate"]
}
```

- `action`：`subscribe|unsubscribe|ping`
- 单连接 symbol 上限：`100`
- 仅允许订阅用户 watchlist + 当前选中合约集合

#### 服务端 -> 客户端消息（统一 envelope）

```json
{
  "type": "market.quote",
  "ts": "2026-02-10T14:34:01.123Z",
  "source": "WS",
  "data": {
    "symbol": "AAPL",
    "event_ts": "2026-02-10T14:34:01.021Z",
    "bid": 203.11,
    "ask": 203.12,
    "last": 203.12
  }
}
```

#### 控制/错误消息

```json
{
  "type": "system.error",
  "ts": "2026-02-10T14:34:02.000Z",
  "source": "WS",
  "data": {
    "code": "STREAM_SUBSCRIPTION_LIMIT_EXCEEDED",
    "message": "max 100 symbols per connection"
  }
}
```

- 常见 WS 错误码：
  - `STREAM_INVALID_ACTION`
  - `STREAM_SUBSCRIPTION_LIMIT_EXCEEDED`
  - `STREAM_SYMBOL_NOT_ALLOWED`
  - `STREAM_RATE_LIMITED`

#### 心跳

- 服务端每 `20s` 发送 `{"type":"system.ping"}`
- 客户端需在 `10s` 内回应 `{"action":"ping"}` 或 pong 帧
- 连续 `2` 次超时则关闭连接，close code `4408`

### 3.8 OpenAPI/WS 联调补充（评审意见收敛）

#### OpenAPI 示例片段（建议）

```yaml
paths:
  /api/v1/market-data/snapshots:
    get:
      summary: 批量获取行情快照
      parameters:
        - in: query
          name: tickers
          required: true
          schema:
            type: string
            example: AAPL,NVDA,TSLA
      responses:
        '200':
          description: 成功
        '400':
          description: 参数错误
        '401':
          description: 未认证
        '429':
          description: 限流
        '502':
          description: 上游不可用
```

#### WS close code 对照表

| close code | 场景 | 前端建议动作 |
|---|---|---|
| 4401 | JWT 缺失/无效/过期 | 刷新 token 并重连 |
| 4403 | 订阅 symbol 不在授权范围 | 回退到 watchlist 默认订阅集 |
| 4408 | 心跳超时 | 立即重连并触发短窗口补拉 |
| 4413 | 触发订阅数量上限 | 减少订阅后重试 |
| 4500 | 服务端内部错误 | 指数退避重连并显示降级状态 |

## 4. 数据与任务影响

- DB schema/index changes:
  - 本阶段无强制 DDL 变更；沿用现有 bars 存储策略
- Background jobs changes:
  - 可选新增预热任务：watchlist snapshots 短 TTL 预取
- Caching/queue impact:
  - snapshots/expirations/chain/contracts 建议接入 Redis cache-aside
  - WS 依赖 Redis Pub/Sub 进行多实例广播

## 5. 交付计划

1. Phase 1（接口定义冻结）
   - 固化 OpenAPI 字段、枚举、错误码
   - 前端按合同接入 mock adapter
2. Phase 2（REST 能力落地）
   - 实现 snapshots + options 三组 REST
   - 完成 bars 参数校验与兼容回归
3. Phase 3（实时能力落地）
   - 实现 WS 鉴权、订阅协议、心跳与配额
   - 验证断线重连与 REST 轮询降级协同

## 6. 验收清单

- [ ] API docs updated（含 OpenAPI + WS 协议说明）
- [ ] 与前端完成字段级合同走查
- [ ] 错误码覆盖参数错误、上游错误、配额错误
- [ ] bars 兼容性通过：旧前端不改代码可继续使用
- [ ] WS 协议包含鉴权、订阅、心跳、错误回执
