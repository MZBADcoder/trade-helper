# TODO（架构落地待办）

- [x] 项目范围精简清理：已移除非股票扩展代码、接口、测试与文档引用（2026-03-03）。
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

- [x] FE-MW-V2：已补充 `/terminal` 信息架构与交互原型（watchlist/detail/status）。
- [ ] FE-MW-V2：与产品确认 `/terminal` 信息优先级并冻结版本。
- [x] FE-MW-V2：WS 降级态（reconnecting/degraded/recovering）文案与颜色语义已落地到页面状态展示。
- [ ] FE-MW-V2：与 BE 对齐 `system.status` 推送字段，避免前端自行推导连接原因。
- [x] FE-MW-V2：对齐 minute 粒度（`1m/5m/15m/60m`，10 个交易日边界），并在详情区展示 bars 的 `X-Data-Source`。
- [x] FE-MW-V2：K 线支持 `300/500/1000` 缩放、鼠标横向平移，以及左边界自动补拉历史（`1m` 按 3 天窗口补拉）。
- [x] FE-MW-V2（P2）：分钟级 K 线交易日判定已改为后端交易日接口（历史基于 XNYS 日历，今天/未来叠加 Massive holidays 覆盖），不再由前端用 weekday 近似。
- [ ] BE-TRADING-CALENDAR 收尾：补充 `market_status` 的“临时停市/异常交易日”覆盖策略与监控告警，避免仅依赖 upcoming holidays。
- [ ] MARKET-SNAPSHOTS 优化：将交易日盘中 watchlist 的 `change/change_pct` 改为“WS 最新价 + DB `prev_close` 实时重算”全链路口径（当前已完成非交易日 DB 基准回退）。
- [ ] MARKET-BARS-WS 后续：`delay=0` 下分钟 K 停更已通过“独立 K 线自动 refresh”止血；后续仍需评估将 WS `aggregate` 接入 detail bars 增量合并，减少对 REST 补拉的依赖。
- [ ] MARKET-BARS-GAP-FILL 后续：`bars` 读取链路仍使用 `min/max coverage` 粗判；后续需补齐“先用 DB immutable 数据，再只回源缺口”的 gap-aware 覆盖判断与补齐策略。
- [ ] DEMO-REPLAY 后续项：评估将 `/demo` 的 mock 回放窗口从“纯后端生成”升级为“真实历史数据抽样 + mock 增量拼接”，以便逐步接近生产链路。
- [ ] SESSION-SECURITY 后续项：开发阶段暂保留前端 `localStorage` token；后续单独评估并实施更安全的 session 承载方案（如 HttpOnly Cookie / memory-only token + refresh 流程）。
- [ ] HTTP-ASYNC 收尾：持续跟踪 Massive 官方 Python SDK 是否提供原生 async REST client；若可用，替换当前 `to_thread` 过渡适配层。
- [ ] HTTP-ASYNC 收尾：补充真实 Postgres / Redis 的异步集成测试，覆盖 AsyncSession 事务回滚、Redis 限流与应用关闭时资源释放。
