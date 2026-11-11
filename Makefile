.PHONY: sfx-informatica-up sfx-informatica-run sfx-informatica-test sfx-informatica-down sfx-informatica-snowconvert
.PHONY: help infra-up infra-down up down build test test-coverage test-api-flows test-api-flows-collect lint deploy-dev teardown-dev seed wait-for-db security-scan test-report build-report testdata-validate testdata-clean testdata-setup-schema batch-usage-rollup batch-usage-rollup-seed dev-backend dev-web dev-admin dev-android dev-electron workbench-up workbench-down dast-list dast-scan dast-verify dast-baseline dast-zap procs-validate procs-up procs-down procs-record procs-list procs-parity procs-rules-gate insurance-up insurance-down insurance-test deps-inventory deps-gate deps-command deps-transcript deps-transcript-baseline deps-tests deps-record dast-coverage dast-routes dast-test eq-list eq-gate eq-baseline eq-verify eq-exploit eq-exploit-refactored eq-tests eq-record demo-up demo-migrate demo-destroy demo-verify-clean demo-reaper incident-up incident-down incident-arm incident-disarm incident-status incident-verify incident-load incident-seed incident-simulate incident-fingerprint incident-record incident-reset-fixture incident-chart-sync incident-chart-check arm disarm lp-up lp-replay lp-status lp-reset lp-down lp-verify-clean lp-ec2-up lp-ec2-status lp-ec2-replay lp-ec2-down lp-ec2-verify-clean lp-deploy lp-break lp-heal lp-page-status

SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: sfx-teradata-up sfx-teradata-run sfx-teradata-test sfx-teradata-down sfx-teradata-snowconvert sfx-teradata-validate

.PHONY: sfx-exit-reads sfx-exit-board sfx-exit-decommission
sfx-exit-reads sfx-exit-board sfx-exit-decommission: warehouse/.venv/.requirements
	$(SFX_TD_ENV) $(SFX_TD_PY) warehouse/exit/$(patsubst sfx-exit-%,%,$@).py $(ARGS)

ROWS_PER_TABLE ?= 200000
BUSINESS_DATE ?= 20261109
SFX_TD_PYTHON ?= python3
SCAI ?= $(or $(shell command -v scai 2>/dev/null),$(wildcard $(HOME)/.local/bin/scai),scai)
TD_PG_PORT ?= $(shell NS="$(NS)" $(SFX_TD_PYTHON) -c 'import os,zlib; print(54500+zlib.crc32(os.environ["NS"].encode())%1000)')
SFX_TD_ENV = NS="$(NS)" TD_PG_PORT="$(TD_PG_PORT)" PYTHONPATH="$(abspath warehouse/teradata)"
SFX_TD_PY = warehouse/.venv/bin/python

sfx-teradata-validate:
	@test -n "$(NS)" || (echo "NS is required, e.g. NS=sfx-d1110-before" >&2; exit 2)
	@[[ "$(NS)" =~ ^[a-z0-9][a-z0-9-]*$$ ]] || (echo "NS must contain lowercase letters, digits or hyphens" >&2; exit 2)

warehouse/.venv/.requirements: warehouse/requirements.txt
	$(SFX_TD_PYTHON) -m venv warehouse/.venv
	$(SFX_TD_PY) -m pip install -r warehouse/requirements.txt
	@touch $@

sfx-teradata-up: sfx-teradata-validate warehouse/.venv/.requirements ## Start and load the Teradata warehouse (NS required; ROWS_PER_TABLE=200000)
	docker pull mirror.gcr.io/library/postgres:16
	docker tag mirror.gcr.io/library/postgres:16 postgres:16
	$(SFX_TD_ENV) warehouse/teradata/bin/compose up -d --wait --pull never
	$(SFX_TD_ENV) $(SFX_TD_PY) -m bteq.setup
	$(SFX_TD_ENV) $(SFX_TD_PY) warehouse/seed/generate.py --rows "$(ROWS_PER_TABLE)" --seed 1110 --business-date "$(BUSINESS_DATE)"
	$(SFX_TD_ENV) $(SFX_TD_PY) -m bteq.load --landing warehouse/landing --business-date "$(BUSINESS_DATE)"
	$(SFX_TD_ENV) $(SFX_TD_PY) warehouse/teradata/jobs/daily_chain --reuse-landing --business-date "$(BUSINESS_DATE)"

sfx-teradata-run: sfx-teradata-validate warehouse/.venv/.requirements ## Rerun the warehouse chain using existing landing files (NS required)
	$(SFX_TD_ENV) $(SFX_TD_PY) warehouse/teradata/jobs/daily_chain --reuse-landing --business-date "$(BUSINESS_DATE)"

sfx-teradata-test: sfx-teradata-validate warehouse/.venv/.requirements ## Test the warehouse against its PostgreSQL instance (NS required)
	$(SFX_TD_ENV) $(SFX_TD_PY) -m pytest -q warehouse/seed/tests warehouse/teradata/tests

sfx-teradata-down: sfx-teradata-validate ## Stop the warehouse and remove its volume (NS required)
	$(SFX_TD_ENV) warehouse/teradata/bin/compose down -v

sfx-teradata-snowconvert: sfx-teradata-validate warehouse/.venv/.requirements ## Run offline SnowConvert into ignored output (NS required; SCAI executable optional)
	$(SFX_TD_PY) warehouse/teradata/jobs/snowconvert.py --scai "$(SCAI)" --namespace "$(NS)"

# Billing proof is deliberately independent of the target scaffold and other subject areas.
PARITY_OUT ?= migration/dw-exit/.runs
CANDIDATE ?= fixed
SFX_BILLING = migration/dw-exit/billing

warehouse/.venv/.billing-requirements: migration/dw-exit/requirements.txt warehouse/requirements.txt
	@test -x $(SFX_TD_PY) || $(SFX_TD_PYTHON) -m venv warehouse/.venv
	$(SFX_TD_PY) -m pip install -r migration/dw-exit/requirements.txt
	@touch $@

.PHONY: sfx-billing-capture sfx-billing-prove sfx-billing-promote sfx-billing-test
sfx-billing-capture: sfx-teradata-validate warehouse/.venv/.billing-requirements ## Freeze the post-chain BEFORE, once per fresh baseline schema
	@mkdir -p "$(PARITY_OUT)"
	$(SFX_TD_ENV) $(SFX_TD_PY) $(SFX_BILLING)/capture.py --business-date "$(BUSINESS_DATE)" --output "$(PARITY_OUT)/capture.json"
	$(SFX_TD_ENV) $(SFX_TD_PY) $(SFX_BILLING)/reports.py --capture --business-date "$(BUSINESS_DATE)"
	$(SFX_TD_ENV) $(SFX_TD_PY) $(SFX_BILLING)/probes.py --capture --initial

sfx-billing-prove: warehouse/.venv/.billing-requirements ## Load converted billing and fail on live mismatch (CANDIDATE=initial|fixed)
	@test "$(CANDIDATE)" = initial -o "$(CANDIDATE)" = fixed
	@mkdir -p "$(PARITY_OUT)"
	$(SFX_TD_PY) $(SFX_BILLING)/deploy.py $(if $(filter initial,$(CANDIDATE)),--initial,) --business-date "$(BUSINESS_DATE)" --output "$(PARITY_OUT)/deploy-$(CANDIDATE).json"
	$(SFX_TD_PY) $(SFX_BILLING)/reports.py --business-date "$(BUSINESS_DATE)"
	SFX_LIVE_PARITY=1 SFX_PARITY_STEP=billing_$(CANDIDATE) SFX_PARITY_OUTPUT="$(PARITY_OUT)/billing-$(CANDIDATE).json" $(SFX_TD_PY) -m pytest -q migration/dw-exit/tests -k test_live_parity

sfx-billing-promote: warehouse/.venv/.billing-requirements ## Recheck live parity, then mark billing migrated/verified
	@mkdir -p "$(PARITY_OUT)"
	$(SFX_TD_PY) $(SFX_BILLING)/promote.py --output "$(PARITY_OUT)/migration-control.json"

sfx-billing-test: warehouse/.venv/.billing-requirements ## Offline parity tool regression tests (no Snowflake credentials)
	$(SFX_TD_PY) -m pytest -q migration/dw-exit/tests


.PHONY: sfx-airflow-test
sfx-airflow-test: ## Parse generated DAGs and verify routing and retry policy
	AIRFLOW_HOME=$(HOME)/.sfx-airflow AIRFLOW__CORE__LOAD_EXAMPLES=False uv run --python 3.11 --with-requirements etl/airflow/requirements.txt python -m unittest discover -s etl/airflow/tests -v

.PHONY: sfx-spark-snowflake
sfx-spark-snowflake: warehouse/.venv/.sfx-installed ## Run a migrated registry command (JOB=<job>)
	warehouse/.venv/bin/python warehouse/snowflake/run_spark_job.py --job "$(JOB)"

.PHONY: sfx-snowflake-deploy sfx-snowflake-load sfx-snowflake-test sfx-snowflake-dbt
.PHONY: sfx-snowflake-dag sfx-snowflake-consumers
.PHONY: sfx-snowflake-ledger sfx-snowflake-teardown sfx-snowflake-roles-dry-run sfx-snowflake-up sfx-snowflake-run sfx-snowflake-down

SFX_PYTHON ?= python3.10
SFX_VENV ?= warehouse/snowflake/.venv
SFX_TEST_PYTHON ?= $(SFX_VENV)/bin/python

.PHONY: sfx-operate-load sfx-operate-break sfx-operate-reset sfx-operate-check sfx-operate-alert sfx-operate-exporter
sfx-operate-check: $(SFX_VENV)/.sfx-installed ## Print shared pipeline checks
	$(SFX_VENV)/bin/python warehouse/pipeline/checks.py

sfx-operate-alert: $(SFX_VENV)/.sfx-installed ## Send or dry-run pipeline notification
	$(SFX_VENV)/bin/python warehouse/pipeline/fire_alert.py

sfx-operate-exporter: $(SFX_VENV)/.sfx-installed ## Serve pipeline metrics
	$(SFX_VENV)/bin/python observability/pipeline/sfx_pipeline_exporter.py

sfx-operate-load: $(SFX_VENV)/.sfx-installed ## Load the good daily billing feed
	$(SFX_VENV)/bin/python warehouse/pipeline/load_daily.py --date 2026-11-09

sfx-operate-break: $(SFX_VENV)/.sfx-installed ## Receive the changed vendor feed
	SFX_VENV="$(abspath $(SFX_VENV))" bash warehouse/pipeline/break_upstream.sh

sfx-operate-reset: $(SFX_VENV)/.sfx-installed ## Remove the changed feed and rebuild staging
	$(SFX_VENV)/bin/python warehouse/pipeline/load_daily.py --date 2026-11-10 --reset

$(SFX_VENV)/.sfx-installed: warehouse/snowflake/requirements.txt
	$(SFX_PYTHON) -m venv $(SFX_VENV)
	$(SFX_VENV)/bin/pip install -r warehouse/snowflake/requirements.txt
	@touch $@

sfx-snowflake-deploy: $(SFX_VENV)/.sfx-installed ## Deploy Snowflake scaffold migrations
	$(SFX_VENV)/bin/python warehouse/snowflake/deploy.py

sfx-snowflake-load: $(SFX_VENV)/.sfx-installed ## Load Snowflake landing files
	$(SFX_VENV)/bin/python warehouse/snowflake/load.py --area all

.PHONY: sfx-pc-setup sfx-pc-before sfx-pc-dbt sfx-pc-parity sfx-pc-idempotence sfx-pc-mark sfx-pc-licence sfx-pc-dag sfx-pc-test
export PC_CONTROL_SCHEMA ?= MIGRATION_CONTROL
export PC_CONTROL_TABLE ?= MAPPINGS
SFX_PC_PY = $(abspath $(SFX_VENV))/bin/python
sfx-pc-setup: $(SFX_VENV)/.sfx-installed ## Seed additive migration inventory and source snapshot
	cd warehouse && "$(SFX_PC_PY)" -m parity setup $(if $(filter 1,$(SKIP_CONTROL)),--skip-control)

sfx-pc-before sfx-pc-parity sfx-pc-idempotence: $(SFX_VENV)/.sfx-installed ## Capture/compare/rebuild MAPPING
	@test -n "$(MAPPING)" || (echo 'MAPPING is required'; exit 2)
	cd warehouse && "$(SFX_PC_PY)" -m parity $(patsubst sfx-pc-%,%,$@) --mapping "$(MAPPING)"

sfx-pc-dbt: $(SFX_VENV)/.sfx-installed ## Build MAPPING or all PC models in FOLDER
	cd warehouse && "$(SFX_PC_PY)" -m parity dbt $(if $(MAPPING),--mapping "$(MAPPING)",--folder "$(FOLDER)") $(if $(LOAD_DATE),--load-date "$(LOAD_DATE)")

sfx-pc-mark: $(SFX_VENV)/.sfx-installed ## Publish evidence for MAPPING (AMBER/OWNER/PR_URL optional)
	@test -n "$(MAPPING)" || (echo 'MAPPING is required'; exit 2)
	cd warehouse && "$(SFX_PC_PY)" -m parity mark --mapping "$(MAPPING)" $(if $(AMBER),--amber "$(AMBER)") $(if $(OWNER),--owner "$(OWNER)") $(if $(PR_URL),--pr-url "$(PR_URL)")

sfx-pc-licence: $(SFX_VENV)/.sfx-installed ## Count remaining PowerCenter mappings
	cd warehouse && "$(SFX_PC_PY)" -m parity licence

sfx-pc-dag: $(SFX_VENV)/.sfx-installed ## Deploy suspended FOLDER DAG (RUN_ONCE=1 to execute)
	"$(SFX_PC_PY)" warehouse/snowflake/pc_dag.py --folder "$(FOLDER)" $(if $(filter 1,$(RUN_ONCE)),--run-once) $(if $(LOAD_DATE),--load-date "$(LOAD_DATE)")

sfx-pc-test: $(SFX_VENV)/.sfx-installed ## Offline migration harness and PC DAG tests
	cd warehouse && "$(abspath $(SFX_TEST_PYTHON))" -m pytest parity/tests -q

.PHONY: sfx-snowflake-load-before
sfx-snowflake-load-before: sfx-teradata-validate $(SFX_VENV)/.sfx-installed warehouse/.venv/.requirements ## Land processed billing after sfx-teradata-run
	$(SFX_TD_ENV) $(SFX_VENV)/bin/python warehouse/snowflake/load.py --source teradata-before --area billing --date "$(BUSINESS_DATE)" --teradata-python "$(SFX_TD_PY)"

sfx-snowflake-test: $(SFX_VENV)/.sfx-installed ## Run offline Snowflake scaffold tests
	$(SFX_TEST_PYTHON) -m pytest warehouse/snowflake/tests -q
	$(SFX_TEST_PYTHON) warehouse/snowflake/run_dbt.py parse

sfx-snowflake-dbt: $(SFX_VENV)/.sfx-installed ## Build and test billing staging views
	$(SFX_VENV)/bin/python warehouse/snowflake/run_dbt.py build

sfx-snowflake-dag: $(SFX_VENV)/.sfx-installed ## Execute the log-only DAG once and suspend its tasks
	$(SFX_VENV)/bin/python warehouse/snowflake/task_dag.py --run-once

sfx-snowflake-consumers: $(SFX_VENV)/.sfx-installed ## Report observed tagged consumer reads
	$(SFX_VENV)/bin/python warehouse/snowflake/consumer_reads.py

.PHONY: sfx-snowflake-snowconvert
sfx-snowflake-snowconvert: $(SFX_VENV)/.sfx-installed ## Run SnowConvert CLI into ignored raw output
	$(SFX_VENV)/bin/python warehouse/snowflake/snowconvert.py

sfx-snowflake-ledger: $(SFX_VENV)/.sfx-installed ## Report lag-aware Snowflake credits
	$(SFX_VENV)/bin/python warehouse/snowflake/ledger.py

sfx-snowflake-teardown: $(SFX_VENV)/.sfx-installed ## Drop token-scoped objects (TEARDOWN_ARGS=--dry-run to preview)
	$(SFX_VENV)/bin/python warehouse/snowflake/teardown.py --token sfx-d1110 $(TEARDOWN_ARGS)

sfx-snowflake-roles-dry-run: $(SFX_VENV)/.sfx-installed ## Validate roles and check live CREATE ROLE privilege
	$(SFX_VENV)/bin/python warehouse/snowflake/roles/dry_run.py --check-live

ifeq ($(NS),sfx-d1110-before)
sfx-snowflake-up sfx-snowflake-run sfx-snowflake-down:
	@echo "The Snowflake target is not part of namespace sfx-d1110-before"
else
sfx-snowflake-up: sfx-snowflake-deploy ## Deploy the Snowflake target

sfx-snowflake-run: ## Load, build billing staging, and report credits
	$(MAKE) sfx-snowflake-load
	$(MAKE) sfx-snowflake-dbt
	$(MAKE) sfx-snowflake-ledger

sfx-snowflake-down: $(SFX_VENV)/.sfx-installed ## Suspend tasks and warehouses without dropping objects
	$(SFX_VENV)/bin/python warehouse/snowflake/teardown.py --token sfx-d1110 --suspend-only
endif

.PHONY: sfx-spark-up sfx-spark-run sfx-spark-test sfx-spark-down
ROWS_PER_TABLE ?= 200000
SPARK_JOBS ?= 30
SFX_SPARK_NS = $(or $(NS),sfx-d1110-before)
SFX_SPARK_DATA = etl/spark/.data/$(SFX_SPARK_NS)
SFX_SPARK_CACHE = etl/spark/.cache/$(SFX_SPARK_NS)
SFX_SPARK_LANDING ?= $(SFX_SPARK_DATA)/landing
SFX_SPARK_ENV = NS=$(SFX_SPARK_NS) LANDING_DIR=$(abspath $(SFX_SPARK_LANDING))
SFX_SPARK_COMPOSE = docker compose -f docker-compose.spark.yml -p sfx-d1110-spark-$(SFX_SPARK_NS)
SFX_SPARK_UV = uv run --python 3.11 --with pyspark==3.5.3 --with pyyaml==6.0.2

sfx-spark-up: ## Start the local Spark estate and load its fixture
	$(SFX_SPARK_ENV) bash etl/spark/fixture/fetch_jars.sh
	mkdir -p $(SFX_SPARK_DATA)/{landing,lake,eventlogs,logs} "$(abspath $(SFX_SPARK_LANDING))"
	chmod 777 $(SFX_SPARK_DATA)/lake $(SFX_SPARK_DATA)/eventlogs $(SFX_SPARK_CACHE)
	$(SFX_SPARK_ENV) python3 $(if $(wildcard warehouse/seed/generate.py),warehouse/seed/generate.py,etl/spark/fixture/generate_fixture.py) --rows $(ROWS_PER_TABLE) --seed 1110 $(if $(wildcard warehouse/seed/generate.py),--out,--output) "$(abspath $(SFX_SPARK_LANDING))"
	$(SFX_SPARK_ENV) $(SFX_SPARK_COMPOSE) up -d --wait --wait-timeout 120 --pull never
	$(SFX_SPARK_ENV) bash etl/spark/fixture/load_tdemu.sh
	$(SFX_SPARK_ENV) bash etl/spark/scala/build.sh
	@if [ -d etl/spark/history/eventlogs ]; then cp -a etl/spark/history/eventlogs/. $(SFX_SPARK_DATA)/eventlogs/; chmod 777 $(SFX_SPARK_DATA)/eventlogs; fi

sfx-spark-down: ## Stop the local Spark estate and remove its volumes
	$(SFX_SPARK_ENV) $(SFX_SPARK_COMPOSE) down -v

sfx-spark-run: ## Run the first SPARK_JOBS batch jobs, or JOB=<id>
	$(SFX_SPARK_ENV) python3 etl/spark/jobs/py/common/package.py
	$(SFX_SPARK_ENV) bash etl/spark/scala/build.sh
	$(SFX_SPARK_ENV) SPARK_JOBS=$(SPARK_JOBS) JOB=$(JOB) bash etl/spark/run.sh

sfx-spark-test: ## Run fixture, inventory, history and local Spark checks
	$(SFX_SPARK_UV) python -m unittest discover -s etl/spark/tests -v
	python3 etl/spark/history/compute_baseline.py --check

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

PROCS_COMPOSE = docker compose -f docker-compose.procs.yml -p otterworks-procs-$(NS)
PROCS_UV = uv run --with psycopg[binary]==3.2.9 --with pyyaml==6.0.2
PROCS_PORT_OFFSET = $(shell if command -v python3 >/dev/null 2>&1 && test -n "$(NS)"; then python3 -c "import zlib; print(zlib.crc32('$(NS)'.encode()) % 1000)"; fi)
PROCS_DB_PORT = $(shell test -n "$(PROCS_PORT_OFFSET)" && python3 -c "print(55432 + $(PROCS_PORT_OFFSET))")
PROCS_APP_PORT = $(shell test -n "$(PROCS_PORT_OFFSET)" && python3 -c "print(8096 + $(PROCS_PORT_OFFSET))")
PROCS_TARGET_DB_PORT = $(shell test -n "$(PROCS_PORT_OFFSET)" && python3 -c "print(56432 + $(PROCS_PORT_OFFSET))")
PROCS_TARGET_PORT = $(shell test -n "$(PROCS_PORT_OFFSET)" && python3 -c "print(12096 + $(PROCS_PORT_OFFSET))")
PROCS_ENV = NS=$(NS) PROCS_DB_PORT=$(PROCS_DB_PORT) PROCS_APP_PORT=$(PROCS_APP_PORT) PROCS_TARGET_DB_PORT=$(PROCS_TARGET_DB_PORT) PROCS_TARGET_PORT=$(PROCS_TARGET_PORT)

procs-validate:
	@test -n "$(NS)" || (echo "NS is required, e.g. make procs-up NS=dev" >&2; exit 2)
	@command -v python3 >/dev/null 2>&1 || (echo "python3 is required for namespace port derivation" >&2; exit 2)
	@test -n "$(PROCS_PORT_OFFSET)" || (echo "could not derive namespace port offset" >&2; exit 2)

procs-up: procs-validate ## Start the legacy billing stored-procedure stack (NS=<namespace>)
	$(PROCS_ENV) $(PROCS_COMPOSE) up -d --build --wait

procs-down: procs-validate ## Stop the legacy billing stored-procedure stack (NS=<namespace>)
	$(PROCS_ENV) $(PROCS_COMPOSE) down -v

procs-record: procs-validate ## Record legacy billing transcripts (NS=<namespace>, MODULE and OUTPUT_DIR optional)
	$(PROCS_ENV) DB_NAME=billing_$(NS) DB_PORT=$(PROCS_DB_PORT) $(PROCS_UV) procs/harness/record.py $(if $(MODULE),--module $(MODULE),) $(if $(OUTPUT_DIR),--output-dir $(OUTPUT_DIR),) $(if $(ALLOW_RERECORD),--allow-rerecord,) $(if $(RERECORD_REASON),--rerecord-reason $(RERECORD_REASON),)

procs-list: ## List stored-procedure modules and scenarios
	$(PROCS_UV) procs/harness/list.py $(if $(MODULE),--module $(MODULE),)

procs-parity: procs-validate ## Replay extracted billing scenarios (NS=<namespace>, MODULE and SCENARIO optional)
	$(PROCS_ENV) BILLING_SVC_URL=$${BILLING_SVC_URL:-http://localhost:$(PROCS_TARGET_PORT)} $(PROCS_UV) procs/harness/replay.py $(if $(MODULE),--module $(MODULE),) $(if $(SCENARIO),--scenario $(SCENARIO),)

procs-rules-gate: ## Validate the approved HITL rule ledger (MODULE=<module> or ALL=1)
	@test -n "$(MODULE)$(ALL)" || (echo "MODULE or ALL=1 is required" >&2; exit 2)
	uv run --with pyyaml==6.0.2 procs/harness/rules_gate.py $(if $(ALL),--all,--module $(MODULE))

# --- Industry Solutions: insurance Commission Pay (Oracle) ---

INSURANCE_COMPOSE = docker compose -f docker-compose.insurance.yml -p otterworks-insurance-$(NS)
INSURANCE_DB_PORT = $(shell test -n "$(PROCS_PORT_OFFSET)" && python3 -c "print(51521 + $(PROCS_PORT_OFFSET))")
INSURANCE_ENV = NS=$(NS) INSURANCE_DB_PORT=$(INSURANCE_DB_PORT)
INSURANCE_SQLPLUS = docker exec -i otterworks-insurance-$(NS)-insurance-oracle-1 sqlplus -s

insurance-up: procs-validate ## Start the Oracle insurance Commission Pay fixture (NS=<namespace>)
	$(INSURANCE_ENV) $(INSURANCE_COMPOSE) up -d --wait --wait-timeout 900

insurance-down: procs-validate ## Stop the Oracle insurance fixture and drop its data (NS=<namespace>)
	$(INSURANCE_ENV) $(INSURANCE_COMPOSE) down -v

insurance-test: procs-validate ## Run the Commission Pay OLTP + OLAP test suites (NS=<namespace>)
	$(INSURANCE_SQLPLUS) commission_pay/commission_pay@localhost:1521/FREEPDB1 @/opt/oracle/scripts/insurance/tests/run_tests.sql
	$(INSURANCE_SQLPLUS) commission_dw/commission_dw@localhost:1521/FREEPDB1 @/opt/oracle/scripts/insurance/tests/run_olap_tests.sql

# --- Local Development ---

infra-up: ## Start local infrastructure (Postgres, Redis, LocalStack, MeiliSearch)
	docker compose -f docker-compose.infra.yml up -d

infra-down: ## Stop local infrastructure
	docker compose -f docker-compose.infra.yml down

up: ## Start all services (add seed=1 to seed after start)
	docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --build
 ifdef seed
	@$(MAKE) --no-print-directory wait-for-db seed
 endif

down: ## Stop all application services
	docker compose -f docker-compose.infra.yml -f docker-compose.yml down

build: ## Build all service images
	docker compose -f docker-compose.infra.yml -f docker-compose.yml build

seed: ## Seed development data (services must be running)
	uv run scripts/seed.py

wait-for-db: ## Wait for Postgres to accept connections
	@echo "Waiting for Postgres to be healthy..."
	@for i in $$(seq 1 30); do \
		docker exec otterworks-postgres pg_isready -q 2>/dev/null && exit 0; \
		sleep 1; \
	done; echo "Timed out waiting for Postgres" && exit 1

logs: ## Tail logs for all services
	docker compose -f docker-compose.infra.yml -f docker-compose.yml logs -f

# --- App Dev Targets ---
# One-command startup for each frontend app, running from source against the
# Dockerized backend. The compose web-app/admin-dashboard containers are stopped
# where they would clash with the dev servers on ports 3000/4200.

COMPOSE := docker compose -f docker-compose.infra.yml -f docker-compose.yml
# Collab websocket as exposed by docker-compose (host port 8084); source builds
# otherwise default to :8085, which only matches the k8s dev environment.
COLLAB_WS_URL := ws://localhost:8084

dev-backend: ## Start the Dockerized backend (all services except the frontend containers)
	$(COMPOSE) up -d $$($(COMPOSE) config --services | grep -vE '^(web-app|admin-dashboard)$$')
	@echo "Backend up - API gateway on http://localhost:8080 (fresh DB? run: make seed)"

dev-web: dev-backend ## Start the client-app web dev server (HMR) on :3000
	@$(COMPOSE) stop web-app 2>/dev/null || true
	cd frontend/client-app && { [ -d node_modules ] || npm ci; } && \
		VITE_COLLAB_WS_URL=$(COLLAB_WS_URL) npm run dev

dev-admin: dev-backend ## Start the admin dashboard dev server (HMR) on :4200
	@$(COMPOSE) stop admin-dashboard 2>/dev/null || true
	cd frontend/admin-dashboard && { [ -d node_modules ] || npm ci; } && npm start

workbench-up: ## Build and start the Workbench container on :3002
	$(COMPOSE) up -d --build --no-deps workbench
	@echo "Workbench running at http://localhost:3002/"

workbench-down: ## Stop and remove the Workbench container
	$(COMPOSE) stop workbench && $(COMPOSE) rm -f workbench

dev-android: dev-backend ## Build the web bundle and run the Android app on an emulator/device
	cd frontend/client-app && { [ -d node_modules ] || npm ci; } && \
		VITE_COLLAB_WS_URL=ws://10.0.2.2:8084 npm run build && \
		npx cap sync android && npx cap run android

dev-electron: dev-backend ## Build the web bundle and launch the Electron desktop app
	cd frontend/client-app && { [ -d node_modules ] || npm ci; } && \
		VITE_COLLAB_WS_URL=$(COLLAB_WS_URL) npm run build
	cd frontend/client-app/desktop && { [ -d node_modules ] || npm ci; } && npm start

# --- Per-Service Builds ---

build-gateway: ## Build API Gateway
	cd services/api-gateway && go build -o bin/server ./cmd/server

build-auth: ## Build Auth Service
	cd services/auth-service && ./gradlew bootJar

build-file: ## Build File Service
	cd services/file-service && cargo build --release

build-document: ## Build Document Service
	cd services/document-service && pip install -e .

build-collab: ## Build Collaboration Service
	cd services/collab-service && npm run build

build-notification: ## Build Notification Service
	cd services/notification-service && ./gradlew build

build-search: ## Build Search Service
	cd services/search-service && pip install -e .

build-analytics: ## Build Analytics Service
	cd services/analytics-service && sbt compile

build-admin: ## Build Admin Service
	cd services/admin-service && bundle install

build-audit: ## Build Audit Service
	cd services/audit-service && dotnet build

build-web: ## Build Web Frontend
	cd frontend/web-app && npm run build

build-admin-dash: ## Build Admin Dashboard
	cd frontend/admin-dashboard && npm run build

# --- Testing ---

test: ## Run tests for all services
	@echo "=== API Gateway (Go) ===" && cd services/api-gateway && go test ./...
	@echo "=== Auth Service (Java) ===" && cd services/auth-service && ./gradlew test
	@echo "=== File Service (Rust) ===" && cd services/file-service && cargo test
	@echo "=== Document Service (Python) ===" && cd services/document-service && pytest
	@echo "=== Collab Service (Node.js) ===" && cd services/collab-service && npm test
	@echo "=== Notification Service (Kotlin) ===" && cd services/notification-service && ./gradlew test
	@echo "=== Search Service (Python) ===" && cd services/search-service && pytest
	@echo "=== Analytics Service (Scala) ===" && cd services/analytics-service && sbt test
	@echo "=== Admin Service (Ruby) ===" && cd services/admin-service && bundle exec rspec
	@echo "=== Audit Service (C#) ===" && cd services/audit-service && dotnet test
	@echo "=== Web Frontend ===" && cd frontend/web-app && npm test
	@echo "=== Admin Dashboard ===" && cd frontend/admin-dashboard && npm test

test-coverage: ## Run tests with coverage for all services
	@echo "=== Document Service ===" && cd services/document-service && pytest --cov=app --cov-report=term-missing || true
	@echo "=== Search Service ===" && cd services/search-service && pytest --cov=app --cov-report=term-missing || true
	@echo "=== Collab Service ===" && cd services/collab-service && npm test -- --coverage || true
	@echo "=== API Gateway ===" && cd services/api-gateway && go test -cover ./... || true
	@echo "=== Admin Service ===" && cd services/admin-service && bundle exec rspec --format documentation || true
	@echo "=== Auth Service ===" && cd services/auth-service && ./gradlew test jacocoTestReport || true
	@echo "=== File Service ===" && cd services/file-service && cargo test 2>&1 | tail -5 || true

test-api-flows: ## Run black-box API flow tests against the local API gateway
	UV_PROJECT_ENVIRONMENT=.venv uv run python -m pytest tests/api

test-api-flows-collect: ## Collect black-box API flow tests without running them
	UV_PROJECT_ENVIRONMENT=.venv uv run python -m pytest tests/api --collect-only -q

lint: ## Lint all services
	@echo "=== API Gateway ===" && cd services/api-gateway && golangci-lint run
	@echo "=== Auth Service ===" && cd services/auth-service && ./gradlew spotlessCheck
	@echo "=== File Service ===" && cd services/file-service && cargo clippy -- -D warnings
	@echo "=== Document Service ===" && cd services/document-service && ruff check .
	@echo "=== Collab Service ===" && cd services/collab-service && npm run lint
	@echo "=== Search Service ===" && cd services/search-service && ruff check .
	@echo "=== Web Frontend ===" && cd frontend/web-app && npm run lint
	@echo "=== Admin Dashboard ===" && cd frontend/admin-dashboard && npm run lint

# --- Synthetic Test Data ---

# Guard: NS must be alphanumeric/underscore only (prevents SQL injection)
define validate_ns
$(if $(filter ok,$(shell echo '$(NS)' | grep -qE '^[A-Za-z0-9_]+$$' && echo ok)),,$(error NS must contain only letters, digits, and underscores))
endef

testdata-validate: ## Validate generated test data (NS=<namespace>, CRITERIA=<file>)
ifndef NS
	$(error NS is required, e.g. make testdata-validate NS=dev)
endif
	$(call validate_ns)
	uv run testdata/harness/validate.py --ns $(NS) $(if $(CRITERIA),--criteria $(CRITERIA),)

testdata-clean: ## Drop a test-data namespace schema (NS=<namespace>)
ifndef NS
	$(error NS is required, e.g. make testdata-clean NS=dev)
endif
	$(call validate_ns)
	@echo "Dropping schema otterworks_$(NS)..."
	PGPASSWORD=$${DB_PASSWORD:-otterworks_dev} psql \
		-h $${DB_HOST:-localhost} -p $${DB_PORT:-5432} \
		-U $${DB_USER:-otterworks} -d $${DB_NAME:-otterworks} \
		-c "DROP SCHEMA IF EXISTS otterworks_$(NS) CASCADE;"
	@echo "Done."

testdata-setup-schema: ## Create a namespaced schema (NS=<namespace>)
ifndef NS
	$(error NS is required, e.g. make testdata-setup-schema NS=dev)
endif
	$(call validate_ns)
	@echo "Creating schema otterworks_$(NS)..."
	PGPASSWORD=$${DB_PASSWORD:-otterworks_dev} psql \
		-h $${DB_HOST:-localhost} -p $${DB_PORT:-5432} \
		-U $${DB_USER:-otterworks} -d $${DB_NAME:-otterworks} \
		-f testdata/harness/create_schema.sql \
		-v ns=$(NS)
	@echo "Done."

# --- Infrastructure ---

tf-init: ## Initialize Terraform
	cd infrastructure/terraform && terraform init

tf-plan: ## Plan Terraform changes
	cd infrastructure/terraform && terraform plan -var-file=environments/dev.tfvars

tf-apply: ## Apply Terraform changes
	cd infrastructure/terraform && terraform apply -var-file=environments/dev.tfvars -auto-approve

tf-destroy: ## Destroy Terraform resources
	cd infrastructure/terraform && terraform destroy -var-file=environments/dev.tfvars -auto-approve

deploy-dev: ## Deploy all services to dev EKS
	./scripts/deploy-dev.sh

teardown-dev: ## Tear down dev environment
	./scripts/teardown-dev.sh

# --- Security ---

security-scan: ## Run security scans across all services
	@echo "=== Trivy Filesystem Scan ==="
	trivy fs --config security/scanning/trivy-config.yaml . || true
	@echo ""
	@echo "=== Node.js Audit (collab-service) ==="
	cd services/collab-service && npm audit 2>/dev/null || true
	@echo ""
	@echo "=== Python Audit (search-service) ==="
	cd services/search-service && pip-audit -r requirements.txt 2>/dev/null || true
	@echo ""
	@echo "=== Ruby Audit (admin-service) ==="
	cd services/admin-service && bundle-audit check 2>/dev/null || true
	@echo ""
	@echo "=== Report Service (skipped - legacy) ==="

# --- Dynamic Application Security Testing (DAST) ---
#
# DAST attacks the *running* application through the API gateway. TARGET can be
# the local stack (default), a tenant URL, or a preview environment.

DAST_TARGET ?= http://localhost:8080
# Each script declares its own dependencies (PEP 723), so `uv run` needs no --with.
# Note that make reports 2 for any failed recipe: to act on the harness's own exit
# codes (1 findings, 2 nothing tested, 3 no verdict), call security/dast/run.sh.
DAST := uv run security/dast/harness/dast_scan.py
DAST_COVERAGE := uv run security/dast/harness/dast_coverage.py

dast-list: ## List the registered DAST attack probes
	$(DAST) --list

dast-scan: ## Run the DAST suite against a running app (DAST_TARGET=<url>), gated by the baseline
	$(DAST) --target $(DAST_TARGET) $(if $(FAIL_ON),--fail-on $(FAIL_ON),)

dast-verify: ## Prove one finding is remediated (FINDING=<id> DAST_TARGET=<url>); baseline is ignored
ifndef FINDING
	$(error FINDING is required, e.g. make dast-verify FINDING=DAST-MISSING-SECURITY-HEADERS)
endif
	$(DAST) --target $(DAST_TARGET) --only $(FINDING) --no-baseline --fail-on info

dast-routes: ## List the edge-reachable routes read from the services' source
	uv run security/dast/harness/route_inventory.py

dast-coverage: ## Fail if a route the gateway proxies was never attacked by the last scan
	$(DAST_COVERAGE)

dast-test: ## Unit-test the harness itself (route extraction, coverage gate, perimeter verdicts)
	uv run --python '>=3.11' --with pytest --with httpx --with pyyaml --with tabulate \
		python -m pytest security/dast/harness/tests -q

dast-baseline: ## Record current findings as accepted (REASON="...")
	$(DAST) --target $(DAST_TARGET) --reason "$${REASON:-recorded by make dast-baseline}" --update-baseline

dast-zap: ## Run the OWASP ZAP baseline sweep and merge it into the DAST report
	@mkdir -p security/dast/reports
# ZAP writes its report *and* its generated automation plan into its working
# directory, and the image runs as uid 1000 while a CI runner is 1001 (running the
# container as the host uid instead is not an option: ZAP needs /home/zap, which
# only exists for uid 1000). Rather than open up a host directory, the working
# directory is a throwaway docker volume chowned to the image's uid from inside a
# container, so nothing on the host is ever writable by another local user. The
# rule file goes in read-only, and the report is read back out through the volume.
# The stale report is removed first, so "a report exists" can only mean this run
# produced one.
	@rm -f security/dast/reports/zap-report.json
	@set -e; \
	vol="dast-zap-$$$$"; \
	trap 'docker volume rm -f "$$vol" >/dev/null 2>&1' EXIT INT TERM; \
	docker volume create "$$vol" >/dev/null; \
	docker run --rm --user 0 -v "$$vol:/zap/wrk" \
		ghcr.io/zaproxy/zaproxy:stable chown 1000:1000 /zap/wrk; \
	docker run --rm --network host \
		-v "$$vol:/zap/wrk" \
		-v "$(CURDIR)/security/dast/zap/zap-baseline.conf:/zap/wrk/zap-baseline.conf:ro" \
		ghcr.io/zaproxy/zaproxy:stable zap-baseline.py \
		-t $(DAST_TARGET) -c zap-baseline.conf -J zap-report.json -I || true; \
	docker run --rm --user 0 -v "$$vol:/zap/wrk" ghcr.io/zaproxy/zaproxy:stable \
		sh -c 'cat /zap/wrk/zap-report.json 2>/dev/null' \
		> security/dast/reports/zap-report.json || true; \
	[ -s security/dast/reports/zap-report.json ] || rm -f security/dast/reports/zap-report.json
# A ZAP failure must not cost the probe suite: the sweep still reports, without it.
	@if [ -f security/dast/reports/zap-report.json ]; then \
		$(DAST) --target $(DAST_TARGET) --zap-report security/dast/reports/zap-report.json; \
	else \
		echo "::warning::ZAP produced no report (see the log above); the passive sweep is"\
		     "missing from this run. Running the probe suite on its own."; \
		$(DAST) --target $(DAST_TARGET); \
	fi

# --- Dependency CVE remediation ---
#
# The advisory (security/deps/advisory.yaml) names the artifact and its vulnerable
# range; modules.yaml registers every JVM module so the blast radius cannot be
# partial. Reports land in security/deps/reports/ (git-ignored: collect them as CI
# artifacts and paste the summary into the PR).

DEPS := uv run --with pyyaml==6.0.2 --with tabulate==0.10.0 security/deps/harness/deps_check.py

deps-inventory: ## Report the blast radius of the advisory across every JVM module
	$(DEPS) inventory

deps-gate: ## Fail if the vulnerable version is still reachable from any dependency tree
	$(DEPS) gate

deps-command: ## Print the harness invocation, for callers that need its exact exit code
	@echo '$(DEPS)'

deps-tests: ## Build and run every affected module's own suite (MODULE=<id> optional)
	$(DEPS) tests $(if $(MODULE),--module $(MODULE),)

deps-transcript: ## Grade interpolation behavior after remediation (MODULE=<id> optional)
	$(DEPS) transcript --stage remediated $(if $(MODULE),--module $(MODULE),)

deps-transcript-baseline: ## Prove the recorded before-state still reproduces (MODULE=<id> optional)
	$(DEPS) transcript --stage baseline $(if $(MODULE),--module $(MODULE),)

deps-record: ## Record the transcripts as the reference evidence (REASON="..." required)
	@test -n "$(REASON)" || (echo 'REASON is required, e.g. make deps-record REASON="baseline on commons-text 1.9"' >&2; exit 2)
	$(DEPS) transcript --record --reason "$(REASON)" $(if $(MODULE),--module $(MODULE),) $(if $(ALLOW_RERECORD),--allow-rerecord,)

test-report: ## Run report-service tests only
	cd services/report-service && mvn test

build-report: ## Build report-service
	cd services/report-service && mvn package -DskipTests

# --- Batch jobs (legacy scheduled processing) ---

batch-usage-rollup: ## Run the nightly usage-rollup batch job locally (OUT=<path> optional)
	ROLLUP_OUTPUT=$${OUT:-rollup-output.json} scripts/run-usage-rollup.sh

batch-usage-rollup-seed: ## Regenerate the deterministic usage-rollup seed events
	cd services/analytics-service && python3 scripts/generate_seed_events.py

# --- Functional-equivalence gate for source-level security refactors ---
#
# security/equivalence/findings.yaml registers each finding (subject class,
# methods, secure pattern) and each module's emit/test commands. The recorded
# before-state lives in security/equivalence/expected/ and is fingerprinted
# against the cases, the seed, the emitter and the subject sources. Reports land
# in security/equivalence/reports/ (git-ignored: collect them as CI artifacts and
# paste the summary into the PR).

EQ := uv run --with pyyaml==6.0.2 --with tabulate==0.10.0 --with defusedxml==0.7.1 security/equivalence/harness/equivalence_check.py

eq-list: ## List the registered findings and the state of their recorded evidence
	$(EQ) list

eq-gate: ## Grade every finding against its recorded evidence, before-state or refactored
	$(EQ) grade --stage auto $(if $(FINDING),--finding $(FINDING),)

eq-baseline: ## Prove the recorded before-state still reproduces (FINDING=<id> optional)
	$(EQ) grade --stage baseline $(if $(FINDING),--finding $(FINDING),)

eq-verify: ## Grade a refactor: contract cases unchanged, attacks neutralised (FINDING=<id> optional)
	$(EQ) grade --stage remediated $(if $(FINDING),--finding $(FINDING),)

eq-exploit: ## Report whether the attack cases still fire, ignoring the recording
	$(EQ) exploit $(if $(FINDING),--finding $(FINDING),)

eq-exploit-refactored: ## Require a closed exploit verdict from every finding whose subject changed
	$(EQ) exploit --refactored-only $(if $(FINDING),--finding $(FINDING),)

eq-tests: ## Run the affected module's own suite against the recorded pass list
	$(EQ) tests $(if $(FINDING),--finding $(FINDING),)

eq-record: ## Record the before-state as the reference evidence (REASON="..." required)
	@test -n "$(REASON)" || (echo 'REASON is required, e.g. make eq-record REASON="baseline before OW-SEC-401 refactor"' >&2; exit 2)
	$(EQ) record --reason "$(REASON)" $(if $(FINDING),--finding $(FINDING),) $(if $(ALLOW_RERECORD),--allow-rerecord,)

# ---------------------------------------------------------------------------
# Legacy data migration demo (Db2 on EKS -> Azure SQL), ops unit.
# Token NS=<run>-<before|after> (e.g. d24-before); see migration/CONTRACTS.md §12
# and docs/demos/legacy-data-migration.md. DRY_RUN=1 prints commands only.
# ---------------------------------------------------------------------------
DEMO_NS_RE = ^[a-z][a-z0-9]{1,11}-(before|after)$$
define demo_require_ns
	@test -n "$(NS)" || (echo 'NS is required, e.g. make $(1) NS=d24-after' >&2; exit 2)
	@echo "$(NS)" | grep -Eq '$(DEMO_NS_RE)' || (echo "NS='$(NS)' must match $(DEMO_NS_RE) and never main" >&2; exit 2)
endef

demo-up: ## Deploy one demo namespace: tenant + Db2 seed (+ Azure when overlay azure: true). NS=<token> [TTL=72h IMAGE_TAG=..]
	$(call demo_require_ns,demo-up)
	./scripts/deploy-demo.sh up $(NS) $(if $(TTL),--ttl $(TTL),) $(if $(IMAGE_TAG),--image-tag $(IMAGE_TAG),) $(if $(HOST_SUFFIX),--host-suffix $(HOST_SUFFIX),) $(if $(filter 1,$(DRY_RUN)),--dry-run,)

demo-migrate: ## Run the staged migration Jobs for NS=<token> RUN_ID=<id>; streams logs, copies report to .demo/<token>/<run_id>/
	$(call demo_require_ns,demo-migrate)
	@test -n "$(RUN_ID)" || (echo 'RUN_ID is required, e.g. make demo-migrate NS=d24-after RUN_ID=$(shell date -u +r%Y%m%d%H%M%S)' >&2; exit 2)
	@bash -c 'set -euo pipefail; source scripts/lib/demo-common.sh; start_transcript "$(NS)" "migrate-$(RUN_ID)"; demo_migrate "$(NS)" "$(RUN_ID)"'

demo-destroy: ## Destroy everything for NS=<token> (Azure + Helm + tenant + S3 + demo-aws) and verify nothing tagged remains
	$(call demo_require_ns,demo-destroy)
	./scripts/demo-destroy.sh $(NS) $(if $(filter 1,$(DRY_RUN)),--dry-run,)

demo-verify-clean: ## Exit 0 iff no AWS/Azure resource tagged namespace=NS and no otterworks-NS namespace remain
	$(call demo_require_ns,demo-verify-clean)
	./scripts/demo-destroy.sh verify $(NS)

demo-reaper: ## Report (default) or destroy (APPLY=1) expired demo namespaces across AWS, Azure and the cluster
	./scripts/demo-reaper.sh $(if $(filter 1,$(APPLY)),--apply,--dry-run)

# --- Incident responder (see incident/README.md and .agents/skills/incident-responder) ---
INCIDENT = uv run incident/incident.py
INCIDENT_COMPOSE = docker compose -f docker-compose.yml -f docker-compose.infra.yml -f docker-compose.incident.yml

INCIDENT_SERVICES = postgres redis localstack otel-collector jaeger prometheus grafana alertmanager alert-sink document-service
# UI=1 also builds the gateway + web front end so the slowness can be shown in the browser.
ifdef UI
INCIDENT_SERVICES += auth-service api-gateway web-app
endif

incident-up: ## Start document-service + observability + Alertmanager for the incident demo (UI=1 adds gateway/web-app)
	$(INCIDENT_COMPOSE) up -d --build $(INCIDENT_SERVICES)

incident-down: ## Stop the incident demo stack (keeps volumes)
	$(INCIDENT_COMPOSE) --profile double-run down

incident-arm: ## Plant one scenario and start deterministic load (SCENARIO=n-plus-one|log-flood|cache-leak|double-run)
ifndef SCENARIO
	$(error SCENARIO is required, e.g. make incident-arm SCENARIO=n-plus-one)
endif
	$(INCIDENT) arm $(SCENARIO)

incident-disarm: ## Reverse whatever is armed: stop load, clear flags, restore replicas/logs
	$(INCIDENT) disarm

arm: incident-arm ## Alias: make arm SCENARIO=<name>
disarm: incident-disarm ## Alias: make disarm

incident-status: ## Firing alerts and the current numbers behind them
	$(INCIDENT) status

incident-verify: ## Fail-closed gate (SCENARIO=<name> EXPECT=before|after)
ifndef SCENARIO
	$(error SCENARIO is required, e.g. make incident-verify SCENARIO=n-plus-one EXPECT=before)
endif
	$(INCIDENT) verify $(SCENARIO) --expect $(or $(EXPECT),before) $(if $(SOAK),--soak $(SOAK),)

incident-load: ## Run a scenario's load profile in the foreground (SCENARIO=<name> [DURATION=s])
ifndef SCENARIO
	$(error SCENARIO is required, e.g. make incident-load SCENARIO=n-plus-one DURATION=120)
endif
	$(INCIDENT) load $(SCENARIO) $(if $(DURATION),--duration $(DURATION),)

incident-seed: ## Create the deterministic fixture dataset (idempotent)
	$(INCIDENT) seed

incident-reset-fixture: ## Delete the fixture owner's documents so the next seed starts clean
	$(INCIDENT) reset-fixture

incident-simulate: ## Print the exact alert payload the Devin Automation webhook received (RECEIVER=devin|slack)
	$(INCIDENT) simulate-alert --receiver $(or $(RECEIVER),devin)

incident-chart-sync: ## Copy incident alert rules + dashboard into the document-service chart
	scripts/sync-incident-chart-files.sh

incident-chart-check: ## Fail if the chart's incident rules/dashboard differ from observability/
	scripts/sync-incident-chart-files.sh --check

incident-fingerprint: ## Compare fixture/source fingerprints with incident/expected.yaml (exit 2 on drift)
	$(INCIDENT) fingerprint

incident-record: ## Re-pin incident/expected.yaml (REASON="..." required, audited)
	@test -n "$(REASON)" || (echo 'REASON is required, e.g. make incident-record REASON="baseline before n-plus-one fix"' >&2; exit 2)
	$(INCIDENT) record --reason "$(REASON)"

# --- AWS cloud worker (see cloudworker/README.md) ---
CW = $(if $(PAGE),CW_PAGE=$(PAGE) ,)cloudworker/cw.sh
CW_FAULT_ARG = $(if $(FAULT),--fault $(FAULT),)
.PHONY: cw-up cw-apply cw-credentials cw-arm cw-status cw-verify cw-simulate cw-quiet cw-disarm cw-reset cw-teardown cw-trail

cw-up: ## Provision the cloud-worker infra, map the Devin roles, wire the tenant, smoke test
	$(CW) up

cw-apply: ## Re-render the cloud-worker tenant eventing config from eventing.env
	$(CW) apply

cw-credentials: ## Rotate the devin-cw-reader access key into cloudworker/.state/
	$(CW) credentials

cw-arm: ## Plant a fault and publish six file_shared events (FAULT=table|parser, default table; PAGE=0 keeps the EventBridge rule as is)
	$(CW) arm $(CW_FAULT_ARG)

cw-status: ## Tenant pods, live vs git table, image, queue depths, alarm, rule, helm history (JSON=1 for JSON)
	$(CW) status $(if $(JSON),--json,)

cw-verify: ## Fail-closed gate for the cloud-worker demo (EXPECT=before|after, FAULT=table|parser for before)
ifndef EXPECT
	$(error EXPECT is required, e.g. make cw-verify EXPECT=before)
endif
	$(CW) verify $(EXPECT) $(CW_FAULT_ARG)

cw-simulate: ## Publish file_shared events to the cloud-worker topic (COUNT=n, default 1)
	$(CW) simulate --count $(or $(COUNT),1)

cw-quiet: ## Disable the DLQ alarm actions for a while (MINUTES=n, default 10)
	$(CW) quiet $(or $(MINUTES),10)

cw-disarm: ## Restore the config and image, purge both queues, reset the alarm (PAGE=0 keeps the rule as is)
	$(CW) disarm

cw-reset: ## Disarm, close demo-cw-* PRs and branches, drop cw-* tenants, re-plant the drift (SCOPE=run, PAGE=0)
	$(CW) reset $(if $(SCOPE),--scope $(SCOPE),)

cw-teardown: ## Reset, unmap the roles, delete RBAC and keys, destroy the cloud-worker infra
	$(CW) teardown

cw-trail: ## CloudTrail events from devin-cw-* identities in the last two hours
	$(CW) trail

# legacy-portal-serverless: Terraform root infrastructure/terraform/legacy-portal-serverless, one state per run token.
# Transcripts go to .demo/legacy-portal/<token>/. See docs/aws-legacy-portal/README.md.
LP = RUN=$(RUN) CTX=$(CTX) STAGE=$(STAGE) scripts/lp-serverless.sh

lp-up: ## Apply the legacy-portal serverless stack for a run (RUN=lp-<yyyymmdd>-<xx>)
	@$(LP) up

lp-replay: ## Replay the recorded Java corpus against the run's HTTP API (RUN=, CTX=<context|all>, STAGE=first|full)
	@$(LP) replay

lp-status: ## List legacy-portal serverless runs by tag, or one run's outputs and functions (RUN optional)
	@$(LP) status

lp-reset: ## Truncate the run's context tables back to the seeded (empty) state (RUN=, CTX=<context|all>)
	@$(LP) reset

lp-down: ## Destroy the run's legacy-portal serverless stack (RUN=)
	@$(LP) down

lp-verify-clean: ## Prove nothing tagged or named with the run token remains (RUN=)
	@$(LP) verify-clean

lp-deploy: ## Build the Java handlers and move each live alias through CodeDeploy, then start the probe (RUN=, CTX=<context|all>)
	@$(LP) deploy

lp-break: ## Deploy a FAIL_READS=1 version of one function through the canary and tail the alarm to ALARM (RUN=, CTX=)
	@$(LP) break

lp-heal: ## Roll back the in-flight deployment or deploy the good version, then wait for the alarm to clear (RUN=, CTX=)
	@$(LP) heal

lp-page-status: ## Alarm history, deployment history and the page rule's last API destination invocation (RUN=)
	@$(LP) page-status

# legacy-portal-ec2: Terraform root infrastructure/terraform/legacy-portal-ec2, the EC2 "before" state.
# One state per run token; transcripts go to .demo/legacy-portal/<token>/. See docs/aws-legacy-portal/README.md.
LP_EC2 = RUN=$(RUN) CTX=$(CTX) STAGE=$(STAGE) scripts/lp-ec2.sh

lp-ec2-up: ## Build the jar, apply the legacy-portal EC2 stack and wait for a healthy target (RUN=lp-ec2-<yyyymmdd>-<xx>)
	@$(LP_EC2) up

lp-ec2-status: ## List legacy-portal EC2 runs by tag, or one run's outputs, instance and health (RUN optional)
	@$(LP_EC2) status

lp-ec2-replay: ## Replay the recorded Java corpus against the run's ALB (RUN=, CTX=<context|all>, STAGE=first|full)
	@$(LP_EC2) replay

lp-ec2-down: ## Destroy the run's legacy-portal EC2 stack (RUN=)
	@$(LP_EC2) down

lp-ec2-verify-clean: ## Prove nothing tagged or named with the run token remains (RUN=)
	@$(LP_EC2) verify-clean

# --- sfx-informatica: emulated PowerCenter estate (etl/informatica, run token sfx-d1110) ---
# INFA_DB=fixture (default) starts a throwaway warehouse database loaded with the local fixture schema;
# INFA_DB=teradata points the runner at the Teradata emulation's compose service instead.
INFA_DIR = etl/informatica
INFA_NS = $(or $(NS),sfx-d1110-before)
INFA_DB ?= fixture
MAPPINGS ?= 20
INFA_PORT_OFFSET = $(shell python3 -c "import zlib; print(zlib.crc32('$(INFA_NS)'.encode()) % 1000)")
INFA_TD_PORT = $(shell python3 -c "print($(if $(filter teradata,$(INFA_DB)),54500,55500) + $(INFA_PORT_OFFSET))")
INFA_LANDING = $(or $(LANDING_DIR),$(if $(wildcard warehouse/landing/billing),$(CURDIR)/warehouse/landing,$(CURDIR)/$(INFA_DIR)/tests/fixture/landing))
INFA_PY = $(CURDIR)/$(INFA_DIR)/.venv/bin/python
INFA_ENV = NS=$(INFA_NS) MAPPINGS='$(MAPPINGS)' TD_PORT=$(or $(TD_PORT),$(INFA_TD_PORT)) LANDING_DIR=$(INFA_LANDING) PMROOTDIR=$(CURDIR)/$(INFA_DIR)/infa_shared/$(INFA_NS)
INFA_COMPOSE = NS=$(INFA_NS) TD_PORT=$(INFA_TD_PORT) docker compose -f $(INFA_DIR)/docker-compose.informatica.yml
INFA_WORKFLOWS ?= SFX_CONTENT:wf_SFX_CONTENT_DAILY SFX_BILLING:wf_SFX_BILLING_DAILY SFX_AUDIT:wf_SFX_AUDIT_DAILY

sfx-informatica-up: ## Create the runner venv and start the warehouse database for NS (INFA_DB=fixture|teradata)
	@test -x $(INFA_PY) || (python3 -m venv $(INFA_DIR)/.venv && $(INFA_DIR)/.venv/bin/pip install -q -r $(INFA_DIR)/requirements.txt)
	@if [ "$(INFA_DB)" = teradata ]; then $(MAKE) sfx-teradata-up NS=$(INFA_NS); else \
	  docker image inspect postgres:16 >/dev/null 2>&1 || (docker pull mirror.gcr.io/library/postgres:16 && docker tag mirror.gcr.io/library/postgres:16 postgres:16); \
	  $(INFA_COMPOSE) up -d --wait; fi
	@echo "warehouse for $(INFA_NS): 127.0.0.1:$(INFA_TD_PORT) (INFA_DB=$(INFA_DB))"

sfx-informatica-run: ## Run the daily workflows through the pmcmd emulator (NS=, MAPPINGS=all|N|names, INFA_DB=, LANDING_DIR=)
	@cd $(INFA_DIR) && for wf in $(INFA_WORKFLOWS); do \
	  $(INFA_ENV) $(INFA_PY) -m runner startworkflow -f $${wf%%:*} $${wf##*:} || exit 1; done

sfx-informatica-test: ## Unit and integration tests of the runner against the NS warehouse database
	@cd $(INFA_DIR) && $(INFA_ENV) $(INFA_PY) -m pytest -q tests

sfx-informatica-down: ## Stop the NS warehouse database, drop its volume and the run directory
	@if [ "$(INFA_DB)" != teradata ]; then $(INFA_COMPOSE) down -v --remove-orphans; fi
	@rm -rf $(INFA_DIR)/infa_shared/$(INFA_NS)

# SnowConvert AI (scai) on the workflow exports. scai reads the Snowflake password only from connections.toml;
# SNOWFLAKE_CONNECTION names the connection (default: the TOML default). The raw output is kept untouched under
# etl/informatica/snowconvert/<NS>/ (ignored by git); nothing in the repository is edited.
INFA_SCAI = $(or $(shell command -v scai 2>/dev/null),$(wildcard $(HOME)/.local/bin/scai))
INFA_SC_DIR = $(CURDIR)/$(INFA_DIR)/snowconvert/$(INFA_NS)

sfx-informatica-snowconvert: ## Convert the PowerCenter workflow exports with SnowConvert AI and keep its raw output (NS=, SNOWFLAKE_CONNECTION=)
	@test -n "$(INFA_SCAI)" || (echo "scai not found: curl -fsSL https://snowconvert.snowflake.com/storage/linux/prod/cli/install.sh | sh" >&2; exit 2)
	@rm -rf $(INFA_SC_DIR) && mkdir -p $(INFA_SC_DIR)/input
	@cp $(INFA_DIR)/repository/*/wf_*.XML $(INFA_SC_DIR)/input/
	@cd $(INFA_SC_DIR) && $(INFA_SCAI) init project -n sfx-d1110-informatica-$(INFA_NS) -l Teradata $(if $(SNOWFLAKE_CONNECTION),-c $(SNOWFLAKE_CONNECTION)) > init.log 2>&1; rc=$$?; cat init.log; exit $$rc
	@cd $(INFA_SC_DIR)/project && $(INFA_SCAI) code add -i $(INFA_SC_DIR)/input > ../add.log 2>&1; rc=$$?; cat ../add.log; exit $$rc
	@cd $(INFA_SC_DIR)/project && $(INFA_SCAI) code convert --show-ewis > ../convert.log 2>&1; rc=$$?; cat ../convert.log; exit $$rc
	@cp -a $(INFA_SC_DIR)/project/snowflake $(INFA_SC_DIR)/raw-output
	@echo "SnowConvert raw output: $(INFA_SC_DIR)/raw-output (reports in raw-output/Reports)"
