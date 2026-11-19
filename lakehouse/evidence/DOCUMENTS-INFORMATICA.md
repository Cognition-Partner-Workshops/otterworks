# Documents Informatica checkpoint

Scope: 12 documents-only mapping/session/source/target IDs for
`m_SFX_STG_DOCUMENT`, `m_SFX_DOCUMENT` and `m_SFX_DOC_SHARE`.
All 12 are converted. The existing ownership list remains 97 objects; later
documents jobs and shared integration responsibilities remain pending.
Legacy code and the primary legacy warehouse were not changed.

## Independent execution and outputs

The legacy execution path is the PowerCenter emulator documented in
`etl/informatica/README.md` (`make sfx-informatica-run`). The verification helper
invokes its existing `Integration.run_session` for just the three sessions,
using the unmodified repository XML, workflow settings and parameter files.
It creates `lakehouse_documents_infa_sfx-d1110-after` in the local emulator
PostgreSQL instance, initializes empty documents targets and copies the users
lookup tables from the existing legacy database. It never runs BTEQ documents
transformations or uses their published documents snapshots as expected output.

The lakehouse export independently reads DOCUMENT and DOC_SHARE landing feeds,
implements the PowerCenter ports and stateful writers, and publishes distinct
`silver_documents.infa_{stg_document,document,doc_share,metrics}` dbt outputs.
`source()` declarations expose the independent runtime tables. Source widths,
numeric-prefix casts, whitespace/null rules and QUOTE_NONE are PowerCenter
semantics, not the BTEQ staging semantics.

`DOCUMENT` uses the cached pre-load document lookup to distinguish insert from
update, rejects duplicate new keys, updates all mapped fields, and retains
absent target rows. `DOC_SHARE` uses update-else-insert and preserves the
ADMIN to OWNER / EDITOR plus VIEW to EDIT upgrades. Unit tests cover populated
targets, duplicate input keys and absent-row retention as well as empty/error
inputs. The shared landing parity below starts both engines with empty targets;
its action counts do not claim a populated-estate migration was tested.

No users silver model exists on this branch. The runtime reads business-date
`bronze_users.app_user` and `bronze_users.role_grant`; explicit cross-domain
edges connect `bronze_users` to the export and documents dbt task (A-206).
Legacy lookup keys were checked: APP_USER has 300 rows / 300 distinct USER_IDs;
ROLE_GRANT has 200 rows / 200 distinct USER_IDs. A-208 remains open for physical
first-match choices on duplicate lookup keys; no duplicate-key exact parity is
claimed.

Unknown/null-status owners are filtered by `FIL_KNOWN_OWNER`, not sent to a bad
file or counted as rejects. `INACTIVE` is still a known status. The lakehouse
keeps filtered rows in `silver_documents.infa_runtime_filtered`. Writer and
transformation rejects are observable in `silver_documents.infa_runtime_rejects`
and the session counters in `infa_metrics` (A-207). The shared fixture has zero
filtered/rejected rows; unit tests exercise both separately.

Before publication, an atomic last-delivery checkpoint records input/code
signature, full prepared outputs and original counters. Retrying completes
publication without recomputing against partially updated targets. A real
two-pass Spark replay returned identical rows, dates, diagnostics and metrics:

```text
Informatica retry replay: identical rows, dates, diagnostics and metrics
```

The journal covers the last delivery, not arbitrary historical snapshots.
Different input/date deliveries recompute against current targets and must run
serially. Populated-estate migration and backfill comparisons require explicitly
aligned starting state; they are not established by empty-target fixture parity
(A-205).

## Shared inputs and verification

Namespace `sfx-d1110-after`, legacy namespace `sfx-d1110-before`, business date
`20261109`, shared landing `warehouse/landing`, local PostgreSQL port `55395`.
No feeds were regenerated between the two engines. Input SHA-256:

| Feed | SHA-256 |
|---|---|
| documents/DOCUMENT | `859ebee8919ac8ba724e6a852f935fe79be191dd8e7255fb0b73ba98e8bf4d44` |
| documents/DOC_SHARE | `845a531c3593bd9da7e4e1b5777e489644ca134c288991acd8cc2a682bb4a788` |
| users/APP_USER | `9f84be9c328f5c2db6c5147d123202df453d2b4865d9b7d2e70632d439d51d4a` |
| users/ROLE_GRANT | `2019d813d0bbf1575404546edee30e7e6d3338fbe1a413370625415d113e0188` |

With those environment variables set, commands from the repository root:

```sh
lakehouse/.venv/bin/python -m lakehouse.parity.documents_informatica_legacy --landing warehouse/landing --business-date 20261109
lakehouse/.venv/bin/python -m lakehouse.runtime.documents_informatica --landing warehouse/landing --business-date 20261109
DBT_PARTIAL_PARSE=0 lakehouse/.venv/bin/python -m lakehouse.runtime.dbt --select 'infa_document infa_stg_document infa_doc_share infa_metrics'
lakehouse/.venv/bin/python -m lakehouse.parity run --spec documents.infa_stg_document documents.infa_document documents.infa_doc_share documents.infa_metrics --business-date 20261109
make sfx-lakehouse-test NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before BUSINESS_DATE=20261109
```

The helper resets only its isolated database. For a new empty-target parity
baseline, also use empty lakehouse runtime targets with no prepared checkpoint.
Do not reset the primary BTEQ database. Output specs use the isolated emulator
database; metrics use its exported session statistics. Staging comparison uses
full-row occurrence keys to retain duplicates and null IDs. Only target CHAR
columns use rstrip; null and empty text remain distinct (A-209).

Actual legacy execution:

```text
legacy.informatica.stg_document: read=450 written=450 rejected=0
legacy.informatica.document: read=450 written=450 rejected=0
legacy.informatica.doc_share: read=1000 written=1000 rejected=0
```

Actual dbt result (four models, eight data tests):

```text
Done. PASS=12 WARN=0 ERROR=0 SKIP=0 TOTAL=12
```

The first wildcard selection was a no-op; explicit names select the four models.
A stale dbt partial-parse cache also omitted unchanged key tests after the schema
edit. Disabling partial parsing restored all eight tests; no project
configuration or dependency changes were needed.

Fresh output spec results, with detailed JSON in `evidence/parity/`:

```text
documents.infa_doc_share: PASS {'legacy': 1000, 'lakehouse': 1000}
documents.infa_document: PASS {'legacy': 450, 'lakehouse': 450}
documents.infa_metrics: PASS {'legacy': 3, 'lakehouse': 3}
documents.infa_stg_document: PASS {'legacy': 450, 'lakehouse': 450}
```

Test/check tail:

```text
Assumptions: 57 entries, 0 errors
Coverage: 438 inventory objects, 438 map entries, 0 errors
Pipeline: 2 DAGs, 81 tasks, valid
........................................................................ [ 55%]
..........................................................               [100%]
130 passed, 1 warning in 41.85s
```

The warning is the existing dbt `datetime.utcnow()` deprecation. Tests cover
normal, empty and malformed inputs, nulls, source width and quoting, owner
filtering, first-match policy, both role upgrades, insert/update behavior,
observable rejects, retry checkpoints, graph edges and database selection.
The full Airflow DAG and a populated-estate migration were not executed in this
step. There is no changed UI surface to verify.
