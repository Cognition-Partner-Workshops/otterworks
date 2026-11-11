PY ?= python3
SFM_ROOT = migration/snowflake
SFM_RUN_REQUIRED = @test -n "$(RUN)" || (echo "RUN is required, e.g. make sfm-bootstrap RUN=sfm-20261012-bd" >&2; exit 2)
SFM_DATE_REQUIRED = @test -n "$(DATE)" || (echo "DATE is required, e.g. make sfm-gate RUN=sfm-20261012-bd DATE=2026-09-15" >&2; exit 2)

.PHONY: sfm-require-run sfm-bootstrap sfm-load-raw sfm-dbt sfm-gate sfm-dual-run sfm-cutover sfm-teardown sfm-verify-clean sfm-tasks sfm-gate-test sfm-demo-reset sfm-bi-workbooks sfm-bi-parity sfm-bi-console sfm-metabase-up sfm-metabase

sfm-require-run:
	$(SFM_RUN_REQUIRED)

sfm-bootstrap: sfm-require-run ## Bootstrap the Snowflake objects for RUN
	$(PY) $(SFM_ROOT)/target/bootstrap/bootstrap.py up --run "$(RUN)" $(if $(EXPIRES),--expires "$(EXPIRES)",)

sfm-load-raw: sfm-require-run ## Export the source staging tables and load them into RAW
	$(PY) $(SFM_ROOT)/target/python/load_raw.py --run "$(RUN)"

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
	$(PY) -m pytest $(SFM_ROOT)/gate/tests $(SFM_ROOT)/gate/bi/tests $(SFM_ROOT)/consumers/metabase/tests -q

sfm-bi-workbooks: ## Regenerate the 20 legacy Tableau workbooks from the SSRS reports (needs SQL Server)
	$(PY) $(SFM_ROOT)/source/tableau/generate.py

sfm-bi-parity: sfm-require-run ## Report parity for every Tableau workbook, SQL Server vs Snowflake (WORKBOOK=name for one)
	$(SFM_DATE_REQUIRED)
	$(PY) $(SFM_ROOT)/gate/bi/parity.py --run "$(RUN)" --date "$(DATE)" $(if $(WORKBOOK),--workbook "$(WORKBOOK)",)

sfm-bi-console: ## Serve the report parity console on 127.0.0.1:$(or $(PORT),8050)
	$(PY) -m http.server $(or $(PORT),8050) --bind 127.0.0.1 --directory $(SFM_ROOT)/gate/out/bi

sfm-metabase-up: ## Start Metabase on 127.0.0.1:$(or $(MB_PORT),3000), on the SQL Server fixture's network
	docker compose -f $(SFM_ROOT)/compose.yaml --profile metabase up -d --wait metabase

sfm-metabase: sfm-require-run ## Build each workbook as a Metabase dashboard on SQL Server, and on Snowflake once migrated (WORKBOOK=name for one)
	$(PY) $(SFM_ROOT)/consumers/metabase/dashboards.py --run "$(RUN)" $(if $(DATE),--date "$(DATE)",) $(if $(filter-out all,$(WORKBOOK)),--workbook "$(WORKBOOK)",)

# Presenter reset: a fresh Snowflake build for the token, back to the 7-of-25 starting ledger.
sfm-demo-reset: sfm-require-run
	-$(PY) $(SFM_ROOT)/target/bootstrap/bootstrap.py teardown --run "$(RUN)"
	rm -rf $(SFM_ROOT)/gate/out
	$(PY) $(SFM_ROOT)/target/bootstrap/bootstrap.py up --run "$(RUN)" $(if $(EXPIRES),--expires "$(EXPIRES)",)
	$(PY) $(SFM_ROOT)/target/python/load_raw.py --run "$(RUN)"
	-$(PY) $(SFM_ROOT)/gate/dual_run.py --run "$(RUN)" --date 2026-09-15
	-$(PY) $(SFM_ROOT)/gate/bi/parity.py --run "$(RUN)" --date 2026-09-15
	@head -1 $(SFM_ROOT)/gate/out/ledger.md
