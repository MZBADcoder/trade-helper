# PRD 索引

## 规则

- 编号：`PRD-0001`、`PRD-0002`...
- 文件命名：`PRD-xxxx-<short-slug>.md`
- 每个 PRD 需要有明确验收标准（DoD）与非目标

## 清单

- `PRD-0001` 实时行情 / 数据观察（Stocks，Massive.com，Web Terminal MVP）
  - `docs/prd/PRD-0001-market-watch.md`

## 写作要求

每个 PRD 至少包含：
- 目标与非目标
- 用户场景与核心流程
- 功能优先级（MVP / Should / Nice）
- 验收标准
- 风险与开放问题

PRD 冻结后，下一步产出：
- 可能变更的 ADR（如有）
- 对应后端拆分文档（`docs/backend-evolution/`）
- 对应前端设计文档（`docs/frontend-design/`）

## 模板

- `docs/prd/TEMPLATE.md`
