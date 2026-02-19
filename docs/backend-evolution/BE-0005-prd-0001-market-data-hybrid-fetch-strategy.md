# BE-0005 - PRD-0001 market-data 混合拉取与聚合策略（v2）

## 0. 执行状态更新（2026-02-19）

- 当前实现仍是“按请求粒度直接回源 Massive + 同粒度落库”。
- 本文更新为 PMF 阶段 v2 方案：
  - `day` / `minute` 分表
  - `minute` 按交易日分区，保留最近 10 个交易日
  - 前端聚合粒度先收敛到 `5m/15m/60m`
  - `multiplier>1` 查询采用“预聚合 + 未完结桶实时补算”混合返回
- 口径更新：Redis 已用于 WS 实时消息广播（Pub/Sub + 订阅注册表）；但 `bars` 聚合查询链路不使用 Redis 缓存。

## 1. Context

- Source PRD:
  - `docs/prd/PRD-0001-market-watch.md`
- Related ADR:
  - `docs/adr/ARCHITECTURE-BASELINE.md`
  - `docs/adr/ADR-0001-realtime-market-data-streaming.md`
- Scope boundary:
  - 仅调整 `GET /api/v1/market-data/bars` 的后端存储与拉取策略
  - 不新增对外 endpoint，尽量保持请求/响应兼容
  - 遵循 FastAPI DDD + No Interfaces 约束

## 2. API Changes

### 2.1 New APIs

| Method | Path | Purpose | Auth | Priority |
|---|---|---|---|---|
| N/A | N/A | N/A | N/A | N/A |

### 2.2 API Updates

| Method | Path | Change | Compatibility | Priority |
|---|---|---|---|---|
| GET | `/api/v1/market-data/bars` | 后端读取策略改为“基准表 + 预聚合表 + 未完结实时补算 + Massive 兜底” | Compatible（响应结构不变） | P0 |
| GET | `/api/v1/market-data/bars` | PMF 阶段 minute 聚合仅保证 `multiplier in {1,5,15,60}`（后续再扩展） | Compatible（前端当前用法不受影响） | P1 |
| GET | `/api/v1/market-data/bars` | `X-Data-Source` 补充 `DB_AGG_MIXED`（已完结来自聚合表 + 未完结实时补算） | Compatible（新增枚举值） | P1 |

### 2.3 Deprecated APIs

| Method | Path | Replacement | Removal Plan |
|---|---|---|---|
| N/A | N/A | N/A | 当前版本无废弃接口 |

## 3. Contract Details

- Request schema changes:
  - 对外参数不变（`ticker/option_ticker`、`timespan`、`multiplier`、`from/to`、`limit`）。
  - PMF 阶段内部实现仅承诺 minute 的 `1/5/15/60` 聚合路径；其它倍率走兜底路径（可开关）。
- Response schema changes:
  - Body 不变。
  - Header 扩展 `X-Data-Source=DB_AGG_MIXED`。
- Error code conventions:
  - 延续 BE-0002 既有错误码，不引入新对外错误码。

## 4. Data/Task Impact

### 4.1 存储模型（分表 + 分区）

- `market_bars_day`
  - 用途：存储 `day x 1` 基准数据（长期保留）
  - 唯一键：`(ticker, trade_date)`
- `market_bars_minute`（父表）
  - 用途：存储 `minute x 1` 基准数据
  - 分区策略：按 `trade_date`（交易日）分区，建议“每日一分区”
  - 分区命名示例：`market_bars_minute_2026_02_18`
  - 唯一键：`(ticker, start_at)`
- `market_bars_minute_agg`
  - 用途：存储 `5m/15m/60m` 已完结聚合桶（非临时会话表，属于持久化工作表）
  - 关键列：`ticker, multiplier, bucket_start_at, bucket_end_at, is_final`
  - 唯一键：`(ticker, multiplier, bucket_start_at)`

说明：
- “临时表”在此处按可运维实现落地为“预聚合持久化表”，避免数据库 session 级临时表带来的可用性问题。

### 4.2 数据保留策略

- `minute x 1`：仅保留最近 10 个交易日。
- 清理方式：删除过期交易日分区（`DROP TABLE PARTITION`），避免大表 `DELETE`。
- `5m/15m/60m` 预聚合表：建议与 minute 同步保留 10 个交易日。
- `day x 1`：长期保留（后续按容量再评估归档）。

### 4.3 聚合锚点与时间规则

- 时区：分桶计算使用 `America/New_York`，落库存储统一 UTC。
- 锚点：以常规交易时段开盘 `09:30 ET` 作为分钟聚合锚点。
- 桶规则：`[start, end)`。
- `60m` 桶允许收盘截断桶（`15:30-16:00`，30 分钟）。
- 仅“已完结桶”写入 `market_bars_minute_agg` 并标记 `is_final=true`。

### 4.4 查询策略（`multiplier>1`）

目标：避免每次全窗口实时聚合。

1. 计算请求窗口 `[from, to]` 与当前时间对应的“当前桶起点”。
2. 已完结区间：
   - 从 `market_bars_minute_agg` 读取已完结桶。
3. 未完结区间（最多一个当前桶）：
   - 从 `market_bars_minute`（`1m`）实时聚合一个“进行中”bar（不落聚合表）。
4. 合并两部分结果并按时间排序，返回统一 bars 列表。

结果来源标识：
- 全部来自预聚合表：`X-Data-Source=DB_AGG`
- 包含未完结实时补算：`X-Data-Source=DB_AGG_MIXED`

### 4.5 预聚合作业（Celery）

- 保留 Celery；`bars` 聚合作业与查询不依赖 Redis 缓存。
- 新增作业（建议）：
  - `aggregate_minute_bars_5m`
  - `aggregate_minute_bars_15m`
  - `aggregate_minute_bars_60m`
- 调度建议：每分钟执行一次，增量 upsert 新完结桶。
- 幂等要求：
  - 以 `(ticker, multiplier, bucket_start_at)` upsert
  - 重跑不产生重复数据

### 4.6 回源与兜底策略

- 基准优先：
  - `minute/1` 与 `day/1` 缺口优先回源 Massive 补齐基准表。
- 派生优先本地：
  - `5/15/60` 优先读预聚合 + 实时补算。
- 兜底：
  - 当基准覆盖不足且补齐失败时，可通过 feature flag 决定是否按请求粒度直接回源 Massive（可用性优先）。

### 4.7 分层落点（遵循 DDD Guardrails）

- API 层（`api/v1/endpoints/market_data.py`）：
  - 保持薄层：参数校验、调用 application、DTO 映射、错误映射
- Application 层（`application/market_data/service.py`）：
  - 查询计划器：基准读取、聚合表读取、未完结桶实时补算、结果合并
- Domain 层（`domain/market_data/*`）：
  - 纯函数：分桶、OHLCV 聚合、VWAP 计算、桶完结判定
- Infrastructure 层：
  - repository：日线表、分钟分区表、聚合表的访问与 upsert
  - Celery task：预聚合增量生产与分区维护

## 5. Delivery Plan

1. Phase 1（P0，数据模型）
   - 新建 `market_bars_day`、`market_bars_minute`（分区）与 `market_bars_minute_agg`
   - 落地“分钟分区创建/清理”任务（保留 10 交易日）
2. Phase 2（P0，查询链路）
   - `minute/1`、`day/1` 基准查询与缺口回源补齐
   - `5/15/60` 查询改为“预聚合 + 未完结实时补算”
3. Phase 3（P1，作业链路）
   - Celery 周期作业产出已完结桶
   - 增加幂等与失败重试策略
4. Phase 4（P1，可观测与回滚）
   - 增加 metrics 与 `X-Data-Source` 细化
   - 增加 feature flag 支持快速回退

## 6. Acceptance Checklist

- [ ] `market_bars_day` 与 `market_bars_minute` 分表完成，minute 按交易日分区
- [ ] minute 数据仅保留最近 10 个交易日，清理通过分区 drop 完成
- [ ] `5m/15m/60m` 已完结桶由 Celery 预聚合写入聚合表
- [ ] `multiplier>1` 查询可同时返回“已完结预聚合桶 + 未完结实时桶”
- [ ] `60m` 使用 `09:30 ET` 锚点且支持收盘截断桶
- [ ] `bars` 聚合链路未引入 Redis 缓存（Redis 仅用于 Celery 与 WS 广播）
- [ ] 单测覆盖聚合口径、桶边界、DST、回源兜底与幂等 upsert

## 7. 风险与回滚

- 风险：
  - 交易日定义与 DST 处理错误会导致桶边界偏移
  - 周期聚合作业延迟会影响“已完结桶”可见性
- 缓解：
  - 以 `America/New_York` 做分桶并补齐边界测试
  - 查询链路始终保留未完结实时补算，降低作业抖动影响
- 回滚：
  - feature flag 回退到“按请求粒度直接回源 Massive + 同粒度入库”路径
