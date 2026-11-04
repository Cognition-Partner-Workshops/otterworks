# churn_model on Snowpark (synthetic history)

**The labels and support notes this model trains and is evaluated on are synthetic.** They come from
`synthetic_history.py` (seed `20261104`, a documented rule plus noise) and live in their own
`SFNFR_20261104_DB_CHURN_MODEL.SYNTHETIC` schema. The loaded reporting tables have no churn outcome and no
support notes, so a passing gate here shows that the pipeline and the leakage checks work. It does not show
that the model predicts real churn.

Search features are left out: `doc_search_api` is blocked on its source (search-service keeps searches in
process memory only), so there is no search activity to build them from.

```bash
SNOWFLAKE_ACCOUNT=... SNOWFLAKE_USER=... SNOWFLAKE_ROLE=... SNOWFLAKE_PRIVATE_KEY_FILE=... \
uv run -q --python 3.12 --with snowflake-snowpark-python==1.56.0 --with snowflake-connector-python==4.8.1 \
  --with pandas==2.2.3 --with numpy==2.2.6 --with pyarrow==19.0.1 --with tabulate==0.9.0 \
  python workloads/churn_model/snowpark/run.py all      # or: load features leakage train reasons report
```

Every step runs on `SFNFR_20261104_WH_CHURN_MODEL` through `sf_attribution.connection_params()`.

| step | what it writes |
|---|---|
| `load` | `ACCOUNTS`, `DAILY_ACTIVITY`, `QUOTA_SNAPSHOTS`, `CHURN_EVENTS`, `SUPPORT_NOTES`, `GENERATOR_RUNS` (row counts and SHA-256 per table) |
| `features` | `CHURN_POPULATION` (labels, splits) and `CHURN_FEATURES` (usage + quota, read only from rows before the prediction date) |
| `leakage` | `LEAKAGE_CHECK`: no label/notes table in the feature SQL, label windows close before the next split, holdout accounts unseen, stored features identical when sources are cut at each prediction date, and a planted future feature (`saves_next_7d`) that the check must catch |
| `train` | Snowpark stored procedure: logistic regression on train weeks, threshold chosen on validation weeks, frozen for the holdout. Writes `CHURN_EVALUATION`, `CHURN_EVALUATION_GATES`, `FEATURE_AUC_SENTINEL`, `CHURN_SCORES`, `CHURN_MODEL_COEFFICIENTS`, and appends to the `*_HISTORY` tables |
| `reasons` | `CHURN_WATCHLIST`: flagged accounts for the score week with an `AI_CLASSIFY` reason from their last 56 days of notes; `CHURN_REASON_CHECK` compares it with the generator's reason |

Splits: train Mondays 2026-03-02..06-29, validation 07-27..08-17, holdout 09-14..10-05 on a separate
20% of accounts (`hash(account_id) % 5 = 0`), score 2026-11-02; 28-day horizon.

Threshold: the lowest cutoff whose validation precision is at least 0.50 with at least 10 flagged
accounts, so at least half of the accounts the team calls are real leavers (base rate is about 4%).
Holdout gates: ROC AUC >= 0.80, PR AUC >= 3x base rate, precision >= 0.50, recall >= 0.50, PR AUC above
`rules_v1`.

`credits_ai_dev` / `credits_ai_runtime` in `provenance.yaml` carry the `AI_CLASSIFY` token credits
(`CORTEX_AISQL_USAGE_HISTORY`), separate from warehouse credits. Legacy `SNOWFLAKE.CORTEX.*` functions are
blocked on this account.
