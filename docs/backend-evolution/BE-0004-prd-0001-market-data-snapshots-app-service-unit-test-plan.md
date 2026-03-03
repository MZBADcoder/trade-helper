# BE-0004 - PRD-0001 Application Service 单测计划（股票主线）

## 1. 背景

当前应用服务以股票能力为主线，需确保以下服务行为稳定：
- `MarketDataApplicationService`
- `WatchlistApplicationService`
- `AuthApplicationService`

## 2. 测试目标

- 输入校验与标准化
- 上游异常映射
- 数据聚合与回退逻辑
- 事务边界（commit/rollback）

## 3. 核心用例

### 3.1 MarketDataApplicationService

- `list_snapshots`：多 ticker、缺失数据回退、上游失败兜底
- `list_bars_with_meta`：不同 timespan/multiplier/session 路径
- `list_trading_days`：交易日窗口与边界
- `is_stream_session_open`：延迟分钟语义

### 3.2 WatchlistApplicationService

- add/delete/list 的标准流程
- ticker 归一化与重复写保护

### 3.3 AuthApplicationService

- 登录成功与失败映射
- token 解析与过期语义

## 4. 不在本次范围

- 非股票扩展 application service（已移除）

## 5. 验收

- [ ] 核心服务用例覆盖并通过
- [ ] 关键异常路径（上游不可用、参数非法）有断言
- [ ] 不引入跨层依赖违规
