# Trader Helper - Agent Start Guide

This file is the primary entrypoint for new coding threads.
Read this before making changes.

## Project Flow (Mandatory)

1. Finalize PRD first: `docs/prd/`
2. Check ADR impact: `docs/adr/`
3. Split backend work from PRD: `docs/backend-evolution/`
4. Design frontend from PRD + backend split: `docs/frontend-design/`
5. Record leftovers after each cycle: `docs/note/todo.md`

## Documentation Language

All documents generated from requirement discussions must be written in Simplified Chinese by default.
This includes PRD, ADR updates, backend evolution notes, frontend design docs, and TODO notes.
Exceptions are allowed only when the user explicitly requests English output.

## Backend Guardrails (FastAPI DDD, No Interfaces)

Applies to all code under `backend/app`.

### 1) Layer direction

Dependency direction must be:

`api -> application -> infrastructure -> domain`

Entry layers (`api`, `tasks`) call `application` only.

### 2) Domain purity

`domain` must stay framework-free.
Do not import these in `domain/*`:

- `sqlalchemy`
- `redis`
- `celery`
- `fastapi`
- `pydantic`
- `pydantic_settings`

### 3) No interfaces style

Do not introduce interface abstractions for repositories/services.
Forbidden patterns:

- `typing.Protocol`
- `typing_extensions.Protocol`
- `abc.ABC` / `ABCMeta`
- interface-only layers/files

Use concrete classes + dependency injection in `application/container.py`.

### 4) Thin API, explicit DTO mapping

API layer responsibilities:

- validate request DTO
- call application service
- map domain result to response DTO
- map domain/application errors to HTTP

API must not touch ORM model, SQLAlchemy session, Redis client.

Use explicit mappers in:

- `backend/app/api/v1/dto/mappers.py`

Do not return domain objects directly from endpoint handlers.

### 5) Repository and mapper rules

- Repositories return **domain entities**, not ORM models.
- ORM <-> Domain mapping lives in `infrastructure/db/mappers.py`.

### 6) Composition root

Dependency wiring lives in:

- `backend/app/application/container.py`

`api/deps.py` can resolve from container, but should not construct infra details inline.

## Required Checks for Backend Changes

Run before commit (in `backend/`):

1. `python3 scripts/check_boundaries.py --root . --package app`
2. `python3 -m pytest -q`

If `pytest` is unavailable in current environment, state that explicitly in the delivery note.

## Canonical Docs

- Docs map: `docs/README.md`
- Architecture baseline: `docs/adr/ARCHITECTURE-BASELINE.md`
- Backend architecture: `backend/ARCHITECTURE.md`
