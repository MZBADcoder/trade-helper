# 前端原型 V1（Trader Terminal）

> 更新说明：PRD-0001 的 market-watch 增量设计已在 `docs/frontend-design/prototype-v2-market-watch.md` 维护；本文件保留为首版基线。

## 0. Context

- Source PRD: `/Users/mz/pmf/trader-helper/docs/prd/PRD-0001-market-watch.md`
- Related BE: `/Users/mz/pmf/trader-helper/docs/backend-evolution/BE-0001-prd-0001-market-watch-api-breakdown.md`
- Out of scope（本原型不覆盖）：`PRD-0002` IV 监控与告警 UI

## 1. 范围

本次原型覆盖：

- 具有交易风格的首页，并提供明确的登录入口。
- 登录/注册流程。
- 鉴权后的自选股管理。
- 股票列表与详情联动交互。
- 最多打开 5 个股票详情标签页并快速切换。
- 详情页展示 K 线与基础指标：MA、MACD、BOLL、RSI、VOL。

本次原型**暂不包含** IV 监控相关 UI。

## 2. 信息架构

路由：

- `/` 首页（公开）
- `/login` 登录/注册页（公开）
- `/demo` demo terminal（公开，本地模拟数据）
- `/terminal` trader terminal（需鉴权）

核心模块：

- `entities/session`：鉴权 token 与当前用户会话状态
- `entities/watchlist`：自选股增/查/删
- `entities/market`：K 线数据获取与指标计算
- `pages/home`：营销信息与 CTA
- `pages/login`：鉴权入口
- `pages/demo-terminal`：与真实后端解耦的设计/原型路由
- `pages/terminal`：自选股、已打开标签、详情图表与指标
- `widgets/topbar`：全局导航与鉴权动作
- `widgets/stock-chart`：SVG K 线与指标图

## 3. 交互流程

1. 用户进入 `/`，看到市场风格首页与 CTA。
2. 用户点击 `Login` 跳转至 `/login`。
3. 用户也可以点击 `Try Demo` 进入 `/demo`。
4. 登录成功后跳转至 `/terminal`。
5. 用户向自选股中添加 ticker。
6. 用户点击自选股 ticker 打开详情标签。
7. 终端最多保留 5 个已打开标签，并支持快速切换。
8. 详情区展示所选 ticker 的 K 线与指标。

## 4. 后端 API 映射

当前原型所需接口均已存在：

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/watchlist`
- `POST /api/v1/watchlist`
- `DELETE /api/v1/watchlist/{ticker}`
- `GET /api/v1/market-data/bars`

`/demo` 路由有意保持后端无依赖，以便快速迭代设计与交互。

鉴权方式：

- 使用登录返回的 Bearer token。
- 对 watchlist 和 market-data 请求带上 `Authorization: Bearer <token>`。

## 5. 指标策略

V1 不新增后端指标接口。  
指标由前端基于 OHLCV K 线数据本地计算：

- MA(20)、MA(50)
- MACD(12,26,9)
- BOLL(20,2)
- RSI(14)
- VOL（原始成交量柱）

## 6. V2 已知缺口

下一阶段可考虑新增后端能力：

- 服务端指标计算接口，保证多端公式一致。
- 多周期 K 线标准化接口，降低前端图表适配成本。
- IV 专用接口（按 ticker 与合约分桶返回 rank/percentile）。

## 7. 本原型验收标准

- 用户可登录，刷新后保持登录态。
- 鉴权下自选股增删查可用。
- 点击 ticker 可打开详情，最多 5 标签，并支持切换。
- 详情区可展示 K 线 + MA/MACD/BOLL/RSI/VOL。
