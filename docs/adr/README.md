# ADR Index

## 目标

记录关键技术决策，保证后续可回溯：为什么改、改了什么、代价是什么。

## 文件约定

- 编号：`ADR-0001`、`ADR-0002`...
- 命名：`ADR-xxxx-<short-slug>.md`
- 单文档尽量控制在 1-2 屏，聚焦一个决策

## 清单

- `ADR-0001` 实时行情推送架构（服务端代理 Massive WebSocket）
  - `/Users/mz/pmf/trader-helper/docs/adr/ADR-0001-realtime-market-data-streaming.md`
- `ARCHITECTURE-BASELINE` 当前通用架构基线（非决策单）
  - `/Users/mz/pmf/trader-helper/docs/adr/ARCHITECTURE-BASELINE.md`

## 什么时候新增 ADR

- PRD 要求引入新组件/中间件/部署模型
- 接口边界或一致性策略发生变化
- 预计会影响多模块协作或后续迁移成本
