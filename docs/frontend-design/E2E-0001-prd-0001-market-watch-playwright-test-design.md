# E2E-0001 - PRD-0001 Market Watch 端到端测试设计（Playwright）

## 0. Context

- Source PRD：
  - `docs/prd/PRD-0001-market-watch.md`
- Related Backend Evolution：
  - `docs/backend-evolution/BE-0001-prd-0001-market-watch-api-breakdown.md`
  - `docs/backend-evolution/BE-0002-prd-0001-market-watch-api-contract-v1.md`
  - `docs/backend-evolution/BE-0003-prd-0001-market-watch-api-unit-test-plan.md`
- Related Frontend Design：
  - `docs/frontend-design/prototype-v1.md`
  - `docs/frontend-design/prototype-v2-market-watch.md`

> 本文档用于定义 Web Trader Terminal 的 E2E 测试方案，目标是补齐 Unit Test 之外的跨层回归保护。

---

## 1. 目标与原则

### 1.1 目标

1. 覆盖 PRD-0001 的关键业务闭环：`登录 -> /terminal -> watchlist -> bars -> options -> 实时状态/降级`。
2. 在 CI 中提供可重复、可观测的回归检查，减少“代码能编译但链路不可用”的风险。
3. 形成 smoke/regression 分层，控制执行时长并优先保护高价值路径。

### 1.2 原则

- E2E 不替代 Unit Test；E2E 只测关键用户旅程与跨模块集成行为。
- 优先稳定性：CI 主通道使用可控测试数据，真实第三方行情链路放在独立 canary 通道。
- 每个场景必须可追溯到 PRD/BE/Frontend 文档中的明确验收口径。

---

## 2. 范围定义

### 2.1 In Scope（PRD-0001 对齐）

- F1：登录与 watchlist 管理（增删查、刷新不丢失）。
- F2：股票行情（首屏 bars + snapshots，详情随实时数据更新）。
- F3：期权观察（expirations -> chain -> contract detail）。
- F4：系统状态与降级（WS 断线重连、Degraded 轮询、恢复后补拉）。
- F5：订阅上限与提示（超限反馈，不拖垮系统）。

### 2.2 Out of Scope（当前阶段不纳入 E2E）

- 真实下单交易流程（PRD 非目标）。
- PRD-0002 的 IV 告警策略验证。
- 全市场扫描、热力图、多窗口布局等 Nice-to-have 视觉能力。

---

## 3. 测试分层与执行策略

### 3.1 套件分层

1. `smoke`（PR 必跑，目标 5~10 分钟）
   - 覆盖核心正向路径与关键降级路径。
2. `regression`（主干每日/每夜跑）
   - 在 smoke 基础上扩展异常、边界与恢复流程。
3. `canary-realtime`（可选，定时跑）
   - 使用真实 Massive 数据链路验证端到端可达性；结果不阻塞普通 PR 合并。

### 3.2 推荐标签

- `@smoke`
- `@regression`
- `@degraded`
- `@options`
- `@auth`

---

## 4. 环境与数据策略

### 4.1 测试环境

- 本地与 CI 均基于 `docker compose` 启动：`frontend + api + redis + postgres`。
- Base URL：
  - Frontend：`http://localhost:5173`
  - API：`http://localhost:8000`

### 4.2 测试账号

- 约定独立 E2E 账号（如 `e2e_user@local.test`），避免与手工联调账号互相污染。
- 每次执行前通过 API 或 seed 脚本保证账号存在且状态可用。

### 4.3 测试数据（稳定性优先）

- 默认通道（smoke/regression）使用可控数据模式：
  - watchlist、bars、options 返回固定可预期数据；
  - WS 推送使用可重放事件序列（便于断言更新时间与状态切换）。
- canary 通道使用真实第三方数据，仅断言“链路可用/字段完整/状态可见”，不做强数值断言。

### 4.4 数据清理

- 每个 spec 前后清理 watchlist 与缓存状态（避免用例间串扰）。
- 以 API 清理优先，数据库直连清理作为兜底。

---

## 5. Playwright 项目结构（建议）

```text
frontend/e2e/
  playwright.config.ts
  .env.e2e
  tests/
    smoke/
      auth-and-terminal.spec.ts
      watchlist-and-bars.spec.ts
      options-basic-flow.spec.ts
      ws-degraded-recovery.spec.ts
    regression/
      subscription-limit.spec.ts
      unauthorized-stream.spec.ts
      fields-fallback.spec.ts
  fixtures/
    auth.fixture.ts
    terminal.fixture.ts
  pages/
    login.page.ts
    terminal.page.ts
    options.page.ts
  helpers/
    api-client.ts
    ws-driver.ts
    test-data.ts
```

### 5.1 页面对象职责

- `login.page.ts`：登录/注册入口、鉴权状态判断。
- `terminal.page.ts`：watchlist 操作、ticker 切换、bars 区域断言、状态栏断言。
- `options.page.ts`：expiration/chain/contract detail 操作与断言。

### 5.2 选择器规范

- 关键元素统一补 `data-testid`，避免依赖文案与样式层级。
- 命名建议：
  - `watchlist-row-{ticker}`
  - `status-connection`
  - `status-data-latency`
  - `bars-chart-main`
  - `options-expiration-select`
  - `options-chain-row-{optionTicker}`
  - `contract-detail-last`

---

## 6. 场景矩阵（PRD/BE/Frontend 映射）

| Case ID | 标签 | 来源映射 | 场景描述 | 核心断言 |
|---|---|---|---|---|
| E2E-MW-001 | `@smoke @auth` | PRD F1, V2 4.1 | 登录后进入 `/terminal` 完成首屏加载 | watchlist 可见；snapshots 字段（Last/Change/%Change/UpdatedAt）可见；状态栏显示 `Connected` 或 `Degraded` |
| E2E-MW-002 | `@smoke` | PRD F1, V1 交互 | watchlist 增删查并刷新页面 | 新增 ticker 后列表存在；删除后消失；刷新后结果保持一致 |
| E2E-MW-003 | `@smoke` | PRD F2, V2 4.2 | 切换 ticker，加载 bars 与详情指标 | `bars` 图表区域有数据；symbol header 与选中 ticker 一致；更新时间发生变化 |
| E2E-MW-004 | `@smoke @options` | PRD F3, V2 4.3 | options 基础闭环 | expiration 列表成功加载；chain 行可点击；contract detail 展示 `Bid/Ask/Last/IV/Volume/OI` 或 `-` |
| E2E-MW-005 | `@smoke @degraded` | PRD F4, V2 4.4 | WS 断线降级与恢复 | 断线后状态变 `Reconnecting/Degraded`；轮询数据仍更新；恢复后状态回 `Connected` |
| E2E-MW-006 | `@regression` | PRD F5, BE-0002 WS | 超过订阅上限 | UI 出现“订阅上限”提示；后续订阅动作被拒绝且已有页面不崩溃 |
| E2E-MW-007 | `@regression @auth` | BE-0002 WS 鉴权 | WS 鉴权失败 | 连接被拒绝并显示可读错误状态（未登录/登录失效） |
| E2E-MW-008 | `@regression @options` | PRD F3, V2 6.3 | 上游字段缺失兜底 | options 表格缺失字段显示 `-`，tooltip 显示来源限制 |
| E2E-MW-009 | `@regression` | PRD 路由约定 | `/demo` 与 `/terminal` 数据链路隔离 | `/demo` 在后端异常时仍可访问；`/terminal` 严格展示真实链路状态 |

---

## 7. 合同断言口径（BE-0002 对齐）

### 7.1 REST

- 关键接口响应成功时，至少断言：
  - `snapshots.items[*].updated_at`
  - `options.chain.items[*].option_ticker`
  - `bars` 数据存在且 UI 可渲染
- 错误场景可通过 UI 文案映射验证以下 code：
  - `MARKET_DATA_UPSTREAM_UNAVAILABLE`
  - `OPTIONS_CHAIN_NOT_FOUND`
  - `MARKET_DATA_RATE_LIMITED`

### 7.2 WebSocket

- 握手失败：映射 `4401` 语义。
- 订阅非法 action：映射 `STREAM_INVALID_ACTION`。
- 超限：映射 `STREAM_SUBSCRIPTION_LIMIT_EXCEEDED`。

---

## 8. CI 设计

### 8.1 执行阶段

1. 安装依赖并构建前端。
2. 启动 compose 环境并等待健康检查。
3. 运行 `@smoke` 套件（PR）。
4. 每日/每夜运行 `@regression` 与 `canary-realtime`（可分开 job）。

### 8.2 失败产物

- Playwright Trace
- Screenshot
- Video
- 浏览器 Console 与网络日志（重点保存 `market-data/stream`）

### 8.3 门禁建议

- `@smoke` 失败阻塞合并。
- `@regression` 失败阻塞主干发布。
- `canary-realtime` 失败仅告警，不直接阻塞 PR。

---

## 9. 落地里程碑

1. M1：搭建 Playwright 基础工程与 `@smoke` 4 条核心用例（E2E-MW-001~005 中选 4 条）。
2. M2：补齐 options、降级恢复、订阅上限场景（覆盖 E2E-MW-006~008）。
3. M3：接入 canary-realtime，形成“稳定回归 + 真实行情探针”双通道。

---

## 10. 风险与应对

- 风险：第三方实时数据抖动导致误报。
  - 应对：主通道使用可控数据，真实链路放 canary。
- 风险：WS 时序不稳定引发偶发失败。
  - 应对：断言基于状态与事件顺序，不依赖固定数值；统一超时与重试策略。
- 风险：页面频繁重构导致选择器失效。
  - 应对：强制 `data-testid` 规范，PR 中把 UI 结构变更与测试更新一起提交。

