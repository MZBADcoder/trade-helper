# 前端设计索引

## 目标

在 PRD 与后端能力明确后，定义页面信息架构、视觉方向与交互原型。

## 清单

- 原型 V1（home/login/terminal/demo，对应 PRD-0001 行情观察）
  - `/Users/mz/pmf/trader-helper/docs/frontend-design/prototype-v1.md`
- 原型 V2（market-watch 增量设计：实时状态、期权链、降级策略）
  - `docs/frontend-design/prototype-v2-market-watch.md`
- E2E 设计（基于 PRD-0001 + BE-0001/0002/0003 + V2 原型）
  - `docs/frontend-design/E2E-0001-prd-0001-market-watch-playwright-test-design.md`

## 约定

- 先引用来源 PRD 与对应 BE 文档。
- 明确哪些页面走真实接口，哪些页面属于 demo 独立路径。
- UI 方案冻结后再进入实现，避免开发期反复返工。
