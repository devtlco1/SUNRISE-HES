# sunrise-hes-platform

Production-grade monorepo for a utility-focused Head-End System (HES) / Advanced Metering Infrastructure (AMI) platform.

The platform has moved beyond the initial scaffold stage. It now includes bounded backend domain foundations, durable orchestration and telemetry persistence, and a validated single-meter live runtime path that has been exercised against real field hardware. The long-term design still targets a clean, auditable, production-minded system that can grow toward 35,000+ smart meters without rewriting the core boundaries.

## Architecture Overview

- `apps/api`: FastAPI backend with bounded modules for auth/RBAC, audit logging, meters, connectivity, commands, jobs, readings/events, and runtime ingress execution
- `apps/web`: Next.js + TypeScript operations web app scaffold and dashboard groundwork
- `apps/worker`: placeholder worker service for future queue-driven orchestration and queue processing
- `packages/shared-python`: shared Python contracts and utilities
- `packages/shared-types`: shared TypeScript types for frontend/backend contracts
- `docker-compose.yml`: local development stack with API, web, PostGIS, and Redis

## Current Platform Status

The backend foundations currently implemented include:

- auth / JWT / RBAC foundation with bootstrap super-admin flow
- audit logging foundation for security-sensitive and admin-sensitive operations
- meter registry foundation with manufacturers, models, firmware, communication profiles, meter profiles, meters, and status history
- connectivity foundation with communication endpoints, endpoint assignments, protocol association profiles, credentials, and session history
- commands foundation with command templates, durable meter commands, append-only execution attempts, and command operational read models
- jobs and scheduler foundations with durable job definitions, job runs, retry queue cues, claim semantics, and internal prepare-for-execution orchestration
- readings / register snapshots / interval-load-profile / event-ingestion foundations
- runtime execution foundations covering claim, lease, invocation gates, session heartbeat, protocol planning, and durable runtime artifact chains

## Validated Live Runtime Baseline

The current production-minded live runtime baseline is intentionally bounded to the existing single-meter path and is now validated on a real meter session:

`connect -> discover -> register -> bind -> read -> persist readings -> relay disconnect/reconnect`

Current live validation status:

- live TCP ingress listener is active and reusable through the bounded bind/unbind foundation
- identity discovery before bind is working
- discovered meter persistence and endpoint/profile continuity are working
- live on-demand read over the bound ingress path is working and persists durable reading artifacts
- live relay disconnect and reconnect over the bound ingress path are working and report succeeded outcomes on fresh execute-now requests

This live path is intentionally narrow:

- single active bound live meter session
- no multi-meter orchestration yet
- no UI-driven field workflows yet
- no broad bulk execution flows yet

## Backend Domains

The API already contains durable module foundations under `apps/api/app/modules` for:

- `auth`
- `users`
- `audit`
- `meters`
- `connectivity`
- `commands`
- `jobs`
- `readings`
- `events`

The runtime execution and live ingress services live under `apps/api/app/runtime` and currently cover:

- runtime execution claim / lease / invocation gate / session heartbeat
- runtime protocol planning and adapter boundaries
- bounded live TCP meter ingress foundation
- live identity discovery before bind
- live meter persistence from discovered identity
- live on-demand read execution
- live relay-control execution

## Technology Baseline

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic
- Frontend: Next.js, React, TypeScript
- Database: PostgreSQL + PostGIS
- Cache / queue foundation: Redis
- Python quality tools: Ruff, Black, MyPy, Pytest
- Local runtime: Docker Desktop + Docker Compose

## Prerequisites

- Docker Desktop installed and running
- Optional for local non-Docker workflows: Python 3.12+ and Node.js 22+

## Local Startup

1. Copy environment templates as needed:

   ```bash
   cp .env.example .env
   cp apps/api/.env.example apps/api/.env
   cp apps/web/.env.example apps/web/.env.local
   ```

2. Start the local platform:

   ```bash
   docker compose up --build
   ```

3. Open the running services:

- Web UI: [http://localhost:3000](http://localhost:3000)
- API root: [http://localhost:8000](http://localhost:8000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Common Commands

```bash
make up
make down
make logs
make test-api
make test-runtime-foundations
make seed-command-execution
make verify-command-execution-seed
make smoke-command-execution-seed
make local-operational-readiness
make lint-api
make format-api
make typecheck-api
```

Useful direct API test paths from `apps/api`:

```bash
docker compose run --rm api pytest tests/test_runtime_tcp_meter_ingress_foundation.py
docker compose run --rm api pytest tests/test_commands_on_demand_read_execute_now.py
docker compose run --rm api pytest tests/test_commands_relay_control_execute_now.py
docker compose run --rm api pytest tests/test_commands_relay_control_status_readback.py
```

## Reproducible Real Command Seed

Use the tracked seed workflow below whenever a local DB reset removes the dev/demo command context needed for truthful relay-control and on-demand-read execution.

1. Start the local platform if it is not already running:

   ```bash
   make up
   ```

2. Recreate the seeded command context and sample recent command history:

   ```bash
   make seed-command-execution
   ```

This workflow is idempotent. It restarts the API first so the bootstrap super-admin account is recreated after local DB resets, then ensures one seeded meter plus the required manufacturer, model, communication profile, meter profile, communication endpoint, protocol association profile, endpoint assignment, and command templates. It also ensures one successful relay-disconnect execution and one successful on-demand-read execution so `/commands` and the meter command surfaces have real recent history to render.

The seed helper uses the existing application APIs rather than direct database writes. By default it targets `http://localhost:8000/api/v1` and logs in with the bootstrap super-admin account from the example local environment. Override the connection or credentials when needed with:

```bash
SUNRISE_SEED_API_BASE_URL=http://localhost:8000/api/v1
SUNRISE_SEED_USERNAME=admin
SUNRISE_SEED_PASSWORD=ChangeThisPassword123!
```

The current local runtime path is safe for dev/demo/test use because local execute-now flows still use the bounded Gurux stub adapter rather than field hardware. The real live meter validation path is currently a separately operated VPS-bound single-meter baseline.

To verify that the seeded context is still present without reseeding it, run:

```bash
make verify-command-execution-seed
```

This verifier checks that the seeded meter is visible, that meter-scoped relay-control and on-demand-read succeeded history exists, and that the global recent command projection still includes the seeded meter context. It fails clearly and boundedly when the seeded context is missing.

For the one-step local smoke path, run:

```bash
make smoke-command-execution-seed
```

This convenience target runs the seed workflow first, then immediately runs the verifier so local command-execution readiness ends with a clear pass/fail signal.

For the broader local operator/dev readiness path, run:

```bash
make local-operational-readiness
```

This target first runs the stable backend readiness/public smoke, then runs the existing seeded command-execution smoke so local startup readiness ends with one broader pass/fail signal.

For CI, automation, or external wrappers that should not depend on `make` as the direct entrypoint, run:

```bash
./scripts/local-operational-readiness.sh
```

This script delegates to the same stable local operational readiness flow and returns the same pass/fail result.

## Focused Runtime Tests

The preferred local path for the runtime foundation suites is Docker-backed, because those tests expect both PostgreSQL and Redis to be available.

1. Copy the environment templates if you have not already:

   ```bash
   cp .env.example .env
   cp apps/api/.env.example apps/api/.env
   ```

2. Run the focused runtime suite:

   ```bash
   make test-runtime-foundations
   ```

This target starts `postgres` and `redis` if needed, then runs:

```bash
pytest \
  tests/test_runtime_execution_claim_to_work_foundation.py \
  tests/test_runtime_execution_lease_foundation.py \
  tests/test_runtime_execution_invocation_gate_foundation.py \
  tests/test_runtime_execution_session_heartbeat_foundation.py
```

### Optional Host-Python Path

If you prefer to run the focused suite from a local Python environment instead of Docker:

1. Create and activate a Python 3.12 virtual environment.
2. Install the API package with its dev extras:

   ```bash
   python3 -m pip install -e packages/shared-python -e "apps/api[dev]"
   ```

3. Ensure local PostgreSQL and Redis are reachable on `127.0.0.1`.
4. Copy the API test environment template:

   ```bash
   cp apps/api/.env.test.example apps/api/.env
   ```

5. Run the same focused suite from `apps/api`:

   ```bash
   python3 -m pytest \
     tests/test_runtime_execution_claim_to_work_foundation.py \
     tests/test_runtime_execution_lease_foundation.py \
     tests/test_runtime_execution_invocation_gate_foundation.py \
     tests/test_runtime_execution_session_heartbeat_foundation.py
   ```

The Docker-backed path is the supported default because it matches the repository's existing local service topology and avoids host-specific database and Redis setup drift.

## Operational Notes

- PostGIS is part of the baseline from day one for GIS-aware asset and topology work.
- Redis remains the coordination and queue foundation for retry, claim, lease, and future worker orchestration.
- The current live field path is intentionally bounded and production-minded rather than broad or fully automated.
- Idempotency keys matter for truthful operator validation: a reused execute-now request can correctly return a previously recorded durable result rather than creating a fresh live execution.
- Fresh field validation should always use a new idempotency key when verifying live relay or read execution.

## Current Suggested Next Step

Treat the now-working single-meter live path as the operational baseline and extend it with the next smallest bounded backend slice:

- bounded live profile-capture / load-profile execution over the same bound TCP ingress path
- preserve the current single-meter live bind/read/relay baseline without refactoring it
- keep the work backend-only and production-minded
