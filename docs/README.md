# Docs Map (Trader Helper)

本目录按一条固定产品流程组织：
1. `PRD`：先定需求边界与验收口径
2. `ADR`：评估是否需要架构/关键决策变更
3. `backend-evolution`：把 PRD 拆成后端接口与实现项
4. `frontend-design`：基于 PRD + 后端能力做前端设计与原型
5. `note`：每轮开发结束后的 TODO / follow-up

## 目录

- `docs/prd/`：需求文档与模板
- `docs/adr/`：技术决策记录与架构基线
- `docs/backend-evolution/`：后端接口演进与拆分计划
- `docs/frontend-design/`：前端信息架构、交互与视觉设计
- `docs/note/`：迭代待办、运行手册、阶段备注

## 使用约定

- 每次新需求先创建/更新 PRD，再决定是否写 ADR。
- 进入开发前，必须在 `backend-evolution` 形成接口拆分记录。
- 前端方案应引用对应 PRD 与后端演进文档编号。
- 一轮开发结束后，将遗留项写入 `docs/note/todo.md`。
