COMPOSE ?= docker compose

.PHONY: up down logs api-shell web-shell test-api lint-api format-api typecheck-api

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

lint-api:
	$(COMPOSE) run --rm api ruff check app tests

format-api:
	$(COMPOSE) run --rm api black app tests

typecheck-api:
	$(COMPOSE) run --rm api mypy app
