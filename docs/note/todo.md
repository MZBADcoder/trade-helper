# TODO Backlog

## Current Items

- [ ] [Backend][P1] 将 watchlist 添加后的历史数据预拉取改为异步（Celery 或 FastAPI BackgroundTasks），避免阻塞接口响应。
- [ ] [Backend][P1] Polygon 数据拉取补全分页/分段逻辑（next_url 或按日期分片），并增加重试/限流处理。
- [ ] [Backend][P1] 增加数据完整性检测（区间缺口识别与补齐策略），避免仅用 min/max 覆盖判断。
- [ ] [Backend][P2] 强化输入校验：timespan 允许值白名单、multiplier 合理范围、from/to 逻辑校验统一化。
- [ ] [Backend][P2] 增加 repository 层 Postgres 集成测试（upsert、唯一约束、索引生效）。
- [ ] [Backend][P2] 增加 API 层最小化集成测试（依赖注入与基础响应）。

## Add Rule

每轮流程结束后追加：
- 来源：`PRD/ADR/BE/Frontend`
- 优先级：`P0/P1/P2`
- 下一步动作：一句话可执行描述
