# Mechanics for the local-only collection stack. Run from demo-platform/collection/.
SHELL := /bin/bash
APP := slack-mock
FAKE_PORT ?= 8781
APP_PORT ?= 8780
LIB := . scripts/lib.sh
UV_VERSION := 0.13.6
UV = $(shell command -v uv >/dev/null 2>&1 && echo uv || echo python3 -m uv)
ENV_TOKEN = COLLECTION_ACCESS_TOKEN=$${COLLECTION_ACCESS_TOKEN:-$$(sed -n 's/^COLLECTION_ACCESS_TOKEN=//p' .env 2>/dev/null)}

.PHONY: uv help env config up ps logs down reset test-reset test lint typecheck check fake-v3 app-fake app-stub mcp-grafana mcp-postgres label governance mock-up mock-down mcp-up mcp-down mcp-smoke

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/'

env: ## write .env with a unique COMPOSE_PROJECT_NAME and random local secrets
	@scripts/new-env.sh

config: ## validate the Compose file (example env; secrets not printed)
	docker compose --env-file .env.example -f compose.yaml --profile mcp config --quiet && echo "compose config OK"

up: env ## start postgres, prometheus, grafana, slack-mock and the grafana viewer-token init
	@$(LIB); load_env; compose up -d --build --wait postgres slack-mock prometheus grafana && compose run --rm -T --no-deps grafana-init </dev/null

ps: ## list this run's containers
	@$(LIB); load_env; compose --profile mcp ps -a

logs:
	@$(LIB); load_env; compose logs --tail=100

down: ## stop containers, keep volumes
	@$(LIB); load_env; compose --profile mcp down --remove-orphans

reset: ## remove ONLY this run's containers/volumes/networks/images and verify none remain
	@scripts/reset.sh

test-reset: ## regression: resetting a run never touches an overlapping "<run>-other" project
	@scripts/test-reset-isolation.sh

uv: ## ensure uv (pinned) is available; CI runners only have python/node
	@command -v uv >/dev/null 2>&1 || python3 -m uv --version >/dev/null 2>&1 || python3 -m pip install --quiet uv==$(UV_VERSION)

lint: uv ## ruff + shellcheck-equivalent bash -n
	cd $(APP) && $(UV) run --frozen ruff check src tests && $(UV) run --frozen ruff format --check src tests
	bash -n scripts/*.sh mcp/*.sh postgres/init/*.sh

typecheck: uv
	cd $(APP) && $(UV) run --frozen mypy

test: uv ## unit + integration tests against the FAKE v3 server
	cd $(APP) && PYTHONPATH=src $(UV) run --frozen python -m unittest discover -s tests -t . -v
	npm --prefix mock-slack test

check: lint typecheck test config
	npm --prefix mock-slack run check
	python -m py_compile mcp/smoke.py

fake-v3: ## run the FAKE v3 API on loopback (auto-replies; never the real Devin API)
	cd $(APP) && FAKE_V3_API_KEY=$${FAKE_V3_API_KEY:?} FAKE_V3_ORG_ID=org-fake-local PYTHONPATH=src:. \
	  python3 -m tests.fake_v3 --port $(FAKE_PORT)

app-fake: ## run the app on 127.0.0.1 in live mode against the loopback FAKE v3 API
	export $(ENV_TOKEN); cd $(APP) && COLLECTION_MODE=live DEVIN_API_KEY=$${FAKE_V3_API_KEY:?} COLLECTION_DEVIN_ORG_ID=org-fake-local \
	  COLLECTION_CREATE_AS_USER_ID=user-fake-persona COLLECTION_DEVIN_API_BASE=http://127.0.0.1:$(FAKE_PORT) \
	  COLLECTION_POLL_INTERVAL=2 COLLECTION_PORT=$(APP_PORT) COLLECTION_DB_PATH=$${COLLECTION_DB_PATH:-fake-demo.sqlite3} \
	  PYTHONPATH=src python3 -m collection_slack

app-stub: ## run the app on 127.0.0.1 in labelled stub mode
	export $(ENV_TOKEN); cd $(APP) && COLLECTION_PORT=$(APP_PORT) PYTHONPATH=src python3 -m collection_slack

mcp-grafana: ## stdio Grafana MCP (read-only) against this machine's stack
	@mcp/grafana-stdio.sh

mcp-postgres: ## stdio PostgreSQL MCP (restricted) against this machine's stack
	@mcp/postgres-stdio.sh

label: ## check (DRY_RUN=1) or ensure (DRY_RUN=0) the GitHub Issues label `devin`
	@scripts/ensure-devin-label.sh

governance: ## print user_id/devin_mode/acus_consumed for COLLECTION_GOVERNANCE_SESSION_IDS or IDS_FILE only
	cd $(APP) && PYTHONPATH=src python3 -m collection_slack.governance $${IDS_FILE:+--ids-file $$IDS_FILE}

mock-up:
	docker compose -f mock-slack/compose.yml up -d --build --wait
mock-down:
	docker compose -f mock-slack/compose.yml down
mcp-up:
	docker compose -f mcp/compose.yml up -d --build
mcp-down:
	docker compose -f mcp/compose.yml down
mcp-smoke:
	docker compose -f mcp/compose.yml exec -T postgres-mcp python - < mcp/smoke.py
