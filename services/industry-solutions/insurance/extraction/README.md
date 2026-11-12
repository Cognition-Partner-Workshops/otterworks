# Commission Pay rule extraction

Start with [catalog.md](catalog.md) or [catalog.csv](catalog.csv). Both are generated from [rules.json](rules.json), with one ordered live-Oracle case per rule in [cases.json](cases.json).

- [spec-crosswalk.md](spec-crosswalk.md): every clause/table row from the three scanned pages, including missing implementation.
- [decision-tables.md](decision-tables.md): premium tiers, WL-PAR and FIA-7 date/rate schedules, flat-rate precedence, chargeback bands, and monthly cap.
- [sign-off.md](sign-off.md): grouped amber decisions and blank owner approval fields.
- [product-config.json](product-config.json): observed legacy product behavior and **separate** paper-spec alternatives. Descriptive, not deployable, not approved.
- [extraction skill](../../../../.agents/skills/commission-rule-extraction/SKILL.md): method for the next package.

No earning SQL has changed. All rules, including green ones, await owner approval. A passing amber test documents disagreement; it does not resolve it.

## Reproduce on disposable Oracle

Python 3.10+ standard library, Docker Compose, and the Oracle Free image are required. No Python Oracle emulator/driver is used; every assertion runs in SQL*Plus inside the real container.

From the repository root, using a fresh namespace:

```sh
python3 services/industry-solutions/insurance/extraction/render.py
make insurance-up NS=rules
make insurance-test NS=rules
python3 services/industry-solutions/insurance/extraction/characterize.py \
  --namespace rules --allow-disposable-fixture --output "$HOME/commission-evidence/run"
make insurance-down NS=rules
```

The suite mutates saved data, including intentional stale-warehouse cases. Cases are ordered and must run together on a fresh fixture; run original regressions first, then characterization. A failure should exit nonzero. Always perform teardown, including after failures. `insurance-down` drops only the named namespace's container/data volume. Do not run against a shared or production database.

To record a run, put the commands in a shell file with `set -euo pipefail` and an EXIT trap for teardown, then:

```sh
script --return --log-out shell.typescript --log-timing shell.timing \
  --command 'bash /absolute/path/to/run.sh'
# Replay in a terminal:
scriptreplay --log-out shell.typescript --log-timing shell.timing
```

The runner emits per-rule source SQL and SQL*Plus logs, Markdown/CSV rows, and JSON with exact UTC/image/version/source/test fingerprints. Preserve these with the shell recording. The [compact final reports](evidence/README.md) are under `evidence/`; raw logs and recordings are session artifacts to avoid checking large media into git.

## Coverage boundary

The catalog covers the business-bearing package, private helpers/constants, trigger, schema validations/defaults, seeded product/rate configuration, warehouse ETL, and materialized view. Infrastructure grants/identity sequences/display-field lengths are not separate earning rules. Upstream premium/channel mappings are not present and are amber, not guessed. Concurrency/cap races, production authorization, external payment transmission, time-zone conventions, and a migration implementation are outside the executed characterization scope. Date boundary tests use midnight Oracle DATE values.
