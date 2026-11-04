# Snowflake consumption attribution

Three workloads (`doc_usage_dashboard`, `doc_search_api`, `churn_model`) share one Snowflake account.
Every month the team paying for it asks which client, which workload and which commit used the credits,
and whether it was development or production. Snowflake can answer that only if every workload is labeled
the same way from its first query. This directory holds those labeling rules and the code that applies them.
Every session that touches a workload follows these rules.

| File | What it is |
|---|---|
| `sf_attribution.py` | The only place names and tags are built: csid, service user, warehouse, monitor, database, task, Streamlit, `QUERY_TAG`, connection params and DDL |
| `provenance.schema.json` | JSON Schema (draft 2020-12) for `workloads/<id>/provenance.yaml` |
| `validate_provenance.py` | Validates every provenance file against the schema and cross-checks it with the naming rules and the workload spec |
| `sql/monthly_attribution.sql` | The monthly report: credits by csid, workload, commit and phase, idle time per warehouse, and labeling gaps |
| `tests/` | Unit tests (`make workloads-test`) |

## Rules

1. **Client-side ID.** Each endpoint has `csid = cs_<workload>_<endpoint>`, written in lower snake_case. The csid comes from `endpoint.client_side_id` in `workloads/<workload>.yaml`.
2. **One key-pair service user per endpoint.** Name it `SVC_<CSID>`, the csid in upper case (`SVC_CS_DOC_USAGE_DASHBOARD_ACCOUNT_USAGE`). Create it with `TYPE = SERVICE` and an RSA public key. It never gets a password. `DEFAULT_WAREHOUSE` is the workload warehouse.
3. **Every connection is labeled.** Build connections with `sf_attribution.connection_params()` or `connect()`. They set `application='Devin_Demo'` and the session parameter `QUERY_TAG`, a compact JSON object whose keys always come in this order:

   ```json
   {"csid":"cs_doc_usage_dashboard_account_usage","workload":"doc_usage_dashboard","phase":"dev",
    "commit":"<40-char sha>","run_id":"SFNFR_20261104-doc_usage_dashboard-dev-20261104T201600Z",
    "session_url":"https://<host>/sessions/<id>"}
   ```

   - `phase` is `dev` (a Devin session building or testing the workload) or `runtime` (the deployed endpoint, task or app).
   - `commit` is the full SHA of the code running. A dev session uses `HEAD`. Runtime uses the commit that was deployed.
   - `run_id` is `<RUN_TOKEN>-<workload>-<phase>-<UTC yyyymmddThhmmssZ>`, built by `make_run_id()`. The run token for this program is `SFNFR_20261104`.
   - `session_url` is present only when the phase is `dev`, and it is required then. The helper rejects a runtime tag that carries one.
   - The tag must fit Snowflake's 2000-character `QUERY_TAG` limit.
4. **Tasks carry their own tag.** A task run does not inherit the tag of the session that created it. Set `QUERY_TAG` on the task itself with `create_task_sql()` or `alter_task_query_tag_sql()`. The default phase is `runtime`, and the task runs on `WH_<WORKLOAD>`. Name the task `DB_<WORKLOAD>.ANALYTICS.REFRESH_<WORKLOAD>`.
5. **Streamlit apps tag their own session.** An app has no client connection to configure, so its first statement is `streamlit_query_tag_sql()`, which runs `ALTER SESSION SET QUERY_TAG = ...`. Name the app `DB_<WORKLOAD>.ANALYTICS.<WORKLOAD>_APP`.
6. **One X-Small warehouse per workload.** `WH_<WORKLOAD>` is `XSMALL`, with `AUTO_SUSPEND = 60`, `AUTO_RESUME = TRUE` and `INITIALLY_SUSPENDED = TRUE`. It has its own resource monitor `RM_<WORKLOAD>`: monthly, 10 credits by default, notify at 75%, suspend at 100%, suspend immediately at 110%. Nothing else runs on a workload warehouse, and no workload uses another workload's warehouse. Build these with `warehouse_ddl()`.
7. **One database per workload.** `DB_<WORKLOAD>` has schema `RAW` for the landed inputs this workload reads (`RAW.<SERVICE>_<TABLE>`, per `workloads/index.yaml`) and schema `ANALYTICS` for its output table. A Postgres table that two workloads read is landed by each of them on its own warehouse, so the ingest cost is attributed too.
8. **Object tag `DEVIN_CSID`.** The tag lives at `DEVIN_GOVERNANCE.TAGS.DEVIN_CSID` and is created once per account. Each workload's warehouse, database, task and Streamlit app carry it. The value is the workload's csids, sorted and comma-joined (each workload has exactly one today). Users, schemas, tables and resource monitors are not tagged. Build the statements with `object_tag_ddl()`.
9. **Provenance.** `workloads/<id>/provenance.yaml` records:
   - the repository, commit, pull request and session behind the current state
   - the endpoints and their service users
   - the warehouse and its monitor
   - every object the workload owns, with its `state` (`planned`, `deployed` or `dropped`). A deployed or dropped object also needs `deployed_at` and `deployed_commit`.
   - the usage figures

   A session that deploys or changes objects updates the file in the same pull request.
10. **`pending` is not zero.** Any usage figure Snowflake has not reported yet is written as the string `pending`. A number, including `0`, means Snowflake reported it. While `reported_through` is `pending`, every figure must be `pending`. `QUERY_ATTRIBUTION_HISTORY` lags by up to 8 hours and the metering views by up to 3, so a recent month can mix reported and pending figures.

## Commands

```bash
make workloads-test        # unit tests for the helper and the validator
make workloads-provenance  # validate every workloads/*/provenance.yaml

# QUERY_TAG for a dev session (commit defaults to HEAD, run_id to now)
python3 workloads/attribution/sf_attribution.py tag --workload churn_model \
  --csid cs_churn_model_account_score --phase dev --session-url "$SESSION_URL"

# warehouse, monitor and object-tag DDL for a workload
python3 workloads/attribution/sf_attribution.py ddl --workload doc_usage_dashboard \
  --csid cs_doc_usage_dashboard_account_usage --streamlit
```

```python
import sys; sys.path.insert(0, "workloads/attribution")
import sf_attribution as attr

ep = attr.Endpoint.from_csid("cs_churn_model_account_score", "churn_model")
conn = attr.connect(ep, account=ACCOUNT, private_key_file=KEY_PATH, phase="runtime",
                    commit=DEPLOYED_SHA, run_id=attr.make_run_id("churn_model", "runtime"))
```

## Reading the bill

`sql/monthly_attribution.sql` groups `SNOWFLAKE.ACCOUNT_USAGE.QUERY_ATTRIBUTION_HISTORY` by the tag's `csid`, `workload`, `commit` and `phase`. That gives attributed compute, without idle time. It reports idle time per `WH_*` warehouse as metered credits (`WAREHOUSE_METERING_HISTORY`) minus attributed credits, joined to the `DEVIN_CSID` tag through `TAG_REFERENCES`. It also lists queries on a workload warehouse that carry no csid. That list should always be empty. The role running the report needs `USAGE_VIEWER` or `GOVERNANCE_VIEWER` on the `SNOWFLAKE` database.
