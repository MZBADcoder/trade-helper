# Backend Evolution Index

## 目标

将 PRD 拆分为后端可执行项，聚焦接口、数据模型、任务流程与交付顺序。

## 文件约定

- 编号：`BE-0001`、`BE-0002`...
- 命名：`BE-xxxx-prd-xxxx-<short-slug>.md`
- 一份 BE 文档对应一个主 PRD（可含多阶段）

## 最小内容

- 来源 PRD 与关联 ADR
- 接口清单（新增/修改/废弃）
- 请求/响应字段定义
- 数据与任务流程影响
- 实现顺序与验收点

## 清单

- `BE-0001` 对 PRD-0001 的后端接口演进拆分（实时行情 / 数据观察）
  - `/Users/mz/pmf/trader-helper/docs/backend-evolution/BE-0001-prd-0001-market-watch-api-breakdown.md`
  - 备注：`PRD-0002`（IV）相关拆分延后到下一个 thread

## 模板

- `/Users/mz/pmf/trader-helper/docs/backend-evolution/TEMPLATE.md`
