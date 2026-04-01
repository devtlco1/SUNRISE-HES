COMPOSE ?= docker compose
PYTHON ?= python3

.PHONY: up down logs api-shell web-shell test-api test-runtime-foundations lint-api format-api typecheck-api seed-command-execution verify-command-execution-seed smoke-command-execution-seed local-operational-readiness

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down --remove-orphans

logs:
	$(COMPOSE) logs -f

api-shell:
	$(COMPOSE) exec api /bin/sh

web-shell:
	$(COMPOSE) exec web /bin/sh

test-api:
	$(COMPOSE) run --rm api pytest

test-runtime-foundations:
	$(COMPOSE) up -d postgres redis
	$(COMPOSE) run --rm api pytest \
		tests/test_runtime_execution_claim_to_work_foundation.py \
		tests/test_runtime_execution_lease_foundation.py \
		tests/test_runtime_execution_invocation_gate_foundation.py \
		tests/test_runtime_execution_session_heartbeat_foundation.py \
		tests/test_runtime_profile_read_vertical_slice.py

lint-api:
	$(COMPOSE) run --rm api ruff check app tests

format-api:
	$(COMPOSE) run --rm api black app tests

typecheck-api:
	$(COMPOSE) run --rm api mypy app

seed-command-execution:
	$(COMPOSE) up -d postgres redis api
	@if [ "$${SUNRISE_SKIP_API_RESTART:-0}" != "1" ]; then $(COMPOSE) restart api; fi
	$(PYTHON) apps/api/scripts/seed_real_command_execution.py

verify-command-execution-seed:
	$(COMPOSE) up -d postgres redis api
	$(PYTHON) apps/api/scripts/verify_seeded_command_context.py

smoke-command-execution-seed: seed-command-execution verify-command-execution-seed

local-operational-readiness:
	./.venv/bin/python -m pytest apps/api/tests/test_health.py apps/api/tests/test_platform_readiness.py
	$(MAKE) smoke-command-execution-seed
