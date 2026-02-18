# TODO（架构落地待办）

- [HOLD] 后端/前端期权相关开发（options API、options UI、options E2E）暂停；待 Stock 数据主线里程碑完成后恢复。
- [ ] 明确 Massive 上游订阅配额与最大并发连接限制，补充订阅上限策略与告警阈值。
- [ ] 设计 Redis Pub/Sub 的频道命名与消息 envelope 版本管理策略。
- [ ] 定义 WebSocket 心跳/重连的前后端约定与超时阈值。
- [ ] 评估历史行情是否引入 TimescaleDB/分区策略（按数据量决定）。
- [ ] 完成安全配置清单（JWT 过期策略、CORS 白名单、WAF/限流规则）。
- [ ] 形成“首屏 REST + 增量 WS + 断线补拉”联调脚本与验收用例（含缓存命中/未命中场景）。

- [ ] BE-0002 评审后，补充 OpenAPI 示例与 WS close code 对照表（供前后端联调）。

- [ ] BE-0003 落地：补齐 API 层单测基础设施（ASGI client/WS client 选型、依赖与通用 fixtures），并将错误码映射统一到 BE-0002 的错误 envelope。
- [ ] BE-0005 落地：完成 `day/minute` 分表、`minute` 按交易日分区（保留 10 个交易日）、`5m/15m/60m` 预聚合与未完结实时补算，并补齐聚合边界单测。

- [ ] FE-MW-V2：补充 `/terminal` 低保真线框图（watchlist/detail/options/status 四区）并与产品确认信息优先级。
- [ ] FE-MW-V2：定义 WS 降级态（reconnecting/degraded/recovering）的统一文案与颜色语义。
- [ ] FE-MW-V2：与 BE 对齐 `system.status` 推送字段，避免前端自行推导连接原因。
- [ ] FE-MW-V2：评估 options chain 大表渲染方案（分页 vs 虚拟滚动）并给出性能基线。
- [x] FE-MW-V2：对齐 BE-0005 的 minute 粒度（`5m/15m/60m`），并在详情区展示 bars 的 `X-Data-Source`。
