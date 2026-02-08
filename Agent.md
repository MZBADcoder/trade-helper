# Agent Context - Trader Helper

## Purpose

This file gives a new thread the minimum project context and working order.

## Documentation Workflow (Mandatory)

1. Finalize PRD first: `/Users/mz/pmf/trader-helper/docs/prd/`
2. Check ADR impact: `/Users/mz/pmf/trader-helper/docs/adr/`
3. Split backend work from PRD: `/Users/mz/pmf/trader-helper/docs/backend-evolution/`
4. Design frontend based on PRD + backend split: `/Users/mz/pmf/trader-helper/docs/frontend-design/`
5. Record leftovers after each full cycle: `/Users/mz/pmf/trader-helper/docs/note/todo.md`

## Canonical Docs

- Docs index: `/Users/mz/pmf/trader-helper/docs/README.md`
- PRD index: `/Users/mz/pmf/trader-helper/docs/prd/README.md`
- ADR index: `/Users/mz/pmf/trader-helper/docs/adr/README.md`
- Backend evolution index: `/Users/mz/pmf/trader-helper/docs/backend-evolution/README.md`
- Frontend design index: `/Users/mz/pmf/trader-helper/docs/frontend-design/README.md`
- Note index: `/Users/mz/pmf/trader-helper/docs/note/README.md`

## Current Product State

- Frontend has:
  - Real route: `/terminal` (authenticated)
  - Demo route: `/demo` (independent local synthetic data)
  - Login route: `/login`
  - Home route: `/`
- Base market indicators in frontend: MA, MACD, BOLL, RSI, VOL
- IV monitoring UI is pending next stage

## Current Backend Surface (used by real terminal)

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/watchlist`
- `POST /api/v1/watchlist`
- `DELETE /api/v1/watchlist/{ticker}`
- `GET /api/v1/market-data/bars`

## Execution Rules for Future Threads

- Do not start backend/frontend implementation before PRD and BE split are aligned.
- If PRD changes API behavior, update BE doc first, then code.
- Keep demo and real pages decoupled unless explicitly asked to merge.
- After each delivery cycle, append follow-up items into `docs/note/todo.md`.
