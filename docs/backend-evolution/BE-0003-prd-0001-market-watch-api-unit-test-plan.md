# BE-0003 - PRD-0001 API 层单测计划（股票主线）

## 1. 目标

为股票主线 API 提供稳定的参数校验、错误映射与主路径覆盖。

## 2. 覆盖范围

- `GET /api/v1/market-data/snapshots`
- `GET /api/v1/market-data/bars`
- `GET /api/v1/market-data/trading-days`
- `WS /api/v1/market-data/stream`（协议基础行为）

## 3. 重点用例

### 3.1 snapshots

- 空 tickers 与非法 ticker 拦截
- ticker 去重与上限 50
- 正常返回 payload 映射

### 3.2 bars

- 缺失 ticker 拦截
- 非法 ticker 格式拦截
- 非法 timespan/session/range 拦截
- 正常路径返回 `X-Data-Source` / `X-Partial-Range`

### 3.3 trading-days

- 参数透传与默认值验证
- 返回 ISO 日期列表

### 3.4 stream

- 未鉴权关闭
- subscribe/unsubscribe 成功
- 心跳超时关闭与恢复

## 4. 不在本次范围

- 非股票扩展 API 测试（已从项目范围移除）

## 5. 验收

- [ ] API 层主路径测试通过
- [ ] 参数失败分支测试通过
- [ ] WS 基础协议测试通过
