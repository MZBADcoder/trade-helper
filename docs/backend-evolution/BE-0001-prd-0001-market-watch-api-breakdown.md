# BE-0001 — PRD-0001 后端接口拆分（实时行情 / 数据观察）

## 1. Context

- Source PRD: `/Users/mz/pmf/trader-helper/docs/prd/PRD-0001-market-watch.md`
- Related ADR:
  - `/Users/mz/pmf/trader-helper/docs/adr/ARCHITECTURE-BASELINE.md`
  - `/Users/mz/pmf/trader-helper/docs/adr/ADR-0001-realtime-market-data-streaming.md`
- Scope boundary：
  - 支撑 `/terminal` 的行情展示：历史 bars + 实时快照/推送
  - 支撑 options 基础能力：到期列表、期权链、合约详情、（可选）合约实时更新
  - Polygon API Key 仅在服务端使用（前端不直连）

## 2. Current APIs（Already Available）

| Method | Path | Purpose | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register` | 用户注册 | No |
| POST | `/api/v1/auth/login` | 用户登录 | No |
| GET | `/api/v1/auth/me` | 当前用户信息 | Yes |
| GET | `/api/v1/watchlist` | 查询关注列表 | Yes |
| POST | `/api/v1/watchlist` | 添加关注标的 | Yes |
| DELETE | `/api/v1/watchlist/{ticker}` | 删除关注标的 | Yes |
| GET | `/api/v1/market-data/bars` | 查询 OHLCV bars（当前用于股票；后续可复用于期权合约） | Yes |

## 3. API Changes

### 3.1 New APIs（建议新增）

| Method | Path | Purpose | Auth | Priority |
|---|---|---|---|---|
| GET | `/api/v1/market-data/snapshots` | 批量获取 ticker 快照（Last/Change/%Change/UpdatedAt 等） | Yes | P0 |
| WS | `/api/v1/market-data/stream` | 实时推送（股票/期权） | Yes | P0 |
| GET | `/api/v1/options/expirations` | 获取某 underlying 的到期列表 | Yes | P0 |
| GET | `/api/v1/options/chain` | 获取某 underlying + expiration 的期权链快照 | Yes | P0 |
| GET | `/api/v1/options/contracts/{option_ticker}` | 获取单合约详情/快照（用于合约详情页） | Yes | P1 |

### 3.2 API Updates（建议调整/澄清）

| Method | Path | Change | Compatibility | Priority |
|---|---|---|---|---|
| GET | `/api/v1/market-data/bars` | 明确 `timespan/multiplier/from/to` 允许值与错误码；补齐分页/分段拉取策略说明 | Compatible | P1 |
| GET | `/api/v1/market-data/bars` | 明确是否允许传入 option contract ticker（若 Polygon 支持同形态聚合） | Compatible | P2 |

### 3.3 Deprecated APIs

- None

## 4. Contract Details（接口合同要点）

- `GET /market-data/snapshots`
  - 请求：`tickers=AAPL,NVDA,...`（或重复 query param，二选一）
  - 响应：每个 ticker 至少包含：
    - `ticker`
    - `last`、`change`、`change_pct`
    - `updated_at`（UTC ISO8601）
    - `source`（REST/WS，便于 UI 展示状态）
- `WS /market-data/stream`
  - 订阅策略：仅允许订阅「watchlist + 当前选中合约」范围，并有服务端上限保护
  - 消息：统一 envelope（`type` + `data` + `ts`），前端按 `type` 路由处理
  - 鉴权：WebSocket 握手携带 JWT（query/header），服务端校验失败立即拒绝
  - 心跳：服务端定时 ping，客户端需响应，超时清理连接

## 5. 协同加载案例（历史 REST + 实时 WS）

场景：用户打开 `/terminal`，选中 `AAPL` 并观察分钟级走势。

1) 首屏 REST 批量加载：
   - `GET /api/v1/market-data/bars`：拉取 `AAPL` 最近 N 根分钟线（用于图表历史窗口）。
   - `GET /api/v1/market-data/snapshots?tickers=...`：批量拉取 watchlist 最新价（用于列表区）。
2) 建立 WS 订阅：
   - 前端建立 `WS /api/v1/market-data/stream`，提交 `subscribe(AAPL)`。
   - 服务端验证 JWT、订阅权限与订阅数量上限。
3) 增量合并：
   - API 持续推送实时事件；前端将事件并入当前图表最后一根或新增新 bar，保持图表“滚动更新”。
4) 异常修正：
   - 发生断线/重连后，前端补拉最近短窗口 bars（如最近 5-30 分钟）修复可能缺口。
   - WS 不可用时切换 REST 轮询（例如 snapshots 每 2-5s、bars 每 15-30s）。

该流程的职责划分：**REST 负责初始一致性与补洞，WS 负责实时低延迟增量**。

## 6. Data/Task Impact

- DB schema/index changes：
  - 可先不落库 tick；历史 bars 已落库（现有表）
  - options chain/合约引用数据：可先走实时查询；若后续性能不足再评估落库与缓存
- Background jobs changes：
  - 预拉取（prefetch）与数据修复任务可继续由 Celery 承担
- Caching/queue impact：
  - Redis 除 Celery broker 外，建议增加 pub/sub 或 stream 用于实时消息广播与跨进程分发
  - 关键缓存：watchlist 快照、热门 ticker 最新价/最近 bars（设置 TTL）
  - 新增 realtime 进程（长连接）负责 Polygon WS → Redis

## 7. Delivery Plan（建议实现顺序）

1) 先稳定现有 `auth/watchlist/market-data/bars`（输入校验、分页/分段策略、错误码一致性）。  
2) 新增 `market-data/snapshots`（先 REST 实现，满足 watchlist 行展示）。  
3) 新增 `options/expirations` + `options/chain`（先 REST，实现最小 options 观察）。  
4) 增加 realtime 进程 + `market-data/stream`（WS 推送；并落地降级策略）。  
5) 接入 Redis 广播与多实例扇出验证（本地 Compose → 多实例）。  

## 8. Acceptance Checklist

- [ ] `/terminal` 端到端不依赖 mock（bars + snapshot 可用）
- [ ] options chain 可加载（到期列表 + chain）
- [ ] WS 推送可用，且具备断线重连与服务端配额保护
- [ ] 超限/降级状态可见（便于排障与成本控制）
- [ ] WebSocket 鉴权失败有明确错误码/提示
