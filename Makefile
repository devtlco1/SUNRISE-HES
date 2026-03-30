COMPOSE ?= docker compose

.PHONY: up down logs api-shell web-shell test-api test-runtime-foundations lint-api format-api typecheck-api

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
