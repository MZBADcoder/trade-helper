# PRD-0001 — 实时行情 / 数据观察（Stocks，Massive.com）

> 状态：执行中（2026-03-03 更新）

## 0. 范围声明

- 本 PRD 当前仅覆盖 **美股股票（Stocks）**。
- 项目内原有非股票扩展目标、接口、页面与测试设计，已从当前范围中移除。
- 未来如需恢复非股票能力，将以新 PRD 重新立项，不复用本次已清理内容。

## 1. 背景

我们要建设一个自用的 Web Trader Terminal，用于股票行情观察，覆盖：
- watchlist 管理
- 快照行情（last/change/change_pct/open/high/low/volume）
- 历史 bars（day/minute）
- 实时增量推送与断线降级

目标是先把“股票主线”做到稳定可用，再考虑后续扩展。

## 2. 目标与非目标

### 2.1 目标

- G1：登录后可维护个人 watchlist，并查看批量快照。
- G2：可按 ticker 查看日线/分钟线历史 bars，并支持基础时间粒度切换。
- G3：具备实时更新能力（WS），并在异常时自动降级到 REST 轮询。
- G4：前后端数据口径统一，关键错误码可观测。

### 2.2 非目标

- N1：不包含衍生品链路与合约级详情能力。
- N2：不包含下单交易能力。
- N3：不包含告警编排与通知系统（另行立项）。

## 3. 用户场景

1. 用户登录后进入 `/terminal`，看到 watchlist 与实时状态。
2. 用户新增 `AAPL`、`NVDA` 等 ticker，列表显示最新快照。
3. 用户点击某个 ticker 查看 bars，切换 `1m/5m/15m/60m/day/week/month`。
4. WS 正常时，列表与详情持续增量更新；WS 中断时页面进入降级态并继续可用。

## 4. 功能需求（MVP）

### F1：Watchlist

- 支持新增/删除/查询 ticker。
- ticker 做格式校验并统一大写。
- 首次进入页面时默认选中第一支股票。

### F2：Market Snapshots

- 支持按 tickers 批量拉取快照。
- 支持交易时段与非交易时段展示（`market_status`）。
- 前端定时刷新作为 WS 异常时兜底。

### F3：Market Bars

- `GET /api/v1/market-data/bars` 仅接受 `ticker`。
- 支持 `timespan/multiplier/session/from/to/limit`。
- 返回 `X-Data-Source` 与 `X-Partial-Range`，用于前端可视化数据来源与范围截断。

### F4：Realtime Stream

- `WS /api/v1/market-data/stream` 提供股票实时增量。
- 鉴权失败、超限、心跳超时需返回明确关闭语义。
- 前端按状态机展示 `connected/reconnecting/degraded/disconnected`。

## 5. 非功能需求

- 安全：API Key 不暴露到前端；WS 必须鉴权。
- 可用性：WS 异常时自动降级，核心页面仍可读。
- 性能：watchlist 批量快照请求支持最多 50 个 ticker。
- 质量：后端边界检查与测试、前端 lint/test/build 全部通过。

## 6. 验收标准（DoD）

- [ ] 用户可完成 watchlist 的增删查。
- [ ] snapshots 接口可批量返回股票快照并在前端正确渲染。
- [ ] bars 接口可按 ticker 与时间区间稳定返回历史数据。
- [ ] WS 正常时页面有实时增量；WS 异常时前端自动降级且可恢复。
- [ ] 错误码在前后端展示一致，关键失败路径可追踪。

## 7. 里程碑

1. M1：Watchlist + snapshots 稳定可用。
2. M2：bars 查询链路与前端详情图表稳定可用。
3. M3：WS 增量、降级与恢复闭环完成。

## 8. 风险与开放项

- Massive 上游限流与配额策略需持续验证。
- 交易日/节假日边界需持续通过自动化测试守护。
- 后续若恢复非股票扩展能力，必须新建 PRD 并重新评估数据模型与状态机复杂度。
