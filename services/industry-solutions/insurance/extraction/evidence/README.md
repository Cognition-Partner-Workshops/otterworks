# Final live Oracle evidence

- Test revision: `f0393e31f` (only documentation/evidence added afterward).
- Oracle: `Oracle AI Database 26ai Free 23.26.3.0.0`; image ID, UTC and 15 source/test/config SHA-256 fingerprints are in [test-run.json](test-run.json).
- Original regressions: `make insurance-test NS=rules` reported both `OLTP TESTS: ALL PASS` and `OLAP TESTS: ALL PASS`.
- Characterization: **65/65 PASS**; **47 green / 18 amber**; **12 grouped owner decisions**; zero execution failures.
- [Markdown rows](test-run.md) and [CSV rows](test-run.csv) separate business classification from execution result. Every rule maps to its own live SQL assertion case.
- QA: renderer validated 65 rules/65 cases/12 decisions; Ruff, mypy, compileall and `git diff --check` passed.
- Source preservation: no changes to the fixture SQL or scanned specification relative to `demo-insurance`.
- Teardown: the EXIT trap ran `make insurance-down NS=rules`, removing the Oracle container, volume and network; exit 0. A subsequent Docker container query was empty.

The session handoff contains the final shell video, replayable `script` transcript/timing and every per-case SQL/log file. They are not committed as repository media. Re-run from a fresh namespace using the parent README; tests intentionally mutate the disposable fixture. Amber PASS documents current behavior, not spec conformance or owner approval. All approval fields remain pending.
