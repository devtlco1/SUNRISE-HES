# sunrise-hes-platform

Production-grade monorepo scaffold for a utility-focused Head-End System (HES) / Advanced Metering Infrastructure (AMI) platform.

This repository is intentionally feature-light at the start. It provides the architectural foundation, service boundaries, developer tooling, and Docker-based local environment needed to build a long-life, auditable, GIS-ready platform that can grow toward 35,000+ smart meters.

## Architecture Overview

- `apps/api`: FastAPI backend, SQLAlchemy 2 setup, Alembic migrations, API routes, and platform service skeletons
- `apps/web`: Next.js + TypeScript operations web app scaffold
- `apps/worker`: placeholder worker service for future queue-driven job execution
- `packages/shared-python`: shared Python contracts and utilities
- `packages/shared-types`: shared TypeScript types for frontend/backend contracts
- `docker-compose.yml`: local development stack with API, web, PostGIS, and Redis

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
make lint-api
make format-api
make typecheck-api
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

The current local runtime path is safe for dev/demo/test use because the execute-now flow runs through the bounded Gurux stub adapter rather than field hardware.

To verify that the seeded context is still present without reseeding it, run:

```bash
make verify-command-execution-seed
```

This verifier checks that the seeded meter is visible, that meter-scoped relay-control and on-demand-read succeeded history exists, and that the global recent command projection still includes the seeded meter context. It fails clearly and boundedly when the seeded context is missing.

## Focused Runtime Tests

The preferred local path for the runtime placeholder foundation suite is Docker-backed, because those tests expect both PostgreSQL and Redis to be available.

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

## Initial Scaffold Notes

- The API exposes only a root endpoint and a health endpoint.
- Alembic is configured but no business migrations exist yet.
- PostGIS is available from the first day to support GIS-aware assets and topology later.
- Redis is included as the coordination and queue foundation for future polling, command execution, retry, and orchestration workflows.
- Protocol support for IEC 62056-21, HDLC, DLMS/COSEM, and Gurux-compatible adapters is intentionally deferred until the platform boundaries are finalized.

## Suggested Next Step

Define the first bounded contexts and persistence model, then add the initial SQLAlchemy entities and Alembic migrations for:

- tenants / utilities
- sites / feeders / transformers
- meters / communication endpoints
- job scheduling / audit trail / event history
