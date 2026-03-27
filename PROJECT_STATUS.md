# PROJECT STATUS — sunrise-hes-platform

## Project goal
Production-grade HES/AMI platform for large-scale smart meter operations, designed to scale to 35,000+ meters.

## Completed foundations
- Monorepo scaffold completed
- FastAPI backend foundation completed
- PostgreSQL/PostGIS + Redis local stack completed
- Auth + JWT + RBAC completed
- Audit foundation completed
- Meter Registry completed
- Connectivity foundation completed
- Commands foundation completed
- Jobs/Scheduler foundation completed
- Worker execution bridge completed
- Scheduler materialization bridge completed
- Scheduler run generation completed

## Current architecture direction
- Backend: FastAPI + SQLAlchemy 2 + Alembic
- Database: PostgreSQL + PostGIS
- Coordination/runtime later: Redis
- Frontend later: Next.js
- Runtime path later: IEC 62056-21 -> HDLC -> DLMS/COSEM -> Gurux-compatible execution

## Current safe boundaries
- No live protocol/runtime execution yet
- No Redis queue processing yet
- No frontend implementation yet
- Existing module boundaries should be preserved unless a change is clearly necessary
- Prefer minimal safe changes over redesign

## Current next step
Implement the final scheduler-to-execution orchestration bridge:
generate JobRun -> materialize MeterCommand -> claim JobRun -> start CommandExecutionAttempt

## After that
- Readings / Load Profiles / Event Ingestion Foundation
- Protocol Runtime Foundation
- Worker + Redis queue + execution loop
- Hardening, observability, deployment, final testing