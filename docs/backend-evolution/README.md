# Backend Evolution Index

## 目标

将 PRD 拆分为后端可执行项，聚焦接口、数据模型、任务流程与交付顺序。

## 执行状态更新（2026-03-03）

- 当前主线：股票数据能力（watchlist / snapshots / bars / stock stream）。
- 非股票扩展后端文档内容已清理，不纳入当前迭代范围。

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

- `BE-0001`：PRD-0001 后端接口拆分（股票主线）
- `BE-0002`：PRD-0001 接口合同细化（REST/WS 字段与错误码）
- `BE-0003`：PRD-0001 API 层测试计划
- `BE-0004`：PRD-0001 application service 测试计划
- `BE-0005`：`market-data/bars` 混合拉取与聚合策略
- `BE-0007`：`/demo` mock 回放入口
- `BE-0008`：FastAPI HTTP 异步化迁移

## 模板

- `docs/backend-evolution/TEMPLATE.md`
