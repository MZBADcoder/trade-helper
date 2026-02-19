# TODO（架构落地待办）

- [HOLD] 后端/前端期权相关开发（options API、options UI、options E2E）暂停；待 Stock 数据主线里程碑完成后恢复。
- [ ] 明确 Massive 上游订阅配额与最大并发连接限制，补充订阅上限策略与告警阈值。
- [x] 设计并落地 Redis Pub/Sub 频道与消息 envelope（当前使用 `market:stocks:events` + 统一 `type/ts/source/data`）。
- [x] 定义 WebSocket 心跳/重连的前后端约定与超时阈值（已在 BE-0002 与 FE-MW-V2 文档固化）。
- [x] WS 代码结构收敛：已将 `/market-data/stream` 从 REST 文件中拆分，并将订阅/心跳状态机下沉到 application（`stream_session`）。
- [x] 评估历史行情存储策略并形成结论（已选 BE-0005 的 day/minute 分表 + 预聚合路线，原生分区在收尾项推进）。
- [ ] 完成安全配置清单（JWT 过期策略、CORS 白名单、WAF/限流规则）。
- [ ] 形成“首屏 REST + 增量 WS + 断线补拉”联调脚本与验收用例（不依赖 Redis 缓存命中/未命中）。
- [x] PMF 阶段已对齐：Redis 用于 Celery 与 WS 实时广播；`market-data/bars` 聚合/常用数据不走 Redis 缓存。

- [x] BE-0002 评审项已补齐：OpenAPI/JSON 示例与 WS close code（`4401/4408`）对照已写入合同文档。

- [x] BE-0003 第一阶段已落地：API 层单测基础设施（ASGI TestClient + dependency overrides + fake service）已建成并覆盖 snapshots/bars 主路径。
- [x] BE-0003 补齐：WS 心跳语义测试已覆盖（ack 窗口与超时关闭状态机）。
- [ ] BE-0003 收尾：补齐 bars 参数失败分支与 snapshots 上游错误映射（API 层）。
- [x] BE-0005 主体已落地：完成 day/minute 分表、`5m/15m/60m` 预聚合任务、未完结实时补算与边界单测。
- [ ] BE-0005 收尾：将 `market_bars_minute` 升级为 PostgreSQL 原生“按交易日分区”父子表，并将保留期清理改为分区级 drop（当前已完成分表、预聚合、未完结实时补算与边界单测）。

- [x] FE-MW-V2：已补充 `/terminal` 四区信息架构与交互原型（watchlist/detail/options/status）。
- [ ] FE-MW-V2：与产品确认 `/terminal` 四区信息优先级并冻结版本。
- [x] FE-MW-V2：WS 降级态（reconnecting/degraded/recovering）文案与颜色语义已落地到页面状态展示。
- [ ] FE-MW-V2：与 BE 对齐 `system.status` 推送字段，避免前端自行推导连接原因。
- [ ] FE-MW-V2：评估 options chain 大表渲染方案（分页 vs 虚拟滚动）并给出性能基线。
- [x] FE-MW-V2：对齐 BE-0005 的 minute 粒度（`5m/15m/60m`），并在详情区展示 bars 的 `X-Data-Source`。
