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

## Frontend Guardrails (React + TypeScript, Feature-Sliced)

Applies to all code under `frontend/src`.

### 1) Layer direction

Dependency direction must be:

`app -> pages -> widgets -> features -> entities -> shared`

Upper layers can depend on lower layers only.
No upward imports.

### 2) Boundary enforcement

Import boundaries are enforced by ESLint (`import/no-restricted-paths`).
Do not bypass them with relative path tricks or deep cross-layer imports.

### 3) Public API and import style

- Use alias imports via `@/*` from `tsconfig.json`.
- Cross-slice imports should go through each slice public entry (`index.ts`) by default.
- Keep internal files private to the slice unless there is a clear reuse need.

### 4) Data access boundaries

- Shared HTTP primitives live in `frontend/src/shared/api/*`.
- Endpoint-specific API calls live in entity/feature `api/*`.
- `pages/widgets/ui` should not call `fetch`/HTTP client directly.

### 5) UI and state split

- Keep render-focused components in `ui/*`.
- Keep business/stateful logic in `model/*` or dedicated hooks.
- Keep pure helpers/formatters in `lib/*`.
- Page layer should compose flows; avoid embedding feature business logic in route files.

### 6) App-wide concerns

- Global providers and router wiring belong in `frontend/src/app/providers` and `frontend/src/app/routes`.
- Theme tokens and global style baseline belong in `frontend/src/app/styles/theme.css`.

## Required Checks for Backend Changes

Run before commit (in `backend/`):

1. `python3 scripts/check_boundaries.py --root . --package app`
2. `poetry run python3 -m pytest -q`

Local sandbox uses Poetry-managed environment. Run backend checks and tests through `poetry run`.

If `pytest` is unavailable in current environment, state that explicitly in the delivery note.

## Required Checks for Frontend Changes

Run before commit (in `frontend/`):

1. `npm run lint`
2. `npm run test`
3. `npm run build`

If `npm` is unavailable in current environment, state that explicitly in the delivery note.

## Canonical Docs

- Docs map: `docs/README.md`
- Architecture baseline: `docs/adr/ARCHITECTURE-BASELINE.md`
- Backend architecture: `backend/ARCHITECTURE.md`
- Frontend design index: `docs/frontend-design/README.md`

## Git Commit Message Convention

When the user asks to commit and does not provide a custom format, follow this default:

- The title should be a single sentence summarizing the main change.
- The title must include one type: `feat` / `bugfix` / `refactor`.
- The title must include the primary scope: `frontend` or `backend` (for cross-layer changes, use the dominant scope).
- Recommended format: `<type>(<scope>): <one-sentence summary>`.
- If the change is large, add details in the description/body using `summary` / `detail`.

## Git Conflict Resolution (Rebase + Squash Before Main Merge)

For this single-developer project, keep `main` updated first, then rebase your feature branch onto latest `main`, squash branch commits into one, and finally merge with fast-forward only.
This keeps history linear and avoids extra merge commits.

Recommended flow (no merge commit):

1. `git checkout main`
2. `git pull --ff-only origin main`
3. `git checkout <feature-branch>`
4. `git rebase main`
5. If conflicts happen: resolve markers (`<<<<<<<`, `=======`, `>>>>>>>`), run `git add <file>`, then `git rebase --continue` (repeat until done).
6. `git reset --soft main`
7. `git commit -m "<type>(<scope>): <one-sentence summary>"`，if the change is large, add details in the description/body using `summary` / `detail`.
8. `git checkout main`
9. `git merge --ff-only <feature-branch>`

If you need to cancel conflict resolution:

1. `git rebase --abort`

If `git merge --ff-only` fails, it means `main` changed after your rebase.
Pull latest `main` and rebase the feature branch again.

Push rules:

1. Push `main` normally: `git push origin main`.
2. If a rebased feature branch has already been pushed before, update it with `git push --force-with-lease origin <feature-branch>`.

Unless explicitly requested, do not use `git merge --no-ff` in this repo.
