# TODO（架构落地待办）

- [ ] 明确 Polygon 上游订阅配额与最大并发连接限制，补充订阅上限策略与告警阈值。
- [ ] 设计 Redis Pub/Sub 的频道命名与消息 envelope 版本管理策略。
- [ ] 定义 WebSocket 心跳/重连的前后端约定与超时阈值。
- [ ] 评估历史行情是否引入 TimescaleDB/分区策略（按数据量决定）。
- [ ] 完成安全配置清单（JWT 过期策略、CORS 白名单、WAF/限流规则）。
- [ ] 形成“首屏 REST + 增量 WS + 断线补拉”联调脚本与验收用例（含缓存命中/未命中场景）。

- [ ] BE-0002 评审后，补充 OpenAPI 示例与 WS close code 对照表（供前后端联调）。

- [ ] BE-0003 落地：补齐 API 层单测基础设施（ASGI client/WS client 选型、依赖与通用 fixtures），并将错误码映射统一到 BE-0002 的错误 envelope。
