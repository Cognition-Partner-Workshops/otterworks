import json
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pandas as pd
import pytest

from workloads.churn_model import warehouse as w
from workloads.churn_model.usage import cortex_detection


@pytest.mark.parametrize("failure", [None, 0, 1, 2])
def test_fallback_model_is_dropped_after_every_prediction_outcome(monkeypatch, failure):
    session = MagicMock()
    monkeypatch.setattr(w.model, "threshold", lambda *args: 0.5)
    calls = []

    def predict(frame):
        calls.append(frame)
        if len(calls) - 1 == failure:
            raise RuntimeError("prediction failed")
        return []

    train = SimpleNamespace(churned=[])
    if failure is None:
        assert w.prediction_scores(session, "CHURN_TEST", train, [], [], predict) == (0.5, [], [])
    else:
        with pytest.raises(RuntimeError, match="prediction failed"):
            w.prediction_scores(session, "CHURN_TEST", train, [], [], predict)
    session.sql.assert_called_once_with("DROP SNOWFLAKE.ML.CLASSIFICATION CHURN_TEST")


def test_main_run_finalises_after_later_failure(monkeypatch):
    writes = []

    def failing_model(session, run_id, commit, fallback, record):
        record.update(status="document_labels", gate_passed=False, leakage_passed=True, training_status="not_trainable")
        raise RuntimeError(f"{w.HISTORICAL_ERROR_QUERY}: Cortex failed")

    monkeypatch.setattr(w, "run_model", failing_model)
    monkeypatch.setattr(w, "append", lambda *args: writes.append(args))
    with pytest.raises(RuntimeError, match="Cortex failed"):
        w.run(None, "run", "commit", "")
    assert len(writes) == 1
    record = writes[0][3][0]
    assert writes[0][1:3] == ("CHURN_MODEL_RUNS", "run")
    assert record["status"] == "failed_at_document_labels"
    assert record["error_query_id"] == w.HISTORICAL_ERROR_QUERY
    assert record["gate_passed"] is False and record["leakage_passed"] is True
    assert record["finished_at"] is not None


def test_main_run_finalises_success(monkeypatch):
    writes = []

    def success(session, run_id, commit, fallback, record):
        record["status"] = "completed"
        return "result"

    monkeypatch.setattr(w, "run_model", success)
    monkeypatch.setattr(w, "append", lambda *args: writes.append(args))
    assert w.run(None, "run", "commit", "") == "result"
    assert writes[0][3][0]["status"] == "completed"
    assert writes[0][3][0]["error_message"] is None


@pytest.mark.parametrize("gate,leakage,violations", [(False, True, 0), (True, False, 1)])
def test_historical_finalisation_uses_persisted_outcomes(gate, leakage, violations):
    record = w.historical_finalisation(dict(run_id=w.HISTORICAL_RUN, passed=gate),
        [dict(feature="overall", passed=leakage, violations=violations)])
    assert record["gate_passed"] == gate
    assert record["leakage_passed"] == leakage
    assert record["training_status"] is None
    assert record["model_kind"] is None and record["split_rule"] is None
    assert record["threshold"] is None
    assert "not inferred" in record["threshold_justification"]
    assert record["status"] == "failed_at_document_labels"
    assert record["error_query_id"] == w.HISTORICAL_ERROR_QUERY


def test_historical_finalisation_rejects_missing_evidence():
    with pytest.raises(ValueError):
        w.historical_finalisation(dict(run_id="wrong"), [])
    with pytest.raises(ValueError, match="overall"):
        w.historical_finalisation(dict(run_id=w.HISTORICAL_RUN), [dict(feature="login")])


class PersistedRow(dict):
    def as_dict(self):
        return {key.upper(): value for key, value in self.items()}


def test_historical_finalisation_is_insert_only_and_conflicts_are_rejected():
    evaluation = PersistedRow(run_id=w.HISTORICAL_RUN, passed=False)
    checks = [PersistedRow(feature="overall", passed=True, violations=0)]
    existing = []
    queries = []

    def sql(text, params):
        queries.append(text)
        assert params == [w.HISTORICAL_RUN]
        return SimpleNamespace(collect=lambda: [evaluation] if "CHURN_MODEL_EVALUATION" in text else checks if "CHURN_LEAKAGE_CHECK" in text else existing)

    session = SimpleNamespace(sql=sql)
    expected = w.read_finalisation(session, w.HISTORICAL_RUN)
    assert expected["gate_passed"] is False
    existing.append(PersistedRow(expected))
    assert w.read_finalisation(session, w.HISTORICAL_RUN) is None
    existing[0]["gate_passed"] = True
    with pytest.raises(ValueError, match="Conflicting"):
        w.read_finalisation(session, w.HISTORICAL_RUN)
    assert all(query.startswith("SELECT") for query in queries)


@pytest.mark.parametrize("fail_labels", [False, True])
def test_document_recovery_never_calls_model_or_mutates_protected_tables(monkeypatch, fail_labels):
    writes = []
    monkeypatch.setattr(w, "run_model", Mock(side_effect=AssertionError("training path forbidden")))
    monkeypatch.setattr(w, "read_finalisation", lambda *args: {"status": "historical"})
    monkeypatch.setattr(w, "append", lambda *args: writes.append(args))

    def label(*args):
        if fail_labels:
            raise RuntimeError("labels failed")
        return "cortex-query"

    monkeypatch.setattr(w, "label_documents", label)
    if fail_labels:
        with pytest.raises(RuntimeError, match="labels failed"):
            w.documents_only(None, "fresh-run", "fresh-commit", w.HISTORICAL_RUN)
    else:
        result = json.loads(w.documents_only(None, "fresh-run", "fresh-commit", w.HISTORICAL_RUN))
        assert result["run_id"] == "fresh-run" and result["cortex_query_id"] == "cortex-query"
    w.run_model.assert_not_called()
    assert [row[1] for row in writes] == ["CHURN_MODEL_RUNS", "CHURN_MODEL_RUNS"]
    assert [row[2] for row in writes] == [w.HISTORICAL_RUN, "fresh-run"]
    record = writes[-1][3][0]
    assert record["step"] == "documents_only"
    assert record["commit"] == "fresh-commit"
    assert record["status"] == ("failed_at_document_labels" if fail_labels else "completed")


class DocumentSession:
    def __init__(self, count=10, invalid=False):
        self.calls = []
        self.count = count
        self.invalid = invalid

    def sql(self, sql, params=None):
        self.calls.append((sql, params))
        if "RAW.DOCUMENT_DOCUMENTS" in sql:
            return SimpleNamespace(to_pandas=lambda: pd.DataFrame(dict(
                ID=[str(i) for i in range(self.count)], TITLE=["Annual report"] * self.count,
                IS_DELETED=[False] * self.count)))
        if "AI_CLASSIFY(" in sql:
            return SimpleNamespace(collect=lambda: [(str(i), "title_only", "Annual report", None if self.invalid else "report") for i in range(10)])
        return SimpleNamespace(collect=lambda: [])

    def create_dataframe(self, inputs, schema):
        assert len(inputs) == 10
        return SimpleNamespace(write=SimpleNamespace(save_as_table=lambda *args, **kwargs: None))

    def query_history(self):
        class History:
            queries = [SimpleNamespace(query_id="cortex-query")]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False
        return History()


def test_document_classification_is_single_bounded_query_and_atomic_insert():
    session = DocumentSession()
    assert w.label_documents(session, "fresh-run") == "cortex-query"
    cortex = [sql for sql, _ in session.calls if "AI_CLASSIFY(" in sql]
    assert len(cortex) == 1 and ":labels[0]::string" in cortex[0] and "LIMIT 10" in cortex[0]
    inserts = [(sql, params) for sql, params in session.calls if sql.startswith("INSERT")]
    assert len(inserts) == 1 and "CHURN_DOCUMENT_LABELS" in inserts[0][0]
    assert inserts[0][1].count("fresh-run") == 10
    assert inserts[0][1].count("cortex-query") == 10


@pytest.mark.parametrize("session", [DocumentSession(count=0), DocumentSession(count=9), DocumentSession(invalid=True)])
def test_document_empty_short_or_null_labels_are_not_written(session):
    with pytest.raises(ValueError):
        w.label_documents(session, "run")
    assert not any(sql.startswith("INSERT") for sql, _ in session.calls)


@pytest.mark.parametrize("text,usage,recorded,expected", [
    ("<redacted>", {"q"}, set(), True),
    (None, set(), {"q"}, True),
    ("SELECT AI_CLASSIFY('text',['a','b'])", set(), set(), True),
    ("SELECT SNOWFLAKE.CORTEX.COMPLETE('model','text')", set(), set(), True),
    ("<redacted>", set(), set(), "unknown"),
    (None, set(), set(), "unknown"),
    ("SELECT 1", set(), set(), False),
])
def test_cortex_detection_handles_history_ai_functions_and_unknown(text, usage, recorded, expected):
    assert cortex_detection("q", text, usage, recorded)[0] == expected
