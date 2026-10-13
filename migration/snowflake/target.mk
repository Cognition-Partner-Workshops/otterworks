PY ?= python3
SFM_ROOT = migration/snowflake
SFM_RUN_REQUIRED = @test -n "$(RUN)" || (echo "RUN is required, e.g. make sfm-bootstrap RUN=sfm-20261012-bd" >&2; exit 2)
SFM_DATE_REQUIRED = @test -n "$(DATE)" || (echo "DATE is required, e.g. make sfm-gate RUN=sfm-20261012-bd DATE=2026-09-15" >&2; exit 2)

.PHONY: sfm-require-run sfm-bootstrap sfm-load-raw sfm-dbt sfm-gate sfm-dual-run sfm-cutover sfm-teardown sfm-verify-clean sfm-tasks sfm-gate-test sfm-load-extracts sfm-ssis-replay sfm-staging-gate sfm-procs

sfm-require-run:
	$(SFM_RUN_REQUIRED)

sfm-bootstrap: sfm-require-run ## Bootstrap the Snowflake objects for RUN
	$(PY) $(SFM_ROOT)/target/bootstrap/bootstrap.py up --run "$(RUN)" $(if $(EXPIRES),--expires "$(EXPIRES)",)

sfm-load-raw: sfm-require-run ## Export the source staging tables and load them into RAW
	$(PY) $(SFM_ROOT)/target/python/load_raw.py --run "$(RUN)"

sfm-load-extracts: sfm-require-run ## Load the SSIS packages' flat files into RAW.EXT_*
	$(PY) $(SFM_ROOT)/target/python/load_raw.py --run "$(RUN)" --package-extracts

sfm-ssis-replay: ## Replay one SSIS package into SQL Server stg (PKG=, optional DATE=)
	@test -n "$(PKG)" || (echo "PKG is required, e.g. make sfm-ssis-replay PKG=pkg_files" >&2; exit 2)
	$(SFM_ROOT)/.venv/bin/python $(SFM_ROOT)/source/replay/ssis_replay.py "$(PKG)" $(if $(DATE),--business-date "$(DATE)",)

sfm-staging-gate: sfm-require-run ## Compare one package's stg table with its staging model (PKG=, optional DATE=)
	@test -n "$(PKG)" || (echo "PKG is required, e.g. make sfm-staging-gate RUN=sfm-20261012-bd PKG=pkg_files" >&2; exit 2)
	$(PY) $(SFM_ROOT)/gate/staging_parity.py --run "$(RUN)" --package "$(PKG)" $(if $(DATE),--date "$(DATE)",)

sfm-procs: sfm-require-run ## Create the Snowpark procedures that replace SSIS Script Tasks
	$(PY) $(SFM_ROOT)/target/snowpark/deploy.py --run "$(RUN)"

sfm-dbt: sfm-require-run ## Build the dbt project in Snowflake
	UBW_RUN="$(RUN)" $(PY) $(SFM_ROOT)/target/python/dbt_env.py -- build $(if $(DATE),--vars '{business_date: $(DATE)}',)

sfm-gate: sfm-require-run ## Compare SQL Server and Snowflake for DATE
	$(SFM_DATE_REQUIRED)
	$(PY) $(SFM_ROOT)/gate/parity.py --run "$(RUN)" --date "$(DATE)"

sfm-dual-run: sfm-require-run ## Replay, build, and compare for DATE
	$(SFM_DATE_REQUIRED)
	$(PY) $(SFM_ROOT)/gate/dual_run.py --run "$(RUN)" --date "$(DATE)"

sfm-cutover: sfm-require-run ## Stop the SQL Server replay and select Snowflake
	$(PY) $(SFM_ROOT)/gate/cutover.py --run "$(RUN)"

sfm-teardown: sfm-require-run ## Drop the Snowflake objects for RUN
	$(PY) $(SFM_ROOT)/target/bootstrap/bootstrap.py teardown --run "$(RUN)"

sfm-verify-clean: sfm-require-run ## Check for Snowflake objects remaining for RUN
	$(PY) $(SFM_ROOT)/target/bootstrap/bootstrap.py verify-clean --run "$(RUN)"

sfm-tasks: sfm-require-run ## Create the suspended Snowflake task graph
	$(PY) $(SFM_ROOT)/target/tasks/tasks.py --run "$(RUN)" create

sfm-gate-test: ## Run the in-memory parity gate tests
	$(PY) -m pytest $(SFM_ROOT)/gate/tests -q
