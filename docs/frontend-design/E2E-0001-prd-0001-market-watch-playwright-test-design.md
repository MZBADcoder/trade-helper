# E2E-0001 - PRD-0001 股票终端 Playwright 测试设计

## 1. 目标

覆盖股票终端主链路：
- watchlist 操作
- snapshots + bars 展示
- WS 状态机与降级恢复

## 2. 范围

- 页面：`/terminal`
- 数据面：股票接口与股票 WS
- 仅覆盖股票场景

## 3. 用例矩阵

| Case ID | 标签 | 场景 | 预期 |
|---|---|---|---|
| E2E-MW-001 | `@smoke` | 登录后进入终端并加载 watchlist | 页面可渲染且首支 ticker 可选中 |
| E2E-MW-002 | `@smoke` | 新增 ticker 并刷新快照 | 列表新增行且有快照字段 |
| E2E-MW-003 | `@smoke` | 切换 ticker 查看 bars | 图表更新且数据来源可见 |
| E2E-MW-004 | `@regression` | timeframe 与 session 切换 | 请求参数变化正确，页面无报错 |
| E2E-MW-005 | `@regression` | WS 断开后降级轮询 | 状态显示 degraded，数据继续刷新 |
| E2E-MW-006 | `@regression` | WS 恢复后补拉对齐 | 状态回到 connected，时间序列连续 |

## 4. 页面对象建议

- `terminal.page.ts`
  - watchlist 操作
  - detail workspace 操作
  - status bar 状态断言

## 5. 关键断言

- watchlist 行数据与 active ticker 一致
- bars 区域在 timeframe 切换后重新加载
- 状态文案与样式类随连接状态变化
- 出错后提示可见且恢复后消失

## 6. 门禁建议

- CI 最小门禁：`E2E-MW-001` ~ `E2E-MW-004`
- 夜间回归：全量执行至 `E2E-MW-006`
