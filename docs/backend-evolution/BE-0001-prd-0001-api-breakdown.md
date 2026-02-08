# BE-0001 - PRD-0001 Backend API Breakdown

## 1. Context

- Source PRD: `/Users/mz/pmf/trader-helper/docs/prd/PRD-0001-iv-percentile-alerts.md`
- Related ADR: `/Users/mz/pmf/trader-helper/docs/adr/ADR-0001-mvp-stack.md`
- Scope: 支撑第一版 Web 终端（登录、watchlist、行情 bars、扫描触发）并为 IV 模块预留接口位。

## 2. Current APIs (Already Available)

| Method | Path | Purpose | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register` | 用户注册 | No |
| POST | `/api/v1/auth/login` | 用户登录 | No |
| GET | `/api/v1/auth/me` | 当前用户信息 | Yes |
| GET | `/api/v1/watchlist` | 查询关注列表 | Yes |
| POST | `/api/v1/watchlist` | 添加关注标的 | Yes |
| DELETE | `/api/v1/watchlist/{ticker}` | 删除关注标的 | Yes |
| GET | `/api/v1/market-data/bars` | 查询 OHLCV bars | Yes |

## 3. API Evolution from PRD

### 3.1 Phase A (Prototype / Base)

- 目标：完成前端基础原型所需能力。
- 结论：现有接口可满足，不新增强制接口。

### 3.2 Phase B (IV Monitoring Integration)

建议新增以下接口（从 PRD 的 IV 监控需求拆分）：

| Method | Path | Purpose | Priority |
|---|---|---|---|
| GET | `/api/v1/iv/signals` | 获取 watchlist 的 IV 告警结果与优先级 | P0 |
| GET | `/api/v1/iv/signals/{ticker}` | 获取单 ticker 告警详情（窗口、阈值、规则维度） | P0 |
| GET | `/api/v1/iv/snapshots/{ticker}` | 获取代表性 IV 时间序列（用于图表） | P1 |
| POST | `/api/v1/rules/iv` | 创建 IV 规则（窗口、阈值、DTE 桶、Call/Put） | P0 |
| GET | `/api/v1/rules/iv` | 查询当前规则 | P0 |
| PATCH | `/api/v1/rules/iv/{id}` | 更新规则 | P1 |

## 4. Key Contract Notes

- 告警去重键应显式返回：`(ticker, call_put, dte_bucket, history_window, threshold_level)`。
- 阈值等级必须标准化：`P90 | P95`。
- 时间字段统一 UTC ISO8601。
- 列表接口默认分页，避免前端一次拉全量历史。

## 5. Implementation Order (Recommended)

1. 保持现有 auth/watchlist/market-data 稳定，补齐测试与错误码一致性。
2. 新增 `iv/signals` 聚合读取接口（先读数据库结果，不在请求内做重计算）。
3. 新增规则管理接口 `rules/iv`。
4. 新增 `iv/snapshots/{ticker}` 图表数据接口。

## 6. Acceptance Checklist

- [ ] 现有基础接口覆盖基础 E2E 用例
- [ ] IV 告警接口返回规则维度字段
- [ ] 规则管理接口支持最小 CRUD
- [ ] Worker 写入与 API 读取字段一致
