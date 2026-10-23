.PHONY: sfm-up sfm-down

UBW_SQL_HOST ?= 127.0.0.1
UBW_SQL_PORT ?= 14333
UBW_SQL_USER ?= sa
UBW_SQL_PASSWORD ?= OtterUbw_2016dev
UBW_SEED ?= 20261012
export UBW_SQL_HOST UBW_SQL_PORT UBW_SQL_USER UBW_SQL_PASSWORD UBW_SEED

.venv/.requirements-installed: source/requirements.txt
	python3 -m venv .venv
	.venv/bin/pip install -r source/requirements.txt
	touch .venv/.requirements-installed

sfm-up: .venv/.requirements-installed
	mkdir -p source/build
	@set -e; \
	total_start=$$(date +%s); \
	run_step() { \
		label="$$1"; shift; \
		start=$$(date +%s); \
		"$$@"; \
		elapsed=$$(( $$(date +%s) - start )); \
		printf '[sfm-up] %s: %ss\n' "$$label" "$$elapsed"; \
	}; \
	run_step "start SQL Server" docker compose up -d --wait; \
	run_step "generate extracts" .venv/bin/python source/generate.py; \
	run_step "load database and packages" .venv/bin/python source/load.py; \
	run_step "agent replay 2026-09-15" .venv/bin/python source/replay/agent_replay.py --job "UBW Nightly Load" --business-date 2026-09-15; \
	run_step "agent replay 2026-09-30" .venv/bin/python source/replay/agent_replay.py --job "UBW Nightly Load" --business-date 2026-09-30; \
	run_step "table and schema counts" .venv/bin/python source/load.py --counts; \
	printf '[sfm-up] total: %ss\n' "$$(( $$(date +%s) - total_start ))"

sfm-down:
	docker compose down -v --remove-orphans
	rm -rf source/build
