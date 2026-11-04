"""Build churn_model with Snowpark on SFNFR_20261104_WH_CHURN_MODEL against the seeded SYNTHETIC history.

  python run.py all       # generate + load, features, leakage check, train/evaluate, reasons, report
  python run.py features leakage train   # selected steps, one run_id
  python run.py report    # print the evaluation, leakage check and ten reasons

Needs SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE and SNOWFLAKE_PRIVATE_KEY_FILE
(the SFNFR_* key-pair service credentials) in the environment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'workloads/attribution'))
sys.path.insert(0, str(HERE))
import features as F  # noqa: E402
import sf_attribution as attr  # noqa: E402
import synthetic_history as G  # noqa: E402
import train_evaluate as T  # noqa: E402

WORKLOAD = 'churn_model'
CSID = 'cs_churn_model_account_score'
SESSION_URL = 'https://partner-workshops.devinenterprise.com/sessions/6eebc1acb0d4426c985e41f45bb0adda'
SCHEMA = F.SCHEMA
SPROC_PACKAGES = ['snowflake-snowpark-python[pandas]', 'scikit-learn==1.9.1', 'pandas', 'numpy', 'pyarrow']
REASON_CATEGORIES = [*G.REASONS, G.ROUTINE]
NOTES_WINDOW_DAYS = 56

DDL = {
    'GENERATOR_RUNS': 'RUN_ID VARCHAR, SEED NUMBER, MANIFEST VARIANT, LOADED_AT TIMESTAMP_NTZ',
    'ACCOUNTS': 'ACCOUNT_ID VARCHAR(36), TIER VARCHAR(16), QUOTA_BYTES NUMBER(20,0), CREATED_AT TIMESTAMP_NTZ',
    'DAILY_ACTIVITY': 'ACCOUNT_ID VARCHAR(36), ACTIVITY_DATE DATE, DOCUMENT_SAVES NUMBER(6,0), LOGINS NUMBER(3,0)',
    'QUOTA_SNAPSHOTS': 'ACCOUNT_ID VARCHAR(36), SNAPSHOT_DATE DATE, TAKEN_AT TIMESTAMP_NTZ, USED_BYTES NUMBER(20,0), QUOTA_BYTES NUMBER(20,0)',
    'CHURN_EVENTS': 'ACCOUNT_ID VARCHAR(36), CHURNED_AT TIMESTAMP_NTZ, GENERATOR_REASON VARCHAR(32)',
    'SUPPORT_NOTES': 'NOTE_ID VARCHAR(36), ACCOUNT_ID VARCHAR(36), CREATED_AT TIMESTAMP_NTZ, NOTE_TEXT VARCHAR, GENERATOR_REASON VARCHAR(32)',
}
SYNTHETIC_COMMENT = 'SYNTHETIC: seeded churn_model test history (synthetic_history.py). Not real accounts.'


def session():
    from snowflake.snowpark import Session

    os.environ.pop('SNOWFLAKE_HOST', None)
    run_id = attr.make_run_id(WORKLOAD, 'dev')
    params = attr.connection_params(
        attr.Endpoint.from_csid(CSID, WORKLOAD), account=os.environ['SNOWFLAKE_ACCOUNT'],
        private_key_file=os.environ['SNOWFLAKE_PRIVATE_KEY_FILE'], phase='dev',
        commit=attr.current_commit(str(ROOT)), run_id=run_id, session_url=SESSION_URL,
        role=os.environ['SNOWFLAKE_ROLE'], schema=SCHEMA,
    )
    params['user'] = os.environ['SNOWFLAKE_USER']
    params.pop('schema')
    s = Session.builder.configs(params).create()
    s.sql('USE SECONDARY ROLES NONE').collect()
    s.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA} COMMENT = '{SYNTHETIC_COMMENT}'").collect()
    s.use_schema(SCHEMA)
    return s, run_id


def load_synthetic(s, run_id):
    tables = G.generate()
    for name, cols in DDL.items():
        s.sql(f"CREATE OR REPLACE TABLE {SCHEMA}.{name} ({cols}) COMMENT = '{SYNTHETIC_COMMENT}'").collect()
    for name, frame in tables.items():
        s.write_pandas(frame, name, schema=SCHEMA, use_logical_type=True)
    manifest = G.manifest(tables)
    s.sql(f'INSERT INTO {SCHEMA}.GENERATOR_RUNS SELECT ?, ?, PARSE_JSON(?), SYSDATE()',
          params=[run_id, G.SEED, json.dumps(manifest)]).collect()
    for name, meta in manifest['tables'].items():
        got = s.sql(f'SELECT COUNT(*) FROM {SCHEMA}.{name}').collect()[0][0]
        if got != meta['rows']:
            raise RuntimeError(f'{name}: loaded {got} rows, generated {meta["rows"]}')
    print('loaded', {k: v['rows'] for k, v in manifest['tables'].items()})


def build_features(s):
    problems = F.check_split_gaps()
    if problems:
        raise RuntimeError(problems)
    s.sql(F.population_sql()).collect()
    s.sql(F.features_sql()).collect()
    print('population', s.sql(f'SELECT split, COUNT(*), SUM(label) FROM {SCHEMA}.CHURN_POPULATION GROUP BY 1 ORDER BY 1').collect())


def leakage_check(s, run_id):
    rows = []
    found = F.static_label_check(F.features_sql())
    rows.append(('feature SQL reads no label or notes table', 'CHURN_FEATURES', 1, len(found), 'no leak',
                 not found, f'label sources referenced: {found or "none"}'))
    gaps = F.check_split_gaps()
    rows.append(('label windows close before the next split starts', 'train/validation/holdout/score', 3, len(gaps),
                 'no leak', not gaps, '; '.join(gaps) or f'horizon {F.HORIZON_DAYS} days'))
    overlap = s.sql(f"SELECT COUNT(DISTINCT h.account_id) FROM {SCHEMA}.CHURN_POPULATION h JOIN {SCHEMA}.CHURN_POPULATION m "
                    "ON m.account_id = h.account_id AND m.split IN ('train','validation') WHERE h.split = 'holdout'").collect()[0][0]
    rows.append(('holdout accounts never seen in training or validation', 'holdout', 1, overlap, 'no leak',
                 overlap == 0, f'{overlap} shared accounts'))
    dates = [d for ds in F.PERIODS.values() for d in ds]
    checked = mismatched = 0
    for d in dates:
        r = s.sql(F.stored_features_check_sql(SCHEMA, d)).collect()[0]
        checked += r[0]
        mismatched += r[1]
    rows.append(('stored features unchanged when sources are cut at the prediction date', f'{len(dates)} prediction dates',
                 checked, mismatched, 'no leak', mismatched == 0, f'all {len(F.FEATURES)} features, full-row hash'))
    c_checked = c_mis = 0
    for d in F.PERIODS['holdout']:
        r = s.sql(F.truncation_check_sql(SCHEMA, d, ['saves_next_7d'], canary=True)).collect()[0]
        c_checked += r[0]
        c_mis += r[1]
    rows.append(('positive control: planted future feature saves_next_7d is caught', 'holdout dates',
                 c_checked, c_mis, 'leak detected', c_mis > 0, 'the check must flag a feature that reads [T, T+7)'))
    frame = [dict(zip(['CHECK_NAME', 'SCOPE', 'ROWS_CHECKED', 'MISMATCHES', 'EXPECTED', 'PASSED', 'DETAIL'], r)) for r in rows]
    import pandas as pd

    df = pd.DataFrame(frame)
    df['RUN_ID'] = run_id
    s.write_pandas(df, 'LEAKAGE_CHECK', schema=SCHEMA, auto_create_table=True, overwrite=True, use_logical_type=True)
    print(df.drop(columns='RUN_ID').to_string(index=False))
    return bool(df.PASSED.all())


def train(s, run_id):
    from snowflake.snowpark.types import StringType

    proc = s.sproc.register_from_file(
        str(HERE / 'train_evaluate.py'), 'train_evaluate', packages=SPROC_PACKAGES,
        input_types=[StringType(), StringType(), StringType()], return_type=StringType(),
        is_permanent=False, replace=True, name='TRAIN_EVALUATE_CHURN_MODEL',
    )
    out = json.loads(proc(SCHEMA, run_id, json.dumps(F.FEATURES), session=s))
    sentinel_ok = s.sql(f'SELECT BOOLAND_AGG(PASSED) FROM {SCHEMA}.FEATURE_AUC_SENTINEL').collect()[0][0]
    s.sql(f"INSERT INTO {SCHEMA}.LEAKAGE_CHECK SELECT 'no single feature separates the training labels (AUC <= {T.MAX_SINGLE_FEATURE_AUC})', "
          f"'train', COUNT(*), COUNT_IF(NOT PASSED), 'no leak', BOOLAND_AGG(PASSED), 'max single-feature AUC ' || "
          f"TO_VARCHAR(MAX(TRAIN_AUC), '0.000'), '{run_id}' FROM {SCHEMA}.FEATURE_AUC_SENTINEL").collect()
    print('train', out, 'sentinel', sentinel_ok)
    return out


def reasons(s, run_id):
    cats = ', '.join(f"'{c}'" for c in REASON_CATEGORIES)
    task = ('Classify why this document-platform customer may leave, based on their support notes. '
            'Use "routine request" when the notes are only ordinary questions.')
    s.sql(f"""
create or replace table {SCHEMA}.CHURN_WATCHLIST as
with flagged as (
 select prediction_date, account_id, churn_probability, top_driver_1, top_driver_2
 from {SCHEMA}.CHURN_SCORES where split = 'score' and flagged),
notes as (
 select f.prediction_date, f.account_id, count(*) as note_count,
  listagg(n.note_text, ' | ') within group (order by n.created_at, n.note_id) as notes_text
 from flagged f join {SCHEMA}.SUPPORT_NOTES n on n.account_id = f.account_id
  and n.created_at < f.prediction_date::timestamp_ntz
  and n.created_at >= dateadd(day, -{NOTES_WINDOW_DAYS}, f.prediction_date)::timestamp_ntz
 group by 1, 2),
classified as (
 select prediction_date, account_id, note_count,
  ai_classify(notes_text, [{cats}], {{'task_description': '{task}'}}):labels[0]::varchar as support_reason
 from notes)
select f.prediction_date, dateadd(day, -7, f.prediction_date) as week_start_date, f.account_id,
 round(f.churn_probability, 4) as churn_probability, f.top_driver_1, f.top_driver_2,
 coalesce(c.note_count, 0) as note_count, coalesce(c.support_reason, 'no support notes') as support_reason,
 '{T.MODEL_VERSION}' as model_version, 'synthetic' as data_origin, '{run_id}' as run_id
from flagged f left join classified c on c.prediction_date = f.prediction_date and c.account_id = f.account_id
""").collect()
    s.sql(f"""
create or replace table {SCHEMA}.CHURN_REASON_CHECK as
with truth as (
 select w.account_id, max_by(n.generator_reason, n.created_at) as generator_reason
 from {SCHEMA}.CHURN_WATCHLIST w join {SCHEMA}.SUPPORT_NOTES n on n.account_id = w.account_id
  and n.created_at < w.prediction_date::timestamp_ntz
  and n.created_at >= dateadd(day, -{NOTES_WINDOW_DAYS}, w.prediction_date)::timestamp_ntz
  and n.generator_reason <> '{G.ROUTINE}'
 group by 1)
select count(*) as accounts_with_reason_notes, count_if(w.support_reason = t.generator_reason) as agree,
 agree / nullif(accounts_with_reason_notes, 0) as agreement_rate, '{run_id}' as run_id
from {SCHEMA}.CHURN_WATCHLIST w join truth t on t.account_id = w.account_id
""").collect()
    print('watchlist', s.sql(f'SELECT support_reason, COUNT(*) FROM {SCHEMA}.CHURN_WATCHLIST GROUP BY 1 ORDER BY 2 DESC').collect())
    print('reason check', s.sql(f'SELECT * FROM {SCHEMA}.CHURN_REASON_CHECK').collect())


def report(s):
    def show(sql):
        df = s.sql(sql).to_pandas()
        print(df.to_markdown(index=False, floatfmt='.3f'))
        print()

    show(f'SELECT split, model, n_rows, positives, base_rate, roc_auc, pr_auc, threshold, flagged, true_positives, '
         f'precision, recall, f1, lift FROM {SCHEMA}.CHURN_EVALUATION ORDER BY split, model')
    show(f'SELECT gate, required, observed, passed FROM {SCHEMA}.CHURN_EVALUATION_GATES')
    show(f'SELECT check_name, scope, rows_checked, mismatches, expected, passed, detail FROM {SCHEMA}.LEAKAGE_CHECK')
    show(f'SELECT LEFT(account_id, 8) AS account, churn_probability, top_driver_1, top_driver_2, note_count, support_reason '
         f'FROM {SCHEMA}.CHURN_WATCHLIST WHERE note_count > 0 ORDER BY churn_probability DESC LIMIT 10')
    show(f'SELECT COUNT(*) AS flagged, COUNT_IF(note_count > 0) AS with_notes FROM {SCHEMA}.CHURN_WATCHLIST')
    show(f'SELECT * EXCLUDE run_id FROM {SCHEMA}.CHURN_REASON_CHECK')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('steps', nargs='+', choices=['all', 'load', 'features', 'leakage', 'train', 'reasons', 'report'])
    steps = set(parser.parse_args().steps)
    s, run_id = session()
    print('run_id', run_id, 'warehouse', s.get_current_warehouse(), 'tag', s.sql('SELECT CURRENT_QUERY_TAG()').collect()[0][0])
    if steps & {'all', 'load'}:
        load_synthetic(s, run_id)
    if steps & {'all', 'features'}:
        build_features(s)
    if steps & {'all', 'leakage'}:
        if not leakage_check(s, run_id):
            print('LEAKAGE CHECK FAILED')
    if steps & {'all', 'train'}:
        train(s, run_id)
    if steps & {'all', 'reasons'}:
        reasons(s, run_id)
    if steps & {'all', 'report'}:
        report(s)
    s.close()


if __name__ == '__main__':
    main()
