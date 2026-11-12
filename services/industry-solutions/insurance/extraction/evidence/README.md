# Final live Oracle evidence

- Live-test revision: `f0393e31f`. A later offline renderer drift guard and its unit tests do not change payment SQL, seed/config values or characterization cases. The fingerprints below identify the earlier tested files, including that revision's renderer; they are not a fresh Oracle run of the guard.
- Oracle: `Oracle AI Database 26ai Free 23.26.3.0.0`; image ID, UTC and 15 source/test/config SHA-256 fingerprints are in [test-run.json](test-run.json).
- Original regressions: `make insurance-test NS=rules` reported both `OLTP TESTS: ALL PASS` and `OLAP TESTS: ALL PASS`.
- Characterization: **65/65 PASS**; **47 green / 18 amber**; **12 grouped owner decisions**; zero execution failures.
- [Markdown rows](test-run.md) and [CSV rows](test-run.csv) separate business classification from execution result. Every rule maps to its own live SQL assertion case.
- QA: renderer validated 65 rules/65 cases/12 decisions; Ruff, mypy, compileall and `git diff --check` passed.
- Source preservation: no changes to the fixture SQL or scanned specification relative to `demo-insurance`.
- Teardown: the EXIT trap ran `make insurance-down NS=rules`, removing the Oracle container, volume and network; exit 0. A subsequent Docker container query was empty.

The session handoff contains the final shell video, replayable `script` transcript/timing and every per-case SQL/log file. They are not committed as repository media. Re-run from a fresh namespace using the parent README; tests intentionally mutate the disposable fixture. Amber PASS documents current behavior, not spec conformance or owner approval. All approval fields remain pending.

## Offline drift-guard follow-up

At 2026-11-12 16:26 UTC, all 10 `test_render.py` unit/integration tests passed, including seed/config mutations, missing/extra/duplicate rows, exact decimal handling, formatting tolerance, and optimized-Python CLI rejection before catalog writes. Ruff lint/format, mypy, compileall and diff checks passed. The supplementary shell transcript/timing includes the tested renderer/test/seed/config fingerprints. Oracle was not started; the owned-container query remained empty. The 65-rule live report above is preserved unchanged, not presented as a new Oracle run.

The DELETE-syntax follow-up passes all **11 tests**, including 18 rejection cases covering both `DELETE table` and `DELETE FROM table` across all three tracked tables with bare, quoted and schema-qualified names. Before the fix, that regression reproduced nine missing-FROM bypasses; afterward all variants are rejected. The latest supplementary shell transcript/timing records the final files and passing checks. Oracle was not started.
