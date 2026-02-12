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
- `BE-0002` 对 PRD-0001 的接口合同细化（REST/WS 字段与错误码）
  - `docs/backend-evolution/BE-0002-prd-0001-market-watch-api-contract-v1.md`
  - 备注：仅定义合同，不含实现代码
- `BE-0003` 对 PRD-0001 新增/修改接口的 Unit Test 设计（覆盖 BE-0002 合同）
  - `docs/backend-evolution/BE-0003-prd-0001-market-watch-api-unit-test-plan.md`
  - 备注：以 “API 层单测 + 可选合同测试 + WS 协议测试” 分层描述
- `BE-0004` 对 PRD-0001 `market_data + options` application service 的 Unit Test 设计（TDD 第一阶段）
  - `docs/backend-evolution/BE-0004-prd-0001-market-data-snapshots-app-service-unit-test-plan.md`
  - 备注：统一列出两个 service 全部公有方法的最小测试方法与扩展用例

## 模板

- `/Users/mz/pmf/trader-helper/docs/backend-evolution/TEMPLATE.md`
