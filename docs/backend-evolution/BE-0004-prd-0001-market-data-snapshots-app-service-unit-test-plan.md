# BE-0004 - PRD-0001 Market Data + Options Application Service Unit Test 计划（更新版）

## 0. 执行状态更新（2026-02-18）

- `Default*ApplicationService` 命名已移除，当前类名为 `MarketDataApplicationService` / `OptionsApplicationService`。
- `market-data` 已按 BE-0005 落地混合策略：`day/minute` 基准表 + `5m/15m/60m` 预聚合 + 未完结桶实时补算。
- 已新增并通过：
  - `backend/tests/app/domain/test_market_data_aggregation.py`（DST、60m 收盘截断、桶完结判定）
  - `backend/tests/app/domain/test_market_data_service.py`（`list_bars_with_meta` 混合返回、预聚合作业）
- options 相关开发仍处于 HOLD，但当前基础 application tests 继续保留并保持绿灯。

## 1. 目标与范围

本文定义以下两个 application service 的 unit test plan（TDD 输入）：

- `backend/app/application/market_data/service.py`
- `backend/app/application/options/service.py`

覆盖方法（全部公有方法）：

- `MarketDataApplicationService.list_bars`
- `MarketDataApplicationService.list_bars_with_meta`
- `MarketDataApplicationService.prefetch_default`
- `MarketDataApplicationService.list_snapshots`
- `MarketDataApplicationService.precompute_minute_aggregates`
- `MarketDataApplicationService.enforce_minute_retention`
- `OptionsApplicationService.list_expirations`
- `OptionsApplicationService.list_chain`
- `OptionsApplicationService.get_contract`

测试边界：

- 仅测 application service 编排、输入防御、错误语义
- 不触达真实 Massive/Redis/DB/WS
- HTTP 状态码映射由 API 层单测承担（见 `BE-0003`）

## 2. 测试文件与替身设计

建议测试文件（现状）：

- `backend/tests/app/domain/test_market_data_service.py`（`list_bars/list_bars_with_meta/prefetch_default/precompute_minute_aggregates`）
- `backend/tests/app/domain/test_market_data_aggregation.py`（分桶与聚合纯函数）
- `backend/tests/app/application/test_market_data_app_service_snapshots.py`（`list_snapshots`）
- `backend/tests/app/application/test_options_app_service.py`（options 三个方法）

建议替身：

- `FakeUoW` + `FakeMarketDataRepository`
- `FakeMassiveClient` / `FailMassiveClient`
- `FakeMassiveSnapshotClient`
- options 侧 `FakeMassiveOptionsClient`

## 3. 最小方法覆盖（每个公有方法至少 1 条）

### 3.1 Market Data

1. `list_bars`
   - `test_list_day_bars_reads_db_when_coverage_hit`
2. `list_bars_with_meta`
   - `test_list_minute_aggregated_returns_db_agg_mixed_for_open_bucket`
3. `prefetch_default`
   - `test_prefetch_default_calls_list_bars_with_normalized_ticker`
4. `list_snapshots`
   - `test_list_snapshots_returns_mapped_domain_snapshots`
5. `precompute_minute_aggregates`
   - `test_precompute_minute_aggregates_only_writes_final_buckets`
6. `enforce_minute_retention`
   - 待补：新增最小成功路径与参数校验测试

### 3.2 Options

1. `list_expirations`
   - `test_list_expirations_returns_grouped_result`
2. `list_chain`
   - `test_list_chain_returns_domain_result`
3. `get_contract`
   - `test_get_contract_returns_domain_result_with_greeks`

## 4. 扩展用例清单（BE-0005 对齐）

### 4.1 `list_bars` / `list_bars_with_meta`

- `test_list_minute_baseline_fetches_massive_when_missing`
- `test_list_minute_aggregated_fallbacks_to_rest_when_preagg_empty`
- 覆盖 `X-Data-Source` 语义对应的数据来源：
  - `DB`
  - `REST`
  - `DB_AGG`
  - `DB_AGG_MIXED`
- `multiplier` 非 `{1,5,15,60}` 时的兜底行为（feature flag 开/关）

### 4.2 聚合纯函数（`domain/market_data/aggregation.py`）

- `test_resolve_bucket_bounds_handles_dst_offset`
- `test_resolve_bucket_bounds_60m_supports_close_truncated_bucket`
- `test_aggregate_minute_bars_skips_unfinished_when_requested`
- 增补：跨日边界、空输入、`multiplier<=0` 的防御用例

### 4.3 `precompute_minute_aggregates`

- 非法倍率（非 `5/15/60`）报错
- `lookback_trade_days < 1` 报错
- 多 ticker 增量 upsert 的幂等重跑

### 4.4 `enforce_minute_retention`

- `keep_trade_days < 1` 报错
- 删除数量汇总正确（`minute_deleted` / `minute_agg_deleted`）
- 无删除场景不提交事务

### 4.5 `list_snapshots`

- invalid ticker、>50 ticker、上游限流/不可用映射
- Massive 不同 payload 形态映射一致性

### 4.6 Options（HOLD，维护不回归）

- 保持现有成功/参数校验/上游错误映射测试持续通过
- HOLD 解除后再扩展深度边界（cursor、not found、include_greeks=false 语义）

## 5. 当前缺口与后续顺序

1. 先补 `enforce_minute_retention` 的最小单测。
2. 再补 `list_bars_with_meta` 在 feature flag 关闭时的空结果分支。
3. HOLD 解除后补 options 扩展边界。

## 6. 完成标准

- 上述 9 个公有方法均有最小单测覆盖并通过
- market-data 覆盖成功路径 + 关键失败路径 + 聚合边界（含 DST、收盘截断、未完结桶）
- options 当前阶段保持不回归；扩展覆盖待 HOLD 解除后补齐
- 全程保持 No Interfaces（不引入 `Protocol/ABC`）
