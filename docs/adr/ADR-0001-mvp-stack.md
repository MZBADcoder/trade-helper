# ADR-0001 — Web MVP 技术栈

日期：2026-01-29  
状态：Accepted

## 背景

- MVP 需要快速迭代，单机部署即可
- 业务包含：在线配置/查询 + 定时拉取数据 + 计算 + 告警推送
- 未来会扩展到更多指标与策略/建议，CPU/IO 任务都可能增长

## 决策

- 前端：React
- 在线 API：FastAPI
- 离线任务：Celery workers + Celery Beat
- Broker：Redis
- 存储：Postgres
- 部署：单机 Docker Compose

## 原因

- 在线与离线解耦：API 保持快响应，计算任务可重试/可并发扩展
- 生态成熟：Python 数据分析能力更强，适合后续指标/策略迭代
- 运维成本低：Compose 足够支撑 MVP；后续可平滑演进到更复杂架构

## 影响与后果

- 需要维护 Redis/Postgres 两个基础设施
- 必须设计幂等与去重（避免重复告警/重复推送）

