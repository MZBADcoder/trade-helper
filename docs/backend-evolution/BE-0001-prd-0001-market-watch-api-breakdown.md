# BE-0001 - PRD-0001 股票行情后端接口拆分

## 1. Context

- Source PRD：`docs/prd/PRD-0001-market-watch.md`
- Related ADR：`docs/adr/ADR-0001-realtime-market-data-streaming.md`
- 范围：仅股票主线，不含非股票扩展。

## 2. API 清单

| Method | Path | 用途 | Auth | Priority |
|---|---|---|---|---|
| POST | `/api/v1/auth/login` | 登录获取 token | No | P0 |
| GET | `/api/v1/watchlist` | 查询 watchlist | Yes | P0 |
| POST | `/api/v1/watchlist` | 新增 ticker | Yes | P0 |
| DELETE | `/api/v1/watchlist/{ticker}` | 删除 ticker | Yes | P0 |
| GET | `/api/v1/market-data/snapshots` | 批量股票快照 | Yes | P0 |
| GET | `/api/v1/market-data/bars` | 股票历史 bars | Yes | P0 |
| GET | `/api/v1/market-data/trading-days` | 交易日查询 | Yes | P1 |
| WS | `/api/v1/market-data/stream` | 股票实时增量 | Yes | P0 |
| GET | `/api/v1/demo/*` | demo 回放链路 | No | P2 |

## 3. 关键约束

- `bars` 仅接受 `ticker`，不再提供任何非股票扩展参数。
- API 层只做 DTO 校验/映射，不触达 ORM/Redis/Massive SDK。
- 错误码采用统一结构，前端可直接映射展示。

## 4. 交付顺序

1. 先固化 `auth/watchlist/snapshots/bars` REST 主链路。
2. 再完善 `stream` 的订阅、心跳和降级语义。
3. 最后补齐 demo 回放与边界测试。

## 5. 验收

- [ ] REST 接口可覆盖终端核心页面。
- [ ] stream 在连接异常时可降级并恢复。
- [ ] 单测覆盖参数校验与错误映射。
