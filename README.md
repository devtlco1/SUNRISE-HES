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
make lint-api
make format-api
make typecheck-api
```

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
