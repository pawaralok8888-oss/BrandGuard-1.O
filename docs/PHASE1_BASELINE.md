# Phase 1 Baseline Report (Gate 0)

**Date:** 2026-10-30  
**Environment:** Windows; Python 3.12 virtual environment (`.venv312`); Node.js

## Backend test suite

- **Command:** `$env:PYTHONPATH = (Get-Location).Path; .\.venv312\Scripts\python.exe -m pytest backend\tests -q`
- **Result:** Passed
- **Collected:** 248 tests
- **Passed:** 247
- **Skipped:** 1
- **Failed:** 0
- **Duration:** 27.13 seconds
- **Warning:** One Starlette `TestClient` deprecation warning for `anyio.abc.BlockingPortal`.

## Frontend checks

- **Type check:** `npx tsc --noEmit` in `frontend/` — passed with 0 errors.
- **Production build:** `npm run build` in `frontend/` — passed.
- **Build output:** Vite 5.4.21; 2,569 modules transformed. The generated JavaScript chunk is 1,182.85 kB and triggers Vite's advisory warning for chunks over 500 kB; the build completed successfully.

## Docker Compose build

- **Command:** `docker compose build`
- **Result:** Not run to completion; Docker is unavailable because the Docker Desktop Linux engine pipe could not be found:
  `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`
- **Impact:** Backend and frontend checks above were still completed.

## Schema and seed application

There is no application-startup migration mechanism: the FastAPI lifespan opens and closes a PostgreSQL connection pool but does not apply schema or seed SQL. In local Compose, PostgreSQL's entrypoint applies `data/schema.sql` and `data/seeds/01_foundation.sql` on the first initialization of its data volume. For a full demo reset, `scripts/reset_demo_db.ps1` and `scripts/reset_demo_db.sh` truncate tables and apply the schema followed by the listed seed files in order. CI separately applies `data/schema.sql` and loops over `data/seeds/*.sql` with `psql`.
