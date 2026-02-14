# 本地运行（MVP Scaffold）

## 前置
- 安装 Docker / Docker Compose
- 复制 `.env.example` 为 `.env` 并填入 `MASSIVE_API_KEY`（其余可用默认）

## 启动
```bash
docker compose up --build
```
- API: `http://localhost:8000/api/v1`
- 前端：`http://localhost:5173`

## 开发（只动后端代码时）
- 可在 `backend/` 内本地运行：
```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```
- Celery worker / beat：
```bash
poetry run celery -A app.core.celery_app worker -l INFO
poetry run celery -A app.core.celery_app beat -l INFO
```

## 说明
- Compose 服务：`frontend`（Vite）、`api`（FastAPI）、`worker`、`beat`、`redis`、`postgres`
- API 不做 CPU 密集计算；定时扫描由 Celery Beat 投递，worker 执行
- 数据存储在 Postgres 持久卷 `postgres_data`
