# BE-0003 - PRD-0001 新增/修改接口 Unit Test 设计（基于 BE-0002 合同）

## 1. 目标与范围

本文定义 **API 层**（FastAPI `api/v1/endpoints/*`）的 unit test 设计，用于覆盖 BE-0002 中的：

- **新增 REST**：
  - `GET /api/v1/market-data/snapshots`
  - `GET /api/v1/options/expirations`
  - `GET /api/v1/options/chain`
  - `GET /api/v1/options/contracts/{option_ticker}`
- **新增 WS**：
  - `WS /api/v1/market-data/stream`
- **修改 REST**：
  - `GET /api/v1/market-data/bars`（参数枚举、窗口限制、ticker/option_ticker 二选一、错误码/分页语义、header）

> 约定：此处的 “unit test” 指 **不触达真实外部 IO**（Massive/Redis/DB），通过依赖注入替换 application service（具体类）来验证 API 的入参校验、错误映射与 DTO 映射。

## 2. 测试分层建议

### 2.1 API Handler 级 unit tests（优先）

目标：验证 endpoint handler 的：

- 入参校验（缺失/冲突/枚举/范围）
- auth 依赖是否强制
- application service 异常到 HTTP（状态码 + 错误码）的映射
- response DTO 字段与类型（最小字段集 + 默认值）

做法：

- 通过 FastAPI 的 dependency override 将 `get_*_service` 替换为 **FakeService（具体类）**
- 将 `get_current_user` 替换为固定用户（避免依赖真实 JWT）

### 2.2 合同级 API tests（可选，但对 Query/Path 解析更强）

目标：验证 FastAPI 对 Query/Path 的解析行为是否符合合同（例如 `alias="from"`、`YYYY-MM-DD`、bool/decimal 解析、上限限制等）。

做法：

- 使用 ASGI client（例如 `httpx` + `ASGITransport`）对 `app.main:create_app()` 发起请求
- 依赖 override 同 2.1（只测 API 层逻辑，不走真实 IO）

> 建议在实现阶段落地 2.2，因为它能真实覆盖 FastAPI 的参数解析与响应序列化；2.1 适合作为最小稳定单元测试。

### 2.3 WS 协议 tests（建议单独文件，偏“协议单测”）

目标：覆盖 BE-0002 的 WS 鉴权、订阅协议、配额与心跳关闭语义。

做法建议：

- 采用可控的心跳间隔（测试环境注入更短的超时阈值）
- 用可测试的 WebSocket client（根据现有依赖选型）
- 订阅逻辑与 symbol 白名单校验通过 fake service / fake policy 注入

## 3. 通用夹具（fixtures）设计

### 3.1 固定用户

- `current_user`：构造 `User(id=..., email=..., is_active=True, ...)`（以实际 domain schema 为准）

### 3.2 Fake Application Services（具体类，不使用 Protocol/ABC）

为每个 endpoint 所依赖的 application service 提供一个 “Fake*Service”：

- 返回固定的 domain 对象（用于验证 DTO mapping）
- 或抛出约定异常（用于验证错误映射）

异常约定（推荐统一，便于测试断言）：

- 参数错误：映射为 `400 <DOMAIN>_<SCENARIO>`
- 资源不存在：映射为 `404 <DOMAIN>_<SCENARIO>`
- 上游不可用：映射为 `502 <DOMAIN>_UPSTREAM_UNAVAILABLE`
- 限流：映射为 `429 <DOMAIN>_RATE_LIMITED`

> 若实现阶段暂时仍用 `ValueError(str)`，测试可先断言 status code + detail；但建议尽快引入统一错误对象/错误码以贴合 BE-0002 合同。

## 4. 按接口的 test case 清单（建议最小集）

下表的每一条都应至少覆盖：**无鉴权 401**、**成功 200**、**关键 400**、**关键 4xx/5xx**（如合同列出）。

### 4.1 `GET /api/v1/market-data/snapshots`

**成功路径**

- `tickers=AAPL,NVDA` 返回 `200`，`items` 至少包含：`ticker/last/change/change_pct/updated_at/source`

**参数校验**

- 缺少 `tickers`：`400 MARKET_DATA_INVALID_TICKERS`
- ticker 含非法字符（例如 `AA-PL`）：`400 MARKET_DATA_INVALID_TICKERS`
- 去重后数量 > 50：`400 MARKET_DATA_TOO_MANY_TICKERS`
- `tickers` 仅空白：`400 MARKET_DATA_INVALID_TICKERS`

**错误映射**

- application service 触发限流：`429 MARKET_DATA_RATE_LIMITED`
- 上游不可用：`502 MARKET_DATA_UPSTREAM_UNAVAILABLE`

### 4.2 `GET /api/v1/options/expirations`

**成功路径**

- `underlying=AAPL` 返回 `200`，包含 `underlying/expirations/source/updated_at`
- `limit` 缺省时默认 `12`
- `include_expired=true` 时包含过期项（由 fake service 控制返回即可）

**参数校验**

- 缺少 `underlying`：`400 OPTIONS_INVALID_UNDERLYING`
- `limit=0` 或负数：`400 OPTIONS_INVALID_LIMIT`
- `limit>36`：`400 OPTIONS_INVALID_LIMIT`

**错误映射**

- underlying 不存在：`404 OPTIONS_UNDERLYING_NOT_FOUND`
- 上游不可用：`502 OPTIONS_UPSTREAM_UNAVAILABLE`

### 4.3 `GET /api/v1/options/chain`

**成功路径**

- `underlying=AAPL&expiration=2026-02-21` 返回 `200`，包含 `items` 与 `next_cursor`（可为空）
- `option_type` 缺省时默认 `all`

**参数校验**

- `expiration` 格式非法（例如 `20260221`）：`400 OPTIONS_INVALID_EXPIRATION`
- `strike_from > strike_to`：`400 OPTIONS_INVALID_STRIKE_RANGE`
- `option_type` 非 `call|put|all`：`400 OPTIONS_INVALID_EXPIRATION`（或单独错误码；实现时需固化）
- `limit<=0` 或 `limit>500`：`400 OPTIONS_INVALID_EXPIRATION`（或单独错误码；实现时需固化）
- `cursor` 非法（不可解码/签名不合法）：`400 OPTIONS_INVALID_CURSOR`

**错误映射**

- 未找到 chain：`404 OPTIONS_CHAIN_NOT_FOUND`
- 上游不可用：`502 OPTIONS_UPSTREAM_UNAVAILABLE`

> 说明：上面两条 “或单独错误码” 是为了提前暴露合同里未细化的部分。建议实现阶段将其拆为更明确的错误码并同步 BE-0002。

### 4.4 `GET /api/v1/options/contracts/{option_ticker}`

**成功路径**

- `option_ticker=O:AAPL260221C00210000` 返回 `200`，包含 `quote/session/source`
- `include_greeks=true`（默认）返回 `greeks`
- `include_greeks=false` 时 `greeks` 为空/省略（实现时二选一并固化测试）

**参数校验**

- `option_ticker` 非法：`400 OPTIONS_INVALID_TICKER`

**错误映射**

- 合约不存在：`404 OPTIONS_CONTRACT_NOT_FOUND`
- 上游不可用：`502 OPTIONS_UPSTREAM_UNAVAILABLE`

### 4.5 `GET /api/v1/market-data/bars`（合同补充）

**成功路径**

- `ticker=AAPL&timespan=day&multiplier=1&from=...&to=...` 返回 `200`
- 响应 header 存在：`X-Data-Source`、`X-Partial-Range`
- `option_ticker=O:...` 路径同样可用（与 ticker 二选一）

**参数校验（重点）**

- `timespan` 非 `minute|day|week|month`：`400 MARKET_DATA_INVALID_TIMESPAN`
- `multiplier<1` 或 `multiplier>60`：`400 MARKET_DATA_INVALID_RANGE`（或单独错误码；实现时需固化）
- `from >= to`：`400 MARKET_DATA_INVALID_RANGE`
- 缺少 `ticker` 且缺少 `option_ticker`：`400 MARKET_DATA_SYMBOL_REQUIRED`
- 同时传 `ticker` 与 `option_ticker`：`400 MARKET_DATA_SYMBOL_CONFLICT`
- `limit>5000`：`400 MARKET_DATA_INVALID_RANGE`（或单独错误码；实现时需固化）

**窗口限制（413）**

- 构造超大时间窗口请求：`413 MARKET_DATA_RANGE_TOO_LARGE`
  - 需要实现阶段明确 “过大” 的规则（例如按 timespan*multiplier 限制最大 bars 数），并将该规则写入测试断言

**错误映射**

- 上游不可用：`502 MARKET_DATA_UPSTREAM_UNAVAILABLE`

### 4.6 `WS /api/v1/market-data/stream`

**握手鉴权**

- 缺少 token：连接被拒绝/关闭，close code `4401`
- token 无效：close code `4401`
- token 有效：成功建立连接

**订阅协议**

- `action` 非法：返回 `system.error`，code `STREAM_INVALID_ACTION`
- `symbols` 数量 > 100：返回 `system.error`，code `STREAM_SUBSCRIPTION_LIMIT_EXCEEDED`
- `symbols` 包含不在 “watchlist + 当前选中合约” 的 symbol：返回 `system.error`，code `STREAM_SYMBOL_NOT_ALLOWED`

**心跳**

- 服务端发送 `system.ping` 后，客户端按时回应 `{"action":"ping"}`：连接保持
- 客户端连续 2 次未回应：连接关闭，close code `4408`

> 时间相关测试建议将心跳间隔与超时阈值通过配置注入为更短值（例如 1s/0.5s），避免测试运行缓慢。

## 5. 交付建议（落地到测试代码时）

建议按优先级落地测试文件：

1. `market-data/bars` 参数校验与错误映射（回归风险最高）
2. `market-data/snapshots`（watchlist 首屏关键路径）
3. `options/*` 三个 REST（前端链路所需）
4. `market-data/stream`（协议与心跳，单独跑/可标记为较慢的测试组）

