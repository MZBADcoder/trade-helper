# BE-0006 — PRD-0001 交易日口径统一与 Snapshot 非交易日回退

## 背景

此前分钟级范围校验与前端窗口计算存在“日历日 vs 交易日”口径不一致：

- 后端 `MARKET_DATA_RANGE_TOO_LARGE` 估算按日历天展开，周末/休市日会放大点数。
- 前端曾以 `weekday` 近似交易日，遇到节假日会偏移窗口。
- 非交易日 watchlist 可能出现 `change/change_pct = 0`，不符合“最近交易日涨跌”预期。

## 本次改造目标

1. 后端交易日口径单点收敛到 `TradingCalendar`。
2. 分钟级范围校验按真实交易时段分钟数估算。
3. 提供统一 `trading-days` 接口给前端，替代本地 weekday 近似。
4. 非交易日 snapshot 优先使用 DB 日线基准，避免全 0% 展示。

## 关键设计

### 1) 交易日双源策略

- 历史（`date < today`）：`exchange-calendars(XNYS)` 为主。
- 今天/未来（`date >= today`）：在日历基准上叠加 Massive `market_holidays` 覆盖。
- 半日市分钟数按交易所 open/close 时间计算。

### 2) 范围估算策略

- minute：`sum(session_minutes) / multiplier`
- day：`count(trading_days) / multiplier`
- week/month：按交易日数折算（`5`/`21` 交易日近似）

### 3) Snapshot 策略

- 非交易日：优先使用 DB 最近两日线计算 `change/change_pct`。
- 交易日：仍可使用 Massive snapshot；若上游 `change` 缺失且有 `prev_close`，则重算兜底。

## 接口变更

新增：

- `GET /api/v1/market-data/trading-days?end=YYYY-MM-DD&count=N`
  - 返回：`{ "items": ["YYYY-MM-DD", ...] }`（升序）

## 风险与后续

1. `market_holidays` 为 upcoming 视角，临时停市仍需结合 `market_status` 做覆盖与监控。
2. 交易日盘中 `change/change_pct` 未来可继续收敛为“WS 最新价 + DB prev_close”实时口径。
