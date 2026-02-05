# Backend Architecture (DDD No-Interfaces)

This backend follows a **DDD-inspired, no-interfaces** layout:

- **api/**
  - FastAPI routers and external DTOs.
  - Thin controllers: validate input, call application services, map errors to HTTP.
  - API must not touch ORM/DB clients.

- **application/**
  - Use-case orchestration and transaction boundaries.
  - Depends on concrete infrastructure classes via dependency injection.
  - Uses a Unit of Work (UoW) to control commits.

- **domain/**
  - Pure domain entities (dataclasses), value objects, and domain errors.
  - No imports from FastAPI, Pydantic, SQLAlchemy, Redis, or Celery.

- **infrastructure/**
  - DB session, UoW, repositories, mappers, and external clients.
  - Repositories return domain entities via mappers.

- **core/**
  - App-wide configuration and security helpers.

- **tasks/**
  - Background task entrypoints (Celery).

## Dependency Direction

`api → application → infrastructure → domain`

Notes:
- No interface/Protocol/ABC layers.
- Application services are constructed in `application/container.py`.
- API only imports the container and application services.

## Key Files

```
app/
  api/
    v1/
    dto/
  application/
    container.py
    auth/
    market_data/
    watchlist/
  domain/
    auth/
    market_data/
    watchlist/
  infrastructure/
    db/
      mappers.py
      uow.py
      models/
    repositories/
    clients/
  core/
  tasks/
  main.py
```
