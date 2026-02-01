# Backend Architecture (DDD Skeleton)

This backend is organized as a lightweight DDD-style skeleton. Most layers are **intentionally unimplemented** (raise `NotImplementedError`) and serve as contracts and structure for long-term iteration.

## Layers & Responsibilities

- **api/**
  - FastAPI routers and external API contracts.
  - Uses **DTOs** for request/response models.
  - Should call **application** services only (no direct repository access).

- **application/**
  - Application layer (use-case orchestration / aggregation).
  - Converts **DTOs ↔ domain schemas** via mappers.
  - Depends on **domain services** via interfaces.

- **domain/**
  - Core domain definitions.
  - **schemas.py** = domain input/output models (not DTOs).
  - **interfaces.py** = domain service contracts.
  - **services.py** = domain service implementation (business rules).
  - **models.py** = domain entities placeholder (future ORM/pure domain entities).

- **repository/**
  - Data access contracts and implementations.
  - **interfaces.py** defines repository contracts.
  - **repo.py** holds persistence implementations (currently skeleton).

- **infrastructure/**
  - Technical details (DB sessions/init, external clients, notifications).
  - Keep external integrations here.

- **core/**
  - App-wide configuration and tooling (settings, celery, etc.).

- **tasks/**
  - Background task entrypoints (Celery tasks).

## DTO vs Domain Schema

- **DTO (api/dto/...)**
  - External contract with frontend.
  - Can change frequently.

- **Domain Schema (domain/*/schemas.py)**
  - Internal contract between domain/application.
  - Should be stable and business-focused.

## Dependency Direction

`api → application → domain → repository → infrastructure`

Rules:
- API should not import repository or infrastructure directly.
- Application depends on domain interfaces and maps DTO ↔ domain schemas.
- Domain services depend on repository interfaces (not concrete implementations).
- Infrastructure is only referenced by repository implementations or app bootstrapping.

## Folder Map (Current)

```
app/
  api/
    dto/
    v1/endpoints/
  application/
    watchlist/
      interfaces.py
      mapper.py
      service.py
    rules/
      interfaces.py
      mapper.py
      service.py
    alerts/
      interfaces.py
      mapper.py
      service.py
  domain/
    watchlist/
      interfaces.py
      schemas.py
      services.py
    rules/
      interfaces.py
      schemas.py
      services.py
    alerts/
      interfaces.py
      schemas.py
      services.py
    scans/
      iv_scanner.py
    models.py
    base.py
  repository/
    watchlist/
      interfaces.py
      repo.py
    rules/
      interfaces.py
      repo.py
    alerts/
      interfaces.py
      repo.py
  infrastructure/
    db/
      session.py
      init_db.py
    clients/
      polygon.py
    notifications/
      feishu.py
  core/
  tasks/
  main.py
```

## Notes

- Many methods are placeholders (raise `NotImplementedError`) by design.
- This document is the reference for future iteration and refactors.
