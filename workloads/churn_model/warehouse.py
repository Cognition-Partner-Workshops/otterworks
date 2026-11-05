"""Warehouse procedure implementation; no source data leaves Snowflake."""

import json
import hashlib
from datetime import datetime

import pandas as pd

import model

RAW = {"AUTH_USERS": "ID", "AUTH_USER_STATE_HISTORY": "ID", "ADMIN_USER_STATE_HISTORY": "ID",
       "ADMIN_STORAGE_QUOTAS": "USER_ID", "DOCUMENT_DOCUMENT_VERSIONS": "ID",
       "ANALYTICS_ANALYTICS_EVENTS": "EVENT_ID"}


def raw_sql(table, key):
    per_snapshot = table == "ADMIN_STORAGE_QUOTAS"
    restriction = "" if per_snapshot else "WHERE e.snapshot_date=(SELECT MAX(payload:snapshot_date::date) FROM RAW.PIPELINE_EXPORTS)"
    partition = "t._snapshot_date," if per_snapshot else ""
    return f"""SELECT t.* FROM RAW.{table} t JOIN
      (SELECT payload:snapshot_date::date snapshot_date, MAX(payload:exported_at::timestamp_ntz) exported_at
       FROM RAW.PIPELINE_EXPORTS GROUP BY 1) e
      ON t._snapshot_date=e.snapshot_date AND t._exported_at=e.exported_at {restriction}
      QUALIFY ROW_NUMBER() OVER (PARTITION BY {partition}t.{key}
      ORDER BY t._snapshot_date DESC,t._exported_at DESC,t._row_hash DESC)=1"""


def run(session, run_id, commit, fallback):
    started = datetime.utcnow()

    def append(table, records):
        for record in records:
            values = []
            for value in record.values():
                if value is None or (not isinstance(value, str) and pd.isna(value)):
                    value = None
                elif isinstance(value, pd.Timestamp):
                    value = value.to_pydatetime()
                elif hasattr(value, "item"):
                    value = value.item()
                values.append(value)
            session.sql(f"INSERT INTO APP.{table} (RUN_ID,{','.join(record)}) VALUES (?,{','.join('?' for _ in record)})",
                        params=[run_id, *values]).collect()

    tables = {}
    for table, key in RAW.items():
        frame = session.sql(raw_sql(table, key)).to_pandas()
        frame.columns = frame.columns.str.lower()
        for column in ("created_at", "last_login_at", "effective_at", "updated_at", "_snapshot_date"):
            if column in frame:
                frame[column] = pd.to_datetime(frame[column])
        if "occurred_at" in frame:
            frame["occurred_at"] = pd.to_datetime(pd.to_numeric(frame.occurred_at), unit="ns")
        tables[table] = frame
    end = model.monday(session.sql("SELECT MAX(payload:exported_at::timestamp_ntz) FROM RAW.PIPELINE_EXPORTS").collect()[0][0])
    current = model.monday(started)
    first = model.monday(tables["AUTH_USERS"].created_at.min() + pd.Timedelta(days=28))
    dates = list(pd.date_range(first, end - pd.Timedelta(days=28), freq="W-MON"))
    rows = model.dataset(tables, sorted(set([*dates, current])), end)
    labelled = rows[rows.churned.notna()]
    train, holdout, rule = model.split(labelled)
    checks = model.leakage(labelled)
    safe = all(row["passed"] for row in checks)
    checks.append(dict(feature="overall", rows_checked=len(labelled), violations=sum(r["violations"] for r in checks),
                       max_source_ts=pd.NaT, max_prediction_date=labelled.prediction_date.max(), passed=safe))
    append("CHURN_LEAKAGE_CHECK", checks)
    scoring = rows[rows.prediction_date == current]
    positives = int(train.churned.sum())
    negatives = len(train) - positives
    cutoff, kind, status = None, "none", "not_trainable"
    holdout_scores, scores = [0.0] * len(holdout), [None] * len(scoring)
    if positives and negatives and safe:
        x = pd.get_dummies(train[list(model.FEATURES)], columns=["tier"], dtype=float).fillna(0).astype(float)
        feature_columns = x.columns

        def matrix(frame):
            return pd.get_dummies(frame[list(model.FEATURES)], columns=["tier"], dtype=float).reindex(columns=feature_columns, fill_value=0).fillna(0).astype(float)

        if not fallback:
            from sklearn.linear_model import LogisticRegression
            classifier = LogisticRegression(class_weight="balanced", max_iter=2000, random_state=0)
            classifier.fit(x, train.churned.astype(int))

            def predict(frame):
                return classifier.predict_proba(matrix(frame))[:, 1].tolist() if len(frame) else []

            kind = "snowpark_sklearn_logistic_regression"
        else:
            x.columns = [f"X{i}" for i in range(len(x.columns))]
            columns = list(x.columns)
            x["TARGET"] = train.churned.astype(int).astype(str).to_numpy()
            session.create_dataframe(x).write.save_as_table("CHURN_FIT", mode="overwrite", table_type="temporary")
            classifier_name = "CHURN_" + hashlib.sha256(run_id.encode()).hexdigest()[:16].upper()
            session.sql(f"CREATE SNOWFLAKE.ML.CLASSIFICATION {classifier_name}(INPUT_DATA => SYSTEM$REFERENCE('TABLE','CHURN_FIT'), TARGET_COLNAME => 'TARGET')").collect()

            def predict(frame):
                if frame.empty:
                    return []
                data = matrix(frame)
                data.columns = columns
                data["ROW_ID"] = range(len(data))
                session.create_dataframe(data).write.save_as_table("CHURN_PREDICT", mode="overwrite", table_type="temporary")
                return [float(row[0]) for row in session.sql(f"SELECT {classifier_name}!PREDICT(INPUT_DATA => OBJECT_DELETE(OBJECT_CONSTRUCT(*),'ROW_ID')):probability:\"1\"::float FROM CHURN_PREDICT ORDER BY ROW_ID").collect()]

            kind = "snowflake_ml_classification"
        cutoff = model.threshold(train.churned, predict(train))
        holdout_scores, scores = predict(holdout), predict(scoring)
        if fallback:
            session.sql(f"DROP SNOWFLAKE.ML.CLASSIFICATION {classifier_name}").collect()
        status = "trained"
    auth, admin = tables["AUTH_USER_STATE_HISTORY"], tables["ADMIN_USER_STATE_HISTORY"]
    cause = (f"source state history has {auth.effective_at.nunique()} auth / {admin.effective_at.nunique()} admin effective timestamps "
             f"({auth.effective_at.min()} to {auth.effective_at.max()}); {int(auth.is_deleted.fillna(False).sum())} deletion rows; "
             "first-capture admin rows are not suspension transitions")
    evaluation = model.evaluate(holdout.churned, holdout_scores, cutoff, cause)
    append("CHURN_MODEL_EVALUATION", [evaluation])
    append("CHURN_MODEL_SCORES", [dict(account_id=row.account_id, prediction_date=row.prediction_date, score=score,
           flagged=score is not None and cutoff is not None and score >= cutoff)
           for row, score in zip(scoring.itertuples(), scores)])
    documents = session.sql(f"SELECT * FROM ({raw_sql('DOCUMENT_DOCUMENTS', 'ID')}) WHERE NOT COALESCE(IS_DELETED,FALSE) ORDER BY ID LIMIT 10").to_pandas()
    documents.columns = documents.columns.str.lower()
    documents = model.document_batch(documents)
    if len(documents) != 10:
        raise ValueError(f"Document labelling requires exactly 10 existing documents; found {len(documents)}")
    inputs = []
    for document in documents.to_dict("records"):
        input_kind, input_text = model.document_input(document)
        inputs.append([str(document["id"]), input_kind, input_text])
    session.create_dataframe(inputs, schema=["DOCUMENT_ID", "INPUT_KIND", "INPUT_TEXT"]).write.save_as_table(
        "CHURN_LABEL_INPUT", mode="overwrite", table_type="temporary")
    cortex = session.sql("""SELECT DOCUMENT_ID, INPUT_KIND, INPUT_TEXT,
       SNOWFLAKE.CORTEX.CLASSIFY_TEXT(INPUT_TEXT,
       ['report','budget/finance','plan','meeting_notes','template','generic/untitled','other']):label::string LABEL
       FROM CHURN_LABEL_INPUT ORDER BY DOCUMENT_ID LIMIT 10""")
    with session.query_history() as query_history:
        labelled_documents = cortex.collect()
    cortex_query_id = query_history.queries[-1].query_id
    append("CHURN_DOCUMENT_LABELS", [dict(document_id=r[0], input_kind=r[1], input_text=r[2], label=r[3],
           model="SNOWFLAKE.CORTEX.CLASSIFY_TEXT", cortex_query_id=cortex_query_id, labelled_at=datetime.utcnow())
           for r in labelled_documents])
    reasons = "unavailable_no_support_notes_source"
    append("CHURN_MODEL_RUNS", [dict(commit=commit, model_kind=kind, split_rule=rule, threshold=cutoff,
           gate_passed=evaluation["passed"], leakage_passed=safe, reasons_status=reasons, training_status=status,
           train_positives=positives, train_negatives=negatives,
           threshold_justification="Highest training-only score threshold with recall >= 0.50; holdout never used. No threshold if not trainable.",
           started_at=started, finished_at=datetime.utcnow())])
    return json.dumps(dict(run_id=run_id, model_kind=kind, training_status=status, evaluation=evaluation))
