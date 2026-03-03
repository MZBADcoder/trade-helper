# FE-MW-V2 - PRD-0001 终端页面增量设计（股票主线）

## 1. 范围

- 来源：`docs/prd/PRD-0001-market-watch.md`
- 本文仅覆盖股票观察主线，不包含衍生品工作区。

## 2. 页面信息架构

`/terminal` 采用三块主区域：

1. 左侧 `Watchlist`
2. 中部 `Detail Workspace`（K 线 + 指标 + 快照）
3. 底部 `Status Bar`（连接状态/来源/延迟/错误）

## 3. 关键交互

### 3.1 Watchlist

- 支持 ticker 新增/删除/刷新
- 点击行切换当前 active ticker
- 行内显示 `last/change/change_pct/updated`

### 3.2 Detail Workspace

- 支持 `1m/5m/15m/60m/day/week/month`
- 支持 session 切换（`regular/pre/night`）
- 支持“左侧历史补拉”
- 显示 bars 数据来源（`X-Data-Source`）

### 3.3 Status Bar

- 显示 WS 状态（idle/connecting/connected/reconnecting/degraded/disconnected）
- 显示当前数据来源（WS/REST）与延迟标识
- 显示最近同步时间和最近错误

## 4. 降级策略

- WS 可用：增量推送为主
- WS 不可用：退化为 snapshots/bars 轮询
- WS 恢复：执行短窗口补拉后回到增量模式

## 5. 数据依赖

- `GET /api/v1/watchlist`
- `GET /api/v1/market-data/snapshots`
- `GET /api/v1/market-data/bars`
- `GET /api/v1/market-data/trading-days`
- `WS /api/v1/market-data/stream`

## 6. 验收点

- [ ] watchlist 与详情区状态同步
- [ ] timeframe/session 切换可触发正确查询
- [ ] WS 中断时进入 degraded 且页面仍可用
- [ ] WS 恢复后数据可自动对齐
