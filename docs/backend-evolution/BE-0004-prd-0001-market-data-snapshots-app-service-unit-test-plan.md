# BE-0004 - PRD-0001 Market Data + Options Application Service Unit Test 计划

## 0. 执行状态更新（2026-02-16）

- 当前迭代仅推进 market-data（stock 主线）相关测试补齐。
- options 相关开发与扩展测试进入 HOLD。
- 本文 options 清单保留为下一阶段恢复开发时的执行输入，不纳入当前阶段必做项。

## 1. 目标与范围

本文统一定义以下两个 application service 的 unit test plan（TDD 输入）：

- `backend/app/application/market_data/service.py`
- `backend/app/application/options/service.py`

覆盖方法（全部公有方法）：

- `DefaultMarketDataApplicationService.list_bars`
- `DefaultMarketDataApplicationService.prefetch_default`
- `DefaultMarketDataApplicationService.list_snapshots`
- `DefaultOptionsApplicationService.list_expirations`
- `DefaultOptionsApplicationService.list_chain`
- `DefaultOptionsApplicationService.get_contract`

测试边界：

- 仅测 application service 编排、输入防御、错误语义
- 不触达真实 Massive/Redis/DB/WS
- endpoint 的 HTTP 状态码映射继续由 API 层单测承担（见 `BE-0003`）

## 2. 测试文件与替身设计

建议测试文件：

- `backend/tests/app/domain/test_market_data_service.py`（已有，继续承载 `list_bars/prefetch_default`）
- `backend/tests/app/application/test_market_data_app_service_snapshots.py`（新增，承载 `list_snapshots`）
- `backend/tests/app/application/test_options_app_service.py`（新增，承载 options 三个方法）

建议替身：

- `FakeUoW` + `FakeMarketDataRepository`（已存在，可复用）
- `FakeMassiveClient`（聚合 bars）
- `FakeMassiveSnapshotClient`（快照）
- `RateLimited*Client` / `Failing*Client`（错误语义测试）
- options 侧暂以最小替身驱动（当前方法未接入依赖）

## 3. 每个方法至少 1 个测试方法（最小集合）

### 3.1 Market Data

1. `list_bars`
   - `test_list_bars_uses_cache_when_coverage_sufficient`
2. `prefetch_default`
   - `test_prefetch_default_calls_list_bars_with_normalized_ticker`
3. `list_snapshots`
   - `test_list_snapshots_returns_mapped_domain_snapshots`

### 3.2 Options

1. `list_expirations`
   - `test_list_expirations_raises_options_upstream_unavailable_until_implemented`
2. `list_chain`
   - `test_list_chain_raises_options_upstream_unavailable_until_implemented`
3. `get_contract`
   - `test_get_contract_raises_options_upstream_unavailable_until_implemented`

## 4. 扩展用例清单（建议一次补齐）

### 4.1 `list_bars`

- `test_list_bars_fetches_massive_when_cache_missing`
- `test_list_bars_rejects_invalid_date_range`
- `test_list_bars_rejects_blank_ticker`
- `test_list_bars_rejects_blank_timespan`
- `test_list_bars_rejects_multiplier_less_than_1`
- `test_list_bars_raises_when_massive_client_missing_and_cache_insufficient`
- `test_list_bars_commits_when_massive_returns_bars`
- `test_list_bars_skips_commit_when_massive_returns_empty`

### 4.2 `prefetch_default`

- `test_prefetch_default_rejects_blank_ticker`
- `test_prefetch_default_normalizes_ticker_to_uppercase`
- `test_prefetch_default_uses_daily_lookback_window`（可用 monkeypatch 固定 `date.today()`）

### 4.3 `list_snapshots`

- `test_list_snapshots_rejects_empty_tickers`
- `test_list_snapshots_rejects_invalid_symbol`
- `test_list_snapshots_deduplicates_and_uppercases_symbols`
- `test_list_snapshots_rejects_more_than_50_symbols`
- `test_list_snapshots_returns_empty_list_when_upstream_empty`
- `test_list_snapshots_raises_rate_limited_when_upstream_limited`
- `test_list_snapshots_raises_upstream_unavailable_for_unexpected_error`
- `test_list_snapshots_raises_upstream_unavailable_when_client_missing`

### 4.4 `list_expirations`

- `test_list_expirations_validates_underlying_format`（实现后）
- `test_list_expirations_validates_limit_range`（实现后）
- `test_list_expirations_maps_upstream_result_to_domain`（实现后）
- `test_list_expirations_maps_not_found_to_options_underlying_not_found`（实现后）

### 4.5 `list_chain`

- `test_list_chain_validates_expiration_format`（实现后）
- `test_list_chain_validates_strike_range`（实现后）
- `test_list_chain_validates_option_type`（实现后）
- `test_list_chain_maps_upstream_result_to_domain`（实现后）
- `test_list_chain_maps_invalid_cursor_error`（实现后）

### 4.6 `get_contract`

- `test_get_contract_validates_option_ticker_format`（实现后）
- `test_get_contract_returns_without_greeks_when_include_greeks_false`（实现后）
- `test_get_contract_maps_not_found_to_options_contract_not_found`（实现后）
- `test_get_contract_maps_upstream_unavailable`（实现后）

## 5. TDD 执行顺序

1. Phase A（立即可做）
   - 先补齐第 3 节“每个方法至少 1 个测试方法”
2. Phase B（market-data 强化）
   - 按第 4.1~4.3 扩展，先 `list_snapshots`，再 `prefetch_default`
3. Phase C（options 实现驱动）
   - HOLD：先保持已有测试为绿，待 Stock 主线完成后再按第 4.4~4.6 逐步替换为真实行为测试

## 6. 完成标准

- 上述 6 个公有方法均有对应单测方法并通过
- market-data 方法覆盖成功路径 + 关键失败路径
- options 方法当前仅保持已有测试不回归，扩展覆盖待 HOLD 解除后补齐
- 全程保持 No Interfaces（不引入 `Protocol/ABC`）
