# Analyze evidence (UNT19, run unt19-20261030)

- `census.json`: read-only catalog census of OW_BILLING at 44.213.30.5:1521/FREEPDB1 (dba_objects/dba_tables/dba_triggers/dba_scheduler_jobs/dba_dependencies, SELECT only, principal from `OW_TP_ORACLE_RO_DSN`): 20 tables, 5 packages (19 routines), 7 triggers, 5 sequences, 2 disabled scheduler jobs, plus 11 batch assets from the code export.
- `dependencies.json`: transitive writes/reads per routine, trigger and job (package call graph + trigger side effects), from `services/legacy-billing/db/oracle/packages/*.sql` and `schema/*.sql`.
- `consumer_map.json`: who reads what, with file:line evidence, and the route_group each consumer names.
- `lakebridge/`: `databricks labs lakebridge analyze --source-tech Oracle --generate-json true` over `services/legacy-billing/db/oracle/` and `etl/legacy-extra/`; the analyzer exits 2 on `etl/scripts/` and the Scala batch directory (no SQL assets), so those are inventoried from the code directly.

Check: `python3 <plugin>/tools/slices.py --check .migration/slices.json --deps .migration/analyze/dependencies.json --census .migration/analyze/census.json`
