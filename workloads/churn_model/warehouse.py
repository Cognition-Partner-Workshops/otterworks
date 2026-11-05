"""Warehouse procedure implementation; no source data leaves Snowflake."""

import json
import hashlib
import re
from datetime import datetime

import pandas as pd

try:
    from . import model
except ImportError:
    import model

RAW = {"AUTH_USERS": "ID", "AUTH_USER_STATE_HISTORY": "ID", "ADMIN_USER_STATE_HISTORY": "ID",
       "ADMIN_STORAGE_QUOTAS": "USER_ID", "DOCUMENT_DOCUMENT_VERSIONS": "ID",
       "ANALYTICS_ANALYTICS_EVENTS": "EVENT_ID"}
DOCUMENT_LABELS = ("report", "budget/finance", "plan", "meeting_notes", "template", "generic/untitled", "other")
THRESHOLD_JUSTIFICATION = "Highest training-only score threshold with recall >= 0.50; holdout never used. No threshold if not trainable."
HISTORICAL_RUN = "SFEXT_20261105A-churn_model-dev-20261105T080719Z-c65e9ae0"
HISTORICAL_COMMIT = "86a7f7c9601dabd4350bd0014a29d6dd0bf3d095"
HISTORICAL_ERROR_QUERY = "01c83444-030c-d1ca-0035-065b000a77fa"
HISTORICAL_ERROR = ("SNOWFLAKE.CORTEX.CLASSIFY_TEXT is not available on this account. "
                    "New accounts are blocked from using legacy SNOWFLAKE.CORTEX functions. "
                    "Please migrate to AI Functions and use AI_CLASSIFY instead.")


def insert_statement(table, run_id, record):
    values, marks = [run_id], ["?"]
    for value in record.values():
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            marks.append("NULL")
            continue
        if isinstance(value, (pd.Timestamp, datetime)):
            value = value.isoformat()
            marks.append("TO_TIMESTAMP_NTZ(?)")
        else:
            marks.append("?")
            if hasattr(value, "item"):
                value = value.item()
        values.append(value)
    return (f"INSERT INTO APP.{table} (RUN_ID,{','.join(record)}) VALUES ({','.join(marks)})", values)


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


def append(session, table, run_id, records):
    for record in records:
        sql, values = insert_statement(table, run_id, record)
        session.sql(sql, params=values).collect()


def failure(record, error):
    record["status"] = "failed_at_" + record["status"]
    record["error_message"] = str(error)
    query_id = re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", str(error))
    record["error_query_id"] = query_id.group(0) if query_id else None


def new_run(commit, step, evaluation_run_id=None):
    return dict(commit=commit, step=step, evaluation_run_id=evaluation_run_id, model_kind=None, split_rule=None,
                threshold=None, gate_passed=None, leakage_passed=None, training_status="not_requested" if step == "documents_only" else "not_started",
                train_positives=None, train_negatives=None, threshold_justification=None,
                reasons_status="unavailable_no_support_notes_source", started_at=datetime.utcnow(),
                finished_at=None, status="initialisation", error_message=None, error_query_id=None)


def run(session, run_id, commit, fallback):
    record = new_run(commit, "full")
    try:
        return run_model(session, run_id, commit, fallback, record)
    except Exception as error:
        failure(record, error)
        raise
    finally:
        record["finished_at"] = datetime.utcnow()
        append(session, "CHURN_MODEL_RUNS", run_id, [record])


def run_model(session, run_id, commit, fallback, record):
    started = record["started_at"]
    record["status"] = "dataset"

    def write(table, records):
        append(session, table, run_id, records)

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
    first = model.monday(model.accounts(tables).created_at.min() + pd.Timedelta(days=28))
    dates = list(pd.date_range(first, end - pd.Timedelta(days=28), freq="W-MON"))
    rows = model.dataset(tables, sorted(set([*dates, current])), end)
    labelled = rows[rows.churned.notna()]
    train, holdout, rule = model.split(labelled)
    checks = model.leakage(labelled)
    safe = all(row["passed"] for row in checks)
    checks.append(dict(feature="overall", rows_checked=len(labelled), violations=sum(r["violations"] for r in checks),
                       max_source_ts=pd.NaT, max_prediction_date=labelled.prediction_date.max(), passed=safe))
    write("CHURN_LEAKAGE_CHECK", checks)
    record.update(leakage_passed=safe, split_rule=rule, status="training")
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
    record.update(model_kind=kind, training_status=status, train_positives=positives, train_negatives=negatives,
                  threshold=cutoff, threshold_justification=THRESHOLD_JUSTIFICATION, status="evaluation")
    write("CHURN_MODEL_EVALUATION", [evaluation])
    record.update(gate_passed=evaluation["passed"], status="scores")
    write("CHURN_MODEL_SCORES", [dict(account_id=row.account_id, prediction_date=row.prediction_date, score=score,
           flagged=score is not None and cutoff is not None and score >= cutoff)
           for row, score in zip(scoring.itertuples(), scores)])
    record["status"] = "document_labels"
    label_documents(session, run_id)
    record["status"] = "completed"
    return json.dumps(dict(run_id=run_id, model_kind=kind, training_status=status, evaluation=evaluation))


def label_documents(session, run_id):
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
       AI_CLASSIFY(INPUT_TEXT,
       ['report','budget/finance','plan','meeting_notes','template','generic/untitled','other']):labels[0]::string LABEL
       FROM CHURN_LABEL_INPUT ORDER BY DOCUMENT_ID LIMIT 10""")
    with session.query_history() as query_history:
        labelled_documents = cortex.collect()
    cortex_query_id = query_history.queries[-1].query_id
    if len(labelled_documents) != 10 or any(row[3] not in DOCUMENT_LABELS for row in labelled_documents):
        raise ValueError(f"AI_CLASSIFY must return exactly 10 valid labels; query_id={cortex_query_id}")
    statements, parameters = [], []
    for row in labelled_documents:
        sql, values = insert_statement("CHURN_DOCUMENT_LABELS", run_id,
            dict(document_id=row[0], input_kind=row[1], input_text=row[2], label=row[3], model="AI_CLASSIFY",
                 cortex_query_id=cortex_query_id, labelled_at=datetime.utcnow()))
        prefix, expression = sql.split(" VALUES ", 1)
        statements.append(expression)
        parameters.extend(values)
    session.sql(prefix + " VALUES " + ",".join(statements), params=parameters).collect()
    return cortex_query_id


def historical_finalisation(evaluation, checks):
    if evaluation["run_id"] != HISTORICAL_RUN or not checks:
        raise ValueError("Recovery requires the approved evaluation and persisted leakage checks")
    overall = [row for row in checks if row["feature"] == "overall"]
    if len(overall) != 1:
        raise ValueError("Exactly one persisted overall leakage result is required")
    record = new_run(HISTORICAL_COMMIT, "full", HISTORICAL_RUN)
    record.update(gate_passed=evaluation["passed"],
                  leakage_passed=all(row["passed"] and row["violations"] == 0 for row in checks),
                  status="failed_at_document_labels", error_message=HISTORICAL_ERROR,
                  error_query_id=HISTORICAL_ERROR_QUERY, training_status=None,
                  threshold_justification="Training status, model kind, split rule and threshold were not persisted in evaluation/leakage rows; not inferred from holdout metrics.",
                  started_at=None, finished_at=datetime.utcnow())
    return record


def read_finalisation(session, evaluation_run_id):
    if evaluation_run_id != HISTORICAL_RUN:
        raise ValueError("Only the approved historical run may be finalised")
    def read(table):
        return [{key.lower(): value for key, value in row.as_dict().items()} for row in
                session.sql(f"SELECT * FROM APP.{table} WHERE RUN_ID=?", params=[evaluation_run_id]).collect()]
    existing = read("CHURN_MODEL_RUNS")
    evaluations, checks = read("CHURN_MODEL_EVALUATION"), read("CHURN_LEAKAGE_CHECK")
    if len(evaluations) != 1:
        raise ValueError("Exactly one immutable evaluation row is required")
    expected = historical_finalisation(evaluations[0], checks)
    if existing:
        fields = ("commit", "status", "error_query_id", "gate_passed", "leakage_passed", "evaluation_run_id")
        if len(existing) != 1 or any(existing[0][key] != expected[key] for key in fields):
            raise ValueError("Conflicting historical finalisation; refusing to change existing runs")
        return None
    return expected


def documents_only(session, run_id, commit, evaluation_run_id):
    record = new_run(commit, "documents_only", evaluation_run_id)
    try:
        finalisation = read_finalisation(session, evaluation_run_id)
        record["status"] = "historical_finalisation"
        if finalisation is not None:
            append(session, "CHURN_MODEL_RUNS", evaluation_run_id, [finalisation])
        record["status"] = "document_labels"
        cortex_query_id = label_documents(session, run_id)
        record["status"] = "completed"
        return json.dumps(dict(run_id=run_id, evaluation_run_id=evaluation_run_id, cortex_query_id=cortex_query_id))
    except Exception as error:
        failure(record, error)
        raise
    finally:
        record["finished_at"] = datetime.utcnow()
        append(session, "CHURN_MODEL_RUNS", run_id, [record])
